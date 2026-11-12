"""
Main AWS Lambda API Gateway Handler
Routes HTTP API Gateway requests, manages tenant authorization, handles CORS,
and provides standardized error envelopes.
"""
import json
import os
import re
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone

from src.wrappers.db_client import db_client, DEFAULT_TEST_BUSINESS
from src.handlers.utils import (
    resolve_business_id,
    get_cors_headers,
    make_error_response,
    is_mock_mode
)
from src.handlers.statement_handler import upload_statement, ingest_sms, list_transactions
from src.handlers.debt_handler import create_debt, list_debts, update_debt
from src.handlers.score_handler import get_score, calculate_score, get_weekly_summary, download_lender_pdf
from src.handlers.cron_handler import send_weekly_sms_notification

PHONE_REGEX = re.compile(r"^(\+?254|0)?[17]\d{8}$")
TILL_REGEX = re.compile(r"^\d{4,10}$")


def _format_response(handler_result: Dict[str, Any], origin: Optional[str] = None) -> Dict[str, Any]:
    status_code = handler_result.get("statusCode", 200)
    res_headers = get_cors_headers(origin)
    if "headers" in handler_result:
        res_headers.update(handler_result["headers"])

    is_b64 = handler_result.get("isBase64Encoded", False)
    body_data = handler_result.get("body", {})

    if is_b64:
        body_str = body_data if isinstance(body_data, str) else ""
    elif isinstance(body_data, str):
        body_str = body_data
    else:
        body_str = json.dumps(body_data)

    out = {
        "statusCode": status_code,
        "headers": res_headers,
        "body": body_str
    }
    if is_b64:
        out["isBase64Encoded"] = True
    return out


