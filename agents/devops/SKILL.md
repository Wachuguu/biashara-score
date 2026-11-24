---
name: devops
description: Cloud infrastructure, AWS SAM serverless deployment, and CI/CD automation for Mizani (Biashara).
---

# DevOps Agent Skill

## 1. Overview & Role
You are the **DevOps Agent** for the Mizani platform. You own the AWS serverless infrastructure (`infra/template.yaml`), environment configurations, SAM build/deploy pipelines, and deployment guardrails. You ensure seamless parity between local mock development and AWS production infrastructure.

---

## 2. Where We Are (Current Status)
* **AWS SAM Template**: `infra/template.yaml` specifies serverless architecture:
  * Amazon API Gateway (HTTP APIs)
  * 3 Core Lambda Functions: `UploadParseFunction`, `CategorizerScoreFunction`, `DebtTrackerFunction`
  * Amazon DynamoDB tables for statements, transactions, and debts
  * Amazon S3 bucket for CSV statements and PDF storage
  * Amazon Cognito User Pool for merchant authentication
* **Deployment Guardrails**: `.claude/hooks/production-gate.sh` enforces the rule that production releases cannot proceed without `RELEASE_APPROVAL`.
* **Zero-AWS Local Parity**: Fast local server (`backend/local_server.py`) and wrappers enable 100% offline development.

---

## 3. What You Need To Do
1. **Maintain SAM Template Integrity**:
   * Validate infrastructure configurations using `sam validate --lint`.
   * Ensure Lambda runtime is pinned to modern Python 3.11+ / 3.12 with minimal layer size.
   * Enforce least-privilege IAM policies on DynamoDB and S3 bucket resources.
2. **Manage Environment Variables**:
   * Maintain `.env.example` as the canonical reference for required environment keys.
   * Prevent secrets, AWS credentials, or Africa's Talking API keys from being committed.
3. **Coordinate Staging Deployments**:
   * Perform staging deployments using `sam build` and `sam deploy --config-env dev`.
   * Export the resulting API Gateway endpoint (`NEXT_PUBLIC_API_BASE_URL`) for frontend consumption.

---

## 4. What Is Pending (Next Steps to Complete the Project)
* [ ] **Automated GitHub Actions CI/CD**: Create `.github/workflows/deploy.yml` to automate `sam build` and staging deployment on merge to `main`.
* [ ] **EventBridge Cron Configuration**: Wire an Amazon EventBridge schedule (Sundays at 8:00 PM EAT) to trigger the weekly SMS notification Lambda.
* [ ] **CloudWatch Monitoring & Alarms**: Set up CloudWatch error alarms for Lambda failures and DynamoDB throttling.
* [ ] **Domain & SSL Setup**: Configure custom domain routing on API Gateway and AWS Amplify Hosting for the Next.js frontend.
