# Biashara Score — REST API Contract
**Version:** 1.1.0  
**Target Environment:** Local Mock Server (`http://localhost:8000`) & AWS API Gateway HTTP API  
**Default Frontend Origin:** `http://localhost:3000`  

---

## 1. Overview & General Standards

This document specifies the REST API contract between the Next.js 14 frontend and the Python backend for the Biashara Score MVP.

### 1.0 Implementation Status
| Component / Module | Status | Verification & Notes |
| :--- | :--- | :--- |
| **Pure Business Logic (`backend/src/core/`)** | **Working** | 100% pure Python (zero AWS/boto3 imports): CSV/SMS parser, rule categorizer, 4-pillar score engine, weekly summary, debt reconciliation, PDF generator. |
| **Local REST API Server (`backend/local_server.py`)** | **Working** | FastAPI server running on `http://localhost:8000` with full CORS for `http://localhost:3000`. |
| **AWS Lambda Handlers (`backend/src/handlers/`)** | **Working** | Handlers for API Gateway HTTP API v2 and EventBridge cron jobs. |
| **Infrastructure as Code (`infra/template.yaml`)** | **Working** | Complete AWS SAM template for DynamoDB, S3, Cognito, HTTP API, Lambda. |
| **Next.js 14 Frontend PWA (`frontend/`)** | **Not built yet** | Directory stubbed with `.gitkeep`; scheduled for frontend workstream. |
| **Live Cloud AWS Deployment** | **Not built yet** | Shared AWS account deployment via `sam deploy` scheduled for Phase 5 staging. |
| **Live Bedrock Haiku Fallback** | **Not built yet** (Mock working) | Operates in deterministic offline mock mode when `MOCK_AWS=true`. |
| **Live Africa's Talking Telco Dispatch** | **Not built yet** (Mock working) | Operates with sanitized mock logger when `MOCK_AWS=true`. |

### 1.1 Authentication & Multi-Tenancy Rules
Every protected endpoint enforces strict tenant isolation:

- **Production (AWS Cognito):**
  ```http
  Authorization: Bearer <cognito_jwt_id_token>
  ```
  In production, the backend extracts `business_id` exclusively from the verified Cognito token's `sub` claim (or custom tenant claim). **Any `X-Business-Id` header sent in production is strictly ignored and rejected.**

- **Local Development / Mock Mode (`MOCK_AWS=true`):**
  When running locally with `MOCK_AWS=true`, Cognito validation is bypassed. The backend accepts:
  ```http
  X-Business-Id: biz_test_duka_01
  ```
  If `X-Business-Id` is omitted when `MOCK_AWS=true`, the backend falls back to the default test business `biz_7a8b9c0d1e2f` (Mama Mary Provisions). `X-Business-Id` is declared as an optional Header parameter on every route so it shows in Swagger UI (`/docs`).

- **Public Endpoints (No Auth):**
  - `GET /health` requires no authorization header or tenant identifier.

- **Content & Response Type:**
  - Standard JSON payloads: `Content-Type: application/json`
  - Statement file upload: `multipart/form-data`
  - PDF report downloads: `application/pdf` or JSON containing presigned download URL

### 1.2 Standard Error Response Envelope
All error responses (HTTP status codes `400`, `401`, `403`, `404`, `500`) must strictly conform to this JSON schema:

```json
{
  "error": {
    "code": "INVALID_STATEMENT_FORMAT",
    "message": "The uploaded CSV file is missing required M-Pesa header columns.",
    "details": [
      {
        "field": "headers",
        "issue": "Missing 'Receipt No.' column"
      }
    ],
    "timestamp": "2026-11-12T16:00:00Z"
  }
}
```

