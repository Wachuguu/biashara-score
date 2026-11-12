"""
Unit Tests for Workstream C: Debt Engine, Report Generator & SMS Client
Pure Python, 100% offline with zero AWS credentials.
"""
import unittest
import os
import re
from datetime import datetime, timedelta, timezone
from backend.src.core.models import (
    DebtRecord,
    DebtStatus,
    Transaction,
    TransactionDirection,
    TransactionCategory,
    BiasharaScoreResult
)
from backend.src.core.debt_engine import (
    normalize_phone_number,
    match_repayment_to_debt,
    apply_debt_repayment,
    calculate_debt_metrics
)
from backend.src.core.report_generator import (
    generate_lender_pdf,
    DISCLAIMER_FOOTER,
    TIER_THRESHOLDS_LINE,
    _generate_pure_pdf,
    extract_report_facts
)
from backend.src.wrappers.sms_client import (
    build_weekly_sms_message,
    AfricaTalkingSMSClient,
    sms_client
)
from backend.src.core.parser import parse_csv_statement


class TestDebtReportSMS(unittest.TestCase):
    def setUp(self):
        # Sample Business Profile
        self.business_profile = {
            "business_id": "biz_7a8b9c0d1e2f",
            "shop_name": "Mary's Family Provisions",
            "owner_name": "Mary Wambui Kamau",
            "owner_phone": "+254712345678",
            "till_number": "789123",
            "created_at": "2026-09-01T08:00:00Z"
        }

        # Sample Biashara Score Result
        self.score_result = BiasharaScoreResult(
            business_id="biz_7a8b9c0d1e2f",
            total_score=78,
            tier="Silver",
            consistency_score=26,
            growth_score=19,
            expense_ratio_score=20,
            debt_recovery_score=13,
            weekly_turnover_avg=35087.5,
            weekly_profit_avg=9937.5,
            debt_recovery_rate=58.4,
            computed_at="2026-11-12T15:45:00Z",
            actionable_tips=[
                "Follow up with 2 delinquent debtors who owe over KSh 2,000 for more than 14 days to boost Debt Recovery.",
                "Maintain active customer deposits on weekends to achieve full marks on Cashflow Consistency."
            ]
        )

        # Sample Weekly Summaries
        self.weekly_summaries = [
            {
                "week_label": "2026-W33",
                "gross_sales": 32100.0,
                "operating_expenses": 23400.0,
                "estimated_profit": 8700.0,
                "profit_margin_pct": 27.1
            },
            {
                "week_label": "2026-W34",
                "gross_sales": 35400.0,
                "operating_expenses": 24900.0,
                "estimated_profit": 10500.0,
                "profit_margin_pct": 29.7
            },
            {
                "week_label": "2026-W35",
                "gross_sales": 34100.0,
                "operating_expenses": 25200.0,
                "estimated_profit": 8900.0,
                "profit_margin_pct": 26.1
            },
            {
                "week_label": "2026-W36",
                "gross_sales": 38450.0,
                "operating_expenses": 26800.0,
                "estimated_profit": 11650.0,
                "profit_margin_pct": 30.3
            }
        ]

    def test_normalize_phone_number_formats(self):
        """Validates all common Kenyan phone number formats normalize to +254 E.164 standard."""
        self.assertEqual(normalize_phone_number("0712345678"), "+254712345678")
        self.assertEqual(normalize_phone_number("0112345678"), "+254112345678")
        self.assertEqual(normalize_phone_number("254712345678"), "+254712345678")
        self.assertEqual(normalize_phone_number("+254712345678"), "+254712345678")
        self.assertEqual(normalize_phone_number("712345678"), "+254712345678")
        self.assertEqual(normalize_phone_number("+254 712 345 678"), "+254712345678")
        self.assertEqual(normalize_phone_number("0712-345-678"), "+254712345678")
        self.assertEqual(normalize_phone_number("(0712) 345 678"), "+254712345678")
        self.assertEqual(normalize_phone_number(""), "")

    def test_match_repayment_sample_statement_row_sk067bqrkw(self):
        """
        Loads sample-data/mpesa_statement.csv, finds row SK067BQRKW (Teacher Maina),
        matches it against an open debt by phone, and clears the debt.
        """
        csv_path = os.path.join(os.path.dirname(__file__), "../../sample-data/mpesa_statement.csv")
        with open(csv_path, "r", encoding="utf-8") as f:
            transactions = parse_csv_statement(f.read())

        # Locate row SK067BQRKW
        sk_tx = next((t for t in transactions if t.receipt_number == "SK067BQRKW"), None)
        self.assertIsNotNone(sk_tx, "Row SK067BQRKW should exist in sample statement")
        self.assertEqual(sk_tx.amount, 1526.05)
        self.assertEqual(sk_tx.direction, TransactionDirection.IN)

        # Setup an open debt for Teacher Maina matching the exact amount and phone
        sample_debt = DebtRecord(
            debt_id="debt_maina_001",
            business_id="biz_7a8b9c0d1e2f",
            debtor_name="Teacher Maina",
            debtor_phone="+254719283746",
            amount_owed=1526.05,
            amount_cleared=0.0,
            balance_remaining=1526.05,
            status=DebtStatus.UNPAID,
            items_summary="2x Unga, Sugar, Cooking Oil",
            created_at="2026-08-25T10:00:00Z",
            due_date="2026-09-05T18:00:00Z"
        )

        match_res = match_repayment_to_debt(sk_tx, [sample_debt])
        self.assertIsNotNone(match_res, "Should match Teacher Maina debt by phone")
        matched_debt, applied_amount = match_res
        self.assertEqual(matched_debt.debt_id, "debt_maina_001")
        self.assertEqual(applied_amount, 1526.05)

        # Apply repayment
        updated_debt = apply_debt_repayment(
            matched_debt,
            payment_amount=applied_amount,
            receipt_number=sk_tx.receipt_number,
            payment_date=sk_tx.completion_time,
            notes="Matched inbound M-Pesa transfer"
        )

        # Assert debt is completely cleared
        self.assertEqual(updated_debt.balance_remaining, 0.0)
        self.assertEqual(updated_debt.amount_cleared, 1526.05)
        self.assertEqual(updated_debt.status, DebtStatus.CLEARED)
        self.assertEqual(len(updated_debt.repayment_history), 1)
        self.assertEqual(updated_debt.repayment_history[0]["receipt_number"], "SK067BQRKW")

    def test_match_repayment_by_debtor_name_and_deni_keyword(self):
        """Tests fallback matching via debtor name substring and deni keywords."""
        tx = Transaction(
            receipt_number="SK99DENI01",
            completion_time="2026-09-15T14:30:00Z",
            details="Customer payment from Fundi George for deni ya duka",
            amount=800.0,
            direction=TransactionDirection.IN,
            running_balance=50000.0,
            counterparty="Fundi George"
        )

        debt = DebtRecord(
            debt_id="debt_george_002",
            business_id="biz_7a8b9c0d1e2f",
            debtor_name="George Kinyua (Fundi George)",
            debtor_phone="+254700000000",  # Different phone number
            amount_owed=1500.0,
            amount_cleared=0.0,
            balance_remaining=1500.0,
            status=DebtStatus.UNPAID
        )

        match_res = match_repayment_to_debt(tx, [debt])
        self.assertIsNotNone(match_res)
        matched_debt, applied_amt = match_res
        self.assertEqual(matched_debt.debt_id, "debt_george_002")
        self.assertEqual(applied_amt, 800.0)

    def test_match_repayment_no_match_on_outbound_or_unrelated(self):
        """Ensures OUT transactions and non-matching names/phones return None."""
        out_tx = Transaction(
            receipt_number="SK_OUT_01",
            completion_time="2026-09-10T10:00:00Z",
            details="Payment to Bidco Africa Distributors",
            amount=2500.0,
            direction=TransactionDirection.OUT,
            running_balance=40000.0
        )
        debt = DebtRecord(
            debt_id="debt_01",
            business_id="biz_01",
            debtor_name="Dennis Omondi",
            debtor_phone="+254728192837",
            amount_owed=1000.0,
            balance_remaining=1000.0
        )
        self.assertIsNone(match_repayment_to_debt(out_tx, [debt]))

    def test_apply_debt_repayment_partial_and_overpayment(self):
        """Tests partial payments and capping at 0.0 balance remaining on overpayment."""
        debt = DebtRecord(
            debt_id="debt_partial_01",
            business_id="biz_01",
            debtor_name="Mama Boi",
            debtor_phone="+254728192837",
            amount_owed=2000.0,
            amount_cleared=0.0,
            balance_remaining=2000.0,
            status=DebtStatus.UNPAID
        )

        # 1. Partial payment: KSh 600
        apply_debt_repayment(debt, 600.0, "REC01", "2026-09-02T10:00:00Z", "Partial counter cash")
        self.assertEqual(debt.balance_remaining, 1400.0)
        self.assertEqual(debt.amount_cleared, 600.0)
        self.assertEqual(debt.status, DebtStatus.PARTIAL)
        self.assertEqual(len(debt.repayment_history), 1)

        # 2. Overpayment: Paying KSh 1800 when balance is 1400
        apply_debt_repayment(debt, 1800.0, "REC02", "2026-09-05T12:00:00Z", "Final balance + tip")
        self.assertEqual(debt.balance_remaining, 0.0)
        self.assertEqual(debt.amount_cleared, 2000.0)  # Capped at amount_owed
        self.assertEqual(debt.status, DebtStatus.CLEARED)
        self.assertEqual(len(debt.repayment_history), 2)

    def test_calculate_debt_metrics(self):
        """Tests debt metrics aggregation including delinquency detection."""
        past_due = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        future_due = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()

        debts = [
            DebtRecord(
                debt_id="d1", business_id="b1", debtor_name="Debtor 1", debtor_phone="+254711111111",
                amount_owed=1000.0, amount_cleared=1000.0, balance_remaining=0.0,
                status=DebtStatus.CLEARED
            ),
            DebtRecord(
                debt_id="d2", business_id="b1", debtor_name="Debtor 2", debtor_phone="+254722222222",
                amount_owed=2000.0, amount_cleared=500.0, balance_remaining=1500.0,
                status=DebtStatus.PARTIAL, due_date=past_due  # Delinquent
            ),
            DebtRecord(
                debt_id="d3", business_id="b1", debtor_name="Debtor 3", debtor_phone="+254733333333",
                amount_owed=1500.0, amount_cleared=0.0, balance_remaining=1500.0,
                status=DebtStatus.UNPAID, due_date=future_due  # Not delinquent
            )
        ]

        metrics = calculate_debt_metrics(debts)
        self.assertEqual(metrics["total_outstanding_amount"], 3000.0)
        self.assertEqual(metrics["total_cleared_amount"], 1500.0)
        # 1500 / 4500 = 33.3%
        self.assertEqual(metrics["recovery_rate_pct"], 33.3)
        self.assertEqual(metrics["unpaid_count"], 1)
        self.assertEqual(metrics["delinquent_count"], 1)

        # Empty debts test
        empty_metrics = calculate_debt_metrics([])
        self.assertEqual(empty_metrics["total_outstanding_amount"], 0.0)
        self.assertEqual(empty_metrics["recovery_rate_pct"], 0.0)

    def test_generate_lender_pdf(self):
        """
        Tests generation of the lender business cashflow summary PDF report with debts.
        Must return valid PDF bytes, single page, disclaimer present, and wording checks.
        """
        debt_summary = {
            "total_outstanding_amount": 3200.0,
            "total_cleared_amount": 4500.0,
            "recovery_rate_pct": 58.4,
            "delinquent_count": 1,
            "unpaid_count": 2
        }

        pdf_bytes = generate_lender_pdf(
            business_profile=self.business_profile,
            score_result=self.score_result,
            weekly_summaries=self.weekly_summaries,
            debt_summary=debt_summary
        )

        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"), "PDF must start with %PDF- magic bytes")
        self.assertGreater(len(pdf_bytes), 3000, f"PDF byte size should be > 3000 bytes (got {len(pdf_bytes)})")

        # 1. Exactly one page
        page_count = len(re.findall(rb"/Type\s*/Page[^s]", pdf_bytes))
        self.assertEqual(page_count, 1, f"PDF must be strictly ONE page (got {page_count})")

        text = pdf_bytes.decode("latin1", errors="ignore")

        # 2. Real recovery rate displayed when debts exist
        self.assertIn("Recovery Rate: 58.4%", text)
        self.assertNotIn("No customer credit recorded", text)

        # 3. Disclaimer present
        self.assertIn(DISCLAIMER_FOOTER, text)

        # 4. 'verified' absent apart from 'not verified'
        clean_text = re.sub(r"(?i)\bnot verified\b", "", text)
        self.assertNotIn("verified", clean_text.lower(), "'verified' must be absent apart from 'not verified'")
        self.assertNotIn("certified", text.lower(), "'certified' must not appear anywhere")
        self.assertNotIn("Credit Verification Report", text)
        self.assertNotIn("Confidential Verification Document", text)

        # 5. Table heading and tier thresholds line
        self.assertIn("Last 4 weeks", text)
        self.assertIn(TIER_THRESHOLDS_LINE, text)

        # 6. Facts block fields present
        self.assertIn("Report Date:", text)
        self.assertIn("Data Period Covered:", text)
        self.assertIn("Transactions Analysed:", text)
        self.assertIn("Active Trading Days:", text)
        self.assertIn("Avg Sales Transaction:", text)

        # 7. Chart labelled in KSh
        self.assertIn("Weekly Gross Sales Trend", text)
        self.assertIn("KSh", text)

    def test_generate_lender_pdf_no_debts(self):
        """
        Tests generation when the shop has no debts (debt_recovery_rate is None or total owed is 0).
        Must print 'No customer credit recorded' instead of 'Recovery Rate: 0.0%'.
        """
        score_no_debts = BiasharaScoreResult(
            business_id="biz_7a8b9c0d1e2f",
            total_score=75,
            tier="Silver",
            consistency_score=26,
            growth_score=19,
            expense_ratio_score=20,
            debt_recovery_score=15,
            weekly_turnover_avg=35087.5,
            weekly_profit_avg=9937.5,
            debt_recovery_rate=None,  # Null / None
            computed_at="2026-11-12T15:45:00Z",
            actionable_tips=["Maintain steady customer transactions."]
        )

        empty_debt_summary = {
            "total_outstanding_amount": 0.0,
            "total_cleared_amount": 0.0,
            "recovery_rate_pct": 0.0,
            "delinquent_count": 0,
            "unpaid_count": 0,
            "total_debts_count": 0
        }

        pdf_bytes = generate_lender_pdf(
            business_profile=self.business_profile,
            score_result=score_no_debts,
            weekly_summaries=self.weekly_summaries,
            debt_summary=empty_debt_summary
        )

        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
        page_count = len(re.findall(rb"/Type\s*/Page[^s]", pdf_bytes))
        self.assertEqual(page_count, 1, f"PDF must be strictly ONE page (got {page_count})")

        text = pdf_bytes.decode("latin1", errors="ignore")

        # 'No customer credit recorded' must be present
        self.assertIn("No customer credit recorded", text)
        # 'Recovery Rate: 0.0%' must NOT be present
        self.assertNotIn("Recovery Rate: 0.0%", text)

        # Disclaimer present
        self.assertIn(DISCLAIMER_FOOTER, text)

        # 'verified' absent apart from 'not verified'
        clean_text = re.sub(r"(?i)\bnot verified\b", "", text)
        self.assertNotIn("verified", clean_text.lower())
        self.assertNotIn("certified", text.lower())

    def test_generate_pure_pdf_builder_fallback(self):
        """
        Tests the pure Python vector generator fallback directly.
        Ensures valid PDF bytes, single page, disclaimer, no debts wording, and no disallowed words.
        """
        score_no_debts = BiasharaScoreResult(
            business_id="biz_pure_01",
            total_score=72,
            tier="Silver",
            consistency_score=24,
            growth_score=18,
            expense_ratio_score=18,
            debt_recovery_score=12,
            weekly_turnover_avg=30000.0,
            weekly_profit_avg=8000.0,
            debt_recovery_rate=None,
            computed_at="2026-11-12T12:00:00Z",
            actionable_tips=["Keep growing cash sales."]
        )
        empty_debt_summary = {
            "total_outstanding_amount": 0.0,
            "total_cleared_amount": 0.0,
            "recovery_rate_pct": 0.0,
            "delinquent_count": 0,
            "unpaid_count": 0
        }
        facts = extract_report_facts(score_no_debts, self.weekly_summaries)

        pdf_bytes = _generate_pure_pdf(
            business_profile=self.business_profile,
            score_result=score_no_debts,
            weekly_summaries=self.weekly_summaries,
            debt_summary=empty_debt_summary,
            facts=facts
        )

        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
        page_count = len(re.findall(rb"/Type\s*/Page[^s]", pdf_bytes))
        self.assertEqual(page_count, 1)

        text = pdf_bytes.decode("latin1", errors="ignore")
        self.assertIn("No customer credit recorded", text)
        self.assertNotIn("Recovery Rate: 0.0%", text)
        self.assertIn(DISCLAIMER_FOOTER, text)
        self.assertIn("Last 4 weeks", text)
        self.assertIn(TIER_THRESHOLDS_LINE, text)

        clean_text = re.sub(r"(?i)\bnot verified\b", "", text)
        self.assertNotIn("verified", clean_text.lower())
        self.assertNotIn("certified", text.lower())

    def test_build_weekly_sms_message(self):
        """
        Tests building the Safaricom-compliant SMS summary string.
        Verifies formatting, numbers with commas, and strict length constraint (<= 200 chars).
        """
        sms = build_weekly_sms_message(
            owner_name="Mary Wambui",
            week_label="2026-W36",
            sales=38450.0,
            expenses=26800.0,
            profit=11650.0,
            outstanding_debts=3200.0,
            score=78,
            tier="Silver"
        )

        expected = (
            "Habari Mary! Biashara Score Summary for W36: "
            "Sales KSh 38,450, Expenses KSh 26,800, Est. Profit KSh 11,650. "
            "Outstanding Debts: KSh 3,200. Score: 78/100 (Silver). Keep growing!"
        )

        self.assertEqual(sms, expected)
        self.assertLessEqual(len(sms), 200, f"SMS length must be <= 200 chars (got {len(sms)})")

    def test_sms_client_mock_dispatch(self):
        """Verifies AfricaTalkingSMSClient dispatches correctly in offline mock mode."""
        client = AfricaTalkingSMSClient()
        response = client.send_sms(
            phone_number="+254712345678",
            message="Habari Mary! Your weekly summary is ready."
        )

        self.assertIsInstance(response, dict)
        self.assertEqual(response.get("status"), "success")
        self.assertEqual(response.get("mode"), "mock")
        self.assertEqual(response.get("recipient"), "+254712345678")


if __name__ == "__main__":
    unittest.main()
