"""
Kitabu ya Deni - Customer Debt Tracking Engine (Pure Python)
Handles debt balance updates, payment matching, and repayment logs.
No AWS / boto3 dependencies.
"""
from typing import List, Optional, Tuple, Dict, Any
import re
from datetime import datetime, timezone
from .models import DebtRecord, Transaction, DebtStatus


def normalize_phone_number(phone: str) -> str:
    """
    Standardizes Kenyan phone numbers to E.164 (+254...):
    - '0712345678' -> '+254712345678'
    - '0112345678' -> '+254112345678'
    - '254712345678' -> '+254712345678'
    - '+254712345678' -> '+254712345678'
    - '712345678' -> '+254712345678'
    Strips spaces, dashes, parentheses, and leading noise.
    """
    if not phone:
        return ""
    # Strip any whitespace, hyphens, parentheses, dots
    cleaned = re.sub(r"[\s\-\(\)\.]", "", str(phone).strip())
    if not cleaned:
        return ""

    if cleaned.startswith("+"):
        digits = cleaned[1:]
    else:
        digits = cleaned

    if not digits.isdigit():
        # Strip any other non-digit characters
        digits = re.sub(r"\D", "", digits)
        if not digits:
            return ""

    # Check Kenyan patterns
    if digits.startswith("254") and len(digits) == 12:
        return f"+{digits}"
    if digits.startswith("0") and len(digits) == 10:
        return f"+254{digits[1:]}"
    if (digits.startswith("7") or digits.startswith("1")) and len(digits) == 9:
        return f"+254{digits}"

    # Default fallback
    return f"+{digits}" if not cleaned.startswith("+") else cleaned


def _extract_phones_from_text(text: str) -> List[str]:
    """Extracts and normalizes all potential Kenyan phone numbers from text."""
    if not text:
        return []
    # Match candidate phone strings (e.g., 254719283746, 0719283746, +254719283746, 011...)
    candidates = re.findall(r"(?:\+?254|0)[17]\d{8}", text)
    normalized = []
    for c in candidates:
        norm = normalize_phone_number(c)
        if norm and norm not in normalized:
            normalized.append(norm)
    return normalized


def match_repayment_to_debt(
    tx: Transaction,
    open_debts: List[DebtRecord]
) -> Optional[Tuple[DebtRecord, float]]:
    """
    Checks if an incoming transaction matches an open customer credit record by:
    1. Debtor phone number match against counterparty / details.
    2. Name match (case-insensitive substring/token overlap) combined with debt/deni keywords.

    Only matches against debts with remaining balance > 0 and status != CLEARED.
    Returns (matched DebtRecord, applied payment amount) if matched, else None.
    """
    # Only inbound transactions can be customer repayments
    direction_val = tx.direction.value if hasattr(tx.direction, "value") else str(tx.direction)
    if direction_val.upper() != "IN":
        return None

    active_debts = [d for d in open_debts if d.status != DebtStatus.CLEARED and d.balance_remaining > 0]
    if not active_debts:
        return None

    # Gather search corpus from transaction
    counterparty = tx.counterparty or ""
    details = tx.details or ""
    combined_text = f"{counterparty} {details}".lower()

    # 1. Phone-based matching (Highest confidence)
    tx_phones = _extract_phones_from_text(f"{counterparty} {details}")
    for debt in active_debts:
        debt_phone_norm = normalize_phone_number(debt.debtor_phone)
        if debt_phone_norm and debt_phone_norm in tx_phones:
            return (debt, float(tx.amount))

    # Also check direct phone substring if normalized didn't catch due to formatting
    for debt in active_debts:
        raw_digits = re.sub(r"\D", "", debt.debtor_phone)
        if len(raw_digits) >= 9 and raw_digits[-9:] in combined_text:
            return (debt, float(tx.amount))

    # 2. Name-based matching with repayment/debt intent
    debt_intent_keywords = ["deni", "debt", "settled", "cleared", "repayment", "lipa deni", "kulipa"]
    has_debt_intent = any(kw in combined_text for kw in debt_intent_keywords)

    for debt in active_debts:
        debtor_name = debt.debtor_name.strip().lower()
        if not debtor_name:
            continue

        # Extract tokens (e.g., 'Teacher Maina', 'Dennis Omondi')
        clean_name = re.sub(r"[\(\)\[\]\-_,]", " ", debtor_name)
        name_tokens = [tok for tok in clean_name.split() if len(tok) >= 3]

        # Check full name substring
        if clean_name.strip() in combined_text:
            return (debt, float(tx.amount))

        # Check multi-token match (at least 2 tokens match or 1 significant token + debt intent)
        matching_tokens = [t for t in name_tokens if t in combined_text]
        if len(matching_tokens) >= 2:
            return (debt, float(tx.amount))
        if len(matching_tokens) == 1 and has_debt_intent:
            return (debt, float(tx.amount))

    return None


