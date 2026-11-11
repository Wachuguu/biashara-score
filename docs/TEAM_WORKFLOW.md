# Team Workflow & Engineering Guidelines
## Biashara Score — 15-Day Sprint Protocol for 4 Developers

---

## 1. Team Organization & Roles

We are a team of 4 engineers delivering an MVP in 15 days. We share **one AWS account**, and to avoid configuration drift, permission conflicts, and accidental cloud costs:

> **IMPORTANT RULE:** Only **ONE designated person (Dev 4 - DevOps Lead)** has AWS deployment credentials and deploys infrastructure. Dev 1, Dev 2, and Dev 3 work 100% locally with mocks.

| Team Member | Primary Domain | Core Focus Areas |
| :--- | :--- | :--- |
| **Dev 1 (Backend Core & Logic)** | Core Algorithms | Statement parsing, Rule Engine, Bedrock fallback interface, Biashara Score calculation. |
| **Dev 2 (Backend Services & Debt)** | Business Services | Kitabu ya Deni (Debt tracker), Debt reconciliation logic, Africa's Talking SMS integration, PDF report generator. |
| **Dev 3 (Frontend & Mobile UI)** | Next.js / Tailwind PWA | Mobile-first UI, statement upload UX, weekly profit dashboard, debt ledger views, PDF preview. |
| **Dev 4 (DevOps Lead & Deployer)** | Infra & Deployment | AWS SAM templates, API Gateway routes, Lambda packaging, DynamoDB tables, S3 triggers, and CI/CD. |

---

## 2. The "Zero-AWS Local Development" Protocol

If you are not Dev 4, **you do not need an AWS account or AWS CLI credentials**. 

All backend business logic in `backend/src/core/` is designed as **pure Python modules** that have:
- ZERO `boto3` imports.
- ZERO network dependencies.
- 100% deterministic unit test coverage using `/sample-data/mpesa_statement.csv`.

### How AWS Calls Are Mocked Locally
All interactions with cloud services route through the interface wrappers in `backend/src/wrappers/`:
- `db_client.py`
- `s3_client.py`
- `llm_client.py`
- `sms_client.py`

When running locally (`MOCK_AWS=true` in `.env`):
```python
# In wrappers/db_client.py
if os.getenv("MOCK_AWS", "true").lower() == "true":
    # Reads/writes to local memory or local JSON
    return mock_db_store
else:
    # Production boto3 call (executed only in AWS Lambda)
    import boto3
    return boto3.resource("dynamodb").Table(...)
```

---

## 3. Git Branching & Pull Request Workflow

We use a feature-branch workflow with protected `main` branch.

```
       [feature/parser-rules]  ---------\
                                         +--> [PR + Review] ---> [main] ---> (Dev 4 Deploys)
       [feature/debt-tracker]  ---------/
```

### 3.1 Step 1: Fork or Clone the Repository
If collaborating across forks:
```bash
# 1. Clone your fork or the repo
git clone https://github.com/Wachuguu/biashara-score.git
cd biashara-score

# 2. Add upstream if using a fork
git remote add upstream https://github.com/Wachuguu/biashara-score.git

# 3. Create a local environment
cp .env.example .env
```

### 3.2 Step 2: Create a Feature Branch
Always branch off the latest `main`:
```bash
git checkout main
git pull origin main
git checkout -b <type>/<short-description>
```

#### Branch Naming Conventions:
- `feat/parser-csv-engine` (New features)
- `feat/debt-reconciliation`
- `ui/mobile-upload-screen` (Frontend UI)
- `fix/date-format-edge-case` (Bug fixes)
- `infra/sam-dynamo-tables` (Infrastructure)
- `test/scoring-engine-unit` (Tests)

### 3.3 Step 3: Develop and Test Locally
Before committing, verify your changes pass all local tests without touching AWS:

```bash
# Backend tests (runs in < 2 seconds)
cd backend
python -m pytest tests/

# Frontend tests & lint (if working on UI)
cd ../frontend
npm run lint
```

### 3.4 Step 4: Commit Guidelines
Write clear, concise commit messages:
```bash
git add .
git commit -m "feat(parser): add regex support for KPLC prepaid paybill transactions"
```
*Never commit `.env`, credentials, or temporary files! Check `git status` before committing.*

### 3.5 Step 5: Open a Pull Request (PR)
Push your branch to GitHub:
```bash
git push -u origin feat/parser-csv-engine
```
Then open a Pull Request against `main` on GitHub.

#### PR Title Format:
`[FEAT/FIX/UI] Brief description of changes`

#### PR Template Checklist:
Every PR description must contain:
1. **Summary:** 2-3 sentences explaining what was built or changed.
2. **Local Verification:** Confirmation that `pytest backend/tests` passed with zero AWS credentials.
3. **Screenshots / Terminal Output:** Showing tests passing or UI rendering.
4. **Impacted Modules:** List of files modified in `backend/src/` or `frontend/`.

### 3.6 Step 6: Code Review & Merging
- Every PR requires **at least 1 review and approval** from another teammate before merging.
- **Squash and Merge** into `main` to keep the commit history clean.

---

## 4. Single-Deployer Staging Deployment (Dev 4)

Once PRs are merged into `main`, **Dev 4** deploys the updated system to AWS:

```bash
# Executed ONLY by Dev 4 on their machine:
git checkout main
git pull origin main

# Build SAM artifacts
sam build

# Deploy to AWS staging environment
sam deploy --config-env dev
```

Dev 4 provides the updated API Gateway URL (`NEXT_PUBLIC_API_BASE_URL`) to Dev 3 for testing with the live cloud backend when needed.

---

## 5. Daily 15-Day Standup Rhythm

To ship successfully in 15 days, we hold a **15-minute daily sync** at 9:00 AM EAT:

1. **What did you ship yesterday?** (Must be merged code or passing test suite)
2. **What are you shipping today?**
3. **Any blockers?** (e.g. data format mismatches, interface definitions)

Keep communication active on WhatsApp / Slack. If an interface changes, update `docs/ARCHITECTURE.md` immediately!
