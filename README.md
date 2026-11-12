# Biashara Score 🇰🇪
> **Financial Intelligence & Lender-Ready Credit Scoring for Kenyan Micro-Businesses**

[![Built for Kenyan MSMEs](https://img.shields.io/badge/Market-Kenya%20MSMEs-007A3D.svg)](https://github.com/Wachuguu/biashara-score)
[![Architecture: AWS Serverless](https://img.shields.io/badge/Cloud-AWS%20Serverless-FF9900.svg)](https://aws.amazon.com)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB.svg)](https://www.python.org/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14%20PWA-black.svg)](https://nextjs.org/)

---

## 📖 What is Biashara Score?

Over **7.4 million micro and small businesses** in Kenya operate almost entirely on cash and M-Pesa. Because they lack audited books and formal collateral, **traditional banks and SACCOs reject up to 85% of their loan applications**. Additionally, shopkeepers lose 10%–25% of their hard-earned income to forgotten customer debts scribbled in paper notebooks (*"Kitabu ya Deni"*) and lack clear visibility into their real weekly profit.

**Biashara Score** changes this. A duka owner simply uploads their Safaricom M-Pesa statement (CSV) or pastes recent M-Pesa SMS messages into our mobile-first web app. The platform:

1. **Parses & Auto-Categorizes** transactions into Sales, Inventory/Suppliers, Utilities (KPLC), Rent, and Owner Draw using a fast regex engine with Amazon Bedrock (Claude 3 Haiku) as an AI fallback.
2. **Digitizes the "Kitabu ya Deni"** to track customer debts and automatically reconciles incoming customer repayments.
3. **Calculates the Biashara Score (0–100)**—an objective, transparent creditworthiness score based on real cashflow consistency, sales volume, operating margin, and debt recovery discipline.
4. **Delivers Weekly Financial Pulses** via **Africa's Talking SMS** (*"You made KSh 14,200 this week, profit KSh 3,100"*).
5. **Generates a Lender-Ready PDF Report** that the shopkeeper can hand to microfinance loan officers as verified proof of business health.

---

## 🏗️ Architecture Overview

Biashara Score runs on a 100% serverless, scale-to-zero AWS architecture:

```
[ Next.js + Tailwind PWA ]
          |
     (API Gateway)
          |
  [ Python Lambda Functions ]
   /           |           \
[DynamoDB]   [S3 Bucket]   [Bedrock AI]
     \         |           /
      [EventBridge Cron]
               |
     [Africa's Talking SMS]
```

- **Frontend:** Next.js 14 App Router, Tailwind CSS, Lucide Icons, Mobile PWA.
- **Backend API:** AWS Lambda (Python 3.11) behind Amazon API Gateway HTTP API.
- **Storage:** Amazon DynamoDB (3 tables: Businesses, Transactions, Debts) & Amazon S3 (Statements & PDF Reports).
- **AI Classification:** Amazon Bedrock (Anthropic Claude 3 Haiku).
- **Authentication:** Amazon Cognito User Pools.
- **Scheduled Jobs & SMS:** Amazon EventBridge triggers weekly profit summaries dispatched via Africa's Talking SMS API.
- **Infrastructure as Code:** AWS Serverless Application Model (SAM).

For deep architectural specifications and DynamoDB schemas, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## 🗂️ Project Structure

```
biashara-score/
├── .env.example              # Template for environment configuration
├── .gitignore                # Comprehensive ignore file (never commit AWS keys!)
├── README.md                 # Project overview and quickstart guide
├── sample-data/
│   └── mpesa_statement.csv  # 150 realistic fake transactions for a Nairobi duka
├── docs/
│   ├── PRD.md               # Product Requirements Document & MVP scope
│   ├── ARCHITECTURE.md      # AWS Architecture & DynamoDB data models
│   └── TEAM_WORKFLOW.md     # 4-person Git branching & local dev workflow
├── frontend/                # Next.js 14 + Tailwind CSS web application
├── backend/                 # Python Lambda backend & pure business logic
│   ├── src/
│   │   ├── core/            # 100% pure Python logic (parser, categorizer, score)
│   │   ├── wrappers/        # Thin mockable adapters for AWS services
│   │   └── handlers/        # AWS Lambda entry points
│   └── tests/               # Pytest suite (runs 100% offline with zero AWS creds)
└── infra/                   # AWS SAM infrastructure templates (template.yaml)
```

---

## 🚦 Implementation Status

| Component | Status | Details |
| :--- | :--- | :--- |
| **Backend Core Engine** (`backend/src/core/`) | ✅ **Working** | Pure Python: M-Pesa CSV/SMS parser, rule categorizer, 4-pillar credit scoring, weekly financial pulse, customer debt tracker, ReportLab PDF generator. Zero AWS dependencies. |
| **Backend REST API** (`backend/local_server.py`) | ✅ **Working** | FastAPI server with CORS for local development on `http://localhost:8000`. Full OpenAPI docs at `/docs`. |
| **AWS Lambda Handlers** (`backend/src/handlers/`) | ✅ **Working** | Handlers for API Gateway HTTP API v2 & EventBridge weekly digest cron job. |
| **AWS Infrastructure Template** (`infra/template.yaml`) | ✅ **Working** | CloudFormation SAM template with least-privilege IAM policies, DynamoDB, S3, Cognito. |
| **Frontend PWA** (`frontend/`) | ⏳ **Not built yet** | Next.js 14 mobile-first web app is currently pending frontend sprint. |
| **Live AWS Cloud Deployment** | ⏳ **Not built yet** | Production deployment to AWS shared account is scheduled for Phase 5 staging. |

> **IMPORTANT:** Our team shares **one AWS account that only ONE person deploys to**. 
> If you are working on features, **you do not need AWS credentials!** All parser, categorizer, debt tracking, and score logic can be executed and unit-tested locally using mock adapters and the sample CSV data.

### 1. Prerequisites
- Git
- Python 3.11+
- Node.js 18+ & npm

### 2. Quickstart Setup

```bash
# Clone the repository
git clone https://github.com/Wachuguu/biashara-score.git
cd biashara-score

# Copy the example environment file
cp .env.example .env
```

Notice that `.env` has `MOCK_AWS=true` enabled by default. This tells the backend wrappers to run completely in offline mode!

### 3. Running Backend Tests (Offline)

```bash
# Create and activate Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install testing dependencies
pip install pytest

# Run the test suite against sample-data/mpesa_statement.csv
pytest backend/tests -v
```

### 4. Running the Local API Server

```bash
# Start the local FastAPI server with CORS enabled
python backend/local_server.py
```
Open [http://localhost:8000/docs](http://localhost:8000/docs) in your browser to interactively test all endpoints with Swagger UI.

### 5. Frontend Web App (Not built yet)

> [!NOTE]
> The Next.js 14 frontend web application (`frontend/`) is **Not built yet**. The backend API is fully implemented and tested with CORS support for `http://localhost:3000` ready for when the frontend workstream begins.

```bash
# Once frontend is scaffolded:
cd frontend
npm install
npm run dev
```

---

## 👥 How Teammates Fork, Branch, and Run It

To keep the 15-day sprint running smoothly without stepping on each other's toes:

1. **Fork or Clone:** Follow [docs/TEAM_WORKFLOW.md](docs/TEAM_WORKFLOW.md).
2. **Branch Off `main`:**
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feat/your-feature-name
   ```
3. **Test Locally:** Ensure all unit tests pass with `MOCK_AWS=true`.
4. **Submit a Pull Request:** Open a PR against `main`. Require at least 1 teammate approval before merging.
5. **Deployment:** The DevOps Lead (Dev 4) pulls `main` and deploys to AWS via `sam build && sam deploy`.

---

## 📅 15-Day Sprint Roadmap

- **Phase 1 (Days 1–3):** Foundation, PRD, Data Schemas, Mock Wrappers, Sample Datasets.
- **Phase 2 (Days 4–7):** CSV/SMS Statement Parser, Rule Categorizer, Bedrock Fallback Interface.
- **Phase 3 (Days 8–10):** Digital Kitabu (Debt Tracker), Biashara Score Algorithm, Dashboard UI.
- **Phase 4 (Days 11–13):** Africa's Talking SMS Dispatcher, Lender PDF Generator, End-to-End Flow.
- **Phase 5 (Days 14–15):** User Testing with Sample Duka Data, Staging Deployment, Demo Showcase.

---

## 📜 License & Acknowledgements
Built with ❤️ in Nairobi, Kenya for local MSMEs and Dukas.
Special thanks to Safaricom M-Pesa open format references and Africa's Talking developer community.
