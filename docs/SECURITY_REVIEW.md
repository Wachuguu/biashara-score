# Biashara Score — Backend Security Review & Hardening Audit

**Audit Date:** 2026-11-12  
**Target:** Backend Handlers, FastAPI Local Server, Core Engines, and Infrastructure-as-Code (`infra/template.yaml`)  
**Scope:** Multi-tenancy isolation, secret exposure, authentication/authorization, input validation, DoS resilience, data privacy (PII in logs), CORS, and least-privilege cloud permissions.  
**Compliance Baseline:** Kenya Data Protection Act (2019), AWS Well-Architected Security Pillar, and Biashara REST API Contract v1.1.

---

## Executive Summary

A comprehensive security audit and remediation was conducted across the Biashara Score backend codebase. The review identified several high and medium severity vulnerabilities that could have compromised multi-tenant data isolation, enabled unauthenticated cross-tenant access in production, exposed shopkeeper PII in application logs, or allowed Denial-of-Service via unbounded file uploads.

All easy-to-fix vulnerabilities and architectural gaps have been remediated, verified, and locked in with automated regression tests in `backend/tests/test_security_review.py` (51 total tests passing).

---

## Findings Summary Matrix

| ID | Title | Severity | Status | Remediated In |
|---|---|---|---|---|
| **SEC-01** | Missing Cognito User Pool, Client & JWT Authorizer in Infrastructure Template | **High** | **FIXED** | `infra/template.yaml` |
| **SEC-02** | Unverified JWT Token Fallback & Ineffective `X-Business-Id` Production Rejection | **High** | **FIXED** | `src/handlers/api_handler.py`, `src/handlers/utils.py`, `local_server.py` |
| **SEC-03** | Wildcard CORS (`*`) in Production API Gateway and S3 Bucket | **Medium** | **FIXED** | `infra/template.yaml`, `src/handlers/api_handler.py`, `src/handlers/utils.py`, `local_server.py` |
| **SEC-04** | Unbounded File Uploads & Missing Type Validation on Statement Ingestion | **Medium** | **FIXED** | `src/handlers/statement_handler.py`, `local_server.py` |
| **SEC-05** | Plaintext PII (Customer Names, Phone Numbers) Logged to Stdout | **Medium** | **FIXED** | `src/wrappers/sms_client.py` |
| **SEC-06** | Missing Input Validation & Negative Repayment Logic on Endpoints | **Medium** | **FIXED** | `src/handlers/debt_handler.py`, `src/handlers/statement_handler.py`, `src/handlers/score_handler.py`, `src/handlers/api_handler.py` |
| **SEC-07** | Broad IAM Permissions & Missing Bedrock InvokeModel Permission | **Low** | **FIXED** | `infra/template.yaml` |
| **SEC-08** | S3 Statement Bucket Missing Public Access Block & Server-Side Encryption | **Low** | **FIXED** | `infra/template.yaml` |
| **SEC-09** | Secret & Credentials Git History Audit | **Informational** | **PASSED** | Repository git log & commit history |

---

## Detailed Findings & Remediations

### SEC-01: Missing Cognito User Pool, Client & JWT Authorizer in Infrastructure Template
- **Severity:** High
- **Risk:** Without a Cognito User Pool, User Pool Client, and JWT Authorizer configured on the API Gateway HTTP API (`BiasharaHttpApi`), deployed endpoints would either be completely open to the public or fail to authenticate requests in staging/production.
- **Remediation:**
  1. Added `AWS::Cognito::UserPool` (`CognitoUserPool`) configured with phone number authentication (`+254...`), password complexity policies, and custom attribute schema (`shop_name`, `business_id`).
  2. Added `AWS::Cognito::UserPoolClient` (`CognitoUserPoolClient`) with SRP auth flows and `PreventUserExistenceErrors: ENABLED`.
  3. Added `CognitoJwtAuthorizer` as the `DefaultAuthorizer` on `BiasharaHttpApi`, validating token issuer URL and audience client ID.
  4. Explicitly exempted `/health` route from authentication via `Auth: { Authorizer: NONE }`.

---

