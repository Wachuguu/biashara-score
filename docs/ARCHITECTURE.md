# System Architecture & Technical Specifications
## Biashara Score — Serverless Cloud Architecture & Data Model

---

## 1. High-Level AWS Architecture

Biashara Score uses a modern, cost-effective, serverless architecture on AWS. It scales to zero when not in use (costing pennies for an MVP) while remaining capable of handling spikes during end-of-month duka statement uploads.

```
                              +------------------------------------------+
                              |         Next.js + Tailwind PWA           |
                              |              (AWS Amplify)               |
                              +--------------------+---------------------+
                                                   |
                                     HTTPS / JSON  | Auth: JWT Bearer
                                                   v
                              +--------------------+---------------------+
                              |         Amazon API Gateway               |
                              |             (HTTP APIs)                  |
                              +--------------------+---------------------+
                                                   |
              +------------------------------------+------------------------------------+
              |                                    |                                    |
              v                                    v                                    v
+-----------------------------+      +-----------------------------+      +-----------------------------+
|    Upload & Parse Lambda    |      |  Categorizer & Score Lambda |      |     Debt Tracker Lambda     |
+--------------+--------------+      +--------------+--------------+      +--------------+--------------+
               |                                    |                                    |
               +------------------------------------+------------------------------------+
                                                   |
             +------------------+------------------+------------------+
             |                  |                  |                  |
             v                  v                  v                  v
    +-----------------+ +---------------+ +-----------------+ +-----------------+
    | Amazon DynamoDB | |   Amazon S3   | | Amazon Bedrock  | | EventBridge Cron|
    | (3 Core Tables) | | (CSV & PDFs)  | |(Claude 3 Haiku) | | (Weekly 8PM EAT)|
    +-----------------+ +---------------+ +-----------------+ +--------+--------+
                                                                       |
                                                                       v
                                                             +------------------+
                                                             | Africa's Talking |
                                                             |  (SMS Gateway)   |
                                                             +------------------+
```

### Component Breakdown
1. **Frontend (AWS Amplify Hosting):** Next.js 14 App Router with Tailwind CSS, responsive mobile-first UI with offline PWA capabilities.
2. **Authentication (Amazon Cognito):** User Pool providing phone number and email sign-up/login with JWT verification at API Gateway.
3. **API Gateway (HTTP API):** Low-latency, cost-effective REST routing to backend Lambda functions with CORS enabled for frontend domains.
4. **Compute (AWS Lambda - Python 3.11):** Independent micro-functions packaged via AWS SAM:
   - `UploadStatementHandler`: Presigned S3 URLs + asynchronous statement parsing.
   - `ProcessTransactionsHandler`: Regex rule engine with Bedrock LLM fallback.
   - `ScoreCalculationHandler`: Evaluates 4 pillars of the Biashara Score.
   - `DebtTrackerHandler`: Manages "Kitabu ya Deni" customer credit and reconciliations.
   - `WeeklySummaryCronHandler`: Triggered by EventBridge to calculate weekly metrics and dispatch Africa's Talking SMS.
