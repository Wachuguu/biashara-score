# Biashara Score — End-to-End QA & Contract Compliance Report

**Test Date:** 2026-11-12  
**Test Suite:** `backend/tests/test_e2e.py`  
**Execution Environment:** FastAPI `TestClient` (running `backend/local_server.py`), Python 3.14 venv  
**Specification Baseline:** `docs/API_CONTRACT.md` (v1.1.0) & `docs/BACKEND_TASKS.md`  

---

## 1. Executive Summary

A comprehensive end-to-end (E2E) quality assurance evaluation was performed against the Biashara Score backend API via `TestClient`. The evaluation tested:
1. **A Complete End-to-End User Journey:** Business profile update, initial M-Pesa CSV upload (150 rows), duplicate upload deduplication, manual debt creation in Kitabu ya Deni, matching repayment SMS ingestion with automatic reconciliation, weekly financial intelligence summary, 4-pillar credit scoring and tier classification, lender verification PDF generation, and Africa's Talking weekly SMS digest dispatch.
2. **Robust Bad Input & Negative Tests:** Empty statement files, non-CSV and binary files, wrong header columns, oversized payloads (>5MB limit), malformed phone numbers across endpoints, negative/zero debt amounts, and unauthenticated/missing `X-Business-Id` tenant isolation checks.
3. **API Contract & Schema Parity:** Exact field name parity against `docs/API_CONTRACT.md`, valid tier naming (`"Gold"`, `"Silver"`, `"Bronze"`, `"Needs Improvement"`), and standard error envelope structure (`{"error": {"code", "message", "details", "timestamp"}}`).

All **59 tests** across the backend test suite are **100% passing**.

---

## 2. Test Execution Summary

| Test Category | Description | Status | Pass / Total |
|---|---|:---:|:---:|
| **Full Journey (E2E)** | Full lifecycle from profile setup to statement upload, debt tracking, score, PDF, and SMS | **PASS** | 1 / 1 |
| **Empty File Upload** | 0-byte or empty string statement upload rejection | **PASS** | 1 / 1 |
| **Wrong Columns** | Non-M-Pesa CSV headers missing `Receipt No.` | **PASS** | 1 / 1 |
| **Non-CSV & Binary Files** | Rejection of `.pdf`, `.png`, and files with binary null bytes | **PASS** | 1 / 1 |
| **Oversized Uploads** | Statement uploads exceeding 5MB max payload limit | **PASS** | 1 / 1 |
| **Invalid Phone Numbers** | Malformed phone numbers on `/debts`, `/business`, `/notifications/weekly-sms` | **PASS** | 1 / 1 |
| **Negative & Zero Debt** | Non-positive `amount_owed` on POST and negative `amount_to_clear` on PATCH | **PASS** | 1 / 1 |
| **Missing Tenant Header** | Mock mode fallback to default business; production mode rejects X-Business-Id (403) and requires Bearer auth (401) | **PASS** | 1 / 1 |
| **Existing Suite Regression** | `test_api_endpoints.py`, `test_debt_report_sms.py`, `test_parser_categorizer.py`, etc. | **PASS** | 51 / 51 |
| **TOTAL** | | **PASS** | **59 / 59 (100%)** |

---

## 3. Discovered Bugs & Remediations Log

During initial test authoring and execution, several defects and contract divergences were identified and remediated with minimal edits:

### BUG-001: Missing M-Pesa Header Validation Allowed Wrong CSV Columns
- **Severity:** High
- **Endpoint:** `POST /statements/upload`
- **Root Cause:** When an uploaded CSV contained non-M-Pesa headers (e.g., `Item,Price,Quantity`), `parse_csv_statement` returned an empty list of transactions. The handler then proceeded to process 0 transactions and returned `HTTP 200 OK` with `{"imported": 0, "skipped_duplicates": 0}` instead of rejecting the file format.
- **Contract Reference:** `docs/API_CONTRACT.md` Section 1.2:
  ```json
  {
    "error": {
      "code": "INVALID_STATEMENT_FORMAT",
      "message": "The uploaded CSV file is missing required M-Pesa header columns.",
      "details": [{"field": "headers", "issue": "Missing 'Receipt No.' column"}],
      "timestamp": "..."
    }
  }
  ```
