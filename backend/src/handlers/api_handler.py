"""
Main AWS Lambda API Gateway Handler
Routes HTTP API Gateway requests, manages tenant authorization, handles CORS,
and provides standardized error envelopes.
"""
import json
import os
import re
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from src.wrappers.db_client import db_client, DEFAULT_TEST_BUSINESS
from src.handlers.statement_handler import upload_statement, ingest_sms, list_transactions
from src.handlers.debt_handler import create_debt, list_debts, update_debt
from src.handlers.score_handler import get_score, calculate_score, get_weekly_summary, download_lender_pdf
from src.handlers.cron_handler import send_weekly_sms_notification

MOCK_MODE = os.getenv("MOCK_AWS", "true").lower() == "true"

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Business-Id, *",
    "Content-Type": "application/json"
}


def _extract_business_id(event: Dict[str, Any]) -> str:
    # 1. Cognito JWT Authorizer (Production)
    req_ctx = event.get("requestContext", {})
    authorizer = req_ctx.get("authorizer", {})
    jwt_claims = authorizer.get("jwt", {}).get("claims", {}) or authorizer.get("claims", {})
    sub_claim = jwt_claims.get("sub") or jwt_claims.get("custom:business_id")
    if sub_claim and not MOCK_MODE:
        return str(sub_claim)

    # 2. Mock mode X-Business-Id header
    if MOCK_MODE:
        headers = {str(k).lower(): v for k, v in (event.get("headers") or {}).items()}
        custom_biz = headers.get("x-business-id")
        if custom_biz:
            return str(custom_biz).strip()

    # 3. Default test business fallback
    return DEFAULT_TEST_BUSINESS["business_id"]


def _format_response(handler_result: Dict[str, Any]) -> Dict[str, Any]:
    status_code = handler_result.get("statusCode", 200)
    res_headers = dict(CORS_HEADERS)
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


def health_check(query_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "status": "healthy",
        "environment": os.getenv("ENVIRONMENT", "dev"),
        "mock_aws": MOCK_MODE,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def get_business_profile(business_id: str) -> Dict[str, Any]:
    biz = db_client.get_business(business_id)
    if not biz:
        biz = dict(DEFAULT_TEST_BUSINESS)
        biz["business_id"] = business_id
    return biz


def update_business_profile(business_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    biz = db_client.get_business(business_id) or dict(DEFAULT_TEST_BUSINESS)
    biz["business_id"] = business_id
    if "shop_name" in body:
        biz["shop_name"] = body["shop_name"]
    if "owner_name" in body:
        biz["owner_name"] = body["owner_name"]
    if "owner_phone" in body:
        biz["owner_phone"] = body["owner_phone"]
    if "till_number" in body:
        biz["till_number"] = body["till_number"]

    db_client.put_business(biz)
    return biz



def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda entry point for API Gateway HTTP API."""
    try:
        # Determine HTTP Method
        method = event.get("httpMethod")
        if not method and "requestContext" in event:
            method = event["requestContext"].get("http", {}).get("method")
        method = (method or "GET").upper()

        # Handle CORS OPTIONS Preflight
        if method == "OPTIONS":
            return {
                "statusCode": 200,
                "headers": CORS_HEADERS,
                "body": json.dumps({"status": "ok"})
            }

        # Determine normalized path
        path = event.get("rawPath") or event.get("path") or "/"
        # Strip trailing slash if not root
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]

        # 1. Health check (No auth required)
        if path == "/health" and method == "GET":
            return _format_response({
                "statusCode": 200,
                "body": {
                    "status": "healthy",
                    "environment": os.getenv("ENVIRONMENT", "dev"),
                    "mock_aws": MOCK_MODE,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            })

        # Multi-tenant business ID resolution
        business_id = _extract_business_id(event)

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
                return _format_response({"statusCode": 200, "body": biz})

            elif method == "PUT":
                raw_body = event.get("body", "")
                if isinstance(raw_body, str):
                    try:
                        body = json.loads(raw_body) if raw_body else {}
                    except json.JSONDecodeError:
                        body = {}
                else:
                    body = raw_body or {}

                biz = db_client.get_business(business_id) or dict(DEFAULT_TEST_BUSINESS)
                biz["business_id"] = business_id
                if "shop_name" in body:
                    biz["shop_name"] = body["shop_name"]
                if "owner_name" in body:
                    biz["owner_name"] = body["owner_name"]
                if "owner_phone" in body:
                    biz["owner_phone"] = body["owner_phone"]
                if "till_number" in body:
                    biz["till_number"] = body["till_number"]

                db_client.put_business(biz)
                return _format_response({"statusCode": 200, "body": biz})

        # 3. Statement & Transaction Endpoints
        if path == "/statements/upload" and method == "POST":
            return _format_response(upload_statement(event, business_id))

        if path == "/statements/sms" and method == "POST":
            return _format_response(ingest_sms(event, business_id))

        if path == "/transactions" and method == "GET":
            return _format_response(list_transactions(event, business_id))

        # 4. Summary & Scoring Endpoints
        if path == "/summary/weekly" and method == "GET":
            return _format_response(get_weekly_summary(event, business_id))

        if path == "/score" and method == "GET":
            return _format_response(get_score(event, business_id))

        if path == "/score/calculate" and method == "POST":
            return _format_response(calculate_score(event, business_id))

        if path == "/reports/lender-pdf" and method == "GET":
            return _format_response(download_lender_pdf(event, business_id))

        # 5. Debt Engine ("Kitabu ya Deni") Endpoints
        if path == "/debts" and method == "POST":
            return _format_response(create_debt(event, business_id))

        if path == "/debts" and method == "GET":
            return _format_response(list_debts(event, business_id))

        # Match /debts/{debt_id}
        debt_match = re.match(r"^/debts/([^/]+)$", path)
        if debt_match and method == "PATCH":
            debt_id = debt_match.group(1)
            return _format_response(update_debt(event, business_id, debt_id))

        # 6. Notifications Endpoints
        if path == "/notifications/weekly-sms" and method == "POST":
            return _format_response(send_weekly_sms_notification(event, business_id))

        # 404 Fallback
        return _format_response(_build_error(
            status_code=404,
            code="RESOURCE_NOT_FOUND",
            message=f"Endpoint '{method} {path}' not found."
        ))

    except Exception as e:
        return _format_response(_build_error(
            status_code=500,
            code="INTERNAL_SERVER_ERROR",
            message=f"An unexpected server error occurred: {str(e)}"
        ))