### SEC-02: Unverified JWT Token Fallback & Ineffective `X-Business-Id` Production Rejection
- **Severity:** High
- **Risk:**
  - In `utils.py`, tenant resolution previously attempted to extract tenant identity by slicing the unverified bearer token string (`f"biz_{token[:12]}"`), violating the rule against decoding tokens without signature verification.
  - In `api_handler.py`, if `MOCK_AWS=false` and a caller supplied `X-Business-Id`, the handler did not explicitly reject the request with `403 Forbidden`, and fell through to the default test business if authorizer claims were missing.
- **Remediation:**
  1. Updated `_extract_business_id` and `resolve_business_id`:
     - If `MOCK_AWS=false`: Any request containing `X-Business-Id` (case-insensitive) is immediately rejected with `403 FORBIDDEN`.
     - Tenant identity `business_id` is read **strictly** from verified API Gateway claims: `requestContext.authorizer.jwt.claims.sub`.
     - If `sub` is absent or unverified, the request is rejected with `401 UNAUTHORIZED`.
     - Slicing or decoding unverified bearer tokens has been removed.
     - Handlers never read `business_id` from the request body or custom headers in production.

---

### SEC-03: Wildcard CORS (`*`) in Production API Gateway and S3 Bucket
- **Severity:** Medium
- **Risk:** `AllowOrigins: ['*']` was configured in `BiasharaHttpApi` and `StatementsBucket`, as well as hardcoded in Lambda response headers (`Access-Control-Allow-Origin: *`). In production, this allows arbitrary malicious domains in a shopkeeper's browser to execute authenticated cross-origin requests.
- **Remediation:**
  1. Parameterized `CorsAllowedOrigin` in `infra/template.yaml` (default: `https://app.biasharascore.com`).
  2. Applied CloudFormation condition `IsProd`: in production, only the specific trusted frontend origin is allowed; in development, `http://localhost:3000` and `http://127.0.0.1:3000` are permitted.
  3. Updated `get_cors_headers` in backend utilities to dynamically reflect the authorized origin and never return `*` when `ENVIRONMENT=prod` or `MOCK_AWS=false`.
  4. Removed `X-Business-Id` from `Access-Control-Allow-Headers` in production environments.

---

### SEC-04: Unbounded File Uploads & Missing Type Validation on Statement Ingestion
- **Severity:** Medium
- **Risk:** `POST /statements/upload` accepted raw file bytes without checking content length or file extension. An attacker could transmit multi-gigabyte files or malicious non-CSV binaries, exhausting Lambda memory and triggering Denial-of-Service or high AWS compute charges.
- **Remediation:**
  1. Enforced `MAX_UPLOAD_BYTES = 5 * 1024 * 1024` (5 MB per API Contract Section 2.2.1). Uploads exceeding 5 MB are rejected with `413 PAYLOAD_TOO_LARGE`.
  2. Added file extension validation: statements must have a `.csv` extension; non-CSV files are rejected with `400 INVALID_STATEMENT_FORMAT`.
  3. Enforced payload size checks before string decoding in both base64-encoded Lambda events and FastAPI `local_server.py`.

---

### SEC-05: Plaintext PII (Customer Names, Phone Numbers) Logged to Stdout
- **Severity:** Medium
- **Risk:** `backend/src/wrappers/sms_client.py` printed unmasked Kenyan phone numbers and the full SMS message text containing the shopkeeper's name and business figures (`[LOCAL SMS MOCK to +254712345678]: Habari Mary! ...`). In AWS, stdout is ingested by Amazon CloudWatch Logs where personal data could be retained and exposed, violating the Kenya Data Protection Act 2019.
- **Remediation:**
  1. Implemented `mask_phone_number(phone: str) -> str` which masks phone numbers (e.g. `+254***78`).
  2. Replaced the log statement with a sanitized metadata-only message:
     `[LOCAL SMS MOCK to +254***78]: Dispatched financial digest notification (chars: N)`
  3. Verified that no customer names or full phone numbers are printed to standard output or logging streams.

---

### SEC-06: Missing Input Validation & Negative Repayment Logic on Endpoints
- **Severity:** Medium
- **Risk:**
  - `PATCH /debts/{debt_id}` did not reject negative `amount_to_clear`, which could allow malicious users or frontend bugs to arbitrarily inflate customer debts.
  - `PUT /business` did not validate phone number formats, till numbers, or string lengths, allowing malformed records in DynamoDB.
  - `GET /transactions` and `GET /summary/weekly` crashed with unhandled 500 `ValueError` when non-integer query parameters were passed.
  - `POST /statements/sms` had no character length limit, allowing unbounded text payloads.