- **Remediation:** Added header inspection and transaction count validation in `execute_csv_upload` (`backend/src/handlers/statement_handler.py`). If the file lacks `Receipt No.` or yields no parseable transactions, it immediately returns `HTTP 400 INVALID_STATEMENT_FORMAT`.

---

### BUG-002: Inconsistent Error Envelope on FastAPI `HTTPException`
- **Severity:** Medium
- **Endpoint:** `PUT /business` and server-level exceptions
- **Root Cause:** Handlers raising `HTTPException(status_code=400, detail="Invalid Kenyan phone number.")` returned FastAPI's default response shape `{"detail": "..."}` rather than conforming to the standard error envelope `{"error": {"code": "...", "message": "...", "details": [], "timestamp": "..."}}`.
- **Contract Reference:** `docs/API_CONTRACT.md` Section 1.2 requires all 4xx/5xx responses to strictly follow the nested error envelope.
- **Remediation:**
  1. Updated `put_business` in `backend/local_server.py` to raise structured dict details or `JSONResponse`.
  2. Registered a global exception handler `@app.exception_handler(HTTPException)` in `backend/local_server.py` mapping any raw HTTPException to the standard error schema with appropriate error codes (`VALIDATION_ERROR`, `UNAUTHORIZED`, `RESOURCE_NOT_FOUND`, `FORBIDDEN`, etc.).

---

### BUG-003: Multi-Tenancy Mock Mode Fallback & Production Rejection Parity
- **Severity:** Medium
- **Endpoints:** All endpoints (`/health`, `/business`, `/statements/*`, `/transactions`, `/summary/*`, `/debts*`, `/score*`, `/reports/*`, `/notifications/*`)
- **Root Cause:** In mock mode (`MOCK_AWS=true`), requests without `X-Business-Id` returned `HTTP 401 UNAUTHORIZED`, diverging from `docs/API_CONTRACT.md` Section 1.1 which specifies falling back to default test business `biz_7a8b9c0d1e2f`. Furthermore, `X-Business-Id` was omitted as an optional header parameter on `/health` in FastAPI `/docs`.
- **Contract Reference:** `docs/API_CONTRACT.md` Section 1.1: *"If X-Business-Id is omitted when MOCK_AWS=true, the backend falls back to the default test business biz_7a8b9c0d1e2f (Mama Mary Provisions)."*
- **Remediation:**
  1. Updated `_get_tenant_business_id` in `backend/local_server.py` to fall back to `DEFAULT_TEST_BUSINESS_ID` (`biz_7a8b9c0d1e2f`) when `X-Business-Id` is omitted in mock mode (`MOCK_AWS=true`).
  2. Maintained strict production security (`MOCK_AWS=false`): `X-Business-Id` is rejected with `HTTP 403 FORBIDDEN` and requests without verified claims return `HTTP 401 UNAUTHORIZED`.
  3. Declared `X-Business-Id` as an optional `Header` parameter across every route (including `/health`) so it displays as an input field in OpenAPI `/docs`.

---

### BUG-004: Missing Negative Amount Validation on `PATCH /debts/{debt_id}`
- **Severity:** Medium
- **Endpoint:** `PATCH /debts/{debt_id}`
- **Root Cause:** If a client sent a negative `amount_to_clear` (e.g. `-300.0`), the handler checked `if amount_to_clear > 0:` and skipped applying the repayment, returning `HTTP 200 OK` without error.
- **Contract Reference:** `docs/API_CONTRACT.md` Section 1.2 (`VALIDATION_ERROR`).
- **Remediation:** Added explicit validation in `execute_update_debt` (`backend/src/handlers/debt_handler.py`) returning `HTTP 400 VALIDATION_ERROR` with message `"Field 'amount_to_clear' must be a non-negative number."`.

---

## 4. Contract Shape & Tier Parity Verification

Every endpoint's response shape was validated against `docs/API_CONTRACT.md`:

