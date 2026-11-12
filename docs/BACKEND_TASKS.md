# Biashara Score — Backend Engineering Tasks & Workstreams
**Architecture Specification for Solo Backend Implementation**  
**Sprint Duration:** 15 Days (MVP Delivery)  
**Strict Rule:** No overlapping files across Workstreams A, B, C, and D. Pure business logic in `core/` has zero AWS/boto3 imports.

---

## 1. Workstream File Ownership Matrix

To guarantee clean git branching, zero merge conflicts, and modular testing, the codebase is partitioned into four strictly disjoint workstreams:

| Workstream | Domain | Owned Production Files | Dedicated Test File |
| :--- | :--- | :--- | :--- |
| **Workstream A** | Ingestion & Categorization | `backend/src/core/parser.py`<br>`backend/src/core/categorizer.py` | `backend/tests/test_parser_categorizer.py` |
| **Workstream B** | Scoring & Summary Engines | `backend/src/core/score_engine.py`<br>`backend/src/core/summary.py` *(New)* | `backend/tests/test_score_summary.py` |
| **Workstream C** | Debt Engine, PDF & SMS | `backend/src/core/debt_engine.py`<br>`backend/src/core/report_generator.py` *(New)*<br>`backend/src/wrappers/sms_client.py` | `backend/tests/test_debt_report_sms.py` |
| **Workstream D** | Handlers, Local Server & Infra | `backend/src/handlers/api_handler.py`<br>`backend/src/handlers/statement_handler.py`<br>`backend/src/handlers/debt_handler.py`<br>`backend/src/handlers/score_handler.py`<br>`backend/src/handlers/cron_handler.py`<br>`backend/local_server.py` *(New)*<br>`backend/src/wrappers/db_client.py`<br>`infra/template.yaml` | `backend/tests/test_api_endpoints.py` |

---

## 2. Workstream Details & Specifications

### 2.1 Workstream A: Parser & Categorizer Engine
**Primary Domain:** Ingestion of Safaricom CSV statements and SMS strings; rule-based regex classification with Bedrock fallback interface.

#### 2.1.1 Files Owned
- `backend/src/core/parser.py`
- `backend/src/core/categorizer.py`
- `backend/tests/test_parser_categorizer.py`

#### 2.1.2 Required Functions & Type Signatures

```python
# backend/src/core/parser.py
from typing import List, Optional
from .models import Transaction, TransactionDirection, TransactionCategory

def parse_csv_statement(csv_content: str, business_id: Optional[str] = None) -> List[Transaction]:
    """
    Parses a raw Safaricom M-Pesa CSV statement string into a list of Transaction dataclass instances.
    Extracts: receipt_number, completion_time, details, amount, direction, running_balance, status.
    Cleans formatted numbers (e.g., '1,606.98' -> 1606.98) and determines direction ('IN' for Paid In, 'OUT' for Withdrawn).
    """
    ...

def parse_sms_message(sms_text: str, business_id: Optional[str] = None) -> Transaction:
    """
    Parses a single incoming Safaricom M-Pesa SMS message string into a Transaction dataclass instance.
    Extracts receipt code (e.g., 'SK01YUUM7K'), amount, counterparty name/phone, balance, and timestamp.
    """
    ...

def parse_multiple_sms(sms_text: str, business_id: Optional[str] = None) -> List[Transaction]:
    """
    Splits multi-line or concatenated pasted SMS text blocks into individual messages
    and returns a list of parsed Transaction instances.
    """
    ...
```

