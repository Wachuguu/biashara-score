"""
Statement Handler: Safaricom CSV & SMS Ingestion, Transaction Listing
Implements:
- POST /statements/upload (with 5MB file size limit and .csv type validation)
- POST /statements/sms (with length and text format validation)
- GET /transactions (with query param validation)
"""
import re
import base64
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from .utils import (
    parse_body,
    make_error_response
)
from ..wrappers.db_client import db_client
from ..core.models import (
    Transaction,
    TransactionDirection,
    TransactionCategory,
    DebtRecord,
    DebtStatus
)
from ..core.parser import parse_csv_statement, parse_multiple_sms
from ..core.categorizer import categorize_batch
from ..core.debt_engine import match_repayment_to_debt, apply_debt_repayment

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 Megabytes limit per API Contract 2.2.1
ALLOWED_EXTENSIONS = {".csv", ".txt"}
ALLOWED_MIME_PREFIXES = {"text/csv", "application/vnd.ms-excel", "text/plain", "multipart/form-data"}


def _process_and_store_transactions(
    business_id: str,
    parsed_transactions: List[Transaction]
) -> Dict[str, Any]:
    """
    Categorizes, reconciles debts, de-duplicates by receipt_number, and stores transactions in db_client.
    """
    # 1. Categorize all parsed transactions
    categorized = categorize_batch(parsed_transactions)

    # 2. Retrieve open debts for debt reconciliation
    raw_debts = db_client.get_debts_for_business(business_id)
    open_debts = [
        DebtRecord(
            debt_id=d["debt_id"],
            business_id=d["business_id"],
            debtor_name=d["debtor_name"],
            debtor_phone=d["debtor_phone"],
            amount_owed=float(d.get("amount_owed", 0.0)),
            amount_cleared=float(d.get("amount_cleared", 0.0)),
            balance_remaining=float(d.get("balance_remaining", 0.0)),
            status=DebtStatus(d.get("status", "UNPAID")),
            items_summary=d.get("items_summary", ""),
            created_at=d.get("created_at", ""),
            due_date=d.get("due_date", ""),
            repayment_history=list(d.get("repayment_history", []))
        )
        for d in raw_debts
        if d.get("status") != "CLEARED" and float(d.get("balance_remaining", 0.0)) > 0
    ]

    debts_auto_matched = 0
    for tx in categorized:
        tx.business_id = business_id
        if tx.direction == TransactionDirection.IN:
            match_res = match_repayment_to_debt(tx, open_debts)
            if match_res:
                matched_debt, applied_amt = match_res
                apply_debt_repayment(
                    debt=matched_debt,
                    payment_amount=applied_amt,
                    receipt_number=tx.receipt_number,
                    payment_date=tx.completion_time,
                    notes=f"Auto-reconciled from {tx.details[:60]}"
                )
                # Persist updated debt
                db_client.update_debt(
                    business_id=business_id,
                    debt_id=matched_debt.debt_id,
                    updates={
                        "balance_remaining": matched_debt.balance_remaining,
                        "amount_cleared": matched_debt.amount_cleared,
                        "status": matched_debt.status.value,
                        "repayment_history": matched_debt.repayment_history
                    }
                )
                tx.debt_matched_id = matched_debt.debt_id
                tx.category = TransactionCategory.DEBT_RECOVERY
                debts_auto_matched += 1

    # 3. De-duplicate against existing transactions in db_client
    existing_records = db_client.get_transactions_for_business(business_id, limit=1000)
    existing_receipts = {r.get("receipt_number") for r in existing_records}

    imported_list: List[Dict[str, Any]] = []
    skipped_duplicates = 0
    categories_breakdown: Dict[str, int] = {c.value: 0 for c in TransactionCategory}

    for tx in categorized:
        if tx.receipt_number in existing_receipts:
            skipped_duplicates += 1
            continue

        existing_receipts.add(tx.receipt_number)
        cat_key = tx.category.value if hasattr(tx.category, "value") else str(tx.category)
        categories_breakdown[cat_key] = categories_breakdown.get(cat_key, 0) + 1

        tx_dict = {
            "business_id": business_id,
            "receipt_number": tx.receipt_number,
            "completion_time": tx.completion_time,
            "completion_time_receipt": f"{tx.completion_time}#{tx.receipt_number}",
            "details": tx.details,
            "amount": float(tx.amount),
            "direction": tx.direction.value if hasattr(tx.direction, "value") else str(tx.direction),
            "running_balance": float(tx.running_balance),
            "status": tx.status,
            "category": cat_key,
            "counterparty": tx.counterparty,
            "categorization_method": tx.categorization_method,
            "debt_matched_id": tx.debt_matched_id,
            "source": tx.source
        }
        imported_list.append(tx_dict)

    if imported_list:
        db_client.batch_put_transactions(imported_list)

    # Calculate date range
    timestamps = [t["completion_time"] for t in imported_list if t.get("completion_time")]
    date_range = {
        "start": min(timestamps) if timestamps else datetime.now(timezone.utc).isoformat(),
        "end": max(timestamps) if timestamps else datetime.now(timezone.utc).isoformat()
    }

    return {
        "imported": len(imported_list),
        "skipped_duplicates": skipped_duplicates,
        "debts_auto_matched": debts_auto_matched,
        "categories_breakdown": categories_breakdown,
        "date_range": date_range,
        "imported_transactions": imported_list
    }


