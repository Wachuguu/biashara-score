"""
Debt Handler: Digital Kitabu ya Deni (Customer Debt Tracking)
Implements:
- POST /debts
- GET /debts
- PATCH /debts/{debt_id}
"""
import uuid
from typing import Dict, Any, List
from datetime import datetime, timezone
from dataclasses import asdict

from .utils import (
    parse_body
)
from ..wrappers.db_client import db_client
from ..core.models import DebtRecord, DebtStatus
from ..core.debt_engine import (
    normalize_phone_number,
    apply_debt_repayment,
    calculate_debt_metrics
)


def execute_create_debt(business_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Pure logic to create customer debt record in Kitabu ya Deni."""
    debtor_name = body.get("debtor_name", "").strip()
    debtor_phone = body.get("debtor_phone", "").strip()

    if not debtor_name:
        return {
            "statusCode": 400,
            "body": {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Field 'debtor_name' is required.",
                    "details": [{"field": "debtor_name", "issue": "Missing debtor name"}],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        }

    try:
        amount_owed = float(body.get("amount_owed", 0.0))
        if amount_owed <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return {
            "statusCode": 400,
            "body": {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Field 'amount_owed' must be a positive number.",
                    "details": [{"field": "amount_owed", "issue": "Must be > 0"}],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        }

    normalized_phone = normalize_phone_number(debtor_phone) if debtor_phone else ""
    debt_id = f"debt_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    due_date = body.get("due_date", "")

    debt_dict = {
        "debt_id": debt_id,
        "business_id": business_id,
        "debtor_name": debtor_name,
        "debtor_phone": normalized_phone,
        "amount_owed": amount_owed,
        "amount_cleared": 0.0,
        "balance_remaining": amount_owed,
        "status": DebtStatus.UNPAID.value,
        "items_summary": body.get("items_summary", ""),
        "created_at": now_iso,
        "due_date": due_date,
        "repayment_history": []
    }

    db_client.put_debt(debt_dict)
    return {
        "statusCode": 201,
        "body": debt_dict
    }


def create_debt(event: Dict[str, Any], business_id: str) -> Dict[str, Any]:
    """Lambda adapter for POST /debts."""
    body = parse_body(event)
    return execute_create_debt(business_id, body)


def execute_list_debts(business_id: str, query_params: Dict[str, Any]) -> Dict[str, Any]:
    """Pure logic to list customer debts and aggregate recovery metrics."""
    status_filter = query_params.get("status")
    search_val = query_params.get("search")
    search_query = str(search_val).strip().lower() if search_val else ""

    raw_debts = db_client.get_debts_for_business(business_id)

    debt_models: List[DebtRecord] = []
    for d in raw_debts:
        st = d.get("status", "UNPAID")
        debt_models.append(DebtRecord(
            debt_id=d.get("debt_id", ""),
            business_id=business_id,
            debtor_name=d.get("debtor_name", ""),
            debtor_phone=d.get("debtor_phone", ""),
            amount_owed=float(d.get("amount_owed", 0.0)),
            amount_cleared=float(d.get("amount_cleared", 0.0)),
            balance_remaining=float(d.get("balance_remaining", 0.0)),
            status=DebtStatus(st) if st in [s.value for s in DebtStatus] else DebtStatus.UNPAID,
            items_summary=d.get("items_summary", ""),
            created_at=d.get("created_at", ""),
            due_date=d.get("due_date", ""),
            repayment_history=list(d.get("repayment_history", []))
        ))

    all_metrics = calculate_debt_metrics(debt_models)

    filtered: List[Dict[str, Any]] = []
    for d in raw_debts:
        if status_filter and d.get("status") != status_filter.upper():
            continue
        if search_query:
            name = d.get("debtor_name", "").lower()
            phone = d.get("debtor_phone", "").lower()
            if search_query not in name and search_query not in phone:
                continue
        filtered.append(d)

    summary_response = {
        "total_outstanding_amount": all_metrics["total_outstanding_amount"],
        "total_cleared_amount": all_metrics["total_cleared_amount"],
        "recovery_rate_pct": all_metrics["recovery_rate_pct"],
        "unpaid_count": all_metrics["unpaid_count"],
        "delinquent_count": all_metrics["delinquent_count"]
    }

    return {
        "statusCode": 200,
        "body": {
            "business_id": business_id,
            "summary": summary_response,
            "debts": filtered
        }
    }


def list_debts(event: Dict[str, Any], business_id: str) -> Dict[str, Any]:
    """Lambda adapter for GET /debts."""
    query_params = event.get("queryStringParameters") or {}
    return execute_list_debts(business_id, query_params)


def execute_update_debt(business_id: str, debt_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Pure logic to update debt or log counter cash repayment."""
    existing = db_client.get_debt_by_id(business_id, debt_id)
    if not existing:
        return {
            "statusCode": 404,
            "body": {
                "error": {
                    "code": "RESOURCE_NOT_FOUND",
                    "message": f"Debt with ID '{debt_id}' does not exist.",
                    "details": [],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        }

    amount_to_clear = float(body.get("amount_to_clear", 0.0))
    receipt_number = body.get("receipt_number", "CASH_RECOVERY")
    notes = body.get("notes", "Paid in cash at shop counter")

    debt_model = DebtRecord(
        debt_id=existing.get("debt_id", ""),
        business_id=business_id,
        debtor_name=existing.get("debtor_name", ""),
        debtor_phone=existing.get("debtor_phone", ""),
        amount_owed=float(existing.get("amount_owed", 0.0)),
        amount_cleared=float(existing.get("amount_cleared", 0.0)),
        balance_remaining=float(existing.get("balance_remaining", 0.0)),
        status=DebtStatus(existing.get("status", "UNPAID")),
        items_summary=existing.get("items_summary", ""),
        created_at=existing.get("created_at", ""),
        due_date=existing.get("due_date", ""),
        repayment_history=list(existing.get("repayment_history", []))
    )

    if amount_to_clear > 0:
        now_iso = datetime.now(timezone.utc).isoformat()
        apply_debt_repayment(
            debt=debt_model,
            payment_amount=amount_to_clear,
            receipt_number=receipt_number,
            payment_date=now_iso,
            notes=notes
        )

    updated_dict = asdict(debt_model)
    updated_dict["status"] = debt_model.status.value

    db_client.update_debt(
        business_id=business_id,
        debt_id=debt_id,
        updates={
            "balance_remaining": updated_dict["balance_remaining"],
            "amount_cleared": updated_dict["amount_cleared"],
            "status": updated_dict["status"],
            "repayment_history": updated_dict["repayment_history"]
        }
    )

    return {
        "statusCode": 200,
        "body": updated_dict
    }


def update_debt(event: Dict[str, Any], business_id: str, debt_id: str) -> Dict[str, Any]:
    """Lambda adapter for PATCH /debts/{debt_id}."""
    body = parse_body(event)
    return execute_update_debt(business_id, debt_id, body)


# Aliases for local_server and testing interfaces
handle_create_debt = execute_create_debt
handle_list_debts = execute_list_debts
handle_update_debt = execute_update_debt

