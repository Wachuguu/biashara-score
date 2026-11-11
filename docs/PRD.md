# Product Requirements Document (PRD)
## Biashara Score — Micro-Business Financial Intelligence & Credit Scoring MVP

| Attribute | Details |
| :--- | :--- |
| **Project Name** | Biashara Score |
| **Sprint Duration** | 15 Days (MVP Delivery) |
| **Target Market** | Kenya (Nairobi MSMEs, Dukas, Groceries, Mini-marts) |
| **Tech Stack** | Next.js, Tailwind CSS, Python (AWS Lambda), DynamoDB, S3, Cognito, Amazon Bedrock, Africa's Talking |
| **Document Version** | 1.0 (Sprint Kickoff) |

---

## 1. Executive Summary & Problem Statement

### The Problem
Kenyan micro, small, and medium enterprises (MSMEs)—over 7.4 million businesses contributing 33% of GDP—operate almost entirely on mobile money (M-Pesa) and physical cash. 

1. **Lending Invisibility:** When shop owners approach microfinance institutions (MFIs) or commercial banks (e.g., Equity Bank, KCB, Musoni) for working capital loans, they are turned away because they lack audited financial statements, tax ledgers, and formal collateral.
2. **Untracked Customer Credit ("Kitabu ya Deni"):** Most duka owners sell essential goods to neighborhood regulars on credit, recording debts in fragile paper exercise books. Pages get torn, tea spills, or disputes arise. Duka owners lose 10%–25% of monthly revenue to forgotten or uncollected customer debts.
3. **Financial Blindness:** Duka owners rarely calculate their true net profit versus gross turnover. Money taken from the till for personal household expenses is mixed with store restocking capital.

### The Solution: Biashara Score
A mobile-first progressive web app designed for smartphone-wielding shopkeepers in Kenya. The shopkeeper uploads their M-Pesa CSV statement or pastes M-Pesa transaction SMS texts. In under two minutes, the system:
- Ingests and categorizes transactions into revenue, inventory, utilities, rent, and owner draw.
- Digitizes customer debts and reconciles debt repayments automatically.
- Computes the proprietary **Biashara Score (0–100)**—an objective, lender-ready creditworthiness index based on actual business cash flow.
- Generates a downloadable one-page **Lender-Ready Financial Report** PDF.
- Delivers automated weekly profit and cash flow updates via **Africa's Talking SMS**.

---

## 2. Target User Persona

### "Mama Mary" — Duka Owner in Kawangware, Nairobi
- **Profile:** 34 years old, runs "Mary's Family Provisions" selling maize flour, milk, cooking oil, soap, and snacks.
- **Tools:** Android smartphone (Tecno / Samsung A-series) with WhatsApp and Safaricom M-Pesa App / Till Number.
- **Pain Point:** Applied for a KSh 50,000 inventory expansion loan from a microfinance bank and was asked for "3 years of audited books". She relies on a battered paper notebook for KSh 18,000 in customer credit.
- **Goal:** Wants to know her real weekly profit, stop losing money to customer debts, and show lenders proof of reliable daily income.

---

## 3. Product Scope (15-Day MVP)

### 3.1 In-Scope Features

#### Feature 1: Statement Ingestion & Parsing
- **CSV Statement Upload:** Direct upload of standard Safaricom M-Pesa statements (PDF-to-CSV or standard M-Pesa web portal export).
- **SMS Paste Quick-Entry:** Text area allowing users to paste one or multiple M-Pesa SMS messages (e.g., *"SK01YUUM7K Confirmed. You have received Ksh1,600.00 from John Otieno..."*).
- **Local Pure-Python Parsing:** Deterministic extraction of receipt code, timestamp, counterparty, phone/till, transaction type, amount paid in, amount withdrawn, and running balance.

#### Feature 2: Hybrid Transaction Categorization
- **Layer 1 (Fast Rule-Based Engine):** Regex and keyword dictionary matching common Kenyan merchants and transaction formats:
  - *Sales:* Till payments, Paybill receipts, customer transfers.
  - *Inventory/Suppliers:* Brookside, Pembe, Unga, Bidco, Kapa, Farmer's Choice.
  - *Utilities:* KPLC Prepaid tokens, Nairobi Water (NWSC), WiFi/Data.
  - *Overhead:* Rent transfers to landlords, licenses.
  - *Owner Draw:* Personal withdrawals and transfers to personal numbers.
- **Layer 2 (Amazon Bedrock LLM Fallback):** Unclear or non-standard merchant names are sent to Amazon Bedrock (Claude 3 Haiku / Titan) with zero-shot categorization prompt to classify them into the standardized taxonomy.

#### Feature 3: Customer Debt Tracker ("Digital Kitabu")
- Add customer debts with name, phone number, amount owed, and goods taken.
- Automatic debt settlement suggestion when an inbound M-Pesa transfer matches a debtor's phone number or name note.
- Summary of total outstanding debts, average recovery time, and delinquent accounts (>30 days).

#### Feature 4: Weekly Business Pulse
- Clean, mobile-first dashboard showing:
  - Weekly Gross Revenue (Cash In)
  - Weekly Operating Expenses & Stock Restock (Cash Out)
  - Estimated Net Profit: `Gross Sales - (Inventory Restock + Utilities + Rent)`
  - Real-time notification: *"You made KSh 14,200 this week, profit KSh 3,100"*.

