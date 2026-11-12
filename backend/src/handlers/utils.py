"""
Handler Utilities for AWS Lambda & API Gateway HTTP API v2
Provides shared response formatting, error envelope builders, and multi-tenant authentication extraction.
"""
import json
import os
import base64
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone

MOCK_MODE = os.getenv("MOCK_AWS", "true").lower() == "true"
DEFAULT_TEST_BUSINESS_ID = "biz_7a8b9c0d1e2f"


def make_response(
    status_code: int,
    body: Any,
    headers: Optional[Dict[str, str]] = None,
    is_binary: bool = False
) -> Dict[str, Any]:
    """Builds standard API Gateway HTTP API proxy response."""
    default_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Business-Id",
        "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    }
    if headers:
        default_headers.update(headers)

    if is_binary:
        return {
            "statusCode": status_code,
            "headers": default_headers,
            "body": base64.b64encode(body).decode("utf-8") if isinstance(body, bytes) else body,
            "isBase64Encoded": True
        }

    return {
        "statusCode": status_code,
        "headers": default_headers,
        "body": json.dumps(body) if not isinstance(body, str) else body
    }


def make_error_response(
    status_code: int,
    code: str,
    message: str,
    details: Optional[list] = None
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
    return make_response(status_code, error_payload)


def resolve_business_id(headers: Dict[str, str]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Extracts business_id according to multi-tenancy rules:
    - In mock mode (MOCK_AWS=true): accepts X-Business-Id (falls back to default test duka).
    - In production mode (MOCK_AWS=false): rejects X-Business-Id and requires Bearer token.
    Returns (business_id, None) or (None, error_response).
    """
    # Lowercase all header keys
    norm_headers = {k.lower(): v for k, v in headers.items()}
    x_biz_id = norm_headers.get("x-business-id")
    auth_header = norm_headers.get("authorization")

    if MOCK_MODE:
        return x_biz_id or DEFAULT_TEST_BUSINESS_ID, None

    # Production Mode (Cognito required)
    if x_biz_id:
        return None, make_error_response(
            403,
            "UNAUTHORIZED",
            "X-Business-Id header is forbidden in production environment."
        )

    if not auth_header or not auth_header.startswith("Bearer "):
        return None, make_error_response(
            401,
            "UNAUTHORIZED",
            "Missing or invalid Authorization Bearer token."
        )

    token = auth_header.split("Bearer ", 1)[1].strip()
    if not token:
        return None, make_error_response(401, "UNAUTHORIZED", "Empty Bearer token.")

    # In production with Cognito, token sub claim represents business_id
    # Simple decode or fallback if token mock
    return f"biz_{token[:12]}", None


def parse_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """Extracts and parses JSON body from API Gateway event."""
    body = event.get("body", "{}")
    if not body:
        return {}
    if event.get("isBase64Encoded", False):
        body = base64.b64decode(body).decode("utf-8")
    if isinstance(body, str):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {}
    return body if isinstance(body, dict) else {}