- **Remediation:**
  1. `PATCH /debts/{debt_id}`: Enforced `amount_to_clear >= 0`; negative values return `400 VALIDATION_ERROR`.
  2. `PUT /business`: Added regex validation for Kenyan phone numbers (`^(\+?254\|0)?[17]\d{8}$`), till numbers (`^\d{4,10}$`), string length caps (<= 100), and rejection of unknown fields.
  3. `GET /transactions`: Validates `limit` as integer (1–200), `direction` in `[IN, OUT]`, and `category` against `TransactionCategory` enum.
  4. `GET /summary/weekly`: Validates `weeks` as integer (1–12).
  5. `POST /statements/sms`: Validates non-empty string and caps input length at 10,000 characters.
  6. `GET /reports/lender-pdf`: Validates `format` parameter (`binary` or `base64`).

---

### SEC-07: Broad IAM Permissions & Missing Bedrock InvokeModel Permission
- **Severity:** Low
- **Risk:**
  - `ApiFunction` used blanket `S3CrudPolicy`, granting excessive permissions including deleting the bucket and modifying bucket policies.
  - `ApiFunction` completely lacked IAM permissions to invoke Amazon Bedrock (`anthropic.claude-3-haiku-20240307-v1:0`), causing runtime `AccessDeniedException` when `MOCK_AWS=false` fell back to LLM categorization.
- **Remediation:**
  1. Replaced `S3CrudPolicy` with scoped least-privilege `s3:GetObject` and `s3:PutObject` on `${StatementsBucket.Arn}/*`.
  2. Scoped DynamoDB actions to `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem`, `dynamodb:Query`, `dynamodb:BatchWriteItem`.
  3. Added least-privilege Bedrock IAM statement: `bedrock:InvokeModel` scoped strictly to `arn:aws:bedrock:${AWS::Region}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0`.

---

### SEC-08: S3 Statement Bucket Missing Public Access Block & Server-Side Encryption
- **Severity:** Low
- **Risk:** `StatementsBucket` did not have `PublicAccessBlockConfiguration` or default encryption configured, increasing risk of inadvertent data exposure.
- **Remediation:**
  1. Added `PublicAccessBlockConfiguration` blocking public ACLs, policies, and bucket access.
  2. Enabled default server-side encryption with `SSEAlgorithm: AES256`.
  3. Enabled server-side encryption (`SSESpecification: SSEEnabled: true`) across all three DynamoDB tables.

---

### SEC-09: Secret & Credentials Git History Audit
- **Severity:** Informational
- **Audit Methodology:** Comprehensive regex search across entire git commit history (`git log -p`) covering all branches (`feat/backend-core`, `main`, etc.) scanning for AWS access keys (`AKIA...`), secret keys, private keys (`-----BEGIN PRIVATE KEY-----`), GitHub tokens (`ghp_...`), OpenAI keys (`sk-...`), and Africa's Talking API keys (`atsk_...`).
- **Result:** **PASSED**. No secrets, API keys, private keys, or actual `.env` files were ever committed to version control. Only `.env.example` exists in the repository, containing dummy placeholder values (`atsk_sandbox_your_api_key_here`, `mockClientId1234567890`). `.gitignore` properly excludes `.env`, `credentials`, `*.pem`, and `*.key`.

---

## Verification & Automated Test Coverage

A dedicated security verification suite was authored at `backend/tests/test_security_review.py`. All tests pass deterministically:

```bash
$ PYTHONPATH=. venv/bin/pytest backend/tests
============================= test session starts ==============================
collected 51 items

backend/tests/test_api_endpoints.py ............                         [ 23%]
backend/tests/test_debt_report_sms.py .........                          [ 41%]
backend/tests/test_local_workflow.py ....                                [ 49%]
backend/tests/test_parser_categorizer.py .......                         [ 62%]
backend/tests/test_score_summary.py .........                            [ 80%]
backend/tests/test_security_review.py ..........                         [100%]

======================== 51 passed, 1 warning in 1.01s =========================
```
