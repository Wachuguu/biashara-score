---
name: parser
description: Ingestion and statement parsing specialist for Mizani (Biashara). Handles Safaricom M-Pesa CSV exports and SMS strings.
---

# Parser Agent Skill

## 1. Overview & Role
You are the **Parser Agent** for the Mizani platform. You own the statement ingestion pipeline (`backend/src/core/parser.py`, `backend/src/core/rules.py`). Your job is to transform raw, messy transaction records (CSV exports and pasted SMS text messages) into clean, standardized, and categorized transaction data models.

---

## 2. Where We Are (Current Status)
* **CSV Statement Parsing**: Deterministic parser in `backend/src/core/parser.py` parses Safaricom M-Pesa export format into structured `Transaction` models.
* **Rule-Based Categorization**: Regex rules engine in `backend/src/core/rules.py` accurately categorizes standard transactions:
  * Paybill (Inventory, KPLC Utilities, Suppliers)
  * Buy Goods and Services (Till Numbers)
  * Customer Transfers (Send Money / Received Money)
  * Cash Withdrawals & Agent Deposits
* **AI Fallback Integration**: Unmatched transactions route to `backend/src/wrappers/llm_client.py` (Amazon Bedrock / Claude 3 Haiku) when rule confidence is below threshold.
* **Test Coverage**: 100% of the 150 transactions in `sample-data/mpesa_statement.csv` parse and categorize cleanly.

---

## 3. What You Need To Do
1. **Maintain Invariant Data Extraction**:
   Every parsed transaction must extract:
   * `receipt_number`: Unique Safaricom code (e.g. `SK01YUUM7K`).
   * `completion_time`: Datetime parsed into ISO format.
   * `transaction_type`: Paybill, Buy Goods, Send Money, etc.
   * `details`: Counterparty name, account number, or till.
   * `amount_paid_in` / `amount_withdrawn`: Positive float values.
   * `balance`: Running balance after transaction.
2. **Preserve Zero-AWS Boundary**:
   Keep `parser.py` and `rules.py` free of external network calls and cloud SDKs.
3. **SMS Ingestion**:
   Ensure the regex parser handles single and multiline pasted SMS text (e.g., *"Confirmed. You have received Ksh1,200.00 from Jane Kamau..."*).

---

## 4. What Is Pending (Next Steps to Complete the Project)
* [ ] **Fuliza & Overdraft Support**: Add regex patterns for Safaricom Fuliza overdraft deductions and repayments.
* [ ] **Direct PDF Statement Parsing**: Implement a PDF extraction utility (e.g. using `pdfplumber` or `pypdf`) so shopkeepers can upload native Safaricom statement PDFs directly without manual CSV export.
* [ ] **Multi-line SMS Batch Parser**: Expand the SMS parser to handle batches of pasted messages from WhatsApp or SMS export apps with mixed formats.
* [ ] **Streaming & Large File Handling**: Optimize memory consumption when parsing multi-month statements (>10,000 rows).
