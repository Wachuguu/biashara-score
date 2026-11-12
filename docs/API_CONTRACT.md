# Biashara Score — REST API Contract
**Version:** 1.0.0  
**Target Environment:** Local Mock Server (`http://localhost:8000`) & AWS API Gateway HTTP API  
**Default Frontend Origin:** `http://localhost:3000`  

---

## 1. Overview & General Standards

This document specifies the REST API contract between the Next.js 14 frontend and the Python backend for the Biashara Score MVP.

### 1.1 Authentication & Multi-Tenancy Headers
Every request to protected endpoints must provide authentication and tenant identification:

- **Production (AWS Cognito):**
  ```http
  Authorization: Bearer <cognito_jwt_id_token>
  ```
  The Lambda authorizer / handler extracts `business_id` (and user identity) from token claims (`custom:business_id` or Cognito `sub`).

- **Local Development / Mock Mode (`MOCK_AWS=true`):**
  If `Authorization` is absent or local bypass is active, the backend inspects:
  ```http
  X-Business-Id: biz_test_duka_01
  ```
  If omitted in local mock mode, the backend defaults to `biz_7a8b9c0d1e2f` (Mama Mary Provisions).

- **Content & Response Type:**
  - Standard payloads: `Content-Type: application/json`
  - Statement file upload: `multipart/form-data`
  - PDF downloads: `application/pdf` or JSON containing presigned download URL

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
    "timestamp": "2026-11-12T15:50:00Z"
  }
}
```

#### Standard Error Codes:
- `UNAUTHORIZED`: Missing or invalid Bearer token / Business ID.
- `VALIDATION_ERROR`: Missing required body fields or illegal data types.
- `INVALID_STATEMENT_FORMAT`: CSV or SMS cannot be parsed.
- `RESOURCE_NOT_FOUND`: Specified `debt_id` or `business_id` does not exist.
- `INTERNAL_SERVER_ERROR`: Unhandled exception in processing engine.

---

## 2. API Endpoints

### 2.1 Statement & Transaction Ingestion

#### 2.1.1 Upload M-Pesa CSV Statement
- **Method & Path:** `POST /statements/upload`
- **Description:** Accepts a standard Safaricom M-Pesa CSV statement export, parses all transactions, categorizes them using the rule engine (with LLM fallback for ambiguous rows), reconciles open debts, stores them in the transactions table, and recomputes the business summary.
- **Headers:**
  - `Authorization: Bearer <token>`
  - `Content-Type: multipart/form-data`
- **Request Body (Multipart Form):**
  - `file`: Binary CSV file (`text/csv` or `application/vnd.ms-excel`, up to 5MB)
- **Response (`200 OK`):**
  ```json
  {
    "status": "success",
    "business_id": "biz_7a8b9c0d1e2f",
    "statement_filename": "mpesa_statement_september.csv",
    "total_rows_parsed": 150,
    "inserted_count": 148,
    "duplicate_count": 2,
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
    "debts_reconciled_count": 5,
    "date_range": {
      "start": "2026-09-01T12:49:00Z",
      "end": "2026-09-28T22:15:00Z"
    }
  }
  ```

---

#### 2.1.2 Quick-Entry M-Pesa SMS Ingestion
- **Method & Path:** `POST /statements/sms`
- **Description:** Ingests one or more pasted raw Safaricom M-Pesa SMS strings, extracts transaction details, classifies them, checks for debt settlements, and writes them to the database.
- **Headers:**
  - `Authorization: Bearer <token>`
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
    "parsed_count": 2,
    "transactions": [
      {
        "receipt_number": "SK01YUUM7K",
        "completion_time": "2026-09-01T12:49:00Z",
        "details": "Customer Payment to Till 789123 - John Otieno 254731829405",
        "amount": 1600.0,
        "direction": "IN",
        "running_balance": 50106.98,
        "status": "Completed",
        "category": "SALES",
        "counterparty": "John Otieno 254731829405",
        "categorization_method": "RULE_BASED",
        "debt_matched_id": null
      },
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

#### 2.1.3 List Transactions
- **Method & Path:** `GET /transactions`
- **Description:** Returns paginated transactions for the active business, with optional filtering by category, date range, or search term.
- **Query Parameters:**
  - `limit` (integer, optional, default: `50`, max: `200`)
  - `category` (string, optional: `SALES`, `INVENTORY`, `UTILITIES`, `RENT`, `DEBT_RECOVERY`, `OWNER_DRAW`, `AIRTIME`, `UNCATEGORIZED`)
  - `direction` (string, optional: `IN`, `OUT`)
  - `start_date` (string, optional, ISO-8601: `2026-09-01T00:00:00Z`)
  - `end_date` (string, optional, ISO-8601: `2026-09-30T23:59:59Z`)
  - `cursor` (string, optional: pagination cursor / last evaluated key)
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
      },
      {
        "receipt_number": "SK055QBUGB",
        "completion_time": "2026-09-02T18:18:00Z",
        "details": "Customer Transfer to 254722001122 - Landlord Joseph Njuguna (Shop Rent September)",
        "amount": 15000.0,
        "direction": "OUT",
        "running_balance": 40165.37,
        "status": "Completed",
        "category": "RENT",
        "counterparty": "Landlord Joseph Njuguna",
        "categorization_method": "RULE_BASED",
        "debt_matched_id": null
      }
    ]
  }
  ```

