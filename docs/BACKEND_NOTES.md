# Biashara Score — Backend Engineering Notes

## Workstream A: Ingestion & Categorization Engine
- **Status:** Complete. 100% offline, pure Python with zero AWS/boto3 imports.
- **Owned Files:**
  - `backend/src/core/parser.py`
  - `backend/src/core/categorizer.py`
  - `backend/tests/test_parser_categorizer.py`

### Implemented Interfaces
1. **`parse_csv_statement(csv_content: str, business_id: Optional[str] = None) -> List[Transaction]`**
   - Strips UTF-8 BOM (`\ufeff`) and normalizes CRLF line breaks.
   - Extracts `receipt_number`, `completion_time` (ISO-8601 normalized), `details`, `amount`, `direction` (`TransactionDirection.IN` / `OUT`), `running_balance`, `status`, and `counterparty`.
   - Cleans formatted currency amounts with commas and currency symbols.
   - Successfully parses all 150 rows in `sample-data/mpesa_statement.csv`.

2. **`parse_sms_message(sms_text: str, business_id: Optional[str] = None) -> Transaction`**
   - Extracts receipt codes (e.g., `SK01YUUM7K`, `B101`), amount, direction, balance, timestamp, and counterparty.
   - Accurately parses standard Safaricom confirmations, Buy Goods, Paybill, Airtime purchases, and customer transfers.

3. **`parse_multiple_sms(sms_text: str, business_id: Optional[str] = None) -> List[Transaction]`**
   - Splits multi-line or concatenated pasted SMS blocks (double newlines, message boundaries, bullet points, numbers).

4. **`match_rule_based_category(details: str, direction: str) -> Optional[TransactionCategory]`**
   - Rule-based matching against Kenyan commercial keywords:
     - `SALES`: Till receipts, inbound payments, customer deposits.
     - `INVENTORY`: Brookside, Pembe, Unga, Bidco, Kapa, Farmer's Choice, Devki, Kevian, etc.
     - `UTILITIES`: KPLC PREPAID, Nairobi City Water (NWSC), Wi-Fi, electricity.
     - `RENT`: Landlord transfers, shop rent keywords.
     - `OWNER_DRAW`: Personal Draw, sent to self.
     - `AIRTIME`: Airtime Purchase, airtime bought, data bundles.
     - `DEBT_RECOVERY`: debt repayment, debt settled, deni, cleared, loan cleared, credit payment.
   - Resolves keyword collisions: inbound till payments from entities containing supplier names (e.g. "Farmer's Choice") or customer names containing "Airtime" remain `SALES`.

5. **`categorize_transaction(tx: Transaction, llm_fallback_fn=None) -> Transaction` & `categorize_batch(transactions: List[Transaction], llm_fallback_fn=None) -> List[Transaction]`**
   - First applies rule-based matching (sets `categorization_method = "RULE_BASED"`).
   - If unmatched and `llm_fallback_fn` is provided, invokes fallback and sets `categorization_method = "BEDROCK_HAIKU"`.
   - Unmatched transactions default to `TransactionCategory.UNCATEGORIZED` with `categorization_method = "UNMATCHED"`.

### Performance & Benchmark Metrics
- **Sample CSV Coverage:** 150/150 rows (100.0%) resolved purely via rule matching without invoking LLM fallback.
  - Breakdown: `SALES`: 92, `INVENTORY`: 24, `DEBT_RECOVERY`: 14, `UTILITIES`: 8, `AIRTIME`: 6, `OWNER_DRAW`: 4, `RENT`: 2.
- **Edge Case Suite (B101–B110):** 10/10 (100%) messy hand-written Kenyan SMS cases parsed and categorized correctly.
- **Test Suite Status:** All 11 test cases (including 10 subtests) in `backend/tests/test_parser_categorizer.py` passing offline.

---

## Notes for Teammates & Workstreams

