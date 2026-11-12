# Biashara Score 🇰🇪
> **Financial intelligence, automated debt recovery, and lender-ready credit scoring for Kenyan micro-businesses.**

[![Status: Sprint in progress](https://img.shields.io/badge/Status-Sprint%20in%20progress-orange.svg)](#)
[![Team: 4 Engineers](https://img.shields.io/badge/Team-4%20Engineers-blue.svg)](#team-and-ownership)
[![Deadline: 26 Nov 2026](https://img.shields.io/badge/Deadline-26%20Nov%202026%20(14%20Days%20Left)-red.svg)](#timeline)

Welcome team! This is our single source of truth for building and delivering **Biashara Score** on AWS by **26 November 2026**. Please read this document from top to bottom before touching any code.

---

## 1. Project Overview & Pitch

Biashara Score is a mobile-first web app that transforms raw M-Pesa statements and SMS messages into real-time business profit metrics, digitizes customer debts, calculates an objective 0–100 creditworthiness score, and sends weekly performance summaries via SMS. We give informal duka owners the financial visibility they need to stop leaking cash and qualify for formal loans.

---

## 2. The Problem

Over 7.4 million micro and small enterprises in Kenya operate primarily on cash and Safaricom M-Pesa. Because they run their businesses without formal accounting software or audited financial records, commercial banks and SACCOs reject up to 85% of their loan applications. At the same time, shopkeepers routinely lose between 10% and 25% of their monthly earnings because they lack simple stock tracking and give out goods on informal credit recorded in flimsy paper notebooks—known locally as the *"kitabu ya deni"*. When pages tear, get stained, or customers move away, that money vanishes.

### Meet "Mama Mary" (Our Target User Persona)
Mama Mary is a 34-year-old shopkeeper who runs "Mary's Family Provisions," a small retail grocery duka in Kawangware, Nairobi. She sells essential staples like maize flour, milk, cooking oil, and soap, accepting payments through cash and an M-Pesa Buy Goods Till number. Last month, she applied for a KSh 50,000 working capital loan to restock ahead of the holiday season, but the microfinance bank turned her down because she could not provide 3 years of audited accounts or formal collateral. Meanwhile, she has over KSh 18,000 in uncollected customer debts scattered across a battered exercise book that she struggles to reconcile with incoming phone payments. Mary does not know her exact weekly net profit after paying suppliers, rent, and electricity tokens, and she desperately needs a simple way to prove her business is healthy and growing.

---

## 3. Our Solution

Biashara Score gives Mama Mary complete financial visibility on her smartphone without requiring any manual bookkeeping. Here is how it works:

```
+--------------------------------------------------------------------------------------------------+
|                                    HOW BIASHARA SCORE WORKS                                      |
+--------------------------------------------------------------------------------------------------+
|  1. Ingest      -->  Upload M-Pesa statement (CSV) or paste recent transaction SMS texts.        |
|  2. Categorize  -->  Auto-sort into Sales, Inventory, Utilities, Rent, and Owner Draw.          |
|  3. Track Debts -->  Digitize the "Kitabu ya Deni" and auto-reconcile repayments from customers. |
|  4. Weekly Pulse-->  Show clear profit: "You made KSh 14,200 this week, profit KSh 3,100".       |
|  5. Score (0-100)--> Calculate Biashara Score across consistency, volume, margins, & recovery.   |
|  6. Report      -->  Generate a 1-page downloadable, lender-ready PDF report for loan officers.  |
|  7. Weekly SMS  -->  Send an automated Sunday evening digest directly to the owner's phone.     |
+--------------------------------------------------------------------------------------------------+
```

1. **Upload or Paste:** The shopkeeper uploads their standard Safaricom M-Pesa CSV statement or pastes raw M-Pesa SMS messages into the app.
2. **Parse & Categorize:** The backend parses transaction dates, receipts, amounts, and counterparties. It runs a fast keyword-rule engine first, then calls Amazon Bedrock (Claude 3 Haiku) as an AI fallback for unfamiliar merchant names.
3. **Track Debts:** The digital "Kitabu ya Deni" logs customer credit (name, phone, amount, items) and automatically flags matching incoming M-Pesa transfers to mark debts as partially or fully settled.
4. **Weekly Financial Summary:** The dashboard displays instant weekly figures: *"You made KSh 14,200 this week, profit KSh 3,100"*.
5. **Calculate Biashara Score (0–100):** An objective creditworthiness score is calculated based on income regularity, sales volume, operating expense margin, and debt collection rate.
6. **Download Lender Report:** A single-page PDF report summarizes turnover, score tier (Gold, Silver, Bronze), and debt discipline for bank loan officers.
7. **Weekly SMS Notification:** Every Sunday at 8:00 PM EAT, an automated SMS is dispatched via Africa's Talking with weekly turnover, profit, and outstanding credit totals.

---

## 4. MVP Scope: What We Are Building vs What We Are NOT Building

We have only 14 days to deliver. To guarantee we launch on time, our scope boundaries are strict and copied directly from our [PRD](docs/PRD.md).

### What We ARE Building in this MVP
- **CSV Statement Upload & Parsing:** Support for standard Safaricom M-Pesa CSV exports (using our 150-row sample dataset as the baseline).
- **SMS Paste Textarea:** Quick entry where users paste raw M-Pesa SMS messages to capture immediate daily sales.
- **Rule-Based Categorizer with Bedrock Fallback:** Regex engine for major Kenyan suppliers (Brookside, Pembe, Unga, Bidco), utilities (KPLC Prepaid, Nairobi Water), rent, and airtime, falling back to Amazon Bedrock for ambiguous names.
- **Digital Kitabu ya Deni (Debt Ledger):** Record customer name, phone number, amount owed, and description; auto-match incoming customer transfers.
- **Weekly Profit Dashboard:** Simple mobile-first cards showing cash in, inventory out, utilities/rent out, and estimated net profit.
- **Biashara Score Algorithm (0–100):** Four evaluated pillars (30 pts consistency, 25 pts volume, 25 pts margin, 20 pts debt recovery).
- **Downloadable Lender PDF:** One-click clean PDF summarizing cashflow and score badge.
- **Africa's Talking SMS Integration:** Scheduled weekly digest message sent to the duka owner's phone.

### What We Are NOT Building (Out of Scope)
- ❌ **Direct Safaricom Daraja API Integration:** *Why it's cut:* Applying for Paybill/Till shortcodes, obtaining production credentials, and completing telco KYC approvals takes between 3 to 6 weeks. Waiting for Daraja would kill our 14-day timeline. Statement upload and SMS paste are instant and require zero approvals.
- ❌ **WhatsApp Chatbot Integration:** *Why it's cut:* Meta Business verification and WhatsApp Cloud API approvals take 2 to 4 weeks, with strict messaging template restrictions. We use Africa's Talking SMS instead, which works on any Kenyan phone immediately.
- ❌ **Direct Loan Underwriting & Money Disbursal:** *Why it's cut:* We are not a licensed financial institution. We compute the score and generate the report; the shopkeeper takes the report to their bank or SACCO.
- ❌ **Hardware POS & Barcode Scanners:** *Why it's cut:* We are building pure software for existing mobile phones, not hardware device drivers.
- ❌ **Multi-Currency & International Payments:** *Why it's cut:* Exclusively Kenyan Shillings (KSh) and Safaricom M-Pesa.
- ❌ **Native App Store Binaries (iOS/Android APKs):** *Why it's cut:* We are building a mobile-responsive Progressive Web App (PWA) using Next.js and Tailwind, accessible immediately via mobile browser without app store review delays.

---

## 5. System Architecture & The "Zero-AWS" Local Rule

### Architecture Diagram

```
+-------------------------------------------------------------------------------+
|                       Next.js 14 + Tailwind PWA (Mobile)                      |
|                                 (AWS Amplify)                                 |
+---------------------------------------+---------------------------------------+
                                        | HTTPS / REST + Cognito JWT
                                        v
+-------------------------------------------------------------------------------+
|                        Amazon API Gateway (HTTP APIs)                         |
+---------------------------------------+---------------------------------------+
                                        |
     +----------------------------------+----------------------------------+
     |                                  |                                  |
     v                                  v                                  v
+-----------------------+   +-----------------------+   +-----------------------+
| Upload & Parse Lambda |   | Categorize & Score    |   | Debt Tracker Lambda   |
| (backend/src/handlers)|   | Lambda                |   | (backend/src/handlers)|
+-----------+-----------+   +-----------+-----------+   +-----------+-----------+
            |                           |                           |
            +---------------------------+---------------------------+
                                        |
         +-----------------+------------+------------+-----------------+
         |                 |                         |                 |
         v                 v                         v                 v
+-----------------+ +---------------+       +-----------------+ +---------------+
| Amazon DynamoDB | |   Amazon S3   |       | Amazon Bedrock  | | EventBridge   |
| (3 Tables: Biz, | | (CSV Uploads  |       | (Claude 3 Haiku | | (Sunday Cron) |
|  Tx, Debts)     | |  & Reports)   |       |  Fallback)      | +-------+-------+
+-----------------+ +---------------+       +-----------------+         |
                                                                        v
                                                              +-----------------+
                                                              | Africa's Talking|
                                                              |  (SMS Gateway)  |
                                                              +-----------------+
```

### AWS Services Breakdown

| AWS Service | What We Use It For | Who Touches It |
| :--- | :--- | :--- |
| **AWS Amplify** | Hosting the Next.js 14 frontend and continuous git preview deployments | **[NAME 3]** (Frontend Lead) & **[NAME 4]** (Deployer) |
| **Amazon Cognito** | Duka owner phone/email sign-up, login, and JWT token issuance | **[NAME 4]** (Deploys user pool), **[NAME 3]** (Calls in UI) |
| **Amazon API Gateway** | HTTP REST endpoints connecting the frontend to Lambda functions | **[NAME 4]** (Provisions in SAM template) |
| **AWS Lambda** | Serverless Python 3.11 execution for upload, parsing, scoring, and debt APIs | **[NAME 4]** (Packaging & SAM wiring) |
| **Amazon DynamoDB** | Fast NoSQL storage across 3 tables (`businesses`, `transactions`, `debts`) | **[NAME 4]** (Provisions), accessed via `db_client.py` |
| **Amazon S3** | Storage bucket for uploaded M-Pesa CSVs and generated lender PDF reports | **[NAME 4]** (Provisions), accessed via `s3_client.py` |
| **Amazon Bedrock** | Claude 3 Haiku model to classify ambiguous merchant transaction descriptions | Called via `llm_client.py` wrapper |
| **Amazon EventBridge**| Scheduled cron rule (`cron(0 17 ? * SUN *)`) triggering weekly SMS digest | **[NAME 4]** (Provisions in SAM) |

### 🚨 The Golden Rule: Pure Core Logic & Mockable Wrappers
We share **one AWS account that only ONE person ([NAME 4]) deploys to**. Therefore:
1. **Zero AWS Imports in Core Logic:** Modules inside `backend/src/core/` (`parser.py`, `categorizer.py`, `score_engine.py`, `debt_engine.py`) are **100% pure Python**. They must NEVER import `boto3` or make network calls.
2. **Thin Wrappers:** All AWS and external service interactions live inside `backend/src/wrappers/` (`db_client.py`, `s3_client.py`, `llm_client.py`, `sms_client.py`).
3. **Local Offline Mode (`MOCK_AWS=true`):** In local development, the wrappers automatically mock DynamoDB in memory, read CSV statements from disk, return deterministic categories for Bedrock, and print SMS messages to the terminal. 
4. **Result:** Devs 1, 2, and 3 can develop, run tests, and verify code locally without an AWS account, without IAM credentials, and without incurring cloud charges!

---

## 6. Tech Stack

| Layer / Tool | Technology | Why We Chose It |
| :--- | :--- | :--- |
| **Frontend Framework** | **Next.js 14 (App Router)** | Industry standard for mobile-first web applications, fast routing, and clean React server/client component separation. |
| **Styling** | **Tailwind CSS** | Fast, utility-first CSS allowing rapid construction of clean, mobile-optimized UI cards and responsive tables. |
| **Icons & UI** | **Lucide React** | Lightweight, modern icon set for status badges, scores, and navigation. |
| **Backend Language** | **Python 3.11** | Clean, fast data parsing with standard libraries, rich financial math support, and universal team familiarity. |
| **Unit Testing** | **pytest / unittest** | Built-in test execution; runs 100% offline in under 0.1 seconds without any external dependencies. |
| **Cloud Infrastructure** | **AWS SAM (Serverless Application Model)** | Declarative CloudFormation abstraction that makes serverless DynamoDB, S3, and Lambda definitions simple and repeatable. |
| **Database** | **Amazon DynamoDB (On-Demand)** | Pay-per-request pricing, zero server maintenance, sub-10ms response times for duka transactions. |
| **AI Fallback** | **Amazon Bedrock (Claude 3 Haiku)** | Near-instant latency and fractions of a cent per query for zero-shot text classification of unknown Kenyan business names. |
| **SMS Gateway** | **Africa's Talking API** | The gold standard for Kenyan mobile telco SMS dispatch with free sandbox testing and reliable local delivery. |

---

## 7. Repository Map

Below is our complete file tree. Every file has an explicit status tag so everyone knows what is completed, what is a stub, and what is waiting to be built:

```
biashara-score/
├── .env.example                          # Done: Environment variable template with MOCK_AWS=true enabled
├── .gitignore                            # Done: Strict git ignore (prevents committing AWS keys or .env)
├── README.md                             # Done: This document (onboarding guide & sprint master plan)
├── docs/
│   ├── ARCHITECTURE.md                   # Done: AWS architecture, DynamoDB schema, and scoring formula
│   ├── PRD.md                            # Done: Product requirements, user stories, and MVP scope limits
│   └── TEAM_WORKFLOW.md                  # Done: Git workflow, branch protocol, and single-deployer rules
├── sample-data/
│   └── mpesa_statement.csv               # Done: 150 realistic fake transactions for a Nairobi duka
├── infra/
│   └── template.yaml                     # Done: Starter AWS SAM template (DynamoDB, S3, API Gateway)
├── backend/
│   ├── requirements.txt                  # Done: Production dependencies (pydantic, boto3, requests)
│   ├── requirements-dev.txt              # Done: Local testing dependencies (pytest, black, flake8)
│   ├── src/
│   │   ├── __init__.py                   # Done: Python package marker
│   │   ├── core/
│   │   │   ├── __init__.py               # Done: Python package marker
│   │   │   ├── models.py                 # Done: Shared pure Python dataclasses and Enums
│   │   │   ├── parser.py                 # Stub (needs implementing): CSV & SMS parsing functions
│   │   │   ├── categorizer.py            # Stub (needs implementing): Rule categorizer & Bedrock fallback
│   │   │   ├── score_engine.py           # Stub (needs implementing): 4-pillar 0-100 Biashara score
│   │   │   └── debt_engine.py            # Stub (needs implementing): Debt tracker & payment reconciliation
│   │   ├── wrappers/
│   │   │   ├── __init__.py               # Done: Python package marker
│   │   │   ├── db_client.py              # Done: DynamoDB wrapper with local in-memory fallback
│   │   │   ├── s3_client.py              # Done: S3 storage wrapper with local CSV fallback
│   │   │   ├── llm_client.py             # Done: Bedrock wrapper with deterministic local mock
│   │   │   └── sms_client.py             # Done: Africa's Talking wrapper with terminal stdout mock
│   │   └── handlers/
│   │       └── .gitkeep                  # Empty: Lambda handler entry points (Not built yet)
│   └── tests/
│       ├── __init__.py                   # Done: Python package marker
│       └── test_local_workflow.py        # Done: 4 passing unit tests verifying local mock wrappers
└── frontend/
    └── .gitkeep                          # Empty: Next.js 14 frontend directory (Not built yet)
```

---

## 8. Team and Ownership

To avoid stepping on each other's toes during our 14-day sprint, **each person strictly owns their files and modules**. 

> **TEAM RULES:**
> 1. **Do not edit another teammate's files** without discussing it with them first.
> 2. **`backend/src/core/models.py` is shared:** If you need to add an attribute to `Transaction` or `DebtRecord`, submit a tiny, dedicated pull request and notify the team group chat before merging.

| Teammate | Role & Domain | Files Owned | Specific Tasks & Responsibilities | "Done When" Verification Test |
| :--- | :--- | :--- | :--- | :--- |
| **[YOUR NAME]**<br>*(Team Lead)* | **Backend:** Debt Engine, SMS, PDF Report | • `backend/src/core/debt_engine.py`<br>• `backend/src/wrappers/sms_client.py`<br>• `backend/src/core/report_gen.py` (to create)<br>• `docs/*` | • Implement `match_repayment_to_debt`<br>• Reconcile inbound payments with debtor phone/name<br>• Generate lender-ready PDF summary<br>• Wire Africa's Talking payload formatting | `python -m unittest tests/test_debt_engine.py` passes with test cases for partial, full, and unmatched repayments. PDF generates cleanly to `/tmp/report.pdf`. |
| **Ondigo** | **Backend:** Parser, Categorizer, Score Engine | • `backend/src/core/parser.py`<br>• `backend/src/core/categorizer.py`<br>• `backend/src/core/score_engine.py`<br>• `backend/tests/test_parser.py` (to create) | • Parse `sample-data/mpesa_statement.csv`<br>• Parse raw SMS message strings<br>• Build regex categorizer for Kenyan merchants<br>• Implement 4-pillar Biashara Score formula | `python -m unittest tests/test_parser.py` parses all 150 sample rows with 0 errors and calculates expected score (e.g. 78/100) deterministically. |
| **[NAME 3]** | **Frontend:** Next.js & Tailwind PWA | • Entire `frontend/` directory<br>• `frontend/src/components/*`<br>• `frontend/src/app/*` | • Initialize Next.js 14 with Tailwind<br>• Mobile-first statement upload screen<br>• SMS paste quick-entry box<br>• Weekly profit cards & score gauge<br>• Digital Kitabu ya Deni table & add-debt modal | Frontend boots via `npm run dev`, renders smoothly on mobile viewport (375px width), and uploads CSV to API Gateway. |
| **[NAME 4]**<br>*(AWS Account Holder)* | **DevOps & Cloud:** Infrastructure & Deployment | • `infra/template.yaml`<br>• `backend/src/handlers/*`<br>• IAM & deployment config | • Provision DynamoDB, S3, API Gateway via SAM<br>• Package Python Lambdas with dependencies<br>• Configure EventBridge Sunday cron rule<br>• Deploy staging environment and provide API URL | `sam build && sam deploy` executes with 0 errors; API Gateway returns `200 OK` on healthcheck and `/upload` endpoints. |

---

## 9. Dependencies Between Tasks (Critical Path)

Nobody should sit blocked or wait in silence. Here is the dependency chain:

```
[Day 1-2]: Ondigo builds CSV/SMS Parser in core/parser.py
      │
      ├──> [Day 3]: [NAME 4] needs parsed schema to write Lambda handlers in src/handlers/
      ├──> [Day 3]: Ondigo builds Categorizer & Score Engine on top of parsed Transaction models
      └──> [Day 4]: [YOUR NAME] builds Debt Engine to match repayments against parsed transactions
            │
            └──> [Day 5-6]: [NAME 3] connects Frontend forms to API Gateway once handlers are ready
```

1. **The CSV Parser is our #1 bottleneck:** Ondigo must complete and merge `backend/src/core/parser.py` by **Day 2 (13 Nov)**. Everyone else builds on top of the `Transaction` objects it produces.
2. **Lambda Handlers depend on Core Logic:** **[NAME 4]** should not deploy Lambda handlers until the pure logic functions return expected dataclasses.
3. **Frontend can use Mock JSON:** **[NAME 3]** does not need to wait for the live API Gateway! You can build the entire UI using mock JSON responses matching `backend/src/core/models.py`.

---

## 10. Getting Started in 10 Minutes (Beginner Guide)

Follow these steps to get the project running locally on your computer.

### Prerequisites
- **Git** installed on your machine.
- **Python 3.11+** (`python3 --version` or `python --version`).
- **Node.js 18+** (`node --version`).

### Step-by-Step Setup

#### 1. Clone the Shared Repository
```bash
git clone https://github.com/Wachuguu/biashara-score.git
cd biashara-score
```

#### 2. Create Your Local Environment File
```bash
# On Mac / Linux:
cp .env.example .env

# On Windows (Command Prompt):
copy .env.example .env

# On Windows (PowerShell):
Copy-Item .env.example .env
```
*(Notice that `MOCK_AWS=true` is set by default in `.env`. Leave it as `true`!)*

#### 3. Set Up Python Backend & Run Tests
```bash
# On Mac / Linux:
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements-dev.txt

# On Windows:
python -m venv venv
venv\Scripts\activate
pip install -r backend/requirements-dev.txt
```

Verify your local setup by running the test suite:
```bash
# Run with pytest:
python -m pytest backend/tests -v

# Or run with Python's built-in unittest:
python -m unittest discover -s backend/tests -v
```
**Expected Result:** `Ran 4 tests in 0.002s ... OK` (4 passed, 0 failed).

#### 4. Frontend Setup (When Initialized by [NAME 3])
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser. Toggle Chrome DevTools into **Device Mode (iPhone / Pixel view)** to test the mobile layout.

### Troubleshooting Common Setup Errors

- **Error: `No module named pytest`**
  - *Fix:* Ensure your virtual environment is active (`(venv)` shown in terminal prompt), or simply run `python -m unittest discover -s backend/tests` which requires no third-party packages.
- **Error: `FileNotFoundError: sample-data/mpesa_statement.csv`**
  - *Fix:* Always run tests from the repository root directory (`biashara-score`), or ensure `LOCAL_SAMPLE_DATA_PATH` in your `.env` points to the correct relative path.
- **Error: `Cannot find module ... in frontend`**
  - *Fix:* Run `cd frontend && npm install`. Note that full frontend initialization will be committed by **[NAME 3]** during Phase 1.
- **Error: `AWS credentials not found`**
  - *Fix:* Check your `.env` file and make sure `MOCK_AWS=true`. You should NOT need AWS credentials for local development.

---

## 11. Git Workflow & Branching Guidelines

To prevent merge nightmares, we work in **one shared GitHub repository** (`Wachuguu/biashara-score`) using short-lived feature branches.

> **CRITICAL SECURITY RULE:**
> **Never commit `.env` or AWS keys to git.** Always run `git status` before committing to ensure no secret files or `.pem` keys are staged.

### Branch Naming Convention
Every branch must start with your domain prefix:
- `feat/parser-csv-ondigo` (Ondigo - Parser features)
- `feat/debt-reconciliation-[YOUR-NAME]` ([YOUR NAME] - Debt tracker)
- `feat/ui-mobile-dashboard-[NAME-3]` ([NAME 3] - Frontend screens)
- `infra/sam-api-gateway-[NAME-4]` ([NAME 4] - Infrastructure)
- `fix/date-format-bug` (Bug fixes)

### Daily Git Commands
```bash
# 1. Start each morning by updating your local main
git checkout main
git pull origin main

# 2. Create your feature branch
git checkout -b feat/your-feature-name

# 3. Code, run tests, and stage your changes
python -m unittest discover -s backend/tests
git status
git add <files-you-changed>

# 4. Commit with a clear, descriptive message
git commit -m "feat(parser): add regex parsing for Safaricom Till buy goods transactions"

# 5. Push to GitHub
git push -u origin feat/your-feature-name
```

### Pull Request (PR) & Merge Rules
1. Open a PR from your feature branch against `main` on GitHub.
2. Fill in the PR description: What changed, and proof that local tests pass.
3. Request a review from at least **1 teammate**.
4. Once approved, use **Squash and Merge** into `main` and delete your feature branch.

---

## 12. AWS Access & Security Rules

- **One Shared Account:** The AWS account is owned and maintained by **[NAME 4]**.
- **Individual IAM Users:** If you need read-only AWS Console access to inspect DynamoDB tables or CloudWatch logs, **[NAME 4]** will create an IAM user for you with Multi-Factor Authentication (MFA).
- **Single Deployer:** **Only [NAME 4] runs `sam deploy`**. No other teammate deploys to AWS.
- **Zero Secrets in Chat:** Never paste AWS Access Keys, Secret Keys, or passwords into WhatsApp, Slack, or GitHub issues.
- **Billing Guardrail:** A cloud budget and billing alarm of **$15 USD** is activated on the AWS account. Because our stack is serverless and on-demand, running our MVP costs under $2.

---

## 13. Using Antigravity (AI Coding Assistant)

When using Antigravity to pair-program on your assigned tasks, guide it with strict context to keep code aligned with our architecture:

1. **Grounding:** Always instruct Antigravity to read `README.md`, `docs/`, and `backend/src/core/models.py` before generating code.
2. **File Ownership:** Explicitly tell Antigravity to only modify the files assigned to your role in the Team Ownership table.
3. **Verify Locally:** Have Antigravity run `python -m unittest discover -s backend/tests` to prove all tests pass before making any commit.

### Copy-Paste Opening Prompt for Teammates
Copy and paste this exact prompt when starting a session with Antigravity:

```text
I am working on the Biashara Score MVP as [YOUR ROLE / NAME].
First, read README.md, docs/PRD.md, docs/ARCHITECTURE.md, and backend/src/core/models.py.
I am specifically working on [TASK / FEATURE] in [FILE PATH].
Strict rules:
1. Do not touch or modify files owned by my teammates.
2. Keep core logic 100% pure Python with ZERO AWS / boto3 imports.
3. Write clean unit tests and execute them to verify everything passes before finalizing.
```

---

## 14. Daily Team Routine

To maintain momentum over our 14-day sprint:

- **15-Minute Daily Standup:** Every morning at **9:00 AM EAT** (on Google Meet / WhatsApp Call).
  1. *What did I complete yesterday?* (Must be a merged PR or passing test suite)
  2. *What am I delivering today?*
  3. *What is blocking me?*
- **Where to Ask for Help:** Post in our team WhatsApp group. If you are stuck on a bug or interface mismatch for more than 45 minutes, ping the team immediately—do not wait for the next day's standup!

---

## 15. Timeline & Countdown (12 Nov – 26 Nov 2026)

| Date | Days Left | [YOUR NAME]<br>*(Backend Lead)* | Ondigo<br>*(Parser & Score)* | [NAME 3]<br>*(Frontend Lead)* | [NAME 4]<br>*(AWS DevOps)* | Milestone Status |
| :--- | :---: | :--- | :--- | :--- | :--- | :--- |
| **12 Nov** *(Today)* | 14 | Project onboarding; setup review | Complete `parser.py` CSV logic | Scaffold Next.js 14 + Tailwind PWA | Verify SAM template; setup IAM users | 🟡 In Progress |
| **13–14 Nov** | 12 | Implement `debt_engine.py` core | Build `categorizer.py` (rules) | Build Mobile Upload & SMS screens | Deploy DynamoDB & S3 via SAM | ⚪ Upcoming |
| **15–16 Nov** | 10 | Payment-to-debt reconciliation | Complete `score_engine.py` | Build Weekly Profit dashboard cards | Write `UploadStatementHandler` Lambda | ⚪ Upcoming |
| **17–18 Nov** | 8 | Build `llm_client.py` Bedrock hook | Write unit tests for score engine | Build "Kitabu ya Deni" table & modal | Wire API Gateway routes to Lambdas | ⚪ Upcoming |
| **19–20 Nov** | 6 | Integrate Africa's Talking SMS API | End-to-end local data testing | Build Biashara Score gauge meter | Configure EventBridge weekly cron | ⚪ Upcoming |
| **21–22 Nov** | 4 | Build PDF report generator | Edge case tuning on 150 CSV rows | Connect Frontend to API Gateway | End-to-end cloud integration test | ⚪ Upcoming |
| **23–24 Nov** | 2 | End-to-end system testing | Bug fixes & score calibration | Polish UI, mobile animations & PWA | Load test & staging dry-run | ⚪ Upcoming |
| **25 Nov** | 1 | Pre-demo rehearsal & slide deck | Help with demo data verification | Final UI polish & offline fallback | Freeze deployments; backup demo data | ⚪ Upcoming |
| **26 Nov** | **0** | **FINAL MVP DEMO DAY** 🚀 | **FINAL MVP DEMO DAY** 🚀 | **FINAL MVP DEMO DAY** 🚀 | **FINAL MVP DEMO DAY** 🚀 | 🎯 Target Demo |

---

## 16. Definition of Done & 5-Minute Demo Plan

### Definition of Done (DoD) for MVP
A feature is only considered "Done" when:
- [x] Code is written and conforms to the repository architecture (pure core logic vs. wrappers).
- [x] Unit tests pass locally with `MOCK_AWS=true` using `sample-data/mpesa_statement.csv`.
- [x] Code is reviewed and approved by at least 1 teammate in a GitHub Pull Request.
- [x] Deployed and functional on the AWS staging environment without errors.

### The 5-Minute Live Demo Flow (26 Nov)
1. **Minute 0:00 – 1:00 (The Hook & Problem):** Introduce Mama Mary's Kawangware duka and the rejection letter from the bank.
2. **Minute 1:00 – 2:00 (Ingestion):** Open the Biashara Score web app on a mobile phone. Upload `sample-data/mpesa_statement.csv` (150 transactions). Watch transactions parse in under 2 seconds.
3. **Minute 2:00 – 2:45 (Weekly Dashboard):** Show the real-time summary card: *"You made KSh 14,200 this week, profit KSh 3,100"*, with categorized expenses.
4. **Minute 2:45 – 3:30 (Kitabu ya Deni Reconciliation):** Open the Debt Tracker. Show Dennis Omondi's KSh 2,100 debt. Paste a new M-Pesa SMS payment of KSh 1,000 from Dennis and watch the balance automatically update to KSh 1,100.
5. **Minute 3:30 – 4:15 (The Biashara Score & PDF):** Reveal Mary's Biashara Score: **78/100 (Silver - Stable)**. Click "Download Lender Report" to open the clean 1-page financial verification PDF.
6. **Minute 4:15 – 5:00 (SMS Trigger & Wrap-up):** Trigger the Africa's Talking test SMS and display the incoming message received on Mary's phone.

### Risk Management: What We Cut If We Fall Behind
If unexpected blockers arise, we protect the core demo flow by cutting non-essential features:
- **Cut #1 (Bedrock Fallback):** If Bedrock API quotas or latency cause issues, fall back 100% to our regex rule categorizer.
- **Cut #2 (Dynamic PDF Generation):** If PDF styling takes too long, render a clean browser print preview (`window.print()`) styled specifically for A4 paper.
- **Cut #3 (EventBridge Cron Automation):** If the EventBridge trigger misbehaves, trigger the Africa's Talking SMS via a manual "Send Summary SMS" button in the admin interface.

---

## 17. Glossary (Plain-Language Guide)

- **M-Pesa:** Kenya's leading mobile money transfer and payment service operated by Safaricom.
- **Till Number (Buy Goods):** A 5-to-7 digit merchant code used by shops to receive instant customer payments at the counter.
- **Paybill:** A Safaricom business number used for bill collections, utility payments, and account-based transactions.
- **Daraja API:** Safaricom's official developer API gateway for integrating direct M-Pesa payments.
- **Duka:** A traditional Kenyan neighborhood convenience store selling household staples and groceries.
- **Kitabu ya Deni:** A handwritten paper notebook used by shopkeepers to record customer credit and debts.
- **IAM (Identity & Access Management):** The AWS service that controls who is authenticated and authorized to use cloud resources.
- **AWS Lambda:** A serverless compute service that runs backend Python code only when triggered by an API request or event.
- **Amazon DynamoDB:** A fully managed, ultra-fast NoSQL database service that scales on demand.
- **Amazon Bedrock:** AWS's managed service offering high-performance AI foundation models (such as Claude 3 Haiku).
- **AWS SAM (Serverless Application Model):** An open-source framework and CLI for building and deploying serverless applications on AWS.
- **PWA (Progressive Web App):** A web application built with modern web technologies that looks, feels, and installs like a native mobile app on any smartphone.