```python
# backend/src/core/categorizer.py
from typing import Optional, Callable, List
from .models import Transaction, TransactionCategory

def match_rule_based_category(details: str, direction: str) -> Optional[TransactionCategory]:
    """
    Pure regex & keyword dictionary matcher against Kenyan commercial keywords:
    - SALES: Till receipts, Paybill inbound, customer deposits.
    - INVENTORY: Brookside, Pembe, Unga, Bidco, Kapa, Farmer's Choice, Devki, wholesale depots.
    - UTILITIES: KPLC PREPAID, Nairobi Water (NWSC), WiFi, internet.
    - RENT: Landlord transfers, shop rent keywords.
    - OWNER_DRAW: 'Personal Draw', transfers to owner's private numbers.
    - AIRTIME: Airtime Purchase, Safaricom data bundles.
    - DEBT_RECOVERY: 'debt repayment', 'deni', 'debt settled'.
    Returns None if no rule matches with high confidence.
    """
    ...

def categorize_transaction(
    tx: Transaction,
    llm_fallback_fn: Optional[Callable[[str, str, float], str]] = None,
) -> Transaction:
    """
    Categorizes a transaction.
    1. Runs match_rule_based_category. Sets categorization_method = 'RULE_BASED' on match.
    2. If unmatched and llm_fallback_fn is provided, invokes fallback and sets categorization_method = 'BEDROCK_HAIKU'.
    3. If still unmatched, assigns TransactionCategory.UNCATEGORIZED.
    """
    ...

def categorize_batch(
    transactions: List[Transaction],
    llm_fallback_fn: Optional[Callable[[str, str, float], str]] = None,
) -> List[Transaction]:
    """
    Applies categorization across a list of transactions efficiently.
    """
    ...
```

#### 2.1.3 Edge Cases to Handle
1. **CSV Formatting Quarks:**
   - Byte Order Marks (`\xef\xbb\xbf` UTF-8 BOM) at the start of Safaricom CSV exports.
   - Windows CRLF (`\r\n`) vs Unix LF (`\n`).
   - Comma-formatted numbers: `"1,606.98"`, `"50,106.98"`, or trailing empty columns.
   - Rows with empty "Paid In" or "Withdrawn" columns (must not throw `ValueError`).
   - Missing or empty trailing rows in the CSV export.
2. **SMS Format Variations:**
   - Standard receipt: `"SK01YUUM7K Confirmed. You have received Ksh1,600.00 from..."`
   - Lipa na M-Pesa Buy Goods: `"You have sent Ksh2,479.42 to Bidco Africa Distributors..."`
   - Paybill payment: `"Ksh1,500.00 sent to KPLC PREPAID for account 1428392019..."`
   - Airtime purchase: `"You bought Ksh300.00 of airtime on 4/9/26..."`
   - Multi-message paste with double newlines, dashes, or numbered lists.
3. **Keyword Collision:**
   - "Jane Wanjiku" paying till vs "Farmer's Choice" paying till. Inbound to Till is always `SALES` unless note indicates `DEBT_RECOVERY`.
   - "Airtime" keywords within customer names must not falsely trigger `AIRTIME` category.

#### 2.1.4 "Done When" Test Scenario
**File:** `backend/tests/test_parser_categorizer.py`  
**Assertions:**
1. Loads `sample-data/mpesa_statement.csv` (150 rows).
2. `parse_csv_statement()` returns exactly 150 `Transaction` objects without exceptions.
3. First transaction has `receipt_number == "SK01YUUM7K"`, `amount == 1606.98`, `direction == TransactionDirection.IN`.
4. `categorize_batch()` categorizes:
   - Row 1 (`Till payment - John Otieno`) as `TransactionCategory.SALES`.
   - Row 6 (`Landlord Joseph Njuguna Shop Rent`) as `TransactionCategory.RENT`.
   - Row 10 (`Bidco Africa Distributors`) as `TransactionCategory.INVENTORY`.
   - Row 14 (`Airtime Purchase`) as `TransactionCategory.AIRTIME`.
5. Rule-based categorization coverage on `sample-data/mpesa_statement.csv` achieves **≥ 95%** without needing LLM fallback.
6. `parse_multiple_sms()` successfully parses a 3-SMS multi-block text and returns 3 valid `Transaction` records.

---

### 2.2 Workstream B: Financial Summary & Score Engine
**Primary Domain:** 4-week moving average sales, expenses, net profit, and the 4-pillar Biashara Credit Scoring algorithm.

#### 2.2.1 Files Owned
- `backend/src/core/score_engine.py`
- `backend/src/core/summary.py` *(New File)*
- `backend/tests/test_score_summary.py`

#### 2.2.2 Required Functions & Type Signatures

