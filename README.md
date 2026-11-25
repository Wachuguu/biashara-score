# Biashara Score

Financial Intelligence, M-Pesa Cashflow Analytics, and Lender-Ready Credit Scoring for Micro, Small, and Medium Enterprises (MSMEs).

- **Live Web App (AWS Amplify):** `https://main.d3mh28rzoa6peb.amplifyapp.com`
- **Live API Gateway (`eu-north-1`):** `https://eljw1b70fa.execute-api.eu-north-1.amazonaws.com`
- **Default Demo Profile:** `Geomin Routers` (Owner: `John Doe`)

---

## Overview

Over 7.4 million MSMEs in Kenya operate primarily on M-Pesa and cash. Because they lack audited financial statements and physical collateral, most are rejected for formal bank and SACCO working-capital loans. At the same time, shopkeepers lose 10% to 25% of monthly revenue to untracked customer credit recorded in paper notebooks.

**Biashara Score** turns everyday M-Pesa transactions into an objective, explainable **0-100 credit score**, automates customer debt tracking, and provides a one-page lender-ready PDF report.

### Core Capabilities

1. **Automated M-Pesa Ingestion (Safaricom Daraja + CSV + SMS):**
   - **Safaricom Daraja C2B Webhooks:** Receives real-time customer payments (`/mpesa/c2b/validation`, `/mpesa/c2b/confirmation`) and includes a live sandbox payment simulator (`/mpesa/simulate`).
   - **Statement & SMS Importer:** Parses standard M-Pesa CSV statements, pasted SMS messages, and includes a one-click 150-transaction sample loader (`/statements/sample`).
2. **4-Pillar Credit Scoring Engine (0-100):**
   - **Cashflow Consistency (30 pts):** Active trading days per week over 4-6 weeks.
   - **Revenue Volume (25 pts):** 4-week average weekly turnover.
   - **Operating Margin (25 pts):** Net profit ratio after inventory, utilities, and rent.
   - **Debt Discipline (20 pts):** Customer credit recovery rate.
   - **Tiers:** Gold (80+), Silver (65-79), Bronze (50-64), Needs Improvement (<50).
3. **Digital Customer Debt Ledger:**
   - Tracks customer credit digitally and automatically reconciles incoming M-Pesa payments against open debts by phone number or name.
4. **Lender-Ready PDF Report & Weekly SMS Digest:**
   - Generates a single-page A4 financial report using a zero-dependency pure-Python PDF engine.
   - Dispatches automated Sunday 8:00 PM EAT profit and score summaries via **Africa's Talking SMS**.

---

## Model Context Protocol (MCP) & AI Integration

Biashara Score exposes a standard **JSON-RPC 2.0 Model Context Protocol (MCP) Server** alongside user-friendly AI features.

### 1. Why MCP Matters Here (B2B Lender & Bank Access)
External partner banks (such as KCB, Equity, or SACCO underwriting copilots) can connect their AI systems directly to Biashara Score's MCP server to verify a shop's live creditworthiness, cashflow, and loan eligibility without manual paperwork.

- **HTTP MCP Endpoint:** `POST /mcp` (supports `initialize`, `tools/list`, `tools/call` per MCP `2024-11-05`)
- **Standalone Stdio MCP Server:** `PYTHONPATH=backend python backend/mcp_server.py`

#### Exposed MCP Tools

| Tool Name | Purpose |
| :--- | :--- |
| `get_business_score` | Returns the 0-100 Biashara Score, tier, 4-pillar breakdown, and coaching tips. |
| `get_weekly_cashflow` | Returns multi-week gross sales, operating expenses, and net profit in KSh. |
| `get_debt_ledger` | Returns outstanding customer debts, cleared amounts, and recovery rate. |
| `record_customer_debt` | Logs a new customer credit entry directly into the Customer Debt Ledger. |
| `evaluate_loan_readiness` | Underwriting tool that evaluates loan eligibility, risk level, and safe 30-day working-capital limit for a requested KSh amount. |

### 2. Nia: Conversational Shop Assistant (User Abstraction)
End users do not interact with raw JSON-RPC. In the web app, the **Ask Nia** tab (`/mcp`, powered by `POST /mcp/copilot`) provides a clean chatbot interface where shopkeepers ask plain-English questions such as:
- *"Can I qualify for a KSh 50,000 loan?"*
- *"How much profit did I make this week?"*
- *"Who owes me money right now?"*
- *"Add debt for Jane Wanjiku 0722112233 amount 2500"*

Nia invokes the underlying MCP tools and replies in plain language, while keeping the raw JSON-RPC protocol trace tucked behind an optional **"For Banks & Developers: View Live MCP Query"** toggle.

