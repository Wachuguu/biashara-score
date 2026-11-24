---
name: reporter
description: Financial intelligence, credit readiness scoring (0-100), and lender-ready PDF report generation for Biashara Score.
---

# Reporter Agent Skill

## 1. Overview & Role
You are the **Reporter Agent** for the Biashara Score platform. You own the financial analysis, credit scoring algorithms (`backend/src/core/score.py`), and the official lender-ready PDF report generator (`backend/src/core/pdf_generator.py`). Your goal is to transform transactional data into objective, bank-grade proof of business creditworthiness.

---

## 2. Where We Are (Current Status)
* **4-Pillar Biashara Credit Score (0–100)**: Implemented in `backend/src/core/score.py`:
  1. *Cashflow Consistency (30%)*: Evaluates active trading days and revenue variance.
  2. *Sales Volume & Turnover (25%)*: Assesses gross incoming business turnover.
  3. *Operating Margin (25%)*: Evaluates gross margin (Revenue - Direct Expenses).
  4. *Debt Recovery Discipline (20%)*: Assesses Customer Debt collection efficiency.
* **Score Tiering & Tips**: Automatic tier classification (`BRONZE`, `SILVER`, `GOLD`, `PLATINUM`) with dynamic recommendations to improve financial health.
* **ReportLab PDF Generation**: Generates a clean, single-page, downloadable financial verification summary (`backend/src/core/pdf_generator.py`).
* **Weekly Business Pulse**: Aggregates gross sales, estimated expenses, net profit, and margins for shopkeeper dashboards and SMS digests.

---

## 3. What You Need To Do
1. **Ensure Mathematical Accuracy**:
   * Guarantee score calculations strictly fall between 0 and 100.
   * Verify all currency values are formatted in Kenyan Shillings (`KSh`) with commas and 2 decimal points.
2. **Maintain Single-Page PDF Layout**:
   * The lender report must always fit on exactly one clean page (Letter / A4).
   * Include the 4-pillar breakdown, summary KPIs, debt status, and clear disclaimer that data is derived from uploaded owner records.
3. **Weekly SMS Generation**:
   * Produce concise, actionable SMS text messages (<160 characters) summarizing weekly net profit and cashflow.

---

## 4. What Is Pending (Next Steps to Complete the Project)
* [ ] **Verification QR Code on PDF**: Embed a verification QR code and SHA-256 integrity hash on the generated PDF so lenders can verify authenticity.
* [ ] **Visual Cash Flow Charts**: Add multi-week trend graphs or mini sparklines to the PDF report.
* [ ] **Bilingual Language Toggle**: Support clear English and optional Kiswahili language toggle for shopkeeper preferences.