#### Feature 5: The Biashara Score (0–100) & Lender Report
- Transparent composite credit scoring algorithm evaluating 4 core pillars:
  1. **Income Consistency & Frequency (30%):** Daily/weekly active transaction regularity.
  2. **Revenue Volume & Growth (25%):** Sustained sales volume over 4+ weeks.
  3. **Expense Management & Margin (25%):** Healthy revenue-to-expense ratio (>15% net margin).
  4. **Debt Discipline & Recovery (20%):** Prompt collection of customer credit within 14 days.
- **Lender-Ready PDF Report:** One-click generated summary formatted for loan officers, including business identity, Biashara Score badge, 30-day turnover chart, average ticket size, and debt health breakdown.

#### Feature 6: Africa's Talking SMS Dispatch
- Scheduled weekly SMS digest dispatched every Sunday at 8:00 PM EAT:
  > *"Habari Mary! Biashara Score Summary for W36: Sales KSh 18,450, Expenses KSh 14,100, Est. Profit KSh 4,350. Outstanding Debts: KSh 3,200. Score: 78/100 (Strong). Keep it up!"*

---

### 3.2 Out of Scope for MVP (Explicit Guardrails)

To ensure high-quality delivery within 15 days by a 4-person team, the following are strictly excluded from the MVP:
1. **Direct Safaricom Daraja API Webhook Integration:** Registering shortcodes, obtaining production C2B/B2C credentials, and testing SSL handshakes takes 3–6 weeks with telco approvals. Ingestion is strictly CSV upload and SMS paste.
2. **Direct Loan Underwriting / In-App Disbursals:** Biashara Score is an analytical and scoring tool, not a licensed lending balance sheet. We provide the lender report; the user takes it to existing lenders.
3. **Inventory Barcode Scanning & Hardware POS:** No thermal printer drivers, barcode camera scanners, or RFID hardware.
4. **Multi-Currency / Cross-Border Support:** Restricted strictly to Kenyan Shillings (KSh) and Safaricom M-Pesa.
5. **Native Mobile App Stores (APK / iOS App Store):** The product is a responsive Next.js Progressive Web App (PWA) installable to Android home screens via Chrome.

---

## 4. User Stories

| ID | As a... | I want to... | So that... | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- |
| **US-01** | Duka Owner | Upload my M-Pesa CSV statement | My transactions are imported without manual typing | Upload file (<5MB), parse within 3 seconds, preview first 5 rows with total count. |
| **US-02** | Duka Owner | Paste recent M-Pesa SMS messages | Today's sales are logged immediately | Textarea accepts pasted text, regex parses receipt code, amount, and sender name. |
| **US-03** | Duka Owner | Have my transactions auto-categorized | I don't have to categorize 100+ transactions manually | Known suppliers/utilities categorized automatically; unknown ones resolved via Bedrock fallback. |
| **US-04** | Duka Owner | Log a customer who took milk & sugar on credit | I don't forget how much they owe me | Enter debtor name, phone, amount; appears in the "Kitabu ya Deni" table with status "Unpaid". |
| **US-05** | Duka Owner | Receive an automatic alert when a debtor sends money | The debt is marked as cleared without manual math | Inbound transfer matching debtor phone/name updates debt status to "Cleared" or "Partially Paid". |
| **US-06** | Duka Owner | See my weekly sales, expenses, and estimated profit | I know if my shop is growing or losing money | Clear card displaying weekly totals in KSh with clean visual indicators. |
| **US-07** | Duka Owner | View my Biashara Score (0–100) and how to improve it | I know if I qualify for a microfinance loan | Gauge meter showing score, tier (Needs Improvement, Fair, Good, Excellent), and actionable tips. |
| **US-08** | Duka Owner | Download a PDF report of my business performance | I can take it to my local bank/SACCO loan officer | Clean, single-page PDF with shop name, date range, score, revenue charts, and verified stamp. |
| **US-09** | Duka Owner | Get a weekly SMS update on Sunday evening | I stay updated on my business without opening the app | Africa's Talking SMS delivered to owner's phone with weekly turnover, profit, and debt total. |

---

## 5. 15-Day Delivery Schedule (4-Person Team)

```
[Day 1-3]   Scaffolding, Schema Design, Local Mock Engines, Sample Data (All 4)
[Day 4-6]   Parser & Categorizer (Dev 1), Kitabu ya Deni (Dev 2), UI Components (Dev 3), SAM/Infra (Dev 4)
[Day 7-9]   Score Algorithm (Dev 1), Bedrock Wrapper (Dev 2), Dashboard Screens (Dev 3), API Gateway (Dev 4)
[Day 10-12] Africa's Talking Integration (Dev 1 & 4), PDF Report Gen (Dev 2), E2E UI Flow (Dev 3)
[Day 13-14] Integration Testing, Bug Bash, Sample Dataset Verification, Deploy to Staging (All 4)
[Day 15]    Final Demo, Lender Report Showcase, Video Walkthrough, Code Freeze
```

---

## 6. Success Metrics for MVP
- **Parse Accuracy:** >98% accuracy on standard Safaricom M-Pesa CSV statements.
- **Categorization Speed:** <2 seconds for 150 transactions using rule engine (<5 seconds if Bedrock fallback is invoked).
- **Local Dev Usability:** 100% of core unit tests pass locally on a developer laptop without AWS credentials.
- **Score Explainability:** Duka owner can clearly understand the 4 components contributing to their score.
- **SMS Delivery Rate:** 100% simulated/sandbox delivery through Africa's Talking API.
