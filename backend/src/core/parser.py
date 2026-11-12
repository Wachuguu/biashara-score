"""
M-Pesa Statement & SMS Parser (Pure Python)
Zero AWS dependencies. 100% offline and unit-testable.
"""
import csv
import io
import re
from datetime import datetime
from typing import List, Optional
from .models import Transaction, TransactionDirection, TransactionCategory


def _clean_amount(val: Optional[str]) -> float:
    """Cleans formatted currency numbers (e.g., '1,606.98' -> 1606.98)."""
    if not val:
        return 0.0
    cleaned = re.sub(r"[^\d.]", "", val.strip())
    if not cleaned:
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _normalize_iso_timestamp(date_str: str) -> str:
    """
    Normalizes varied Kenyan M-Pesa date strings into ISO-8601 UTC format.
    Examples:
      '2026-09-01 12:49:00' -> '2026-09-01T12:49:00Z'
      '1/9/26 at 12:49 PM'  -> '2026-09-01T12:49:00Z'
      '12/9/26'             -> '2026-09-12T00:00:00Z'
    Falls back to original string if unrecognized.
    """
    if not date_str:
        return ""
    cleaned = date_str.strip()
    
    # Already ISO-like
    if "T" in cleaned:
        if not cleaned.endswith("Z") and not ("+" in cleaned or "-" in cleaned[10:]):
            return f"{cleaned}Z"
        return cleaned

    # Format: YYYY-MM-DD HH:MM:SS
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pass

    # Normalize SMS-style D/M/YY or D/M/YYYY with optional 'at HH:MM AM/PM'
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})(?:\s+(?:at\s+)?(\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?))?", cleaned)
    if match:
        day, month, year, time_part = match.groups()
        if len(year) == 2:
            year = f"20{year}"
        day = int(day)
        month = int(month)
        year = int(year)
        
        hour, minute, second = 0, 0, 0
        if time_part:
            time_clean = time_part.strip()
            for t_fmt in ("%I:%M %p", "%I:%M:%S %p", "%H:%M:%S", "%H:%M"):
                try:
                    t_dt = datetime.strptime(time_clean, t_fmt)
                    hour, minute, second = t_dt.hour, t_dt.minute, t_dt.second
                    break
                except ValueError:
                    pass
        try:
            dt = datetime(year, month, day, hour, minute, second)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pass

    return cleaned


def _extract_counterparty_from_details(details: str) -> Optional[str]:
    """Extracts counterparty merchant or customer name/phone from details string."""
    if not details:
        return None
    d = details.strip()
    
    # Till payment: 'Customer Payment to Till 789123 - John Otieno 254731829405'
    m_till = re.search(r"to\s+Till\s+\d+\s*-\s*([^(\n]+)", d, re.IGNORECASE)
    if m_till:
        return m_till.group(1).strip()

    # Buy Goods: 'Buy Goods to 771234 - Bidco Africa Distributors'
    m_buy = re.search(r"Buy\s+Goods\s+to\s+\d+\s*-\s*([^(\n]+)", d, re.IGNORECASE)
    if m_buy:
        return m_buy.group(1).strip()

    # Pay Bill: 'Pay Bill to 888888 - KPLC PREPAID Acc. 14283949740'
    m_paybill = re.search(r"Pay\s*Bill\s+to\s+\d+\s*-\s*([^(\n]+)", d, re.IGNORECASE)
    if m_paybill:
        return m_paybill.group(1).strip()

    # Customer Transfer to/from: 'Customer Transfer from 254719283746 - Teacher Maina (Maina Duka Debt Settled)'
    m_transfer = re.search(r"Customer\s+Transfer\s+(?:to|from)\s+([0-9+]+)\s*-\s*([^(\n]+)", d, re.IGNORECASE)
    if m_transfer:
        phone, name = m_transfer.groups()
        return f"{name.strip()} {phone.strip()}"

    # Airtime Purchase: 'Airtime Purchase for 254729112233'
    m_airtime = re.search(r"Airtime\s+Purchase\s+for\s+([0-9+]+)", d, re.IGNORECASE)
    if m_airtime:
        return f"Airtime {m_airtime.group(1).strip()}"

    # Dash separator fallback: '... - Name'
    if " - " in d:
        parts = d.split(" - ")
        cand = parts[-1].strip()
        cand = re.sub(r"\(.*?\)", "", cand).strip()
        if cand:
            return cand

    return None