### Note for Workstream D (Handlers & API):
- `parse_csv_statement(csv_content, business_id)` and `categorize_batch(transactions, llm_fallback_fn)` are ready for `POST /statements/upload`.
- `parse_sms_message(sms_text, business_id)` and `parse_multiple_sms(sms_text, business_id)` are ready for `POST /statements/sms`.

### Note for Workstream B (Summary & Score):
- In `backend/tests/test_score_summary.py`, `test_calculate_weekly_summary_single_week` asserts `operating_expenses > 20000.0` for date range `2026-09-01` to `2026-09-07`. The actual operating expenses in `mpesa_statement.csv` for that week total KSh 18,379.42 (Shop Rent: KSh 15,000, Bidco: KSh 2,479.42, Airtime: KSh 400, etc., while Owner Draw of KSh 8,500 is treated as an equity draw). Consider updating the assertion to `self.assertGreater(summary["operating_expenses"], 15000.0)`.
- Workstream B can now import `parse_csv_statement` and `categorize_batch` directly from `src.core.parser` and `src.core.categorizer` rather than using a mock helper.

---

## Workstream B: Financial Summary & Score Engine
- **Status:** Complete. 100% offline, pure Python with zero AWS/boto3 imports.
- **Owned Files:**
  - `backend/src/core/summary.py` (New File)
  - `backend/src/core/score_engine.py`
  - `backend/tests/test_score_summary.py`

### Implemented Interfaces

1. **`calculate_weekly_summary(transactions: List[Transaction], start_date: Optional[str] = None, end_date: Optional[str] = None, business_id: Optional[str] = None) -> WeeklySummary`**
   - Accurately filters transactions within optional `start_date` and `end_date` bounds.
   - Computes:
     - `gross_sales`: Total inbound transactions categorized as `SALES` or `DEBT_RECOVERY`.
     - `operating_expenses`: Total outbound transactions categorized as `INVENTORY`, `UTILITIES`, `RENT`, or `AIRTIME`. (Excludes `OWNER_DRAW` so shopkeeper equity withdrawals do not penalize operating margin).
     - `estimated_profit`: `gross_sales - operating_expenses`.
     - `profit_margin_pct`: `(estimated_profit / gross_sales) * 100` (safely returns 0.0 if `gross_sales == 0`).
     - `active_trading_days`: Distinct calendar dates with >= 1 sales transaction.
     - `transaction_count`: Total transactions in the window.
     - `expense_breakdown`: Itemized spend for `INVENTORY`, `RENT`, `UTILITIES`, `AIRTIME`.
     - `pulse_message`: Human-readable summary (e.g. *"You made KSh 38,450 this week, profit KSh 11,650."* or operating deficit message).
   - Returns a `WeeklySummary` dataclass instance matching `models.py`.

2. **`calculate_multi_week_series(transactions: List[Transaction], num_weeks: int = 4, reference_date: Optional[str] = None, business_id: Optional[str] = None) -> List[WeeklySummary]`**
   - Groups transactions into ISO calendar weeks ending at `reference_date` (or latest transaction date).
   - Generates a chronological trailing series of `WeeklySummary` models formatted for frontend chart visualization and API responses.
   - Gracefully handles cold-start empty transaction lists, single-week histories, and out-of-order timestamps.

3. **`compute_consistency_score(transactions: List[Transaction]) -> int`**
   - Pillar 1 (Max 30 pts): Income Consistency & Frequency.
   - Evaluates active trading days per week (>5 days/week = full points) and deposit regularity/frequency per active day.

4. **`compute_growth_score(weekly_summaries: List[Dict[str, Any]]) -> int`**
   - Pillar 2 (Max 25 pts): Revenue Volume & Growth.
   - Evaluates monthly turnover baseline (>KSh 40,000 for standard duka) and week-over-week revenue trajectory.

5. **`compute_margin_score(weekly_summaries: List[Dict[str, Any]]) -> int`**
   - Pillar 3 (Max 25 pts): Operating Margin & Expense Ratio.
   - Evaluates net operating margin `(Sales - Expenses) / Sales`. 15%–35% margin awards full 25 pts; negative margins clamped to 0.

