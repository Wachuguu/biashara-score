"""
Biashara Score — Local FastAPI Mock Server
Provides full REST API local testing with CORS enabled for Next.js (http://localhost:3000).
Adheres strictly to docs/API_CONTRACT.md.
"""
import os
import base64
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from fastapi import (
    FastAPI,
    Request,
    Response,
    Header,
    Query,
    Path,
    UploadFile,
    File,
    HTTPException,
    status
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.wrappers.db_client import (
    db_client,
    DEFAULT_TEST_BUSINESS,
    DEFAULT_TEST_BUSINESS_ID,
    MOCK_MODE
)
from src.handlers.statement_handler import (
    execute_csv_upload,
    execute_sms_ingestion,
    execute_list_transactions
)
from src.handlers.debt_handler import (
    execute_create_debt,
    execute_list_debts,
    execute_update_debt
)
from src.handlers.score_handler import (
    execute_weekly_summary,
    execute_score,
    execute_lender_pdf
)
from src.handlers.cron_handler import execute_weekly_sms_notification

app = FastAPI(
    title="Biashara Score Local API",
    version="1.1.0",
    description="Local development and test server matching AWS API Gateway HTTP API contract."
)

# Configure CORS for Next.js local frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_tenant_business_id(
    authorization: Optional[str] = Header(None),
    x_business_id: Optional[str] = Header(None)
) -> str:
    """
    Enforces multi-tenancy rules from API_CONTRACT.md Section 1.1:
    - In Mock Mode (MOCK_AWS=true): accepts X-Business-Id; falls back to default test duka if omitted.
    - In Production Mode (MOCK_AWS=false): X-Business-Id is strictly forbidden (rejected).
      Requires Bearer token.
    """
    is_mock = os.getenv("MOCK_AWS", "true").lower() == "true"

    if is_mock:
        return x_business_id or DEFAULT_TEST_BUSINESS_ID

    # Production Mode validation
    if x_business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "X-Business-Id header is forbidden in production.",
                    "details": [],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Missing or invalid Authorization Bearer token.",
                    "details": [],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        )

    token = authorization.split("Bearer ", 1)[1].strip()
    return f"biz_{token[:12]}"


def _unwrap_result(res: Dict[str, Any]) -> Response:
    status_code = res.get("statusCode", 200)
    body = res.get("body", {})
    headers = res.get("headers", {})

    if res.get("isBase64Encoded"):
        data = base64.b64decode(body)
        media_type = headers.get("Content-Type", "application/pdf")
        return Response(content=data, status_code=status_code, media_type=media_type, headers=headers)

    return JSONResponse(content=body, status_code=status_code, headers=headers)


