# Mizani (formerly Biashara Score)
Micro-Business Financial Intelligence & Credit Readiness Engine (Kenyan MSMEs / Dukas)

## Commands
- Test Backend: `make test-backend` or `PYTHONPATH=. ./venv/bin/pytest backend/tests`
- Test Frontend: `make test-frontend` or `cd frontend && npm run typecheck && npm run lint`
- Test All: `make test` (exits non-zero on any failure)
- Run Local Server: `make dev-backend` (FastAPI at `http://localhost:8000`)
- Run Frontend Dev: `make dev-frontend` (Next.js at `http://localhost:3000`)
- Build Frontend: `make build-frontend`
- Lint All: `make lint`

## Conventions
- **Zero-AWS in Core Logic**: Modules in `backend/src/core/` are pure Python. ZERO `boto3` imports, ZERO network dependencies. 100% deterministic test coverage.
- **AWS Wrapper Isolation**: All DynamoDB, S3, Bedrock, and SMS calls go through `backend/src/wrappers/`. When `MOCK_AWS=true`, operate in-memory/locally.
- **Data Privacy & PII**: Never commit or log real phone numbers, national IDs, or customer statements. Synthetic fixtures live in `sample-data/`.
- **Financial Precision**: All monetary values are float/decimal represented in Kenyan Shillings (KSh). Round outputs to 2 decimal places.
- **Frontend Architecture**: Next.js 14 App Router with Tailwind CSS. Offline PWA capabilities must be preserved (`public/sw.js`, `manifest.json`).

## Architecture
- `backend/src/core/parser.py`: Deterministic Safaricom M-Pesa CSV & SMS statement parser.
- `backend/src/core/categorizer.py`: Rules-first categorizer with Bedrock (Claude 3 Haiku) fallback.
- `backend/src/core/score.py`: 4-pillar credit readiness scoring engine (0–100 index).
- `backend/src/core/debt.py`: Kitabu ya Deni debt management & repayment reconciliation.
- `backend/src/core/pdf_generator.py`: ReportLab single-page lender verification report.
- `frontend/src/app/`: Mobile-first PWA views (Upload, Weekly Summary, Kitabu ya Deni, PDF preview).
- `infra/template.yaml`: AWS SAM serverless infrastructure specification.

## Things Agents Get Wrong
- Do not run `pytest` inside `backend/` without `PYTHONPATH=.` set; always use `make test-backend`.
- Do not add AWS dependencies to `backend/src/core/`.
- Do not generate or commit `.pdf` files into version control.
- Never modify existing test assertions during bug fixes; write a failing reproduction test first.

## Verifying Your Work
- Run `make test` before submitting or reporting any task complete.
- Verify both backend tests and frontend typechecking pass with 0 warnings or errors.