---

### 2.2 Financial Intelligence & Weekly Summary

#### 2.2.1 Get Weekly Summary & Historical Series
- **Method & Path:** `GET /summary/weekly`
- **Description:** Returns the primary dashboard financial pulse: total sales, operating expenses, estimated net profit, profit margin, active trading days, and a 4-week historical trend series.
- **Query Parameters:**
  - `weeks` (integer, optional, default: `4`, min: `1`, max: `12`)
- **Response (`200 OK`):**
  ```json
  {
    "business_id": "biz_7a8b9c0d1e2f",
    "currency": "KSh",
    "current_week": {
      "week_label": "2026-W36",
      "start_date": "2026-09-01",
      "end_date": "2026-09-07",
      "gross_sales": 38450.0,
      "operating_expenses": 26800.0,
      "estimated_profit": 11650.0,
      "profit_margin_pct": 30.3,
      "active_trading_days": 7,
      "transaction_count": 42,
      "expense_breakdown": {
        "INVENTORY": 11500.0,
        "RENT": 15000.0,
        "UTILITIES": 300.0,
        "AIRTIME": 0.0
      },
      "pulse_message": "You made KSh 38,450 this week, estimated profit KSh 11,650."
    },
    "history_series": [
      {
        "week_label": "2026-W33",
        "gross_sales": 32100.0,
        "operating_expenses": 23400.0,
        "estimated_profit": 8700.0,
        "profit_margin_pct": 27.1
      },
      {
        "week_label": "2026-W34",
        "gross_sales": 35400.0,
        "operating_expenses": 24900.0,
        "estimated_profit": 10500.0,
        "profit_margin_pct": 29.7
      },
      {
        "week_label": "2026-W35",
        "gross_sales": 34100.0,
        "operating_expenses": 25200.0,
        "estimated_profit": 8900.0,
        "profit_margin_pct": 26.1
      },
      {
        "week_label": "2026-W36",
        "gross_sales": 38450.0,
        "operating_expenses": 26800.0,
        "estimated_profit": 11650.0,
        "profit_margin_pct": 30.3
      }
    ]
  }
  ```

---

### 2.3 Customer Debt Tracker ("Kitabu ya Deni")

#### 2.3.1 Create Customer Debt Record
- **Method & Path:** `POST /debts`
- **Description:** Adds a new credit record to the digital Kitabu ya Deni when a customer takes goods without immediate payment.
- **Headers:**
  - `Authorization: Bearer <token>`
  - `Content-Type: application/json`
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

#### 2.3.2 List Customer Debts
- **Method & Path:** `GET /debts`
- **Description:** Returns all customer debts for the store, with filtering and aggregate debt metrics.
- **Query Parameters:**
  - `status` (string, optional: `UNPAID`, `PARTIAL`, `CLEARED`)
  - `search` (string, optional: debtor name or phone substring)
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

#### 2.3.3 Update Debt Record / Manual Payment Logging
- **Method & Path:** `PATCH /debts/{debt_id}`
- **Description:** Updates debt status, logs manual cash repayments, or modifies item notes.
- **Path Parameters:**
  - `debt_id` (string, required: e.g. `debt_9921a8_7b4c`)
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

### 2.4 Credit Scoring & Lender Reports