```python
# backend/src/core/summary.py
from typing import List, Dict, Any, Optional
from datetime import datetime
from .models import Transaction, TransactionCategory

def calculate_weekly_summary(
    transactions: List[Transaction],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Computes weekly totals from a list of transactions:
    - gross_sales: Sum of 'IN' transactions categorized as SALES or DEBT_RECOVERY.
    - operating_expenses: Sum of 'OUT' transactions categorized as INVENTORY, UTILITIES, RENT, AIRTIME.
    - estimated_profit: gross_sales - operating_expenses.
    - profit_margin_pct: (estimated_profit / gross_sales) * 100 (0.0 if gross_sales == 0).
    - active_trading_days: Distinct calendar dates with at least 1 sales transaction.
    - expense_breakdown: Dict mapping category to total spend.
    - pulse_message: Formatted summary string ("You made KSh 14,200 this week, profit KSh 3,100.").
    """
    ...

def calculate_multi_week_series(
    transactions: List[Transaction],
    num_weeks: int = 4,
    reference_date: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Groups transactions into calendar weeks (ISO week numbering) for the trailing num_weeks.
    Returns chronological list of weekly summary dicts for trend visualization.
    """
    ...
```

```python
# backend/src/core/score_engine.py
from typing import List, Dict, Any
from .models import Transaction, DebtRecord, BiasharaScoreResult

def compute_consistency_score(transactions: List[Transaction]) -> int:
    """
    Pillar 1 (Max 30 pts): Income Consistency & Frequency.
    Evaluates:
    - Trading days per week (>5 days/week = full points).
    - Variance in daily sales deposits over 30 days.
    """
    ...

def compute_growth_score(weekly_summaries: List[Dict[str, Any]]) -> int:
    """
    Pillar 2 (Max 25 pts): Revenue Volume & Growth.
    Evaluates:
    - Average monthly turnover (>KSh 40,000 for typical duka).
    - Week-over-week growth trajectory across the 4-week window.
    """
    ...

def compute_margin_score(weekly_summaries: List[Dict[str, Any]]) -> int:
    """
    Pillar 3 (Max 25 pts): Operating Margin & Expense Ratio.
    Evaluates net operating margin: (Sales - Operating Expenses) / Sales.
    - 15% to 35% margin = 25 pts.
    - 5% to 14% margin = 15 pts.
    - Negative margin = 0 pts.
    """
    ...

def compute_debt_recovery_score(debts: List[DebtRecord]) -> int:
    """
    Pillar 4 (Max 20 pts): Debt Discipline & Recovery.
    Evaluates:
    - Total recovered / total credit extended (>80% recovery = full points).
    - Presence of delinquent debts older than 30 days.
    - If no debts extended (zero credit shop), returns 15/20 neutral baseline.
    """
    ...

def generate_actionable_tips(
    consistency: int,
    growth: int,
    margin: int,
    debt: int,
    debts: List[DebtRecord]
) -> List[str]:
    """
    Produces 2-4 concrete, contextual tips in plain Kenyan English to help the shopkeeper improve their score.
    """
    ...

def calculate_biashara_score(
    business_id: str,
    transactions: List[Transaction],
    debts: List[DebtRecord],
) -> BiasharaScoreResult:
    """
    Computes total score (0 to 100) = consistency + growth + margin + debt.
    Assigns tier:
    - 80-100: 'Gold'
    - 65-79: 'Silver'
    - 50-64: 'Bronze'
    - <50: 'Needs Improvement'
    Returns fully populated BiasharaScoreResult dataclass.
    """
    ...
```

#### 2.2.3 Edge Cases to Handle
1. **Zero Transactions (Cold Start):**
   - New business with 0 transactions must return a valid `BiasharaScoreResult` with score 0, tier `"Needs Improvement"`, and helpful tips to upload statements without throwing `ZeroDivisionError`.
2. **Negative Profit / High Restocking Week:**
   - When a shop restocks heavily (e.g. rent + 3 sacks of maize flour) in week 1, expenses exceed sales. `profit_margin_pct` must handle negative values cleanly, clamping the margin score pillar to 0 without arithmetic underflow.
3. **Out-of-Order Timestamps:**
   - Statement rows may not be sorted chronologically. All summary calculations must parse ISO timestamps and group by true calendar date/week.
4. **Zero Extended Debts:**
   - Duka owner who operates strictly cash-and-carry has 0 debts in `biashara-debts`. Debt score should award default neutral points (e.g. 15/20) rather than failing a division by zero (`total_cleared / total_owed`).

