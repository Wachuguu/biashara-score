"""
Cron & Notification Handler: Weekly Financial Summary SMS Dispatch
Implements:
- POST /notifications/weekly-sms
- EventBridge Scheduled Cron Entry Point (weekly_cron_handler)
"""
from typing import Dict, Any, List
from datetime import datetime, timezone

from .utils import (
    parse_body,
    DEFAULT_TEST_BUSINESS_ID
)
from ..wrappers.db_client import db_client
from ..wrappers.sms_client import sms_client, build_weekly_sms_message
from ..core.models import (
    Transaction,
    TransactionDirection,
    TransactionCategory,
    DebtRecord,
    DebtStatus
)
from ..core.summary import calculate_weekly_summary
from ..core.score_engine import calculate_biashara_score


def execute_weekly_sms_notification(
    business_id: str,
    override_phone: str = "",
    week_label: str = ""
) -> Dict[str, Any]:
    """Generates financial summary and dispatches SMS for a single business."""
    biz = db_client.get_business(business_id) or {
        "business_id": business_id,
        "shop_name": "Mary's Family Provisions",
        "owner_name": "Mary Wambui",
        "owner_phone": "+254712345678"
    }

    recipient_phone = override_phone or biz.get("owner_phone", "+254712345678")
    owner_name = biz.get("owner_name", "Shopkeeper")

    raw_txs = db_client.get_transactions_for_business(business_id, limit=1000)
    transactions = [
        Transaction(
            receipt_number=t.get("receipt_number", ""),
            completion_time=t.get("completion_time", ""),
            details=t.get("details", ""),
            amount=float(t.get("amount", 0.0)),
            direction=TransactionDirection(t.get("direction", "IN")),
            running_balance=float(t.get("running_balance", 0.0)),
            status=t.get("status", "Completed"),
            category=TransactionCategory(t.get("category", "UNCATEGORIZED")),
            counterparty=t.get("counterparty"),
            categorization_method=t.get("categorization_method", "RULE_BASED"),
            debt_matched_id=t.get("debt_matched_id"),
            business_id=business_id,
            source=t.get("source", "CSV_UPLOAD")
        )
        for t in raw_txs
    ]

    raw_debts = db_client.get_debts_for_business(business_id)
    debts = [
        DebtRecord(
            debt_id=d.get("debt_id", ""),
            business_id=business_id,
            debtor_name=d.get("debtor_name", ""),
            debtor_phone=d.get("debtor_phone", ""),
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
    ]

    summary = calculate_weekly_summary(transactions, business_id=business_id)
    score_res = calculate_biashara_score(business_id, transactions, debts)

    actual_week = week_label or summary.week_label
    total_outstanding = sum(d.balance_remaining for d in debts)

    sms_text = build_weekly_sms_message(
        owner_name=owner_name,
        week_label=actual_week,
        sales=summary.gross_sales,
        expenses=summary.operating_expenses,
        profit=summary.estimated_profit,
        outstanding_debts=total_outstanding,
        score=score_res.total_score,
        tier=score_res.tier
    )

    provider_resp = sms_client.send_sms(recipient_phone, sms_text)

    response_payload = {
        "status": "success",
        "business_id": business_id,
        "recipient_phone": recipient_phone,
        "sms_text": sms_text,
        "provider_response": provider_resp.get("provider_response", {
            "status": "success",
            "mode": provider_resp.get("mode", "mock"),
            "cost": "KSh 0.80"
        }),
        "dispatched_at": datetime.now(timezone.utc).isoformat()
    }

    return {
        "statusCode": 200,
        "body": response_payload
    }


def send_weekly_sms_notification(event: Dict[str, Any], business_id: str) -> Dict[str, Any]:
    """Lambda adapter for POST /notifications/weekly-sms."""
    body = parse_body(event)
    override_phone = body.get("override_phone", "")
    week_label = body.get("week_label", "")
    return execute_weekly_sms_notification(business_id, override_phone, week_label)


def weekly_cron_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """EventBridge Scheduled Sunday 8:00 PM EAT cron handler."""
    result = execute_weekly_sms_notification(DEFAULT_TEST_BUSINESS_ID)
    return {
        "statusCode": 200,
        "body": result["body"]
    }


lambda_handler = weekly_cron_handler
_send_weekly_digest_for_business = execute_weekly_sms_notification