#### 2.4.1 Get Biashara Score
- **Method & Path:** `GET /score`
- **Description:** Returns the most recent Biashara Credit Score (0–100), tier rating, pillar breakdown, and actionable improvement tips for the duka owner.
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

#### 2.4.2 Trigger On-Demand Score Recomputation
- **Method & Path:** `POST /score/calculate`
- **Description:** Forces full recalculation of the credit score based on all ingested transactions and debts in the system.
- **Headers:**
  - `Authorization: Bearer <token>`
- **Response (`200 OK`):**
  Returns identical schema as `GET /score` (`BiasharaScoreResult`).

---

#### 2.4.3 Download Lender-Ready PDF Financial Report
- **Method & Path:** `GET /reports/lender-pdf`
- **Description:** Generates and returns a downloadable, lender-formatted single-page business verification report for SACCO and bank loan officers.
- **Query Parameters:**
  - `format` (string, optional: `binary` | `url`, default: `binary`)
- **Response (when `format=binary`):**
  - **Status:** `200 OK`
  - **Headers:**
    - `Content-Type: application/pdf`
    - `Content-Disposition: attachment; filename="Biashara_Score_Report_Mama_Mary.pdf"`
  - **Body:** Binary PDF byte stream.
- **Response (when `format=url`):**
  - **Status:** `200 OK`
  - **Body:**
    ```json
    {
      "business_id": "biz_7a8b9c0d1e2f",
      "download_url": "https://biashara-statements-dev.s3.amazonaws.com/reports/biz_7a8b9c0d1e2f/lender_report.pdf?AWSAccessKeyId=...",
      "expires_in_seconds": 3600,
      "generated_at": "2026-11-12T15:50:00Z"
    }
    ```

---

### 2.5 Africa's Talking SMS Dispatch

#### 2.5.1 Trigger Weekly SMS Digest
- **Method & Path:** `POST /notifications/weekly-sms`
- **Description:** Computes the latest weekly profit pulse, builds the Safaricom-compliant SMS text, and dispatches it via Africa's Talking API (or logs to stdout in mock mode). Used by AWS EventBridge cron schedule or for testing.
- **Headers:**
  - `Authorization: Bearer <token>`
  - `Content-Type: application/json`
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
    "dispatched_at": "2026-11-12T15:50:00Z"
  }
  ```

---

## 3. Proposed Model Changes

> [!NOTE]
> Per architectural guidelines, `backend/src/core/models.py` has **not** been modified directly. The following additions and refinements are proposed for review and implementation in `models.py`:

1. **Add `business_id` and `source` to `Transaction` Model:**
   - **Current `Transaction`:** Lacks `business_id` and `source`.
   - **Proposed:**
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
         business_id: Optional[str] = None  # PROPOSED: Multi-tenant partition key
         source: str = "CSV_UPLOAD"         # PROPOSED: "CSV_UPLOAD" | "SMS_PASTE"
     ```
   - **Rationale:** Aligns pure model with DynamoDB Table `biashara-transactions` Partition Key (`business_id`) and audit trail.

2. **Define `WeeklySummary` & `WeeklyMetricsSeries` Dataclasses:**
   - **Proposed:**
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
         active_trading_days: int    # Number of days with >= 1 sales tx
         transaction_count: int      # Total transactions
         expense_breakdown: Dict[str, float] = field(default_factory=dict)
         pulse_message: str = ""
     ```
   - **Rationale:** Establishes a strictly typed contract between `core/summary.py`, API endpoints, and the frontend dashboard.

3. **Specify Repayment History Structure:**
   - **Current `DebtRecord`:** Uses untyped `repayment_history: List[Dict[str, Any]]`.
   - **Proposed Type Alias / Dataclass:**
     ```python
     @dataclass
     class RepaymentEntry:
         receipt_number: str
         amount: float
         date: str
         notes: Optional[str] = None
     ```

4. **Define `BusinessProfile` Model:**
   - **Proposed:**
     ```python
     @dataclass
     class BusinessProfile:
         business_id: str
         business_name: str
         owner_name: str
         phone_number: str
         till_number: Optional[str] = None
         category: str = "Retail Duka / Grocery"
         biashara_score: Optional[int] = None
         score_grade: Optional[str] = None
         created_at: str = ""
     ```
   - **Rationale:** Standardizes merchant metadata for the PDF lender report generator and DynamoDB `biashara-businesses` table.