#### 2.2.4 "Done When" Test Scenario
**File:** `backend/tests/test_score_summary.py`  
**Assertions:**
1. Evaluates transactions from `sample-data/mpesa_statement.csv` (September 2026 data).
2. `calculate_multi_week_series()` yields 4 consecutive weekly summaries with valid sales, expenses, and positive net profits.
3. `calculate_biashara_score()` produces:
   - `0 <= total_score <= 100`
   - `consistency_score <= 30`
   - `growth_score <= 25`
   - `expense_ratio_score <= 25`
   - `debt_recovery_score <= 20`
   - `total_score == consistency_score + growth_score + expense_ratio_score + debt_recovery_score`
   - `tier in ["Gold", "Silver", "Bronze", "Needs Improvement"]`
   - `len(actionable_tips) >= 2`
4. Executes with empty lists `transactions=[]` and `debts=[]`: returns cleanly without throwing `ZeroDivisionError`.

---

### 2.3 Workstream C: Debt Engine, PDF Report & SMS Client
**Primary Domain:** Reconciliation of incoming customer payments with open debts, ReportLab PDF generation, and Africa's Talking SMS integration.

#### 2.3.1 Files Owned
- `backend/src/core/debt_engine.py`
- `backend/src/core/report_generator.py` *(New File)*
- `backend/src/wrappers/sms_client.py`
- `backend/tests/test_debt_report_sms.py`

#### 2.3.2 Required Functions & Type Signatures

```python
# backend/src/core/debt_engine.py
from typing import List, Optional, Tuple, Dict, Any
from .models import DebtRecord, Transaction, DebtStatus

def normalize_phone_number(phone: str) -> str:
    """
    Standardizes Kenyan phone numbers to E.164:
    '0712345678' -> '+254712345678'
    '254712345678' -> '+254712345678'
    """
    ...

def match_repayment_to_debt(
    tx: Transaction,
    open_debts: List[DebtRecord]
) -> Optional[Tuple[DebtRecord, float]]:
    """
    Matches an incoming transaction to an open debt:
    1. Phone match: tx counterparty phone matches debtor_phone.
    2. Name match: debtor_name substring appears in tx details.
    Returns (matched_debt, payment_amount) or None.
    """
    ...

def apply_debt_repayment(
    debt: DebtRecord,
    payment_amount: float,
    receipt_number: str,
    payment_date: str,
    notes: str = ""
) -> DebtRecord:
    """
    Applies payment to debt:
    - Increments amount_cleared.
    - Decrements balance_remaining (capped at 0.0).
    - Sets status to DebtStatus.CLEARED if balance_remaining == 0, else DebtStatus.PARTIAL.
    - Appends entry to repayment_history: [{'receipt_number': ..., 'amount': ..., 'date': ..., 'notes': ...}].
    """
    ...

def calculate_debt_metrics(debts: List[DebtRecord]) -> Dict[str, Any]:
    """
    Calculates aggregate metrics for the debt dashboard:
    total_outstanding_amount, total_cleared_amount, recovery_rate_pct, unpaid_count, delinquent_count.
    """
    ...
```

```python
# backend/src/core/report_generator.py
from typing import Dict, Any, List
from .models import BiasharaScoreResult

def generate_lender_pdf(
    business_profile: Dict[str, Any],
    score_result: BiasharaScoreResult,
    weekly_summaries: List[Dict[str, Any]],
    debt_summary: Dict[str, Any],
) -> bytes:
    """
    Generates a professional, single-page A4 PDF financial verification report
    using ReportLab (pure Python, zero OS-level binary dependencies).
    Contains:
    - Business header (Name, Owner, Till number, Date range).
    - Biashara Score Badge & Tier ('Silver - 78/100').
    - 4 Pillar Scores breakdown table.
    - 4-week Sales & Profit cashflow table.
    - Digital Kitabu debt health summary.
    - Lender verification stamp & footer.
    Returns binary PDF bytes (starts with b'%PDF-').
    """
    ...
```