def apply_debt_repayment(
    debt: DebtRecord,
    payment_amount: float,
    receipt_number: str,
    payment_date: str,
    notes: str = ""
) -> DebtRecord:
    """
    Applies a repayment to a DebtRecord:
    - Decrements balance_remaining (capped at 0.0).
    - Increments amount_cleared (capped at amount_owed).
    - Updates status (CLEARED if balance == 0.0, else PARTIAL).
    - Appends an entry to repayment_history.
    """
    payment = max(0.0, float(payment_amount))
    new_balance = max(0.0, round(debt.balance_remaining - payment, 2))
    new_cleared = min(debt.amount_owed, round(debt.amount_cleared + payment, 2))

    debt.balance_remaining = new_balance
    debt.amount_cleared = new_cleared

    if debt.balance_remaining <= 0.0:
        debt.status = DebtStatus.CLEARED
    elif debt.amount_cleared > 0.0:
        debt.status = DebtStatus.PARTIAL
    else:
        debt.status = DebtStatus.UNPAID

    repayment_entry: Dict[str, Any] = {
        "receipt_number": receipt_number,
        "amount": round(payment, 2),
        "date": payment_date,
        "notes": notes or "Customer payment applied"
    }

    if debt.repayment_history is None:
        debt.repayment_history = []
    debt.repayment_history.append(repayment_entry)

    return debt


def calculate_debt_metrics(debts: List[DebtRecord]) -> Dict[str, Any]:
    """
    Calculates aggregate metrics across customer debts:
    - total_outstanding_amount: Sum of remaining balances.
    - total_cleared_amount: Sum of recovered debt payments.
    - recovery_rate_pct: Percentage of extended credit successfully cleared.
    - unpaid_count: Count of fully unpaid debt records.
    - delinquent_count: Count of overdue debts with positive balance.
    """
    if not debts:
        return {
            "total_outstanding_amount": 0.0,
            "total_cleared_amount": 0.0,
            "recovery_rate_pct": 0.0,
            "unpaid_count": 0,
            "delinquent_count": 0,
            "total_debts_count": 0,
            "partial_count": 0,
            "cleared_count": 0
        }

    total_outstanding = round(sum(d.balance_remaining for d in debts), 2)
    total_cleared = round(sum(d.amount_cleared for d in debts), 2)
    total_owed = round(sum(d.amount_owed for d in debts), 2)

    if total_owed > 0:
        recovery_rate = round((total_cleared / total_owed) * 100, 1)
    elif (total_cleared + total_outstanding) > 0:
        recovery_rate = round((total_cleared / (total_cleared + total_outstanding)) * 100, 1)
    else:
        recovery_rate = 0.0

    unpaid_count = sum(1 for d in debts if d.status == DebtStatus.UNPAID)
    partial_count = sum(1 for d in debts if d.status == DebtStatus.PARTIAL)
    cleared_count = sum(1 for d in debts if d.status == DebtStatus.CLEARED)

    now_iso = datetime.now(timezone.utc).isoformat()
    delinquent_count = 0
    for d in debts:
        if d.balance_remaining > 0:
            if d.due_date and d.due_date < now_iso:
                delinquent_count += 1

    return {
        "total_outstanding_amount": total_outstanding,
        "total_cleared_amount": total_cleared,
        "recovery_rate_pct": recovery_rate,
        "unpaid_count": unpaid_count,
        "delinquent_count": delinquent_count,
        "total_debts_count": len(debts),
        "partial_count": partial_count,
        "cleared_count": cleared_count
    }
