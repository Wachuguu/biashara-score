"""
Statement Handler: Safaricom CSV & SMS Ingestion, Transaction Listing
Implements:
- POST /statements/upload
- POST /statements/sms
- GET /transactions
"""
import re
import base64
from typing import Dict, Any, List
from datetime import datetime, timezone

from .utils import (
    parse_body
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
    """Pure logic to parse and ingest CSV statement."""
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
    """Lambda adapter for POST /statements/upload."""
    body = event.get("body", "")
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8", errors="replace")

    # If multipart, extract file content between boundaries
    if "boundary=" in (event.get("headers") or {}).get("content-type", "").lower() or "--" in body[:100]:
        match = re.search(r"\r\n\r\n(.*?)(?:\r\n--|\Z)", body, re.DOTALL)
        csv_content = match.group(1) if match else body
    else:
        csv_content = body

    return execute_csv_upload(business_id, csv_content)


def execute_sms_ingestion(business_id: str, sms_text: str) -> Dict[str, Any]:
    """Pure logic to parse and ingest SMS string."""
    if not sms_text or not sms_text.strip():
        return {
            "statusCode": 400,
            "body": {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Field 'sms_text' cannot be empty.",
                    "details": [],
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
    """Pure logic to list and filter transactions."""
    limit = int(query_params.get("limit", 50))
    limit = min(max(1, limit), 200)

    category_filter = query_params.get("category")
    direction_filter = query_params.get("direction")
    start_date = query_params.get("start_date")
    end_date = query_params.get("end_date")

    raw_items = db_client.get_transactions_for_business(business_id, limit=1000)

    filtered = []
    for item in raw_items:
        if category_filter and item.get("category") != category_filter.upper():
            continue
        if direction_filter and item.get("direction") != direction_filter.upper():
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