#### Standard Error Codes:
- `UNAUTHORIZED`: Missing or invalid Bearer token / Business ID.
- `VALIDATION_ERROR`: Missing required body fields or illegal data types.
- `INVALID_STATEMENT_FORMAT`: CSV or SMS cannot be parsed.
- `RESOURCE_NOT_FOUND`: Specified `debt_id` or `business_id` does not exist.
- `NOT_IMPLEMENTED`: Endpoint stubbed while workstream is in progress (HTTP 501).
- `INTERNAL_SERVER_ERROR`: Unhandled exception in processing engine.

---

## 2. API Endpoints

### 2.0 System & Health

#### 2.0.1 Health Check (No Auth)
- **Method & Path:** `GET /health`
- **Description:** Verifies service availability, current mock mode status, and system time. No authentication required.
- **Headers:** None
- **Response (`200 OK`):**
  ```json
  {
    "status": "healthy",
    "environment": "dev",
    "mock_aws": true,
    "timestamp": "2026-11-12T16:00:00Z"
  }
  ```

---

### 2.1 Business Profile

#### 2.1.1 Get Business Profile
- **Method & Path:** `GET /business`
- **Description:** Retrieves the profile and contact details for the authenticated business.
- **Headers:**
  - `Authorization: Bearer <token>` (or `X-Business-Id: biz_...` if `MOCK_AWS=true`)
- **Response (`200 OK`):**
  ```json
  {
    "business_id": "biz_7a8b9c0d1e2f",
    "shop_name": "Mary's Family Provisions",
    "owner_name": "Mary Wambui",
    "owner_phone": "+254712345678",
    "till_number": "789123",
    "created_at": "2026-09-01T08:00:00Z"
  }
  ```

---

#### 2.1.2 Update Business Profile
- **Method & Path:** `PUT /business`
- **Description:** Updates the store name, owner name, or contact phone number.
- **Headers:**
  - `Authorization: Bearer <token>` (or `X-Business-Id: biz_...` if `MOCK_AWS=true`)
  - `Content-Type: application/json`
- **Request Body:**
  ```json
  {
    "shop_name": "Mama Mary Wholesale & Retail",
    "owner_name": "Mary Wambui Kamau",
    "owner_phone": "+254712345678",
    "till_number": "789123"
  }
  ```
- **Response (`200 OK`):**
  ```json
  {
    "business_id": "biz_7a8b9c0d1e2f",
    "shop_name": "Mama Mary Wholesale & Retail",
    "owner_name": "Mary Wambui Kamau",
    "owner_phone": "+254712345678",
    "till_number": "789123",
    "created_at": "2026-09-01T08:00:00Z"
  }
  ```

---

### 2.2 Statement & Transaction Ingestion

#### 2.2.1 Upload M-Pesa CSV Statement
- **Method & Path:** `POST /statements/upload`
- **Description:** Ingests a Safaricom M-Pesa CSV statement export. De-duplicates incoming transactions against existing records by `receipt_number`. Automatically runs categorization, checks for customer debt repayments, and saves newly imported records.
- **Headers:**
  - `Authorization: Bearer <token>` (or `X-Business-Id: biz_...` if `MOCK_AWS=true`)
  - `Content-Type: multipart/form-data`
- **Request Body (Multipart Form):**
  - `file`: CSV file (`text/csv` or `application/vnd.ms-excel`, up to 5MB)
- **Response (`200 OK`):**
  ```json
  {
    "status": "success",
    "business_id": "biz_7a8b9c0d1e2f",
    "statement_filename": "mpesa_statement_september.csv",
    "imported": 148,
    "skipped_duplicates": 2,
    "debts_auto_matched": 5,
    "categories_breakdown": {
      "SALES": 112,
      "INVENTORY": 18,
      "UTILITIES": 6,
      "RENT": 1,
      "DEBT_RECOVERY": 5,
      "OWNER_DRAW": 5,
      "AIRTIME": 3,
      "UNCATEGORIZED": 0
    },
    "date_range": {
      "start": "2026-09-01T12:49:00Z",
      "end": "2026-09-28T22:15:00Z"
    }
  }
  ```

---

