"""
Handler Utilities for AWS Lambda & API Gateway HTTP API v2
Provides shared response formatting, error envelope builders, and multi-tenant authentication extraction.
"""
import json
import os
import base64
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone

DEFAULT_TEST_BUSINESS_ID = "biz_7a8b9c0d1e2f"


def is_mock_mode() -> bool:
    """Returns True if running in local mock mode."""
    return os.getenv("MOCK_AWS", "true").lower() == "true"


def get_cors_headers(origin: Optional[str] = None) -> Dict[str, str]:
    """
    Returns secure CORS headers.
    In production (MOCK_AWS=false or ENVIRONMENT=prod), CORS is strictly restricted
    to configured domain (never wildcard '*').
    """
    mock = is_mock_mode()
    env = os.getenv("ENVIRONMENT", "dev").lower()
    configured_origin = os.getenv("CORS_ALLOWED_ORIGIN", "https://app.biasharascore.com")

    if mock or env == "dev":
        allowed = origin if origin in ["http://localhost:3000", "http://127.0.0.1:3000"] else "http://localhost:3000"
        allowed_headers = "Content-Type,Authorization,X-Business-Id"
    else:
        allowed = configured_origin
        allowed_headers = "Content-Type,Authorization"

    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": allowed,
        "Access-Control-Allow-Headers": allowed_headers,
        "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    }


def make_response(
    status_code: int,
    body: Any,
    headers: Optional[Dict[str, str]] = None,
    is_binary: bool = False,
    origin: Optional[str] = None
) -> Dict[str, Any]:
    """Builds standard API Gateway HTTP API proxy response."""
    res_headers = get_cors_headers(origin)
    if headers:
        res_headers.update(headers)

    if is_binary:
        return {
            "statusCode": status_code,
            "headers": res_headers,
            "body": base64.b64encode(body).decode("utf-8") if isinstance(body, bytes) else body,
            "isBase64Encoded": True
        }

    return {
        "statusCode": status_code,
        "headers": res_headers,
        "body": json.dumps(body) if not isinstance(body, str) else body
    }


def make_error_response(
    status_code: int,
    code: str,
    message: str,
    details: Optional[list] = None,
    origin: Optional[str] = None
) -> Dict[str, Any]:
    """Formats standard error envelope matching docs/API_CONTRACT.md section 1.2."""
    error_payload = {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }
    return make_response(status_code, error_payload, origin=origin)


def resolve_business_id(event_or_headers: Any) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Extracts business_id according to multi-tenancy rules:
    - In mock mode (MOCK_AWS=true): accepts X-Business-Id (falls back to default test duka).
    - In production mode (MOCK_AWS=false):
      1. Strictly rejects X-Business-Id header with 403 Forbidden.
      2. Reads business_id ONLY from verified authorizer claims:
         requestContext.authorizer.jwt.claims.sub.
      3. Never reads from request body or header, and never decodes tokens without signature verification.
    Returns (business_id, None) or (None, error_response).
    """
    mock_mode = is_mock_mode()

    if isinstance(event_or_headers, dict):
        if "requestContext" in event_or_headers or "rawPath" in event_or_headers or "httpMethod" in event_or_headers:
            event = event_or_headers
            raw_headers = event.get("headers") or {}
        else:
            event = {"headers": event_or_headers}
            raw_headers = event_or_headers
    else:
        event = {}
        raw_headers = {}

    headers = {str(k).lower(): str(v) for k, v in raw_headers.items()}
    x_biz_id = headers.get("x-business-id")
    origin = headers.get("origin")

    if not mock_mode:
        # 1. Strictly forbid X-Business-Id in production
        if x_biz_id:
            return None, make_error_response(
                403,
                "FORBIDDEN",
                "X-Business-Id header is forbidden when MOCK_AWS=false.",
                origin=origin
            )

        # 2. Extract verified business_id claim strictly from API Gateway authorizer context
        req_ctx = event.get("requestContext", {}) if isinstance(event.get("requestContext"), dict) else {}
        authorizer = req_ctx.get("authorizer", {}) if isinstance(req_ctx.get("authorizer"), dict) else {}
        jwt_claims = authorizer.get("jwt", {}).get("claims", {}) or authorizer.get("claims", {})
        sub_claim = jwt_claims.get("sub")

        if not sub_claim or not str(sub_claim).strip():
            return None, make_error_response(
                401,
                "UNAUTHORIZED",
                "Missing verified authorizer claims (requestContext.authorizer.jwt.claims.sub).",
                origin=origin
            )

        return str(sub_claim).strip(), None

    # Mock mode fallback
    if x_biz_id:
        return x_biz_id.strip(), None
    return DEFAULT_TEST_BUSINESS_ID, None


def parse_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """Extracts and parses JSON body from API Gateway event."""
    body = event.get("body", "{}")
    if not body:
        return {}
    if event.get("isBase64Encoded", False):
        try:
            body = base64.b64decode(body).decode("utf-8")
        except Exception:
            return {}
    if isinstance(body, str):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {}
    return body if isinstance(body, dict) else {}