| Endpoint | Method | Expected Fields Verified | Tier / Value Checks |
|---|---|---|---|
| `/business` | `PUT` | `business_id`, `shop_name`, `owner_name`, `owner_phone`, `till_number`, `created_at` | Matches updated attributes |
| `/statements/upload` | `POST` | `status`, `business_id`, `statement_filename`, `imported`, `skipped_duplicates`, `debts_auto_matched`, `categories_breakdown`, `date_range` | All 8 categories present; second upload skips 100% of duplicates (150/150) |
| `/statements/sms` | `POST` | `status`, `business_id`, `imported`, `skipped_duplicates`, `debts_auto_matched`, `transactions` | Auto-reconciled debt ID set; category set to `DEBT_RECOVERY` |
| `/debts` | `POST` | `debt_id`, `business_id`, `debtor_name`, `debtor_phone`, `amount_owed`, `amount_cleared`, `balance_remaining`, `status`, `items_summary`, `created_at`, `due_date`, `repayment_history` | Status starts `UNPAID`, balance equals `amount_owed` |
| `/debts` | `GET` | `business_id`, `summary` (`total_outstanding_amount`, `total_cleared_amount`, `recovery_rate_pct`, `unpaid_count`, `delinquent_count`), `debts` | Verified debt transition to `CLEARED` |
| `/summary/weekly` | `GET` | `business_id`, `currency`, `current_week` (`week_label`, `start_date`, `end_date`, `gross_sales`, `operating_expenses`, `estimated_profit`, `profit_margin_pct`, `active_trading_days`, `transaction_count`, `expense_breakdown`, `pulse_message`), `history_series` | `currency == "KSh"`, positive sales and expenses |
| `/score` | `GET` / `POST` | `business_id`, `total_score`, `tier`, `consistency_score`, `growth_score`, `expense_ratio_score`, `debt_recovery_score`, `weekly_turnover_avg`, `weekly_profit_avg`, `debt_recovery_rate`, `computed_at`, `actionable_tips` | `tier` strictly in `["Gold", "Silver", "Bronze", "Needs Improvement"]`; total matches sum of 4 pillars; `tips >= 2` |
| `/reports/lender-pdf` | `GET` | Binary stream starting with `b"%PDF-"`, `Content-Type: application/pdf`, `Content-Disposition: attachment; filename=...` | Size > 3,000 bytes (ReportLab / vector engine) |
| `/notifications/weekly-sms` | `POST` | `status`, `business_id`, `recipient_phone`, `sms_text`, `provider_response`, `dispatched_at` | SMS text contains `"Habari"` and comma-formatted KSh values; mock mode confirmed |

---

## 5. Summary of System Status

### What Works Completely (100% Verified):
- **Full Ingestion Lifecycle:** M-Pesa CSV parsing (150 rows), deduplication by `receipt_number`, SMS ingestion, and auto-matching inbound payments to debtor records.
- **Credit Scoring & Tier Engine:** 4-pillar calculation (Consistency, Growth, Margin, Debt Discipline) strictly adhering to 0–100 range and standardized credit tier names (`Gold`, `Silver`, `Bronze`, `Needs Improvement`).
- **Kitabu ya Deni:** Debt creation, phone normalization (`+254...`), repayment logging, partial/cleared status transitions, and aggregate metrics.
- **Reporting & Notifications:** A4 lender verification PDF generation (both ReportLab and fallback pure vector engine) and Africa's Talking weekly SMS digest formatting.
- **Negative Input & Tenant Security:** Rejection of empty, non-CSV, binary, and oversized files, invalid phone formats, negative debt amounts, and unauthenticated tenant calls.
- **Test Automation:** 59 automated pytest unit, integration, security, and E2E tests passing offline with `MOCK_AWS=true`.

### What Is Partial / Pending Deployment:
- **Production Cognito JWT Claims:** Local testing runs in mock mode (`MOCK_AWS=true`) using `X-Business-Id`. True production validation requires deployed API Gateway JWT Authorizer with live Cognito User Pool tokens (configured in `infra/template.yaml`).
- **Live Africa's Talking SMS Dispatch:** Local test suite verifies mock mode dispatch (prints to stdout with simulated success response). Live SMS requires provisioning Africa's Talking API key and shortcode in production environment variables.