def execute_csv_upload(business_id: str, csv_content: str, filename: str = "statement.csv") -> Dict[str, Any]:
    """Pure logic to parse and ingest CSV statement with size and format limits."""
    # 1. Type validation: check file extension
    lower_fn = (filename or "").lower()
    if lower_fn and not any(lower_fn.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        return {
            "statusCode": 400,
            "body": {
                "error": {
                    "code": "INVALID_STATEMENT_FORMAT",
                    "message": f"Unsupported file type. Statement must have a .csv extension (received '{filename}').",
                    "details": [{"field": "file", "issue": "Must be a .csv file"}],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        }

    # 2. Content presence check
    if not csv_content or not csv_content.strip():
        return {
            "statusCode": 400,
            "body": {
                "error": {
                    "code": "INVALID_STATEMENT_FORMAT",
                    "message": "CSV statement content is empty.",
                    "details": [],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        }

    # 3. Binary detection check
    if "\x00" in csv_content[:1024]:
        return {
            "statusCode": 400,
            "body": {
                "error": {
                    "code": "INVALID_STATEMENT_FORMAT",
                    "message": "Uploaded file contains binary data, not valid CSV text.",
                    "details": [{"field": "file", "issue": "Binary content detected"}],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        }

    # 4. Required M-Pesa CSV headers check
    content_lower = csv_content.lower()
    if "receipt" not in content_lower:
        return {
            "statusCode": 400,
            "body": {
                "error": {
                    "code": "INVALID_STATEMENT_FORMAT",
                    "message": "The uploaded CSV file is missing required M-Pesa header columns.",
                    "details": [
                        {
                            "field": "headers",
                            "issue": "Missing 'Receipt No.' column"
                        }
                    ],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        }

    # 5. Payload size check
    content_byte_len = len(csv_content.encode("utf-8"))
    if content_byte_len > MAX_UPLOAD_BYTES:
        return {
            "statusCode": 413,
            "body": {
                "error": {
                    "code": "PAYLOAD_TOO_LARGE",
                    "message": f"Statement file exceeds 5MB size limit (received {content_byte_len / (1024*1024):.2f}MB).",
                    "details": [{"field": "file", "limit": "5MB"}],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        }

    try:
        parsed_txs = parse_csv_statement(csv_content, business_id=business_id)
    except Exception as e:
        return {
            "statusCode": 400,
            "body": {
                "error": {
                    "code": "INVALID_STATEMENT_FORMAT",
                    "message": f"Failed to parse CSV statement: {str(e)}",
                    "details": [],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        }

    if not parsed_txs:
        return {
            "statusCode": 400,
            "body": {
                "error": {
                    "code": "INVALID_STATEMENT_FORMAT",
                    "message": "No valid M-Pesa transactions found in CSV.",
                    "details": [{"field": "rows", "issue": "No parseable transaction rows"}],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        }

    result = _process_and_store_transactions(business_id, parsed_txs)

    return {
        "statusCode": 200,
        "body": {
            "status": "success",
            "business_id": business_id,
            "statement_filename": filename,
            "imported": result["imported"],
            "skipped_duplicates": result["skipped_duplicates"],
            "debts_auto_matched": result["debts_auto_matched"],
            "categories_breakdown": result["categories_breakdown"],
            "date_range": result["date_range"]
        }
    }


def upload_statement(event: Dict[str, Any], business_id: str) -> Dict[str, Any]:
    """Lambda adapter for POST /statements/upload with size and content-type enforcement."""
    raw_headers = {str(k).lower(): str(v) for k, v in (event.get("headers") or {}).items()}
    content_type = raw_headers.get("content-type", "")

    raw_body = event.get("body", "")
    if event.get("isBase64Encoded"):
        try:
            decoded_bytes = base64.b64decode(raw_body)
        except Exception:
            return {
                "statusCode": 400,
                "body": {
                    "error": {
                        "code": "INVALID_STATEMENT_FORMAT",
                        "message": "Invalid base64 payload.",
                        "details": [],
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                }
            }

        # Size check on binary before string decode
        if len(decoded_bytes) > MAX_UPLOAD_BYTES:
            return {
                "statusCode": 413,
                "body": {
                    "error": {
                        "code": "PAYLOAD_TOO_LARGE",
                        "message": f"Uploaded file exceeds 5MB size limit ({len(decoded_bytes) / (1024*1024):.2f}MB).",
                        "details": [],
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                }
            }
        body = decoded_bytes.decode("utf-8", errors="replace")
    else:
        if len(raw_body.encode("utf-8")) > MAX_UPLOAD_BYTES:
            return {
                "statusCode": 413,
                "body": {
                    "error": {
                        "code": "PAYLOAD_TOO_LARGE",
                        "message": "Uploaded file exceeds 5MB size limit.",
                        "details": [],
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                }
            }
        body = raw_body

    # Extract filename from Content-Disposition if multipart
    filename = "statement.csv"
    fn_match = re.search(r'filename="([^"]+)"', body[:500])
    if fn_match:
        filename = fn_match.group(1)

    # Extract CSV content between multipart boundaries
    if "boundary=" in content_type.lower() or "--" in body[:100]:
        match = re.search(r"\r\n\r\n(.*?)(?:\r\n--|\Z)", body, re.DOTALL)
        csv_content = match.group(1) if match else body
    else:
        csv_content = body

    return execute_csv_upload(business_id, csv_content, filename=filename)


def execute_sms_ingestion(business_id: str, sms_text: str) -> Dict[str, Any]:
    """Pure logic to parse and ingest SMS string with input validation."""
    if not isinstance(sms_text, str) or not sms_text.strip():
        return {
            "statusCode": 400,
            "body": {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Field 'sms_text' must be a non-empty string.",
                    "details": [{"field": "sms_text", "issue": "Missing or empty"}],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        }

    # Length guard
    if len(sms_text) > 10000:
        return {
            "statusCode": 400,
            "body": {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Field 'sms_text' exceeds maximum length of 10,000 characters.",
                    "details": [{"field": "sms_text", "limit": "10000 characters"}],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        }

    try:
        parsed_txs = parse_multiple_sms(sms_text, business_id=business_id)
    except Exception as e:
        return {
            "statusCode": 400,
            "body": {
                "error": {
                    "code": "INVALID_STATEMENT_FORMAT",
                    "message": f"Failed to parse SMS message(s): {str(e)}",
                    "details": [],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        }

    result = _process_and_store_transactions(business_id, parsed_txs)

    return {
        "statusCode": 201,
        "body": {
            "status": "success",
            "business_id": business_id,
            "imported": result["imported"],
            "skipped_duplicates": result["skipped_duplicates"],
            "debts_auto_matched": result["debts_auto_matched"],
            "transactions": result["imported_transactions"]
        }
    }


def ingest_sms(event: Dict[str, Any], business_id: str) -> Dict[str, Any]:
    """Lambda adapter for POST /statements/sms."""
    body = parse_body(event)
    sms_text = body.get("sms_text", "")
    return execute_sms_ingestion(business_id, sms_text)


def execute_list_transactions(business_id: str, query_params: Dict[str, Any]) -> Dict[str, Any]:
    """Pure logic to list and filter transactions with robust input validation."""
    raw_limit = query_params.get("limit", 50)
    try:
        limit = int(raw_limit)
        if limit < 1 or limit > 200:
            limit = min(max(1, limit), 200)
    except (TypeError, ValueError):
        return {
            "statusCode": 400,
            "body": {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Query parameter 'limit' must be an integer between 1 and 200.",
                    "details": [{"param": "limit", "value": str(raw_limit)}],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        }

    category_filter = query_params.get("category")
    if category_filter:
        valid_cats = {c.value for c in TransactionCategory}
        if str(category_filter).upper() not in valid_cats:
            return {
                "statusCode": 400,
                "body": {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": f"Invalid category '{category_filter}'. Allowed: {sorted(list(valid_cats))}",
                        "details": [{"param": "category", "allowed": sorted(list(valid_cats))}],
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                }
            }

    direction_filter = query_params.get("direction")
    if direction_filter:
        if str(direction_filter).upper() not in ["IN", "OUT"]:
            return {
                "statusCode": 400,
                "body": {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Query parameter 'direction' must be 'IN' or 'OUT'.",
                        "details": [{"param": "direction", "allowed": ["IN", "OUT"]}],
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                }
            }

    start_date = query_params.get("start_date")
    end_date = query_params.get("end_date")

    raw_items = db_client.get_transactions_for_business(business_id, limit=1000)

    filtered = []
    for item in raw_items:
        if category_filter and item.get("category") != str(category_filter).upper():
            continue
        if direction_filter and item.get("direction") != str(direction_filter).upper():
            continue
        comp_time = item.get("completion_time", "")
        if start_date and comp_time < start_date:
            continue
        if end_date and comp_time > end_date:
            continue
        filtered.append(item)

    total_count = len(filtered)
    page_items = filtered[:limit]

    # Provide pagination next_cursor if there are subsequent items
    next_cursor = None
    if total_count > limit and page_items:
        last = page_items[-1]
        next_cursor = f"{last.get('completion_time')}#{last.get('receipt_number')}"

    return {
        "statusCode": 200,
        "body": {
            "business_id": business_id,
            "total_count": total_count,
            "next_cursor": next_cursor,
            "transactions": page_items
        }
    }


def list_transactions(event: Dict[str, Any], business_id: str) -> Dict[str, Any]:
    """Lambda adapter for GET /transactions."""
    query_params = event.get("queryStringParameters") or {}
    return execute_list_transactions(business_id, query_params)


# Aliases for local_server and testing interfaces
handle_csv_upload = execute_csv_upload
handle_sms_ingestion = execute_sms_ingestion
handle_list_transactions = execute_list_transactions

def handle_weekly_summary(business_id: str, query_params: Dict[str, Any]) -> Dict[str, Any]:
    from .score_handler import execute_weekly_summary
    return execute_weekly_summary(business_id, query_params)
