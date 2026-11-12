"""
Score Handler: Biashara Credit Scoring, Financial Summary & Lender PDF Verification Report
Implements:
- GET /summary/weekly
- GET /score
- POST /score/calculate
- GET /reports/lender-pdf
"""
import base64
from typing import Dict, Any, List
from dataclasses import asdict

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
from ..core.score_engine import calculate_biashara_score
from ..core.summary import calculate_weekly_summary, calculate_multi_week_series
from ..core.debt_engine import calculate_debt_metrics
from ..core.report_generator import generate_lender_pdf


def _load_transactions_and_debts(business_id: str):
    """Helper to convert db_client records into core dataclass instances."""
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

    return transactions, debts


def execute_weekly_summary(business_id: str, query_params: Dict[str, Any]) -> Dict[str, Any]:
    """Pure logic to calculate weekly financial summary and historical series."""
    weeks = int(query_params.get("weeks", 4))
    weeks = min(max(1, weeks), 12)

    txs, _ = _load_transactions_and_debts(business_id)
    curr_sum = calculate_weekly_summary(txs, business_id=business_id)
    history_models = calculate_multi_week_series(txs, num_weeks=weeks, business_id=business_id)

    current_week_dict = asdict(curr_sum)
    current_week_dict.pop("business_id", None)

    history_series = []
    for h in history_models:
        hd = asdict(h)
        history_series.append({
            "week_label": hd["week_label"],
            "gross_sales": hd["gross_sales"],
            "operating_expenses": hd["operating_expenses"],
            "estimated_profit": hd["estimated_profit"],
            "profit_margin_pct": hd["profit_margin_pct"]
        })

    return {
        "statusCode": 200,
        "body": {
            "business_id": business_id,
            "currency": "KSh",
            "current_week": current_week_dict,
            "history_series": history_series
        }
    }


def get_weekly_summary(event: Dict[str, Any], business_id: str) -> Dict[str, Any]:
    """Lambda adapter for GET /summary/weekly."""
    qp = event.get("queryStringParameters") or {}
    return execute_weekly_summary(business_id, qp)


def execute_score(business_id: str) -> Dict[str, Any]:
    """Pure logic to calculate Biashara Credit Score (0–100)."""
    txs, debts = _load_transactions_and_debts(business_id)
    score_res = calculate_biashara_score(business_id, txs, debts)
    return {
        "statusCode": 200,
        "body": asdict(score_res)
    }


def get_score(event: Dict[str, Any], business_id: str) -> Dict[str, Any]:
    """Lambda adapter for GET /score."""
    return execute_score(business_id)


def calculate_score(event: Dict[str, Any], business_id: str) -> Dict[str, Any]:
    """Lambda adapter for POST /score/calculate."""
    return execute_score(business_id)


def execute_lender_pdf(business_id: str, query_params: Dict[str, Any]) -> Dict[str, Any]:
    """Pure logic to generate downloadable single-page A4 lender verification PDF."""
    business_profile = db_client.get_business(business_id) or {
        "business_id": business_id,
        "shop_name": "Mama Mary Wholesale & Retail",
        "owner_name": "Mary Wambui",
        "owner_phone": "+254712345678",
        "till_number": "789123"
    }

    txs, debts = _load_transactions_and_debts(business_id)
    score_res = calculate_biashara_score(business_id, txs, debts)
    weekly_models = calculate_multi_week_series(txs, num_weeks=4, business_id=business_id)
    weekly_summaries = [asdict(w) for w in weekly_models]
    debt_summary = calculate_debt_metrics(debts)

    pdf_bytes = generate_lender_pdf(
        business_profile=business_profile,
        score_result=score_res,
        weekly_summaries=weekly_summaries,
        debt_summary=debt_summary
    )

    filename = f"Biashara_Score_Report_{business_profile.get('shop_name', 'Duka').replace(' ', '_')}.pdf"
    b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/pdf",
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
        "body": b64_pdf,
        "isBase64Encoded": True
    }


def download_lender_pdf(event: Dict[str, Any], business_id: str) -> Dict[str, Any]:
    """Lambda adapter for GET /reports/lender-pdf."""
    qp = event.get("queryStringParameters") or {}
    return execute_lender_pdf(business_id, qp)


# Aliases for local_server and testing interfaces
handle_score = execute_score
handle_lender_pdf = execute_lender_pdf
handle_weekly_summary = execute_weekly_summary