```python
# backend/src/wrappers/sms_client.py
from typing import Dict, Any
import os

def build_weekly_sms_message(
    owner_name: str,
    week_label: str,
    sales: float,
    expenses: float,
    profit: float,
    outstanding_debts: float,
    score: int,
    tier: str
) -> str:
    """
    Constructs the Safaricom-compliant SMS digest string:
    'Habari Mary! Biashara Score Summary for W36: Sales KSh 38,450, Expenses KSh 26,800, Est. Profit KSh 11,650. Outstanding Debts: KSh 3,200. Score: 78/100 (Silver). Keep growing!'
    Ensures message remains concise, friendly, and clean.
    """
    ...

class AfricaTalkingSMSClient:
    def send_sms(self, phone_number: str, message: str) -> Dict[str, Any]:
        """
        Dispatches SMS via Africa's Talking API.
        When MOCK_AWS=true, prints to stdout and returns mock success payload.
        """
        ...
```

#### 2.3.3 Edge Cases to Handle
1. **Phone Number Variations:**
   - Kenyan numbers entered as `0712345678`, `254712345678`, `+254712345678`, or `011...` (Safaricom newer prefix). Normalizer must unify all to `+254...` before comparison.
2. **Overpayment & Partial Repayments:**
   - Debtor owes KSh 1,200 and sends KSh 1,500. `balance_remaining` must not become negative (`max(0.0, balance - amount)`), status must be `CLEARED`, and the overpayment amount logged in notes.
3. **Pure-Python PDF Generation in Lambda:**
   - Must use `reportlab` standard canvas and flowables without requiring external C libraries, Cairo, or headless browser binaries so it runs seamlessly inside AWS Lambda and local machines.
4. **SMS Character Length & Number Formatting:**
   - Large floating numbers must be formatted with commas and zero decimals (`KSh 14,200` instead of `KSh 14200.000000001`).

#### 2.3.4 "Done When" Test Scenario
**File:** `backend/tests/test_debt_report_sms.py`  
**Assertions:**
1. Tests matching sample statement row `SK067BQRKW` (`Teacher Maina 254719283746 - KSh 1,526.05`) against a sample `DebtRecord` for Teacher Maina:
   - Correctly matches by phone number.
   - `apply_debt_repayment()` reduces `balance_remaining` to 0.0 and sets status to `DebtStatus.CLEARED`.
2. Tests `generate_lender_pdf()`:
   - Returns non-empty `bytes`.
   - Starts with `b"%PDF-"`.
   - Size exceeds 3,000 bytes.
3. Tests `build_weekly_sms_message()`:
   - Result string starts with `"Habari "` and contains `"Sales KSh "`, `"Est. Profit KSh "`, and `"Score: "`.
   - Length is ≤ 200 characters.
4. `sms_client.send_sms()` succeeds in mock mode without throwing network errors.

---

### 2.4 Workstream D: Handlers, Local Server & SAM Routes
**Primary Domain:** Thin AWS Lambda adapters, local FastAPI mock server with CORS for `http://localhost:3000`, database client wrapper updates, and `template.yaml` routing.

#### 2.4.1 Files Owned
- `backend/src/handlers/api_handler.py`
- `backend/src/handlers/statement_handler.py`
- `backend/src/handlers/debt_handler.py`
- `backend/src/handlers/score_handler.py`
- `backend/src/handlers/cron_handler.py`
- `backend/local_server.py` *(New File)*
- `backend/src/wrappers/db_client.py`
- `infra/template.yaml`
- `backend/tests/test_api_endpoints.py`

#### 2.4.2 Required Implementations & Signatures

```python
# backend/src/wrappers/db_client.py (Extended methods needed by handlers)
class DatabaseClient:
    def put_transaction(self, tx_dict: Dict[str, Any]) -> None: ...
    def batch_put_transactions(self, tx_dicts: List[Dict[str, Any]]) -> None: ...
    def get_transactions_for_business(self, business_id: str, limit: int = 100) -> List[Dict[str, Any]]: ...
    def put_debt(self, debt_dict: Dict[str, Any]) -> None: ...
    def get_debts_for_business(self, business_id: str) -> List[Dict[str, Any]]: ...
    def get_debt_by_id(self, business_id: str, debt_id: str) -> Optional[Dict[str, Any]]: ...
    def update_debt(self, business_id: str, debt_id: str, updates: Dict[str, Any]) -> Dict[str, Any]: ...
    def get_business(self, business_id: str) -> Optional[Dict[str, Any]]: ...
    def put_business(self, business_dict: Dict[str, Any]) -> None: ...
```