#### 2.2.2 Quick-Entry M-Pesa SMS Ingestion
- **Method & Path:** `POST /statements/sms`
- **Description:** Ingests one or multiple pasted Safaricom SMS texts. De-duplicates by `receipt_number` against previously stored transactions, auto-matches customer debts, and returns standard ingestion metrics.
- **Headers:**
  - `Authorization: Bearer <token>` (or `X-Business-Id: biz_...` if `MOCK_AWS=true`)
  - `Content-Type: application/json`
- **Request Body:**
  ```json
  {
    "sms_text": "SK01YUUM7K Confirmed. You have received Ksh1,600.00 from John Otieno 254731829405 on 1/9/26 at 12:49 PM. New M-PESA balance is Ksh50,106.98. Transaction cost, Ksh0.00.\n\nSK067BQRKW Confirmed. You have received Ksh1,526.05 from Teacher Maina 254719283746 on 3/9/26 at 3:01 AM. Maina Duka Debt Settled. New M-PESA balance is Ksh41,691.42."
  }
  ```
- **Response (`201 Created`):**
  ```json
  {
    "status": "success",
    "business_id": "biz_7a8b9c0d1e2f",
    "imported": 1,
    "skipped_duplicates": 1,
    "debts_auto_matched": 1,
    "transactions": [
      {
        "receipt_number": "SK067BQRKW",
        "completion_time": "2026-09-03T03:01:00Z",
        "details": "Customer Transfer from 254719283746 - Teacher Maina (Maina Duka Debt Settled)",
        "amount": 1526.05,
        "direction": "IN",
        "running_balance": 41691.42,
        "status": "Completed",
        "category": "DEBT_RECOVERY",
        "counterparty": "Teacher Maina 254719283746",
        "categorization_method": "RULE_BASED",
        "debt_matched_id": "debt_001_maina"
      }
    ]
  }
  ```

---

#### 2.2.3 List Transactions
- **Method & Path:** `GET /transactions`
- **Description:** Returns paginated transactions for the active business, with optional filtering by category, date range, or direction.
- **Query Parameters:**
  - `limit` (integer, optional, default: `50`, max: `200`)
  - `category` (string, optional: `SALES`, `INVENTORY`, `UTILITIES`, `RENT`, `DEBT_RECOVERY`, `OWNER_DRAW`, `AIRTIME`, `UNCATEGORIZED`)
  - `direction` (string, optional: `IN`, `OUT`)
  - `start_date` (string, optional, ISO-8601: `2026-09-01T00:00:00Z`)
  - `end_date` (string, optional, ISO-8601: `2026-09-30T23:59:59Z`)
  - `cursor` (string, optional: pagination cursor)
- **Response (`200 OK`):**
  ```json
  {
    "business_id": "biz_7a8b9c0d1e2f",
    "total_count": 150,
    "next_cursor": "2026-09-20T10:15:00#SK88Z991",
    "transactions": [
      {
        "receipt_number": "SK01YUUM7K",
        "completion_time": "2026-09-01T12:49:00Z",
        "details": "Customer Payment to Till 789123 - John Otieno 254731829405",
        "amount": 1606.98,
        "direction": "IN",
        "running_balance": 50106.98,
        "status": "Completed",
        "category": "SALES",
        "counterparty": "John Otieno 254731829405",
        "categorization_method": "RULE_BASED",
        "debt_matched_id": null
      }
    ]
  }
  ```

---

### 2.3 Financial Intelligence & Weekly Summary

#### 2.3.1 Get Weekly Summary & Historical Series
- **Method & Path:** `GET /summary/weekly`
- **Description:** Returns the primary dashboard financial pulse: `current_week` represents the most recent single ISO week (Monday to Sunday, at most 7 active trading days) having transactions in the data, with its pulse message using that single week's figures. `history_series` returns the trailing `weeks` prior to `current_week`, ordered oldest to newest, with strictly zero overlap with `current_week`.
- **Query Parameters:**
  - `weeks` (integer, optional, default: `4`, min: `1`, max: `12`)
