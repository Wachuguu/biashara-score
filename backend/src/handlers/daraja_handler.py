"""
Safaricom Daraja M-Pesa Handler
Processes C2B Validation, C2B Confirmation webhooks, STK push callbacks,
and provides live payment simulation and sample data preloading.
"""
import os
import csv
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from src.core.models import (
    Transaction,
    TransactionDirection,
    TransactionCategory,
    DebtRecord,
    DebtStatus
)
from src.core.debt_engine import match_repayment_to_debt, apply_debt_repayment, normalize_phone_number
from src.wrappers.db_client import db_client, DEFAULT_TEST_BUSINESS_ID
from src.wrappers.daraja_client import daraja_client


def _parse_daraja_timestamp(raw_time: Optional[str]) -> str:
    """Converts Daraja TransTime format 'YYYYMMDDHHmmss' to ISO-8601 UTC string."""
    if not raw_time or len(raw_time) < 14:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        dt = datetime.strptime(raw_time[:14], "%Y%m%d%H%M%S")
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def execute_c2b_validation(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handles Safaricom C2B Validation webhook."""
    return {
        "ResultCode": 0,
        "ResultDesc": "Accepted"
    }


def execute_c2b_confirmation(
    payload: Dict[str, Any],
    target_business_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Handles Safaricom C2B Confirmation webhook.
    1. Extracts transaction details (TransID, Amount, MSISDN, Name).
    2. Maps payment to business.
    3. Auto-reconciles customer debts if sender matches open debt.
    4. Saves transaction to database.
    5. Returns Safaricom-compliant JSON.
    """
    trans_id = payload.get("TransID", "").strip()
    if not trans_id:
        return {"ResultCode": 1, "ResultDesc": "Missing TransID"}

    raw_amount = payload.get("TransAmount", 0.0)
    try:
        amount = float(raw_amount)
    except (ValueError, TypeError):
        amount = 0.0

    raw_time = payload.get("TransTime", "")
    completion_time = _parse_daraja_timestamp(raw_time)

    first_name = payload.get("FirstName", "").strip()
    last_name = payload.get("LastName", "").strip()
    counterparty = f"{first_name} {last_name}".strip() or "M-Pesa Customer"

    msisdn = payload.get("MSISDN", "").strip()
    phone = normalize_phone_number(msisdn) if msisdn else ""

    shortcode = payload.get("BusinessShortCode", "").strip()
    details = f"Customer Payment to Till {shortcode} - {counterparty} {phone}".strip()

    # Determine business_id:
    biz_id = target_business_id
    if not biz_id:
        # Search for business with matching till_number
        all_biz = db_client.list_all_businesses() if hasattr(db_client, "list_all_businesses") else []
        for b in all_biz:
            if b.get("till_number") and str(b.get("till_number")).strip() == shortcode:
                biz_id = b.get("business_id")
                break

    if not biz_id:
        biz_id = DEFAULT_TEST_BUSINESS_ID

    # Check for customer debt reconciliation
    raw_debts = db_client.get_debts_for_business(biz_id)
    debt_models: List[DebtRecord] = []
    for d in raw_debts:
        hist = d.get("repayment_history", [])
        if isinstance(hist, str):
            try:
                hist = json.loads(hist)
            except Exception:
                hist = []
        debt_models.append(DebtRecord(
            debt_id=d["debt_id"],
            business_id=biz_id,
            debtor_name=d["debtor_name"],
            debtor_phone=d.get("debtor_phone", ""),
            amount_owed=float(d["amount_owed"]),
            amount_cleared=float(d.get("amount_cleared", 0.0)),
            balance_remaining=float(d.get("balance_remaining", d["amount_owed"])),
            status=DebtStatus(d.get("status", "UNPAID")),
            items_summary=d.get("items_summary", ""),
            created_at=d.get("created_at", ""),
            due_date=d.get("due_date", ""),
            repayment_history=hist
        ))

    temp_tx = Transaction(
        receipt_number=trans_id,
        completion_time=completion_time,
        details=details,
        amount=amount,
        direction=TransactionDirection.IN,
        running_balance=0.0,
        status="Completed",
        category=TransactionCategory.SALES,
        counterparty=counterparty,
        source="MPESA_DARAJA_C2B",
        business_id=biz_id
    )

    matched = match_repayment_to_debt(temp_tx, debt_models)
    matched_debt_id: Optional[str] = None
    category = TransactionCategory.SALES

    if matched:
        matched_debt, pay_amt = matched
        matched_debt_id = matched_debt.debt_id
        category = TransactionCategory.DEBT_RECOVERY

        updated_debt = apply_debt_repayment(
            matched_debt,
            pay_amt,
            receipt_number=trans_id,
            payment_date=completion_time,
            notes=f"Auto-cleared via Safaricom Daraja M-Pesa Till ({trans_id})"
        )

        db_client.update_debt(biz_id, updated_debt.debt_id, {
            "amount_cleared": updated_debt.amount_cleared,
            "balance_remaining": updated_debt.balance_remaining,
            "status": updated_debt.status.value,
            "repayment_history": updated_debt.repayment_history
        })

    # Save transaction
    tx_item = {
        "business_id": biz_id,
        "receipt_number": trans_id,
        "completion_time": completion_time,
        "details": details,
        "amount": amount,
        "direction": "IN",
        "running_balance": 0.0,
        "status": "Completed",
        "category": category.value,
        "counterparty": counterparty,
        "source": "MPESA_DARAJA_C2B",
        "debt_matched_id": matched_debt_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    db_client.put_transaction(tx_item)

    return {
        "ResultCode": 0,
        "ResultDesc": "Confirmation received successfully",
        "transaction": tx_item,
        "debt_matched": bool(matched_debt_id)
    }


def execute_simulate_payment(business_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simulates a live customer payment arriving via Safaricom Daraja.
    Enables instant pitch demonstrations and live interactive testing.
    """
    raw_amount = body.get("amount", 1500.0)
    try:
        amount = float(raw_amount)
    except (ValueError, TypeError):
        amount = 1500.0

    phone = str(body.get("phone", "+254712345678")).strip()
    full_name = str(body.get("customer_name", "John Kamau")).strip()
    name_parts = full_name.split()
    first_name = name_parts[0] if name_parts else "John"
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else "Kamau"

    biz = db_client.get_business(business_id) or {}
    till_number = biz.get("till_number") or "789123"

    payload = daraja_client.generate_simulated_c2b_payload(
        amount=amount,
        phone=phone,
        first_name=first_name,
        last_name=last_name,
        till_number=till_number
    )

    result = execute_c2b_confirmation(payload, target_business_id=business_id)
    return {
        "status": "success",
        "simulated": True,
        "payload": payload,
        "result": result
    }


def execute_load_sample_statement(business_id: str) -> Dict[str, Any]:
    """
    Loads the official 150-transaction sample M-Pesa statement in 1 click.
    Guarantees reliable demonstration even without external files.
    """
    # Look for sample csv in repo root or fallback paths
    possible_paths = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "sample-data", "mpesa_statement.csv"),
        "/home/paul/Desktop/biashara/sample-data/mpesa_statement.csv",
        "sample-data/mpesa_statement.csv"
    ]

    csv_path = None
    for p in possible_paths:
        if os.path.exists(p):
            csv_path = p
            break

    if not csv_path:
        return {"status": "error", "message": "Sample statement file not found."}

    from src.handlers.statement_handler import execute_csv_upload
    with open(csv_path, "r", encoding="utf-8") as f:
        csv_text = f.read()

    res = execute_csv_upload(business_id=business_id, csv_content=csv_text, filename="mpesa_statement.csv")
    body = res.get("body", {}) if isinstance(res.get("body"), dict) else {}
    return {
        "status": "success",
        "imported": body.get("imported", 0),
        "skipped_duplicates": body.get("skipped_duplicates", 0),
        "debts_auto_matched": body.get("debts_auto_matched", 0),
        "date_range": body.get("date_range")
    }