```python
# backend/src/handlers/
# Thin Lambda handlers parsing API Gateway v2 HTTP event and delegating to core/
def upload_statement_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]: ...
def sms_statement_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]: ...
def list_transactions_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]: ...
def weekly_summary_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]: ...
def debt_router_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]: ...
def score_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]: ...
def lender_pdf_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]: ...
def weekly_cron_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]: ...
```

```python
# backend/local_server.py
# FastAPI application serving identical endpoints for local frontend development
from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

app = FastAPI(title="Biashara Score Local API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Implements all 10 REST endpoints matching docs/API_CONTRACT.md exactly
```

```yaml
# infra/template.yaml Updates
# Add API Gateway HTTP Routes and Lambda definitions:
# - POST /statements/upload
# - POST /statements/sms
# - GET  /transactions
# - GET  /summary/weekly
# - POST /debts
# - GET  /debts
# - PATCH /debts/{debt_id}
# - GET  /score
# - POST /score/calculate
# - GET  /reports/lender-pdf
# - POST /notifications/weekly-sms
# - EventBridge Rule for Sunday 8:00 PM EAT
```

#### 2.4.3 Edge Cases to Handle
1. **CORS Preflight in Local Server:**
   - Browser preflight `OPTIONS` requests from `http://localhost:3000` must return 200 with proper `Access-Control-Allow-Origin` and `Access-Control-Allow-Headers`.
2. **Binary / PDF Streaming in API Gateway vs FastAPI:**
   - API Gateway HTTP API requires base64 encoding with `isBase64Encoded: true` for binary responses, whereas FastAPI returns `Response(content=pdf_bytes, media_type="application/pdf")`.
3. **Multipart/Form-Data Parsing in Serverless Lambda:**
   - Statement upload endpoint must cleanly extract file content whether received via FastAPI `UploadFile` locally or API Gateway base64-encoded body in Lambda.
4. **Multi-Tenant Identification:**
   - If `Authorization` header is present, extract `business_id` from token claims; if running locally or `X-Business-Id` header is passed, fallback gracefully.

#### 2.4.4 "Done When" Test Scenario
**File:** `backend/tests/test_api_endpoints.py`  
**Assertions:**
1. Using FastAPI `TestClient(app)`:
   - `POST /statements/upload` with `sample-data/mpesa_statement.csv`: returns HTTP `200` with `total_rows_parsed == 150`.
   - `POST /statements/sms`: returns HTTP `201` with parsed transactions.
   - `GET /transactions`: returns HTTP `200` with transaction list.
   - `GET /summary/weekly`: returns HTTP `200` with `current_week` and `history_series`.
   - `POST /debts`: creates new debt, returns HTTP `201`.
   - `GET /debts`: lists debts including newly created debt, returns HTTP `200`.
   - `PATCH /debts/{debt_id}`: logs payment, returns HTTP `200`.
   - `GET /score`: returns HTTP `200` with score result.
   - `GET /reports/lender-pdf`: returns HTTP `200`, `Content-Type: application/pdf`, and valid binary content.
   - `POST /notifications/weekly-sms`: returns HTTP `200` with mock SMS response.
2. CORS headers are returned for `Origin: http://localhost:3000`.

---

## 3. Recommended Implementation Dependency Order

Because you are a solo developer implementing the entire backend, follow this sequential dependency path to minimize context switching and ensure each layer builds upon verified underlying logic:

```mermaid
flowchart TD
    subgraph Step 1: Ingestion & Rules [Phase 1: Ingestion Engine]
        A1["Workstream A: core/parser.py"] --> A2["Workstream A: core/categorizer.py"]
        A2 --> A3["backend/tests/test_parser_categorizer.py"]
    end

    subgraph Step 2: Metrics & Scoring [Phase 2: Analytics Engine]
        A3 --> B1["Workstream B: core/summary.py"]
        B1 --> B2["Workstream B: core/score_engine.py"]
        B2 --> B3["backend/tests/test_score_summary.py"]
    end

    subgraph Step 3: Debts, Reports & SMS [Phase 3: Business Services]
        A3 --> C1["Workstream C: core/debt_engine.py"]
        B3 --> C2["Workstream C: core/report_generator.py"]
        C1 --> C3["Workstream C: wrappers/sms_client.py"]
        C2 --> C4["backend/tests/test_debt_report_sms.py"]
        C3 --> C4
    end

    subgraph Step 4: Handlers & Local Server [Phase 4: API & Server]
        C4 --> D1["Workstream D: db_client.py extensions"]
        D1 --> D2["Workstream D: local_server.py (FastAPI)"]
        D2 --> D3["Workstream D: handlers/*.py"]
        D3 --> D4["Workstream D: infra/template.yaml"]
        D4 --> D5["backend/tests/test_api_endpoints.py"]
    end
```