def parse_csv_statement(csv_content: str, business_id: Optional[str] = None) -> List[Transaction]:
    """
    Parses a raw Safaricom M-Pesa CSV statement string into a list of Transaction dataclass instances.
    Extracts: receipt_number, completion_time, details, amount, direction, running_balance, status.
    Cleans formatted numbers (e.g., '1,606.98' -> 1606.98) and determines direction ('IN' for Paid In, 'OUT' for Withdrawn).
    """
    if not csv_content:
        return []

    # Strip Byte Order Mark (UTF-8 BOM) and handle CRLF
    content = csv_content.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line for line in content.split("\n") if line.strip()]
    if not lines:
        return []

    # Find the header row
    header_idx = -1
    for idx, line in enumerate(lines):
        line_lower = line.lower()
        if "receipt" in line_lower and ("details" in line_lower or "balance" in line_lower):
            header_idx = idx
            break

    if header_idx == -1:
        # Fallback to the first line if no explicit header matched
        header_idx = 0

    reader = csv.reader(lines[header_idx:])
    try:
        raw_headers = next(reader)
    except StopIteration:
        return []

    # Map normalized header names to column index
    header_map = {}
    for idx, h in enumerate(raw_headers):
        h_norm = re.sub(r"[^a-z0-9]", "", h.lower())
        if "receipt" in h_norm:
            header_map["receipt_no"] = idx
        elif "completion" in h_norm or "time" in h_norm or "date" in h_norm:
            header_map["completion_time"] = idx
        elif "detail" in h_norm:
            header_map["details"] = idx
        elif "status" in h_norm:
            header_map["status"] = idx
        elif "paidin" in h_norm or "paid" in h_norm or "credit" in h_norm:
            header_map["paid_in"] = idx
        elif "withdrawn" in h_norm or "debit" in h_norm:
            header_map["withdrawn"] = idx
        elif "balance" in h_norm:
            header_map["balance"] = idx

    transactions: List[Transaction] = []

    for row in reader:
        if not row or not any(field.strip() for field in row):
            continue

        def get_val(key: str, default: str = "") -> str:
            idx = header_map.get(key)
            if idx is not None and idx < len(row):
                return row[idx].strip()
            return default

        receipt_no = get_val("receipt_no")
        if not receipt_no:
            continue

        raw_time = get_val("completion_time")
        completion_time = _normalize_iso_timestamp(raw_time)

        details = get_val("details")
        status = get_val("status", "Completed") or "Completed"

        paid_in = _clean_amount(get_val("paid_in"))
        withdrawn = _clean_amount(get_val("withdrawn"))
        balance = _clean_amount(get_val("balance"))

        if paid_in > 0:
            amount = paid_in
            direction = TransactionDirection.IN
        elif withdrawn > 0:
            amount = withdrawn
            direction = TransactionDirection.OUT
        else:
            # Check details if both columns are zero/empty
            amount = 0.0
            direction = TransactionDirection.IN

        counterparty = _extract_counterparty_from_details(details)

        tx = Transaction(
            receipt_number=receipt_no,
            completion_time=completion_time,
            details=details,
            amount=amount,
            direction=direction,
            running_balance=balance,
            status=status,
            category=TransactionCategory.UNCATEGORIZED,
            counterparty=counterparty,
            categorization_method="PENDING",
            debt_matched_id=None,
            business_id=business_id,
            source="CSV_UPLOAD",
        )
        transactions.append(tx)

    return transactions