def _build_error(status_code: int, code: str, message: str, details: Optional[list] = None) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "body": {
            "error": {
                "code": code,
                "message": message,
                "details": details or [],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
    }


def _validate_business_update(body: Any) -> Tuple[bool, Optional[str]]:
    if not isinstance(body, dict) or not body:
        return False, "Request body must be a non-empty JSON object."

    allowed_keys = {"shop_name", "owner_name", "owner_phone", "till_number"}
    for k in body.keys():
        if k not in allowed_keys:
            return False, f"Unknown field '{k}'. Allowed: {sorted(list(allowed_keys))}"

    if "shop_name" in body:
        sn = body["shop_name"]
        if not isinstance(sn, str) or not sn.strip() or len(sn) > 100:
            return False, "Field 'shop_name' must be a non-empty string up to 100 characters."

    if "owner_name" in body:
        on = body["owner_name"]
        if not isinstance(on, str) or not on.strip() or len(on) > 100:
            return False, "Field 'owner_name' must be a non-empty string up to 100 characters."

    if "owner_phone" in body:
        op = str(body["owner_phone"]).strip().replace(" ", "").replace("-", "")
        if not PHONE_REGEX.match(op):
            return False, "Field 'owner_phone' must be a valid Kenyan phone number (e.g. +254712345678)."

    if "till_number" in body:
        tn = str(body["till_number"]).strip()
        if not TILL_REGEX.match(tn):
            return False, "Field 'till_number' must be 4 to 10 digits."

    return True, None


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda entry point for API Gateway HTTP API."""
    origin = None
    try:
        raw_headers = event.get("headers") or {}
        origin = raw_headers.get("origin") or raw_headers.get("Origin")

        # Determine HTTP Method
        method = event.get("httpMethod")
        if not method and "requestContext" in event:
            method = event["requestContext"].get("http", {}).get("method")
        method = (method or "GET").upper()

        # Handle CORS OPTIONS Preflight
        if method == "OPTIONS":
            return _format_response({"statusCode": 200, "body": {"status": "ok"}}, origin=origin)

        # Determine normalized path
        path = event.get("rawPath") or event.get("path") or "/"
        # Strip trailing slash if not root
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]

        # 1. Health check (Public - No auth required)
        if path == "/health" and method == "GET":
            return _format_response({
                "statusCode": 200,
                "body": {
                    "status": "healthy",
                    "environment": os.getenv("ENVIRONMENT", "dev"),
                    "mock_aws": is_mock_mode(),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }, origin=origin)

        # Multi-tenant business ID resolution:
        # - When MOCK_AWS=false: Strictly rejects X-Business-Id (403), extracts sub from authorizer (or 401)
        # - When MOCK_AWS=true: Accepts X-Business-Id or default test business
        business_id, auth_error = resolve_business_id(event)
        if auth_error:
            return _format_response(auth_error, origin=origin)

        # 2. Business Profile Endpoints
        if path == "/business":
            if method == "GET":
                biz = db_client.get_business(business_id) or {
                    "business_id": business_id,
                    "shop_name": "Mary's Family Provisions",
                    "owner_name": "Mary Wambui",
                    "owner_phone": "+254712345678",
                    "till_number": "789123",
                    "created_at": "2026-09-01T08:00:00Z"
                }
                return _format_response({"statusCode": 200, "body": biz}, origin=origin)

            elif method == "PUT":
                raw_body = event.get("body", "")
                if isinstance(raw_body, str):
                    try:
                        body = json.loads(raw_body) if raw_body else {}
                    except json.JSONDecodeError:
                        return _format_response(_build_error(
                            400, "VALIDATION_ERROR", "Invalid JSON in request body."
                        ), origin=origin)
                else:
                    body = raw_body or {}

                is_valid, err_msg = _validate_business_update(body)
                if not is_valid:
                    return _format_response(_build_error(
                        400, "VALIDATION_ERROR", err_msg or "Validation error"
                    ), origin=origin)

                biz = db_client.get_business(business_id) or dict(DEFAULT_TEST_BUSINESS)
                biz["business_id"] = business_id
                if "shop_name" in body:
                    biz["shop_name"] = str(body["shop_name"]).strip()
                if "owner_name" in body:
                    biz["owner_name"] = str(body["owner_name"]).strip()
                if "owner_phone" in body:
                    biz["owner_phone"] = str(body["owner_phone"]).strip()
                if "till_number" in body:
                    biz["till_number"] = str(body["till_number"]).strip()

                db_client.put_business(biz)
                return _format_response({"statusCode": 200, "body": biz}, origin=origin)

        # 3. Statement & Transaction Endpoints
        if path == "/statements/upload" and method == "POST":
            return _format_response(upload_statement(event, business_id), origin=origin)

        if path == "/statements/sms" and method == "POST":
            return _format_response(ingest_sms(event, business_id), origin=origin)

        if path == "/transactions" and method == "GET":
            return _format_response(list_transactions(event, business_id), origin=origin)

        # 4. Summary & Scoring Endpoints
        if path == "/summary/weekly" and method == "GET":
            return _format_response(get_weekly_summary(event, business_id), origin=origin)

        if path == "/score" and method == "GET":
            return _format_response(get_score(event, business_id), origin=origin)

        if path == "/score/calculate" and method == "POST":
            return _format_response(calculate_score(event, business_id), origin=origin)

        if path == "/reports/lender-pdf" and method == "GET":
            return _format_response(download_lender_pdf(event, business_id), origin=origin)

        # 5. Debt Engine ("Kitabu ya Deni") Endpoints
        if path == "/debts" and method == "POST":
            return _format_response(create_debt(event, business_id), origin=origin)

        if path == "/debts" and method == "GET":
            return _format_response(list_debts(event, business_id), origin=origin)

        # Match /debts/{debt_id}
        debt_match = re.match(r"^/debts/([^/]+)$", path)
        if debt_match and method == "PATCH":
            debt_id = debt_match.group(1)
            return _format_response(update_debt(event, business_id, debt_id), origin=origin)

        # 6. Notifications Endpoints
        if path == "/notifications/weekly-sms" and method == "POST":
            return _format_response(send_weekly_sms_notification(event, business_id), origin=origin)

        # 404 Fallback
        return _format_response(_build_error(
            status_code=404,
            code="RESOURCE_NOT_FOUND",
            message=f"Endpoint '{method} {path}' not found."
        ), origin=origin)

    except Exception as e:
        return _format_response(_build_error(
            status_code=500,
            code="INTERNAL_SERVER_ERROR",
            message=f"An unexpected server error occurred: {str(e)}"
        ), origin=origin)
