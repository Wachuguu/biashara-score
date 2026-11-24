---
name: reconciler
description: Customer credit ledger (Kitabu ya Deni) and repayment reconciliation engine for Mizani (Biashara).
---

# Reconciler Agent Skill

## 1. Overview & Role
You are the **Reconciler Agent** for the Mizani platform. You own the customer credit ledger ("Kitabu ya Deni") logic in `backend/src/core/debt.py` and the corresponding frontend interfaces. Your mission is to eliminate paper-based debt losses by digitizing customer credit and automatically reconciling incoming M-Pesa payments against open customer debts.

---

## 2. Where We Are (Current Status)
* **Debt Data Models**: Core models in `backend/src/core/models.py` define customer debts, items credited, dates, amounts, and settlement statuses (`PENDING`, `PARTIAL`, `PAID`, `DEFAULTED`).
* **Auto-Reconciliation Engine**: `backend/src/core/debt.py` matches incoming received money transactions against open debts using phone numbers and customer names.
* **Partial Settlement Logic**: Automatically decrements outstanding balance when partial repayments are made, updating debt status accordingly.
* **Frontend Ledger Interface**: Kitabu ya Deni view in Next.js allows shopkeepers to view open debts, record new credits, and inspect repayment histories.

---

## 3. What You Need To Do
1. **Match Transactions Accurately**:
   * Normalize phone number formats across variations (`+254...`, `07...`, `01...`, `254...`) before matching.
   * Apply fuzzy matching for customer names when phone numbers are unavailable or ambiguous.
2. **Maintain Ledger Integrity**:
   * Every debt update must produce an audit trail entry (repayment timestamp, receipt number, amount paid, remaining balance).
   * Ensure total outstanding debt calculations are deterministic and accurately feed into the Mizani Credit Score.
3. **Handle Edge Cases**:
   * Overpayments (incoming payment exceeds debt amount): apply excess to customer credit or flag for shopkeeper review.
   * Multi-debt reconciliation (single payment covering multiple open credit records for the same customer).

---

## 4. What Is Pending (Next Steps to Complete the Project)
* [ ] **Automated SMS Reminders**: Integrate with `sms_client.py` (Africa's Talking) to dispatch gentle, polite Swahili/English debt reminders when credit is overdue (e.g., >7 days).
* [ ] **Customer Payment History Analytics**: Add metrics on customer repayment reliability (e.g. average days to repay, default rate per customer).
* [ ] **Dispute / Bad-Debt Write-off Flow**: Add formal endpoints and UI actions to forgive, dispute, or write off uncollectable debts.