def parse_sms_message(sms_text: str, business_id: Optional[str] = None) -> Transaction:
    """
    Parses a single incoming Safaricom M-Pesa SMS message string into a Transaction dataclass instance.
    Extracts receipt code (e.g., 'SK01YUUM7K'), amount, counterparty name/phone, balance, and timestamp.
    """
    if not sms_text:
        raise ValueError("SMS text cannot be empty")

    text = sms_text.strip()

    # 1. Receipt Code extraction
    receipt_code = "UNKNOWN"
    m_code = re.search(r"^([A-Z0-9]+)\s+Confirmed\b", text, re.IGNORECASE)
    if m_code:
        receipt_code = m_code.group(1).upper()
    else:
        # Search for any alphanumeric token followed by Confirmed
        m_alt = re.search(r"\b([A-Z0-9]{4,12})\s+Confirmed\b", text, re.IGNORECASE)
        if m_alt:
            receipt_code = m_alt.group(1).upper()
        else:
            # Fallback receipt code from first alphanumeric token
            m_first = re.search(r"^([A-Z0-9]{4,12})\b", text)
            if m_first:
                receipt_code = m_first.group(1).upper()

    # 2. Amount extraction
    amount = 0.0
    m_amt = re.search(r"(?:Ksh|KES|Ksh\.)\s*([\d,]+(?:\.\d{1,2})?)", text, re.IGNORECASE)
    if m_amt:
        amount = _clean_amount(m_amt.group(1))

    # 3. Direction
    text_lower = text.lower()
    if (
        "received" in text_lower
        or "you have received" in text_lower
        or "payment received" in text_lower
    ):
        direction = TransactionDirection.IN
    else:
        direction = TransactionDirection.OUT

    # 4. Running Balance extraction
    balance = 0.0
    m_bal = re.search(
        r"(?:(?:new\s+)?(?:m-pesa\s+)?balance\s+is\s+(?:ksh|kes|ksh\.)?\s*([\d,]+(?:\.\d{1,2})?))",
        text,
        re.IGNORECASE,
    )
    if m_bal:
        balance = _clean_amount(m_bal.group(1))

    # 5. Timestamp extraction
    completion_time = ""
    m_time = re.search(
        r"(?:on|at)\s+(\d{1,2}/\d{1,2}/\d{2,4}(?:\s+(?:at\s+)?\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)?)",
        text,
        re.IGNORECASE,
    )
    if m_time:
        completion_time = _normalize_iso_timestamp(m_time.group(1))
    else:
        # Fallback to current time if no date found
        completion_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # 6. Counterparty extraction
    counterparty = None
    if direction == TransactionDirection.IN:
        m_from = re.search(
            r"from\s+([A-Za-z0-9\s+]+?)(?:\s+on\s+\d|\s+at\s+\d|\.|\n|deni|debt|for\s+)",
            text,
            re.IGNORECASE,
        )
        if m_from:
            counterparty = m_from.group(1).strip()
    else:
        m_to = re.search(
            r"(?:sent to|paid to|to)\s+([A-Za-z0-9\s'/]+?)(?:\s+on\s+\d|\s+at\s+\d|\.|\n|via\s+|for\s+account|acc|\bfor\b)",
            text,
            re.IGNORECASE,
        )
        if m_to:
            counterparty = m_to.group(1).strip()

    if not counterparty:
        if "airtime" in text_lower:
            counterparty = "Safaricom Airtime"

    return Transaction(
        receipt_number=receipt_code,
        completion_time=completion_time,
        details=text,
        amount=amount,
        direction=direction,
        running_balance=balance,
        status="Completed",
        category=TransactionCategory.UNCATEGORIZED,
        counterparty=counterparty,
        categorization_method="PENDING",
        debt_matched_id=None,
        business_id=business_id,
        source="SMS_PASTE",
    )


def parse_multiple_sms(sms_text: str, business_id: Optional[str] = None) -> List[Transaction]:
    """
    Splits multi-line or concatenated pasted SMS text blocks into individual messages
    and returns a list of parsed Transaction instances.
    """
    if not sms_text:
        return []

    # First attempt: split by double newlines or list items
    chunks = re.split(r"\n\s*\n+", sms_text.strip())
    
    # If chunks only has 1 element, check if multiple 'Confirmed.' appear in single block
    if len(chunks) <= 1:
        # Split on message boundary: look for tokens followed by Confirmed
        split_pattern = r"(?=(?:^|\n)\s*[A-Z0-9]+\s+Confirmed\b)"
        sub_chunks = re.split(split_pattern, sms_text.strip(), flags=re.IGNORECASE)
        chunks = [c for c in sub_chunks if c.strip()]

    transactions: List[Transaction] = []
    for chunk in chunks:
        clean_chunk = chunk.strip()
        # Clean leading numbering like '1. ', '- '
        clean_chunk = re.sub(r"^\s*(?:\d+[\.\)]|-|\*)\s*", "", clean_chunk)
        if not clean_chunk:
            continue
        try:
            tx = parse_sms_message(clean_chunk, business_id=business_id)
            transactions.append(tx)
        except Exception:
            continue

    return transactions