5. **Database (Amazon DynamoDB):** On-demand serverless NoSQL storage for sub-10ms transactional reads/writes.
6. **Object Storage (Amazon S3):** Stores raw M-Pesa CSV uploads and generated lender-ready PDF reports.
7. **AI / LLM (Amazon Bedrock):** Anthropic Claude 3 Haiku for classifying unstructured, novel merchant names that rule engines miss.
8. **SMS Integration (Africa's Talking):** Kenya telco SMS delivery for weekly merchant digest notifications.

---

## 2. Decoupled Architecture for Local Development

### The Team Reality: Single AWS Deployer
- Our team of 4 shares **one AWS account**.
- Only **Dev 4 (DevOps Lead)** possesses AWS deployment credentials and deploys to staging/production via AWS SAM.
- **Devs 1, 2, and 3 must be able to run, build, and test 100% of their business logic locally without AWS credentials.**

### The Dependency Inversion Pattern
To guarantee local development works out-of-the-box, the backend codebase strictly enforces **Hexagonal / Clean Architecture**:

```
/backend/src/
  ├── core/               # <-- 100% PURE PYTHON. NO AWS IMPORTS. NO BOTO3.
  │    ├── parser.py       # Reads CSV strings / SMS text, returns typed dicts.
  │    ├── categorizer.py  # Evaluates regex rules; falls back to LLM interface.
  │    ├── score_engine.py # Pure mathematical scoring algorithms.
  │    └── debt_engine.py  # Pure debt reconciliation logic.
  │
  ├── wrappers/           # <-- THIN INTERFACE WRAPPERS (Mockable).
  │    ├── db_client.py    # Reads DynamoDB or fallback to local in-memory/JSON.
  │    ├── s3_client.py    # Fetches from S3 or fallback to local disk.
  │    ├── llm_client.py   # Calls Bedrock API or returns mock classifications.
  │    └── sms_client.py   # Calls Africa's Talking or prints to local console.
  │
  └── handlers/           # <-- THIN LAMBDA ADAPTERS.
       ├── api_handler.py
       └── cron_handler.py
```

### Local Mocking Switch (`MOCK_AWS=true`)
When `MOCK_AWS=true` in `.env`:
- `db_client` stores data in memory or reads `/sample-data/mpesa_statement.csv`.
- `s3_client` reads and writes to local `/tmp` or `backend/tests/fixtures`.
- `llm_client` uses a deterministic rule lookup for fallback categories.
- `sms_client` prints formatted SMS messages to the terminal stdout.

Every developer can execute `pytest backend/tests` instantly with 0 cloud dependencies!

---

## 3. DynamoDB Data Model

Biashara Score uses three clean, dedicated DynamoDB tables with On-Demand billing. This multi-table structure is beginner-friendly, eliminates complex single-table key collision risks, and enables parallel development across team members.

### 3.1 Table: `biashara-businesses`
Stores merchant profile information, contact numbers, and latest computed credit scores.

- **Primary Key:**
  - Partition Key (`PK`): `business_id` (String, e.g. `biz_7a8b9c0d1e2f`)

| Attribute | Type | Example | Description |
| :--- | :--- | :--- | :--- |
| `business_id` | String (PK) | `"biz_7a8b9c0d1e2f"` | Unique business identifier (UUID) |
| `business_name` | String | `"Mama Mary Provisions"` | Registered or display name of the duka |
| `owner_name` | String | `"Mary Wambui"` | Name of the primary shopkeeper |
| `phone_number` | String | `"+254712345678"` | Safaricom phone number for SMS digests |
| `till_number` | String | `"789123"` | M-Pesa Buy Goods Till or Paybill |
| `category` | String | `"Retail Duka / Grocery"` | Sector classification |
| `biashara_score` | Number | `78` | Most recently calculated score (0-100) |
| `score_grade` | String | `"Good"` | Human-readable score tier |
| `score_breakdown` | Map | `{ "consistency": 26, "growth": 19, "expense_ratio": 20, "debt_recovery": 13 }` | 4 scoring pillars |
| `last_scored_at` | String | `"2026-10-24T18:00:00Z"` | ISO-8601 timestamp of score generation |
| `created_at` | String | `"2026-09-01T08:00:00Z"` | Account registration timestamp |

---

### 3.2 Table: `biashara-transactions`
Stores parsed and categorized M-Pesa transactions.

- **Primary Key:**
  - Partition Key (`PK`): `business_id` (String)
  - Sort Key (`SK`): `completion_time#receipt_number` (String, e.g. `2026-09-01T12:49:00#SK01YUUM7K`)
- **Global Secondary Index (GSI):** `CategoryTimeIndex`
  - GSI PK: `business_id_category` (String, e.g. `biz_7a8b9c0d1e2f#SALES`)
  - GSI SK: `completion_time` (String)

| Attribute | Type | Example | Description |
| :--- | :--- | :--- | :--- |
| `business_id` | String (PK) | `"biz_7a8b9c0d1e2f"` | Multi-tenant tenant ID |
| `completion_time#receipt` | String (SK) | `"2026-09-01T12:49:00#SK01YUUM7K"` | Compound sort key for time-range queries |
| `receipt_number` | String | `"SK01YUUM7K"` | Safaricom 10-char receipt reference |
| `completion_time` | String | `"2026-09-01T12:49:00Z"` | Normalized ISO-8601 transaction time |
| `details` | String | `"Customer Payment to Till 789123 - John Otieno"` | Raw statement description |
| `category` | String | `"SALES"` | `SALES`, `INVENTORY`, `UTILITIES`, `RENT`, `DEBT_RECOVERY`, `OWNER_DRAW` |
| `direction` | String | `"IN"` | `"IN"` (Paid In) or `"OUT"` (Withdrawn) |
| `amount` | Number | `1606.98` | Transaction value in KSh |
| `running_balance` | Number | `50106.98` | Account balance following transaction |
| `source` | String | `"CSV_UPLOAD"` | `"CSV_UPLOAD"` or `"SMS_PASTE"` |
| `categorizer` | String | `"RULE_BASED"` | `"RULE_BASED"` or `"BEDROCK_HAIKU"` |
| `debt_id_matched` | String | `"debt_9921a8"` | Link to debt table if this cleared a debt |

---

### 3.3 Table: `biashara-debts`
Digitizes the shopkeeper's "Kitabu ya Deni" (Customer Credit Book).

- **Primary Key:**
  - Partition Key (`PK`): `business_id` (String)
  - Sort Key (`SK`): `debt_id` (String, e.g. `debt_9921a8`)
- **Global Secondary Index (GSI):** `DebtorPhoneIndex`
  - GSI PK: `debtor_phone` (String, e.g. `"+254728192837"`)
  - GSI SK: `status` (String, e.g. `"UNPAID"`)

| Attribute | Type | Example | Description |
| :--- | :--- | :--- | :--- |
| `business_id` | String (PK) | `"biz_7a8b9c0d1e2f"` | Store identifier |
| `debt_id` | String (SK) | `"debt_9921a8"` | Unique debt entry identifier |
| `debtor_name` | String | `"Dennis Omondi (Mama Boi)"` | Customer name |
| `debtor_phone` | String (GSI) | `"+254728192837"` | Customer phone for reconciliation & SMS reminders |
| `amount_owed` | Number | `2100.00` | Initial credit extended in KSh |
| `amount_cleared` | Number | `1000.00` | Amount paid back so far in KSh |
| `balance_remaining` | Number | `1100.00` | Current balance outstanding |
| `status` | String | `"PARTIAL"` | `"UNPAID"`, `"PARTIAL"`, or `"CLEARED"` |
| `items_summary` | String | `"2x Unga Pembe, 1x Cooking Oil 1L, Sugar 1kg"` | Goods taken on credit |
| `created_at` | String | `"2026-09-02T10:15:00Z"` | Date credit was recorded |
| `due_date` | String | `"2026-09-16T18:00:00Z"` | Expected repayment date (14 days default) |
| `repayments` | List | `[{"receipt": "SK067BQRKW", "amount": 1000.00, "date": "2026-09-10"}]` | Audit trail of matching payments |

---

## 4. Ingestion & Scoring Logic

### 4.1 Ingestion Flow
1. User uploads CSV file in Next.js frontend.
2. Frontend requests presigned S3 PUT URL from `UploadStatementHandler`.
3. Frontend uploads directly to S3 bucket `biashara-statements-{env}/uploads/{business_id}/`.
4. S3 trigger invokes `ProcessTransactionsHandler`.
5. Transactions are parsed into standard schema, categorized via Rule Engine (and Bedrock if needed), and batch-written to DynamoDB.
6. Trigger updates weekly summary and triggers score computation.

### 4.2 Biashara Score Algorithm (Max: 100 Points)

| Scoring Component | Weight | Logic & Benchmark |
| :--- | :---: | :--- |
| **1. Income Consistency** | **30 pts** | Evaluates active trading days per week and regularity of customer deposits. >5 active days/week with steady daily cash flow gets max points. |
| **2. Volume & Growth** | **25 pts** | Evaluates total monthly turnover relative to store baseline and week-over-week revenue trajectory (>KSh 40,000/month for micro-duka). |
| **3. Operating Margin** | **25 pts** | `(Gross Sales - Expenses) / Gross Sales`. A healthy duka maintaining 15%–30% net operational margin scores full marks. Negative margins heavily penalize. |
| **4. Debt Recovery Rate** | **20 pts** | `Total Recovered Debt / Total Credit Extended`. Duka owners who collect >85% of extended credit within 30 days receive full points. |

#### Score Tier Categorization
- **80 – 100:** *Gold Biashara (Lender Preferred)* — Eligible for uncollateralized working capital micro-loans.
- **65 – 79:** *Silver Biashara (Stable)* — Eligible for standard inventory financing.
- **50 – 64:** *Bronze Biashara (Emerging)* — Needs tighter debt collection; qualified for micro-credit with group guarantee.
- **< 50:** *Needs Improvement* — High expense leakage or uncollected debts.

---

## 5. Amazon Bedrock LLM Fallback

For transactions with ambiguous descriptions (e.g., *"Payment to 918273 - Alpha Tech Ventures"*, *"Internal transfer 01928"*), the system calls Amazon Bedrock.

- **Model:** `anthropic.claude-3-haiku-20240307-v1:0` (Fast, low-latency, lowest cost).
- **Prompt Structure:**
  ```
  Classify the following Kenyan M-Pesa transaction into exactly one category:
  [SALES, INVENTORY, UTILITIES, RENT, DEBT_RECOVERY, OWNER_DRAW, OTHER]
  
  Transaction Details: "{details}"
  Direction: {direction}
  Amount: KSh {amount}
  
  Output ONLY valid JSON: {"category": "<CATEGORY>", "confidence": 0.95, "reason": "<brief>"}
  ```

---

## 6. Africa's Talking Integration

A scheduled AWS EventBridge rule triggers the `WeeklySummaryCronHandler` every Sunday at 17:00 UTC (20:00 EAT).
- Queries `biashara-transactions` for the trailing 7 days.
- Aggregates sales, expenses, and net profit.
- Dispatches SMS via Africa's Talking REST API:
  ```json
  POST https://api.africastalking.com/version1/messaging
  Headers: { "apiKey": "...", "Accept": "application/json" }
  Body: {
    "username": "...",
    "to": "+254712345678",
    "message": "Habari Mary! You made KSh 14,200 this week, profit KSh 3,100. Outstanding customer debts: KSh 3,200. Score: 78/100 (Good). Keep growing!"
  }
  ```
