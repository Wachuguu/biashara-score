"""
Authentication & Shop Account Handler
Provides salted PBKDF2-HMAC-SHA256 password hashing, timing-safe verification,
and signed session tokens for cross-device shop login and registration.
Zero external dependencies (Python stdlib hashlib + hmac + os.urandom).
"""
import os
import re
import hmac
import json
import time
import uuid
import base64
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from src.core.debt_engine import normalize_phone_number
from src.wrappers.db_client import db_client

PBKDF2_ITERATIONS = 100_000
PHONE_REGEX = re.compile(r"^(\+?254|0)?[17]\d{8}$")
TILL_REGEX = re.compile(r"^\d{4,10}$")


def _get_auth_secret() -> bytes:
    return os.getenv("AUTH_SECRET", "biashara-dev-hmac-secret-key-change-in-prod").encode("utf-8")


def hash_password(password: str) -> str:
    """Hashes a plaintext password with a 16-byte random salt using PBKDF2-HMAC-SHA256."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored_hash: Optional[str]) -> bool:
    """Verifies a plaintext password against a stored PBKDF2 hash in constant time."""
    if not stored_hash or not password:
        return False
    try:
        parts = stored_hash.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected_dk = bytes.fromhex(parts[3])
        actual_dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual_dk, expected_dk)
    except Exception:
        return False


def create_session_token(business_id: str, ttl_seconds: int = 86400 * 7) -> str:
    """Generates a signed HMAC-SHA256 session token."""
    payload = {"sub": business_id, "exp": int(time.time()) + ttl_seconds}
    b64_payload = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
    sig = hmac.new(_get_auth_secret(), b64_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{b64_payload}.{sig}"


def _sanitize_business(biz: Dict[str, Any]) -> Dict[str, Any]:
    """Removes sensitive fields (password_hash) before returning business JSON."""
    return {k: v for k, v in biz.items() if k != "password_hash"}


def _err(status_code: int, code: str, message: str) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "body": {
            "error": {
                "code": code,
                "message": message,
                "details": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        },
    }


def execute_register(body: Dict[str, Any]) -> Dict[str, Any]:
    """Registers a new shop account with salted PBKDF2 password hashing."""
    if not isinstance(body, dict):
        return _err(400, "VALIDATION_ERROR", "Request body must be a JSON object.")

    shop_name = str(body.get("shop_name", "")).strip()
    owner_name = str(body.get("owner_name", "")).strip()
    raw_phone = str(body.get("owner_phone", "")).strip()
    password = str(body.get("password", ""))
    till_raw = body.get("till_number")
    till_number = str(till_raw).strip() if till_raw else None

    if not shop_name or len(shop_name) > 100:
        return _err(400, "VALIDATION_ERROR", "Shop name is required (1 to 100 characters).")
    if not owner_name or len(owner_name) > 100:
        return _err(400, "VALIDATION_ERROR", "Your name is required (1 to 100 characters).")
    if not PHONE_REGEX.match(raw_phone.replace(" ", "").replace("-", "")):
        return _err(400, "VALIDATION_ERROR", "Enter a valid Kenyan phone number (e.g. 0712 345 678).")
    if len(password) < 6:
        return _err(400, "VALIDATION_ERROR", "Password must be at least 6 characters.")
    if till_number and not TILL_REGEX.match(till_number):
        return _err(400, "VALIDATION_ERROR", "Till number must be 4 to 10 digits.")

    norm_phone = normalize_phone_number(raw_phone)
    existing = db_client.get_business_by_phone(norm_phone)
    if existing and existing.get("password_hash"):
        return _err(409, "ACCOUNT_EXISTS", "An account with this phone number already exists. Sign in instead.")

    biz_id = f"biz_{uuid.uuid4().hex[:12]}"
    biz_record: Dict[str, Any] = {
        "business_id": biz_id,
        "shop_name": shop_name,
        "owner_name": owner_name,
        "owner_phone": norm_phone,
        "password_hash": hash_password(password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if till_number:
        biz_record["till_number"] = till_number

    db_client.put_business(biz_record)
    token = create_session_token(biz_id)
    return {
        "statusCode": 201,
        "body": {
            "token": token,
            "business": _sanitize_business(biz_record),
        },
    }


def execute_login(body: Dict[str, Any]) -> Dict[str, Any]:
    """Authenticates a shopkeeper by phone number and salted PBKDF2 password."""
    if not isinstance(body, dict):
        return _err(400, "VALIDATION_ERROR", "Request body must be a JSON object.")

    raw_phone = str(body.get("owner_phone", "")).strip()
    password = str(body.get("password", ""))
    if not raw_phone or not password:
        return _err(400, "VALIDATION_ERROR", "Phone number and password are required.")

    norm_phone = normalize_phone_number(raw_phone)
    biz = db_client.get_business_by_phone(norm_phone)
    if not biz or not verify_password(password, biz.get("password_hash")):
        return _err(401, "INVALID_CREDENTIALS", "Incorrect phone number or password.")

    token = create_session_token(biz["business_id"])
    return {
        "statusCode": 200,
        "body": {
            "token": token,
            "business": _sanitize_business(biz),
        },
    }
