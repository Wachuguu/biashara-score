"""
Debt Handler: Digital Kitabu ya Deni (Customer Debt Tracking)
Implements:
- POST /debts (with input validation for name, phone, amount)
- GET /debts (with status and search query validation)
- PATCH /debts/{debt_id} (with negative amount rejection)
"""
import re
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

PHONE_PATTERN = re.compile(r"^(\+?254|0)?[17]\d{8}$")
VALID_STATUSES = {s.value for s in DebtStatus}


def is_valid_phone(phone: str) -> bool:
    """Validates Kenyan phone number format."""
    if not phone or not isinstance(phone, str):
        return False
    clean_phone = phone.replace(" ", "").replace("-", "")
    return bool(PHONE_PATTERN.match(clean_phone))


def execute_create_debt(business_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Pure logic to create customer debt record in Kitabu ya Deni with strict validation."""
    if not isinstance(body, dict):
        return {
            "statusCode": 400,
            "body": {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request body must be a JSON object.",
                    "details": [],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        }

    debtor_name = str(body.get("debtor_name", "")).strip()
    debtor_phone = str(body.get("debtor_phone", "")).strip()

    if not debtor_name or len(debtor_name) > 100:
        return {
            "statusCode": 400,
            "body": {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Field 'debtor_name' is required and must be between 1 and 100 characters.",
                    "details": [{"field": "debtor_name", "issue": "Missing or too long"}],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        }

    try:
        raw_amt = body.get("amount_owed")
        if raw_amt is None:
            raise ValueError
        amount_owed = float(raw_amt)
        if amount_owed <= 0 or amount_owed > 10000000:
            raise ValueError
    except (TypeError, ValueError):
        return {
            "statusCode": 400,
            "body": {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Field 'amount_owed' must be a positive number up to 10,000,000.",
                    "details": [{"field": "amount_owed", "issue": "Must be > 0 and <= 10,000,000"}],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        }

    if debtor_phone:
        clean_phone = debtor_phone.replace(" ", "").replace("-", "")
        if not PHONE_PATTERN.match(clean_phone):
            return {
                "statusCode": 400,
                "body": {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Field 'debtor_phone' must be a valid Kenyan phone number (e.g. +254712345678 or 0712345678).",
                        "details": [{"field": "debtor_phone", "issue": "Invalid format"}],
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                }
            }
        normalized_phone = normalize_phone_number(clean_phone)
    else:
        normalized_phone = ""

    items_summary = str(body.get("items_summary", ""))[:500]
    due_date = str(body.get("due_date", ""))[:50]
    debt_id = f"debt_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    debt_dict = {
        "debt_id": debt_id,
        "business_id": business_id,
        "debtor_name": debtor_name,
        "debtor_phone": normalized_phone,
        "amount_owed": amount_owed,
        "amount_cleared": 0.0,
        "balance_remaining": amount_owed,
        "status": DebtStatus.UNPAID.value,
        "items_summary": items_summary,
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
    """Pure logic to list customer debts and aggregate recovery metrics with query validation."""
    status_filter = query_params.get("status")
    if status_filter:
        st_upper = str(status_filter).upper()
        if st_upper not in VALID_STATUSES:
            return {
                "statusCode": 400,
                "body": {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": f"Invalid debt status '{status_filter}'. Allowed: {sorted(list(VALID_STATUSES))}",
                        "details": [{"param": "status", "allowed": sorted(list(VALID_STATUSES))}],
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                }
            }

    search_val = query_params.get("search")
    search_query = str(search_val).strip().lower()[:100] if search_val else ""

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
            status=DebtStatus(st) if st in VALID_STATUSES else DebtStatus.UNPAID,
            items_summary=d.get("items_summary", ""),
            created_at=d.get("created_at", ""),
            due_date=d.get("due_date", ""),
            repayment_history=list(d.get("repayment_history", []))
        ))

    all_metrics = calculate_debt_metrics(debt_models)

    filtered: List[Dict[str, Any]] = []
    for d in raw_debts:
        if status_filter and d.get("status") != str(status_filter).upper():
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
    """Pure logic to update debt or log counter cash repayment with input validation."""
    if not debt_id or len(debt_id) > 64:
        return {
            "statusCode": 400,
            "body": {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid debt ID format.",
                    "details": [],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        }

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

    raw_amt = body.get("amount_to_clear", 0.0)
    try:
        amount_to_clear = float(raw_amt)
        if amount_to_clear < 0:
            raise ValueError("Negative amount")
    except (TypeError, ValueError):
        return {
            "statusCode": 400,
            "body": {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Field 'amount_to_clear' must be a non-negative number.",
                    "details": [{"field": "amount_to_clear", "issue": "Cannot be negative"}],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        }

    receipt_number = str(body.get("receipt_number", "CASH_RECOVERY"))[:50]
    notes = str(body.get("notes", "Paid in cash at shop counter"))[:500]

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