6. **`compute_debt_recovery_score(debts: List[DebtRecord]) -> int`**
   - Pillar 4 (Max 20 pts): Debt Discipline & Recovery.
   - Returns neutral baseline 15/20 for zero-credit shops.
   - Evaluates recovery rate (`total_cleared / total_owed`), with deductions for delinquent debts older than 30 days.

7. **`generate_actionable_tips(consistency, growth, margin, debt, debts) -> List[str]`**
   - Produces 2–4 targeted, practical recommendations in Kenyan English addressing the lowest-performing scoring pillars.

8. **`calculate_biashara_score(business_id: str, transactions: List[Transaction], debts: List[DebtRecord]) -> BiasharaScoreResult`**
   - Assembles composite 4-pillar score (0–100), maps credit tier (`Gold`, `Silver`, `Bronze`, `Needs Improvement`), computes averages, and generates tips.

### Notes for Teammates & Workstreams

#### Note for Workstream D (Handlers & API):
- For `GET /summary/weekly`:
  Call `calculate_weekly_summary(transactions)` for `current_week` and `calculate_multi_week_series(transactions, num_weeks=weeks)` for `history_series`.
- For `GET /score` & `POST /score/calculate`:
  Call `calculate_biashara_score(business_id, transactions, debts)`.
- All methods return pure Python dataclasses / dicts that easily serialize into JSON matching `docs/API_CONTRACT.md`.

#### Note for Workstream C (Debts, PDF & SMS):
- `generate_lender_pdf` can pass `score_result` and `weekly_summaries` directly to ReportLab canvas.
- `build_weekly_sms_message` can consume metrics directly from `calculate_weekly_summary(transactions)` and `calculate_biashara_score(...)`.

---

## Workstream C: Debt Engine, Report Generator & SMS Client
- **Status:** Complete. 100% offline, pure Python with zero AWS/boto3 imports in `core/`.
- **Owned Files:**
  - `backend/src/core/debt_engine.py`
  - `backend/src/core/report_generator.py` (New File)
  - `backend/src/wrappers/sms_client.py`
  - `backend/tests/test_debt_report_sms.py`

### Implemented Interfaces

1. **`normalize_phone_number(phone: str) -> str`**
   - Standardizes Kenyan mobile numbers to international E.164 (`+254...`):
     - `0712345678` -> `+254712345678`
     - `0112345678` -> `+254112345678`
     - `254712345678` -> `+254712345678`
     - `+254712345678` -> `+254712345678`
     - `712345678` -> `+254712345678`
   - Resiliently strips whitespaces, hyphens, parentheses, and dots.

2. **`match_repayment_to_debt(tx: Transaction, open_debts: List[DebtRecord]) -> Optional[Tuple[DebtRecord, float]]`**
   - Inbound transaction reconciliation engine for "Kitabu ya Deni".
   - Only considers active debts with `balance_remaining > 0` and `status != CLEARED`.
   - Highest confidence: Normalized phone number extraction and matching against `debtor_phone`.
   - Secondary heuristic: Substring and token matching on debtor names combined with repayment intent keywords (`deni`, `debt`, `settled`, `cleared`, `repayment`).
   - Successfully matched sample CSV transaction `SK067BQRKW` (`Teacher Maina`) and verified clearing balance to 0.0.

3. **`apply_debt_repayment(debt: DebtRecord, payment_amount: float, receipt_number: str, payment_date: str, notes: str = "") -> DebtRecord`**
   - Safely decrements `balance_remaining` (capped at `0.0`).
   - Increments `amount_cleared` (capped at `amount_owed`).
   - Automatically transitions status (`CLEARED` if balance is `0.0`, `PARTIAL` if partially cleared, `UNPAID` otherwise).
   - Appends detailed transaction entry to `debt.repayment_history`.