- **Response (`200 OK`):**
  ```json
  {
    "business_id": "biz_7a8b9c0d1e2f",
    "currency": "KSh",
    "current_week": {
      "week_label": "2026-W40",
      "start_date": "2026-09-28",
      "end_date": "2026-10-04",
      "gross_sales": 42917.44,
      "operating_expenses": 19995.0,
      "estimated_profit": 22922.44,
      "profit_margin_pct": 53.4,
      "active_trading_days": 6,
      "transaction_count": 30,
      "expense_breakdown": {
        "INVENTORY": 19595.0,
        "RENT": 0.0,
        "UTILITIES": 0.0,
        "AIRTIME": 400.0
      },
      "pulse_message": "You made KSh 42,917 this week, profit KSh 22,922."
    },
    "history_series": [
      {
        "week_label": "2026-W36",
        "gross_sales": 38450.0,
        "operating_expenses": 18379.42,
        "estimated_profit": 20070.58,
        "profit_margin_pct": 52.2
      },
      {
        "week_label": "2026-W37",
        "gross_sales": 32100.0,
        "operating_expenses": 12400.0,
        "estimated_profit": 19700.0,
        "profit_margin_pct": 61.4
      },
      {
        "week_label": "2026-W38",
        "gross_sales": 35400.0,
        "operating_expenses": 14900.0,
        "estimated_profit": 20500.0,
        "profit_margin_pct": 57.9
      },
      {
        "week_label": "2026-W39",
        "gross_sales": 34100.0,
        "operating_expenses": 15200.0,
        "estimated_profit": 18900.0,
        "profit_margin_pct": 55.4
      }
    ]
  }
  ```

---

### 2.4 Customer Debt Tracker ("Kitabu ya Deni")

#### 2.4.1 Create Customer Debt Record
- **Method & Path:** `POST /debts`
- **Description:** Adds a new credit entry to the digital Kitabu ya Deni.
- **Request Body:**
  ```json
  {
    "debtor_name": "Dennis Omondi (Mama Boi)",
    "debtor_phone": "+254728192837",
    "amount_owed": 2100.0,
    "items_summary": "2x Unga Pembe, 1x Cooking Oil 1L, Sugar 1kg",
    "due_date": "2026-09-16T18:00:00Z"
  }
  ```
- **Response (`201 Created`):**
  Matches `DebtRecord` in `models.py` exactly:
  ```json
  {
    "debt_id": "debt_9921a8_7b4c",
    "business_id": "biz_7a8b9c0d1e2f",
    "debtor_name": "Dennis Omondi (Mama Boi)",
    "debtor_phone": "+254728192837",
    "amount_owed": 2100.0,
    "amount_cleared": 0.0,
    "balance_remaining": 2100.0,
    "status": "UNPAID",
    "items_summary": "2x Unga Pembe, 1x Cooking Oil 1L, Sugar 1kg",
    "created_at": "2026-09-02T10:15:00Z",
    "due_date": "2026-09-16T18:00:00Z",
    "repayment_history": []
  }
  ```

---

#### 2.4.2 List Customer Debts
- **Method & Path:** `GET /debts`
- **Description:** Returns all debts for the store, with filtering and aggregate debt summary.
- **Query Parameters:**
  - `status` (string, optional: `UNPAID`, `PARTIAL`, `CLEARED`)
  - `search` (string, optional: name or phone substring)