### Execution Phases:
1. **Phase 1 (Workstream A):** Build `parser.py` and `categorizer.py`. Verify with `test_parser_categorizer.py` on `sample-data/mpesa_statement.csv`. (Est: 1-2 days)
2. **Phase 2 (Workstream B):** Build `summary.py` and `score_engine.py`. Verify with `test_score_summary.py`. (Est: 1-2 days)
3. **Phase 3 (Workstream C):** Build `debt_engine.py`, `report_generator.py`, and `sms_client.py`. Verify with `test_debt_report_sms.py`. (Est: 2 days)
4. **Phase 4 (Workstream D):** Build `local_server.py` (FastAPI) first so frontend can integrate immediately, then write thin Lambda `handlers/` and update `infra/template.yaml`. Verify with `test_api_endpoints.py`. (Est: 2 days)

---

## 4. Architecture & Implementation Risks and Mitigations

| # | Risk Description | Severity | Impact | Concrete Mitigation |
| :- | :--- | :---: | :---: | :--- |
| **R-1** | **Safaricom Statement Format Inconsistency:** M-Pesa CSV exports occasionally vary headers or date formats between consumer app and business web portal. | **High** | Parser failure during duka onboarding. | Implement resilient header normalization in `parser.py` (case-insensitive strip, fuzzy column matching for `Receipt`, `Time`, `Details`, `Paid In`, `Withdrawn`, `Balance`). Support both `YYYY-MM-DD HH:MM:SS` and `DD/MM/YYYY HH:MM:SS`. |
| **R-2** | **Bedrock LLM Latency & Cost Spill:** Ambiguous transactions sent sequentially to Bedrock Claude 3 Haiku could slow down statement upload and exceed free tier budget. | **Medium** | Slow upload response (>15s), higher AWS bills. | The rule engine must handle ≥95% of transactions locally. For remaining ambiguous rows, invoke Bedrock in batches or fallback to default heuristic (`INVENTORY` for OUT, `SALES` for IN) if Bedrock latency exceeds 2 seconds. |
| **R-3** | **ReportLab Lambda Package Size & Cold Start:** PDF libraries can introduce bloated dependencies or fail due to missing font libraries. | **Medium** | Lambda packaging errors or deployment bloat. | Use standard `reportlab` with built-in Helvetica fonts only. Do not install heavy external libraries like Cairo or Chromium. Keep Lambda package < 35MB. |
| **R-4** | **Debt Reconciliation False Positives:** A customer might send an M-Pesa payment for a new cash purchase that accidentally gets credited against an old debt. | **Medium** | Incorrect debt clearing in "Kitabu ya Deni". | Require explicit matching heuristics: (1) exact phone number match AND (2) either matching amount or explicit reference in transaction details/note. Expose an undo/revert endpoint in API (`PATCH /debts/{id}`). |
| **R-5** | **SMS Gateway Latency & Failures:** Africa's Talking API timeouts during scheduled Sunday 8:00 PM cron run. | **Low** | Weekly SMS not delivered on time. | Add a 5-second timeout on SMS HTTP requests, log delivery status in DynamoDB, and decouple cron calculation from SMS sending with an idempotent retry guard. |
| **R-6** | **Local Server vs Lambda Parity Drift:** Discrepancy between FastAPI behavior locally and API Gateway + Lambda in AWS. | **Medium** | Works on developer machine but fails when Dev 4 deploys to staging. | Keep Lambda handlers paper-thin: handlers only translate API Gateway event `dict` into typed arguments and call the exact same `core/` functions that `local_server.py` calls. |