### 3. AI Classification Fallback (Amazon Bedrock)
- **Model:** **Anthropic Claude 3 Haiku** (`anthropic.claude-3-haiku-20240307-v1:0`) via **Amazon Bedrock**.
- **How it works:** Known Kenyan merchants (`Bidco Africa`, `Kapa Oil`, `Unga Farm Care`, `KPLC`, `Nairobi Water`) are matched in under 1ms using deterministic regex rules. Ambiguous transaction descriptions fall back to Claude 3 Haiku for classification.
- The 0-100 credit score itself remains 100% deterministic math so lending decisions are transparent and auditable.

---

## AWS Services Used

Biashara Score runs on a serverless, scale-to-zero AWS architecture in `eu-north-1`:

| AWS Service | Role |
| :--- | :--- |
| **AWS Amplify Hosting** | Builds and hosts the Next.js 14 frontend PWA directly from GitHub (`frontend/`). |
| **Amazon CloudFront** | Global CDN serving the frontend over HTTPS. |
| **Amazon API Gateway (HTTP API v2)** | Routes REST, Daraja C2B webhooks, and MCP JSON-RPC endpoints with CORS rules. |
| **AWS Lambda (Python 3.11)** | Runs `ApiFunction` (REST, Daraja, MCP, PDF generation) and `WeeklyCronFunction` (weekly digest). |
| **Amazon DynamoDB** | On-Demand (`PAY_PER_REQUEST`) NoSQL tables: `BusinessesTable`, `TransactionsTable`, `DebtsTable`. |
| **Amazon S3** | Archives uploaded M-Pesa CSV statements and SAM deployment artifacts. |
| **Amazon EventBridge** | Scheduled cron (`cron(0 17 ? * SUN *)`) triggering the Sunday 8:00 PM EAT SMS digest. |
| **Amazon Cognito** | Provisioned User Pool and App Client for production JWT authentication. |
| **Amazon Bedrock** | Hosts Claude 3 Haiku (`bedrock:InvokeModel`) for transaction categorization fallback. |
| **AWS CloudFormation / SAM** | Infrastructure-as-Code (`infra/template.yaml`) managing all backend resources. |

---

## External Integrations

- **Safaricom Daraja API:** M-Pesa C2B Validation/Confirmation webhooks and sandbox simulation (`backend/src/wrappers/daraja_client.py`, `backend/src/handlers/daraja_handler.py`).
- **Africa's Talking API:** Weekly SMS financial summary dispatch (`backend/src/wrappers/sms_client.py`, `backend/src/handlers/cron_handler.py`).

---

## Project Structure

```text
biashara-score/
├── README.md
├── Makefile                     # Unified test commands (make test-backend, make test-frontend)
├── sample-data/
│   └── mpesa_statement.csv      # 150-transaction sample M-Pesa statement
├── docs/                        # PRD, architecture, API contract, and workflow specs
├── frontend/                    # Next.js 14 + Tailwind CSS web application (Amplify root)
│   └── src/app/
│       ├── setup/               # Shop profile creation & demo shop loader
│       ├── dashboard/           # Biashara Score gauge & weekly cashflow summary
│       ├── import/              # Live Daraja simulator, CSV upload, SMS paste, 150-tx loader
│       ├── deni/                # Digital Customer Debt Ledger
│       ├── report/              # 1-page Lender-Ready A4 PDF download
│       └── mcp/                 # "Ask Nia" conversational assistant & MCP protocol trace
├── backend/                     # Python 3.11 Lambda backend & core engines
│   ├── local_server.py          # FastAPI local development server (mirrors API Gateway)
│   ├── mcp_server.py            # Standalone stdio MCP JSON-RPC 2.0 server
│   ├── src/core/                # Pure Python engines (parser, categorizer, scorer, debt, PDF)
│   ├── src/wrappers/            # AWS, Daraja, Bedrock, and Africa's Talking clients
│   ├── src/handlers/            # Lambda, Daraja, and MCP handlers
│   └── tests/                   # 76 unit, integration, security, Daraja, and MCP tests
└── infra/
    └── template.yaml            # AWS SAM / CloudFormation template
```

---

## Local Development & Verification

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm

### Run All Tests

```bash
# Backend unit, integration, security, Daraja, and MCP tests (76 tests)
make test-backend

# Frontend TypeScript typecheck and ESLint
make test-frontend
```

### Run Locally

```bash
# Terminal 1: Start local FastAPI backend (http://localhost:8000)
PYTHONPATH=backend ./venv/bin/uvicorn local_server:app --reload --port 8000

# Terminal 2: Start Next.js frontend (http://localhost:3000)
cd frontend && npm run dev
```

### Deploy Backend to AWS (SAM)

```bash
cd infra
sam build && sam deploy
```