- **Response (`200 OK`):**
  ```json
  {
    "business_id": "biz_7a8b9c0d1e2f",
    "summary": {
      "total_outstanding_amount": 3200.0,
      "total_cleared_amount": 4500.0,
      "recovery_rate_pct": 58.4,
      "unpaid_count": 3,
      "delinquent_count": 1
    },
    "debts": [
      {
        "debt_id": "debt_9921a8_7b4c",
        "business_id": "biz_7a8b9c0d1e2f",
        "debtor_name": "Dennis Omondi (Mama Boi)",
        "debtor_phone": "+254728192837",
        "amount_owed": 2100.0,
        "amount_cleared": 1000.0,
        "balance_remaining": 1100.0,
        "status": "PARTIAL",
        "items_summary": "2x Unga Pembe, 1x Cooking Oil 1L, Sugar 1kg",
        "created_at": "2026-09-02T10:15:00Z",
        "due_date": "2026-09-16T18:00:00Z",
        "repayment_history": [
          {
            "receipt_number": "SK067BQRKW",
            "amount": 1000.0,
            "date": "2026-09-10T14:20:00Z",
            "notes": "Matched inbound M-Pesa transfer"
          }
        ]
      }
    ]
  }
  ```

---

#### 2.4.3 Update Debt Record / Manual Payment Logging
- **Method & Path:** `PATCH /debts/{debt_id}`
- **Description:** Updates debt status or logs a manual cash repayment.
- **Path Parameters:**
  - `debt_id` (string, required)
- **Request Body:**
  ```json
  {
    "amount_to_clear": 1100.0,
    "receipt_number": "CASH_RECOVERY",
    "notes": "Paid in cash at shop counter"
  }
  ```
- **Response (`200 OK`):**
  ```json
  {
    "debt_id": "debt_9921a8_7b4c",
    "business_id": "biz_7a8b9c0d1e2f",
    "debtor_name": "Dennis Omondi (Mama Boi)",
    "debtor_phone": "+254728192837",
    "amount_owed": 2100.0,
    "amount_cleared": 2100.0,
    "balance_remaining": 0.0,
    "status": "CLEARED",
    "items_summary": "2x Unga Pembe, 1x Cooking Oil 1L, Sugar 1kg",
    "created_at": "2026-09-02T10:15:00Z",
    "due_date": "2026-09-16T18:00:00Z",
    "repayment_history": [
      {
        "receipt_number": "SK067BQRKW",
        "amount": 1000.0,
        "date": "2026-09-10T14:20:00Z",
        "notes": "Matched inbound M-Pesa transfer"
      },
      {
        "receipt_number": "CASH_RECOVERY",
        "amount": 1100.0,
        "date": "2026-09-15T11:00:00Z",
        "notes": "Paid in cash at shop counter"
      }
    ]
  }
  ```

---

### 2.5 Credit Scoring & Lender Reports

#### 2.5.1 Get Biashara Score
- **Method & Path:** `GET /score`
- **Description:** Returns the Biashara Credit Score (0–100), tier rating (`Gold`, `Silver`, `Bronze`, `Needs Improvement`), pillar breakdown, and actionable improvement tips. If the store has recorded no customer debts in Kitabu ya Deni, `debt_recovery_rate` returns `null` and the Debt Recovery pillar evaluates to the neutral score of 15 / 20.
- **Query Parameters:**
  - `recalculate` (boolean, optional, default: `false`)
- **Response (`200 OK`):**
  Matches `BiasharaScoreResult` in `models.py` exactly:
  ```json
  {
    "business_id": "biz_7a8b9c0d1e2f",
    "total_score": 78,
    "tier": "Silver",
    "consistency_score": 26,
    "growth_score": 19,
    "expense_ratio_score": 20,
    "debt_recovery_score": 13,
    "weekly_turnover_avg": 35087.5,
    "weekly_profit_avg": 9937.5,
    "debt_recovery_rate": 58.4,
    "computed_at": "2026-11-12T15:45:00Z",
    "actionable_tips": [
      "Follow up with 2 delinquent debtors who owe over KSh 2,000 for more than 14 days to boost your Debt Recovery pillar to Gold tier.",
      "Maintain active customer deposits on weekends to achieve full 30/30 marks on Cashflow Consistency."
    ]
  }
  ```

---