4. **`calculate_debt_metrics(debts: List[DebtRecord]) -> Dict[str, Any]`**
   - Computes aggregate metrics for the Kitabu ya Deni overview:
     - `total_outstanding_amount`: Sum of remaining balances.
     - `total_cleared_amount`: Sum of recovered payments.
     - `recovery_rate_pct`: `(total_cleared / total_owed) * 100` (safely returns 0.0 if zero debts).
     - `unpaid_count`: Fully unpaid debts.
     - `delinquent_count`: Debts with overdue `due_date` and outstanding balance.
     - `total_debts_count`, `partial_count`, `cleared_count`.

5. **`generate_lender_pdf(business_profile, score_result, weekly_summaries, debt_summary) -> bytes`**
   - Generates a lender-ready single-page A4 PDF financial verification report.
   - Outputs valid binary PDF bytes (starts with `b"%PDF-1.4"`, size ~6.3 KB, well above the 3,000 bytes minimum).
   - Features full vector layout:
     - Brand headers and verification badge.
     - Business Identification & Store Details card.
     - Biashara Score badge, tier color styling, and 4-pillar breakdown.
     - Historical weekly cashflow performance table (trailing weeks).
     - Customer credit & Kitabu ya Deni discipline metrics.
     - Actionable improvement tips for lenders.
     - Loan officer / applicant legal sign-off and underwriting stamps.
   - Dual-engine design: Transparently uses ReportLab if installed; otherwise utilizes high-performance zero-dependency `PurePythonPDFBuilder` so it runs 100% offline out-of-the-box.

6. **`build_weekly_sms_message(owner_name, week_label, sales, expenses, profit, outstanding_debts, score, tier) -> str`**
   - Safaricom-compliant weekly SMS digest.
   - Format: *"Habari Mary! Biashara Score Summary for W36: Sales KSh 38,450, Expenses KSh 26,800, Est. Profit KSh 11,650. Outstanding Debts: KSh 3,200. Score: 78/100 (Silver). Keep growing!"*
   - Strictly enforces comma-formatted figures, clean integer rounding, and keeps character length <= 200 chars.

7. **`AfricaTalkingSMSClient.send_sms(phone_number, message) -> Dict[str, Any]`**
   - Dispatches SMS via Africa's Talking API.
   - In offline mock mode (`MOCK_AWS=true`), prints to stdout and returns standard simulated success envelope.

---

## Notes for Teammates & Workstreams

### Note for Workstream D (Handlers & API Scaffolding):
- **For `POST /debts`:**
  - Instantiate `DebtRecord` with:
    - `balance_remaining = amount_owed`
    - `amount_cleared = 0.0`
    - `status = DebtStatus.UNPAID`
    - `repayment_history = []`
- **For `GET /debts`:**
  - Fetch debts for `business_id` from database client.
  - Call `summary = calculate_debt_metrics(debts)` and return `{"business_id": business_id, "summary": summary, "debts": debts}`.
- **For `PATCH /debts/{debt_id}`:**
  - Retrieve existing debt record, call `apply_debt_repayment(debt, amount_to_clear, receipt_number, payment_date, notes)`.
  - Persist updated debt back to database client.
- **For `GET /reports/lender-pdf`:**
  - Call `generate_lender_pdf(business_profile, score_result, weekly_summaries, debt_summary)`.
  - Return `Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="Biashara_Score_Report.pdf"'})`.
- **For `POST /notifications/weekly-sms`:**
  - Call `build_weekly_sms_message(...)` and `sms_client.send_sms(recipient_phone, message)`.
- **For `POST /statements/upload` & `POST /statements/sms`:**
  - After categorizing transactions, iterate through inbound transactions and run `match_repayment_to_debt(tx, open_debts)`.
  - When matched, apply the repayment and set `tx.debt_matched_id = matched_debt.debt_id` and `tx.category = TransactionCategory.DEBT_RECOVERY`.

### Note for DevOps (Dev 4):
- `report_generator.py` works out-of-the-box with zero third-party dependencies using standard vector graphics operators in pure Python. If you want ReportLab in the production Lambda bundle, add `reportlab>=4.0.0` to `backend/requirements.txt`.