# ============================================================================
# 2.0 System & Health
# ============================================================================
@app.get("/health", tags=["System"])
def get_health():
    """System health check (Public, no auth required)."""
    return {
        "status": "healthy",
        "environment": os.getenv("ENVIRONMENT", "dev"),
        "mock_aws": os.getenv("MOCK_AWS", "true").lower() == "true",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ============================================================================
# 2.1 Business Profile
# ============================================================================
@app.get("/business", tags=["Business"])
def get_business(
    authorization: Optional[str] = Header(None),
    x_business_id: Optional[str] = Header(None)
):
    """Retrieves business profile for authenticated tenant."""
    biz_id = _get_tenant_business_id(authorization, x_business_id)
    biz = db_client.get_business(biz_id) or {
        "business_id": biz_id,
        "shop_name": "Mary's Family Provisions",
        "owner_name": "Mary Wambui",
        "owner_phone": "+254712345678",
        "till_number": "789123",
        "created_at": "2026-09-01T08:00:00Z"
    }
    return JSONResponse(content=biz, status_code=200)


@app.put("/business", tags=["Business"])
async def put_business(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_business_id: Optional[str] = Header(None)
):
    """Updates store profile details."""
    biz_id = _get_tenant_business_id(authorization, x_business_id)
    body = await request.json()

    biz = db_client.get_business(biz_id) or dict(DEFAULT_TEST_BUSINESS)
    biz["business_id"] = biz_id
    for key in ["shop_name", "owner_name", "owner_phone", "till_number"]:
        if key in body:
            biz[key] = body[key]

    db_client.put_business(biz)
    return JSONResponse(content=biz, status_code=200)


# ============================================================================
# 2.2 Statement & Transaction Ingestion
# ============================================================================
@app.post("/statements/upload", tags=["Ingestion"])
async def upload_statement(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
    x_business_id: Optional[str] = Header(None)
):
    """Uploads and ingests Safaricom M-Pesa CSV statement."""
    biz_id = _get_tenant_business_id(authorization, x_business_id)
    content_bytes = await file.read()
    try:
        content_str = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        content_str = content_bytes.decode("latin-1")

    filename = file.filename or "statement.csv"
    res = execute_csv_upload(biz_id, content_str, filename=filename)
    return _unwrap_result(res)


@app.post("/statements/sms", status_code=201, tags=["Ingestion"])
async def paste_sms(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_business_id: Optional[str] = Header(None)
):
    """Ingests one or multiple pasted Safaricom SMS texts."""
    biz_id = _get_tenant_business_id(authorization, x_business_id)
    body = await request.json()
    sms_text = body.get("sms_text", "")
    res = execute_sms_ingestion(biz_id, sms_text)
    return _unwrap_result(res)


@app.get("/transactions", tags=["Ingestion"])
def list_transactions(
    limit: int = Query(50, ge=1, le=200),
    category: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    cursor: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    x_business_id: Optional[str] = Header(None)
):
    """Lists transactions with filtering and pagination."""
    biz_id = _get_tenant_business_id(authorization, x_business_id)
    qp = {
        "limit": limit,
        "category": category,
        "direction": direction,
        "start_date": start_date,
        "end_date": end_date,
        "cursor": cursor
    }
    res = execute_list_transactions(biz_id, qp)
    return _unwrap_result(res)


# ============================================================================
# 2.3 Financial Intelligence & Weekly Summary
# ============================================================================
@app.get("/summary/weekly", tags=["Intelligence"])
def get_weekly_summary(
    weeks: int = Query(4, ge=1, le=12),
    authorization: Optional[str] = Header(None),
    x_business_id: Optional[str] = Header(None)
):
    """Returns primary dashboard financial pulse and trailing multi-week series."""
    biz_id = _get_tenant_business_id(authorization, x_business_id)
    res = execute_weekly_summary(biz_id, {"weeks": weeks})
    return _unwrap_result(res)


# ============================================================================
# 2.4 Customer Debt Tracker ("Kitabu ya Deni")
# ============================================================================
@app.post("/debts", status_code=201, tags=["Debts"])
async def create_debt(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_business_id: Optional[str] = Header(None)
):
    """Adds a new credit entry to Kitabu ya Deni."""
    biz_id = _get_tenant_business_id(authorization, x_business_id)
    body = await request.json()
    res = execute_create_debt(biz_id, body)
    return _unwrap_result(res)


@app.get("/debts", tags=["Debts"])
def list_debts(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    x_business_id: Optional[str] = Header(None)
):
    """Lists customer debts and aggregate recovery metrics."""
    biz_id = _get_tenant_business_id(authorization, x_business_id)
    qp = {"status": status, "search": search}
    res = execute_list_debts(biz_id, qp)
    return _unwrap_result(res)


@app.patch("/debts/{debt_id}", tags=["Debts"])
async def update_debt(
    debt_id: str = Path(...),
    request: Request = None,
    authorization: Optional[str] = Header(None),
    x_business_id: Optional[str] = Header(None)
):
    """Updates customer debt status or logs a repayment."""
    biz_id = _get_tenant_business_id(authorization, x_business_id)
    body = await request.json()
    res = execute_update_debt(biz_id, debt_id, body)
    return _unwrap_result(res)


# ============================================================================
# 2.5 Credit Scoring & Lender Reports
# ============================================================================
@app.get("/score", tags=["Scoring"])
def get_score(
    recalculate: bool = Query(False),
    authorization: Optional[str] = Header(None),
    x_business_id: Optional[str] = Header(None)
):
    """Retrieves current Biashara Credit Score (0–100) and actionable tips."""
    biz_id = _get_tenant_business_id(authorization, x_business_id)
    res = execute_score(biz_id)
    return _unwrap_result(res)


@app.post("/score/calculate", tags=["Scoring"])
def post_score_calculate(
    authorization: Optional[str] = Header(None),
    x_business_id: Optional[str] = Header(None)
):
    """Forces recalculation of the credit score."""
    biz_id = _get_tenant_business_id(authorization, x_business_id)
    res = execute_score(biz_id)
    return _unwrap_result(res)


@app.get("/reports/lender-pdf", tags=["Reports"])
def get_lender_pdf(
    format: str = Query("binary"),
    authorization: Optional[str] = Header(None),
    x_business_id: Optional[str] = Header(None)
):
    """Downloads single-page A4 lender verification PDF report."""
    biz_id = _get_tenant_business_id(authorization, x_business_id)
    res = execute_lender_pdf(biz_id, {"format": format})
    return _unwrap_result(res)


# ============================================================================
# 2.6 Africa's Talking SMS Dispatch
# ============================================================================
@app.post("/notifications/weekly-sms", tags=["Notifications"])
async def send_weekly_sms(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_business_id: Optional[str] = Header(None)
):
    """Dispatches weekly summary SMS to store owner."""
    biz_id = _get_tenant_business_id(authorization, x_business_id)
    body = await request.json() if (await request.body()) else {}
    override_phone = body.get("override_phone", "")
    week_label = body.get("week_label", "")
    res = execute_weekly_sms_notification(biz_id, override_phone, week_label)
    return _unwrap_result(res)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("local_server:app", host="0.0.0.0", port=8000, reload=True)