#### 2.5.2 Trigger On-Demand Score Recomputation
- **Method & Path:** `POST /score/calculate`
- **Description:** Forces full recalculation of the credit score based on all ingested transactions and debts.
- **Response (`200 OK`):**
  Returns identical schema as `GET /score` (`BiasharaScoreResult`).

---

#### 2.5.3 Download Lender-Ready PDF Financial Report
- **Method & Path:** `GET /reports/lender-pdf`
- **Description:** Generates and returns a downloadable, lender-formatted single-page business verification report.
- **Query Parameters:**
  - `format` (string, optional: `binary` | `url`, default: `binary`)
- **Response (when `format=binary`):**
  - **Status:** `200 OK`
  - **Headers:**
    - `Content-Type: application/pdf`
    - `Content-Disposition: attachment; filename="Biashara_Score_Report_Mama_Mary.pdf"`
  - **Body:** Binary PDF byte stream.

---

### 2.6 Africa's Talking SMS Dispatch

#### 2.6.1 Trigger Weekly SMS Digest
- **Method & Path:** `POST /notifications/weekly-sms`
- **Description:** Formats and sends the weekly summary SMS to the duka owner's registered phone number via Africa's Talking (or mock output).
- **Request Body (Optional overrides):**
  ```json
  {
    "override_phone": "+254712345678",
    "week_label": "2026-W36"
  }
  ```
- **Response (`200 OK`):**
  ```json
  {
    "status": "success",
    "business_id": "biz_7a8b9c0d1e2f",
    "recipient_phone": "+254712345678",
    "sms_text": "Habari Mary! Biashara Score Summary for W36: Sales KSh 38,450, Expenses KSh 26,800, Est. Profit KSh 11,650. Outstanding Debts: KSh 3,200. Score: 78/100 (Silver). Keep growing!",
    "provider_response": {
      "status": "success",
      "mode": "mock",
      "cost": "KSh 0.80"
    },
    "dispatched_at": "2026-11-12T16:00:00Z"
  }
  ```

---

## 3. Proposed Model Changes

> [!NOTE]
> The following models are proposed for addition to `backend/src/core/models.py`:

1. **Add `Business` Model:**
   ```python
   @dataclass
   class Business:
       business_id: str
       shop_name: str
       owner_name: str
       owner_phone: str
       till_number: Optional[str] = None
       created_at: str = ""
   ```

2. **Add `business_id` and `source` to `Transaction` Model:**
   ```python
   @dataclass
   class Transaction:
       receipt_number: str
       completion_time: str
       details: str
       amount: float
       direction: TransactionDirection
       running_balance: float
       status: str = "Completed"
       category: TransactionCategory = TransactionCategory.UNCATEGORIZED
       counterparty: Optional[str] = None
       categorization_method: str = "PENDING"
       debt_matched_id: Optional[str] = None
       business_id: Optional[str] = None  # Multi-tenant partition key
       source: str = "CSV_UPLOAD"         # "CSV_UPLOAD" | "SMS_PASTE"
   ```

3. **Add `WeeklySummary` Dataclass:**
   ```python
   @dataclass
   class WeeklySummary:
       business_id: str
       week_label: str             # e.g., "2026-W36"
       start_date: str             # "2026-09-01"
       end_date: str               # "2026-09-07"
       gross_sales: float          # Inbound sales transactions
       operating_expenses: float   # Inventory + Utilities + Rent + Airtime
       estimated_profit: float     # gross_sales - operating_expenses
       profit_margin_pct: float    # (estimated_profit / gross_sales) * 100
       active_trading_days: int    # Distinct calendar days with >= 1 sales tx
       transaction_count: int      # Total transactions
       expense_breakdown: Dict[str, float] = field(default_factory=dict)
       pulse_message: str = ""
   ```

4. **Add `RepaymentEntry` Dataclass:**
   ```python
   @dataclass
   class RepaymentEntry:
       receipt_number: str
       amount: float
       date: str
       notes: Optional[str] = None
   ```
