"""
Unit Test Suite for Workstream B: Financial Summary & Score Engine
Tests:
- calculate_weekly_summary (returning WeeklySummary model)
- calculate_multi_week_series (returning List[WeeklySummary] models)
- compute_consistency_score (Pillar 1: 30 pts)
- compute_growth_score (Pillar 2: 25 pts)
- compute_margin_score (Pillar 3: 25 pts)
- compute_debt_recovery_score (Pillar 4: 20 pts)
- generate_actionable_tips
- calculate_biashara_score
Edge cases tested:
- No data (empty transactions, empty debts)
- Only one week of transactions
- All debts unpaid
- Hand-built Transaction fixtures (independent of parser)
- Real data verification using sample-data/mpesa_statement.csv
"""
import os
import sys
import csv
import unittest
from datetime import datetime, timedelta, timezone

# Ensure backend directory is in path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
ROOT_DIR = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from src.core.models import (
    Transaction,
    TransactionDirection,
    TransactionCategory,
    DebtRecord,
    DebtStatus,
    WeeklySummary,
    BiasharaScoreResult,
)
from src.core.summary import calculate_weekly_summary, calculate_multi_week_series
from src.core.score_engine import (
    compute_consistency_score,
    compute_growth_score,
    compute_margin_score,
    compute_debt_recovery_score,
    generate_actionable_tips,
    calculate_biashara_score,
)
from src.handlers.score_handler import execute_weekly_summary
from src.wrappers.db_client import db_client


def _build_handcrafted_week_fixtures() -> list[Transaction]:
    """Builds a hand-crafted 1-week transaction fixture across 7 distinct days."""
    fixtures = [
        # Monday
        Transaction(
            receipt_number="FX01",
            completion_time="2026-09-01 09:15:00",
            details="Customer Till Payment - Alice",
            amount=2500.0,
            direction=TransactionDirection.IN,
            running_balance=52500.0,
            category=TransactionCategory.SALES,
            business_id="biz_duka_01",
        ),
        Transaction(
            receipt_number="FX02",
            completion_time="2026-09-01 14:00:00",
            details="Shop Rent September Landlord",
            amount=8000.0,
            direction=TransactionDirection.OUT,
            running_balance=44500.0,
            category=TransactionCategory.RENT,
            business_id="biz_duka_01",
        ),
        # Tuesday
        Transaction(
            receipt_number="FX03",
            completion_time="2026-09-02 10:30:00",
            details="Customer Till Payment - Bob",
            amount=3200.0,
            direction=TransactionDirection.IN,
            running_balance=47700.0,
            category=TransactionCategory.SALES,
            business_id="biz_duka_01",
        ),
        Transaction(
            receipt_number="FX04",
            completion_time="2026-09-02 16:00:00",
            details="Brookside Milk Restock",
            amount=2000.0,
            direction=TransactionDirection.OUT,
            running_balance=45700.0,
            category=TransactionCategory.INVENTORY,
            business_id="biz_duka_01",
        ),
        # Wednesday
        Transaction(
            receipt_number="FX05",
            completion_time="2026-09-03 11:00:00",
            details="Customer Till Payment - Charlie",
            amount=1800.0,
            direction=TransactionDirection.IN,
            running_balance=47500.0,
            category=TransactionCategory.SALES,
            business_id="biz_duka_01",
        ),
        Transaction(
            receipt_number="FX06",
            completion_time="2026-09-03 15:45:00",
            details="Teacher Maina Debt Repayment Settled",
            amount=1500.0,
            direction=TransactionDirection.IN,
            running_balance=49000.0,
            category=TransactionCategory.DEBT_RECOVERY,
            business_id="biz_duka_01",
        ),
        # Thursday
        Transaction(
            receipt_number="FX07",
            completion_time="2026-09-04 12:20:00",
            details="Customer Till Payment - David",
            amount=4100.0,
            direction=TransactionDirection.IN,
            running_balance=53100.0,
            category=TransactionCategory.SALES,
            business_id="biz_duka_01",
        ),
        Transaction(
            receipt_number="FX08",
            completion_time="2026-09-04 18:00:00",
            details="KPLC Prepaid Electricity Token",
            amount=500.0,
            direction=TransactionDirection.OUT,
            running_balance=52600.0,
            category=TransactionCategory.UTILITIES,
            business_id="biz_duka_01",
        ),
        # Friday
        Transaction(
            receipt_number="FX09",
            completion_time="2026-09-05 09:40:00",
            details="Customer Till Payment - Eva",
            amount=2800.0,
            direction=TransactionDirection.IN,
            running_balance=55400.0,
            category=TransactionCategory.SALES,
            business_id="biz_duka_01",
        ),
        Transaction(
            receipt_number="FX10",
            completion_time="2026-09-05 14:10:00",
            details="Airtime Purchase",
            amount=300.0,
            direction=TransactionDirection.OUT,
            running_balance=55100.0,
            category=TransactionCategory.AIRTIME,
            business_id="biz_duka_01",
        ),
        # Saturday
        Transaction(
            receipt_number="FX11",
            completion_time="2026-09-06 10:15:00",
            details="Customer Till Payment - Francis",
            amount=3600.0,
            direction=TransactionDirection.IN,
            running_balance=58700.0,
            category=TransactionCategory.SALES,
            business_id="biz_duka_01",
        ),
        Transaction(
            receipt_number="FX12",
            completion_time="2026-09-06 17:30:00",
            details="Personal Draw To Owner Phone",
            amount=2000.0,
            direction=TransactionDirection.OUT,
            running_balance=56700.0,
            category=TransactionCategory.OWNER_DRAW,
            business_id="biz_duka_01",
        ),
        # Sunday
        Transaction(
            receipt_number="FX13",
            completion_time="2026-09-07 11:50:00",
            details="Customer Till Payment - Grace",
            amount=2900.0,
            direction=TransactionDirection.IN,
            running_balance=59600.0,
            category=TransactionCategory.SALES,
            business_id="biz_duka_01",
        ),
    ]
    return fixtures


def _load_sample_csv_fixtures() -> list[Transaction]:
    """Helper to parse sample-data/mpesa_statement.csv into Transaction fixtures."""
    csv_path = os.path.join(ROOT_DIR, "sample-data", "mpesa_statement.csv")
    transactions = []

    def categorize_row(details: str, direction: str) -> TransactionCategory:
        d = details.lower()
        if direction == "IN":
            if "debt" in d or "deni" in d or "settled" in d:
                return TransactionCategory.DEBT_RECOVERY
            return TransactionCategory.SALES
        else:
            if "rent" in d:
                return TransactionCategory.RENT
            if "kplc" in d or "water" in d or "wifi" in d or "sewerage" in d:
                return TransactionCategory.UTILITIES
            if "airtime" in d:
                return TransactionCategory.AIRTIME
            if "personal draw" in d or "owner draw" in d:
                return TransactionCategory.OWNER_DRAW
            return TransactionCategory.INVENTORY

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            paid_in_str = row.get("Paid In", "").replace(",", "").strip()
            withdrawn_str = row.get("Withdrawn", "").replace(",", "").strip()
            balance_str = row.get("Balance", "").replace(",", "").strip()

            paid_in = float(paid_in_str) if paid_in_str else 0.0
            withdrawn = float(withdrawn_str) if withdrawn_str else 0.0
            direction = TransactionDirection.IN if paid_in > 0 else TransactionDirection.OUT
            amount = paid_in if paid_in > 0 else withdrawn
            running_balance = float(balance_str) if balance_str else 0.0

            cat = categorize_row(row["Details"], direction.value)

            tx = Transaction(
                receipt_number=row["Receipt No."],
                completion_time=row["Completion Time"],
                details=row["Details"],
                amount=amount,
                direction=direction,
                running_balance=running_balance,
                status=row.get("Transaction Status", "Completed"),
                category=cat,
                business_id="biz_7a8b9c0d1e2f",
                source="CSV_UPLOAD",
            )
            transactions.append(tx)

    return transactions


class TestScoreAndSummaryEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample_txs = _load_sample_csv_fixtures()
        cls.handcrafted_1week = _build_handcrafted_week_fixtures()

    # =========================================================================
    # Edge Case 1: No Data (Cold Start)
    # =========================================================================
    def test_edge_case_no_data(self):
        """Verifies summary, series, and scoring execute gracefully with empty data."""
        # 1. Weekly summary on empty transactions
        summary = calculate_weekly_summary([])
        self.assertIsInstance(summary, WeeklySummary)
        self.assertEqual(summary.gross_sales, 0.0)
        self.assertEqual(summary.operating_expenses, 0.0)
        self.assertEqual(summary.estimated_profit, 0.0)
        self.assertEqual(summary.profit_margin_pct, 0.0)
        self.assertEqual(summary.active_trading_days, 0)
        self.assertEqual(summary.transaction_count, 0)
        self.assertEqual(summary.week_label, "N/A")
        self.assertIn("profit KSh 0", summary.pulse_message)

        # 2. Multi-week series on empty transactions
        series = calculate_multi_week_series([], num_weeks=4)
        self.assertEqual(len(series), 4)
        for s in series:
            self.assertIsInstance(s, WeeklySummary)
            self.assertEqual(s.gross_sales, 0.0)
            self.assertEqual(s.operating_expenses, 0.0)
            self.assertEqual(s.profit_margin_pct, 0.0)

        # 3. Individual pillar computations
        self.assertEqual(compute_consistency_score([]), 0)
        self.assertEqual(compute_growth_score([]), 0)
        self.assertEqual(compute_margin_score([]), 0)
        # Neutral baseline for shop extending no credit
        self.assertEqual(compute_debt_recovery_score([]), 15)

        # 4. Actionable tips
        tips = generate_actionable_tips(0, 0, 0, 15, [])
        self.assertGreaterEqual(len(tips), 2)
        self.assertLessEqual(len(tips), 4)

        # 5. Full score computation
        result = calculate_biashara_score("biz_empty", [], [])
        self.assertIsInstance(result, BiasharaScoreResult)
        self.assertEqual(result.consistency_score, 0)
        self.assertEqual(result.growth_score, 0)
        self.assertEqual(result.expense_ratio_score, 0)
        self.assertEqual(result.debt_recovery_score, 15)
        self.assertEqual(result.total_score, 15)
        self.assertEqual(result.tier, "Needs Improvement")
        self.assertEqual(result.weekly_turnover_avg, 0.0)
        self.assertEqual(result.weekly_profit_avg, 0.0)
        self.assertIsNone(result.debt_recovery_rate)
        self.assertGreaterEqual(len(result.actionable_tips), 2)

    # =========================================================================
    # Edge Case 2: Only One Week of Transactions
    # =========================================================================
    def test_edge_case_only_one_week(self):
        """Verifies summary and scoring logic when merchant only has 1 week of history."""
        # Weekly summary returns WeeklySummary model
        summary = calculate_weekly_summary(self.handcrafted_1week)
        self.assertIsInstance(summary, WeeklySummary)
        self.assertEqual(summary.business_id, "biz_duka_01")
        self.assertEqual(summary.week_label, "2026-W36")  # 2026-09-01 is W36
        # Inbound: 2500 + 3200 + 1800 + 1500 (debt recovery) + 4100 + 2800 + 3600 + 2900 = 22400
        self.assertEqual(summary.gross_sales, 22400.0)
        # Outbound: 8000 (rent) + 2000 (stock) + 500 (kplc) + 300 (airtime) = 10800 (owner draw 2000 excluded!)
        self.assertEqual(summary.operating_expenses, 10800.0)
        self.assertEqual(summary.estimated_profit, 11600.0)
        self.assertEqual(summary.profit_margin_pct, 51.8)
        self.assertEqual(summary.active_trading_days, 7)
        self.assertEqual(summary.transaction_count, 13)

        # Multi-week series handles single week cleanly
        series = calculate_multi_week_series(self.handcrafted_1week, num_weeks=4)
        self.assertEqual(len(series), 4)
        for s in series:
            self.assertIsInstance(s, WeeklySummary)

        # Full score with only 1 week of data
        debts = [
            DebtRecord(
                debt_id="d1",
                business_id="biz_duka_01",
                debtor_name="Teacher Maina",
                debtor_phone="+254719283746",
                amount_owed=1500.0,
                amount_cleared=1500.0,
                balance_remaining=0.0,
                status=DebtStatus.CLEARED,
                created_at="2026-09-01T08:00:00Z",
            )
        ]
        score_res = calculate_biashara_score("biz_duka_01", self.handcrafted_1week, debts)
        self.assertIsInstance(score_res, BiasharaScoreResult)
        # High consistency (7/7 days active)
        self.assertGreaterEqual(score_res.consistency_score, 20)
        # Healthy margin
        self.assertGreaterEqual(score_res.expense_ratio_score, 20)
        # 100% recovered debt
        self.assertEqual(score_res.debt_recovery_score, 20)
        self.assertTrue(0 <= score_res.total_score <= 100)
        self.assertIn(score_res.tier, ["Gold", "Silver"])
        self.assertGreaterEqual(len(score_res.actionable_tips), 2)

    # =========================================================================
    # Edge Case 3: All Debts Unpaid
    # =========================================================================
    def test_edge_case_all_debts_unpaid(self):
        """Verifies debt scoring and tips when customer debts are completely unpaid."""
        old_due_date = (datetime.now(timezone.utc) - timedelta(days=45)).strftime("%Y-%m-%dT%H:%M:%SZ")
        unpaid_debts = [
            DebtRecord(
                debt_id="deb_01",
                business_id="biz_duka_01",
                debtor_name="Dennis Omondi",
                debtor_phone="+254728192837",
                amount_owed=3500.0,
                amount_cleared=0.0,
                balance_remaining=3500.0,
                status=DebtStatus.UNPAID,
                items_summary="2x Unga, Cooking Oil",
                created_at="2026-09-01T10:00:00Z",
                due_date=old_due_date,
            ),
            DebtRecord(
                debt_id="deb_02",
                business_id="biz_duka_01",
                debtor_name="Mama Boi",
                debtor_phone="+254712334455",
                amount_owed=1800.0,
                amount_cleared=0.0,
                balance_remaining=1800.0,
                status=DebtStatus.UNPAID,
                items_summary="Sugar, Milk",
                created_at="2026-09-05T12:00:00Z",
                due_date=old_due_date,
            ),
        ]

        # Debt recovery score should be heavily penalized (0 to 1 point)
        debt_score = compute_debt_recovery_score(unpaid_debts)
        self.assertLessEqual(debt_score, 1)

        # Full score evaluation
        score_res = calculate_biashara_score("biz_duka_01", self.handcrafted_1week, unpaid_debts)
        self.assertLessEqual(score_res.debt_recovery_score, 1)
        self.assertEqual(score_res.debt_recovery_rate, 0.0)

        # Actionable tips must include follow-up for the 2 unpaid debtors
        tips_text = " ".join(score_res.actionable_tips)
        self.assertIn("Follow up with 2 customer(s) with pending debts", tips_text)

    # =========================================================================
    # Real Data Verification (sample-data/mpesa_statement.csv)
    # =========================================================================
    def test_sample_csv_loaded_properly(self):
        """Verifies 150 transactions from sample-data/mpesa_statement.csv."""
        self.assertEqual(len(self.sample_txs), 150)
        first_tx = self.sample_txs[0]
        self.assertEqual(first_tx.receipt_number, "SK01YUUM7K")
        self.assertEqual(first_tx.direction, TransactionDirection.IN)
        self.assertEqual(first_tx.category, TransactionCategory.SALES)

    def test_calculate_weekly_summary_sample_data(self):
        """Verifies weekly totals calculation for a specific date range."""
        summary = calculate_weekly_summary(
            self.sample_txs,
            start_date="2026-09-01",
            end_date="2026-09-07",
        )
        self.assertIsInstance(summary, WeeklySummary)
        self.assertEqual(summary.business_id, "biz_7a8b9c0d1e2f")
        self.assertEqual(summary.week_label, "2026-W36")
        self.assertGreater(summary.gross_sales, 30000.0)
        self.assertEqual(summary.operating_expenses, 18379.42)
        self.assertGreater(summary.estimated_profit, 0.0)
        self.assertGreater(summary.profit_margin_pct, 15.0)
        self.assertGreaterEqual(summary.active_trading_days, 5)
        self.assertGreater(summary.transaction_count, 20)
        self.assertIn("INVENTORY", summary.expense_breakdown)
        self.assertIn("RENT", summary.expense_breakdown)
        self.assertIn("UTILITIES", summary.expense_breakdown)
        self.assertIn("AIRTIME", summary.expense_breakdown)
        self.assertIn("profit KSh", summary.pulse_message)

    def test_calculate_multi_week_series_sample_data(self):
        """Verifies calculate_multi_week_series yields 4 consecutive weekly summaries."""
        series_4 = calculate_multi_week_series(self.sample_txs, num_weeks=4)
        self.assertEqual(len(series_4), 4)
        week_labels = [s.week_label for s in series_4]
        self.assertEqual(week_labels, ["2026-W37", "2026-W38", "2026-W39", "2026-W40"])
        for s in series_4:
            self.assertIsInstance(s, WeeklySummary)
            self.assertGreater(s.gross_sales, 0.0)
            self.assertGreater(s.operating_expenses, 0.0)
            self.assertIsNotNone(s.estimated_profit)
            self.assertIsNotNone(s.profit_margin_pct)

    def test_calculate_biashara_score_sample_data(self):
        """
        Verifies calculate_biashara_score on sample data:
        - 0 <= total_score <= 100
        - total_score == consistency + growth + expense_ratio + debt_recovery
        - tier in ["Gold", "Silver", "Bronze", "Needs Improvement"]
        - len(actionable_tips) >= 2
        """
        sample_debts = [
            DebtRecord(
                debt_id="debt_001",
                business_id="biz_7a8b9c0d1e2f",
                debtor_name="Dennis Omondi",
                debtor_phone="+254728192837",
                amount_owed=2100.0,
                amount_cleared=1500.0,
                balance_remaining=600.0,
                status=DebtStatus.PARTIAL,
                items_summary="Unga & Sugar",
                created_at="2026-09-02T10:15:00Z",
                due_date="2026-09-16T18:00:00Z",
            ),
            DebtRecord(
                debt_id="debt_002",
                business_id="biz_7a8b9c0d1e2f",
                debtor_name="Teacher Maina",
                debtor_phone="+254719283746",
                amount_owed=1526.05,
                amount_cleared=1526.05,
                balance_remaining=0.0,
                status=DebtStatus.CLEARED,
                items_summary="Milk & Bread",
                created_at="2026-09-01T08:00:00Z",
                due_date="2026-09-15T18:00:00Z",
            ),
        ]

        result = calculate_biashara_score("biz_7a8b9c0d1e2f", self.sample_txs, sample_debts)

        self.assertIsInstance(result, BiasharaScoreResult)
        self.assertTrue(0 <= result.total_score <= 100)
        self.assertEqual(
            result.total_score,
            result.consistency_score
            + result.growth_score
            + result.expense_ratio_score
            + result.debt_recovery_score,
        )
        self.assertIn(result.tier, ["Gold", "Silver", "Bronze", "Needs Improvement"])
        self.assertGreaterEqual(len(result.actionable_tips), 2)
        self.assertLessEqual(len(result.actionable_tips), 4)
        self.assertGreater(result.weekly_turnover_avg, 0)
        self.assertGreater(result.weekly_profit_avg, 0)
        self.assertTrue(0.0 <= result.debt_recovery_rate <= 100.0)
        self.assertTrue(len(result.computed_at) > 0)

    def test_negative_profit_handling_high_restock(self):
        """Verifies handling of high restock week where expenses exceed sales."""
        restock_txs = [
            Transaction(
                receipt_number="RESTOCK01",
                completion_time="2026-09-21 10:00:00",
                details="Sales from Till",
                amount=10000.0,
                direction=TransactionDirection.IN,
                running_balance=10000.0,
                category=TransactionCategory.SALES,
            ),
            Transaction(
                receipt_number="RESTOCK02",
                completion_time="2026-09-22 14:00:00",
                details="Bulk Unga Stock Purchase",
                amount=25000.0,
                direction=TransactionDirection.OUT,
                running_balance=5000.0,
                category=TransactionCategory.INVENTORY,
            ),
        ]
        summary = calculate_weekly_summary(restock_txs)
        self.assertIsInstance(summary, WeeklySummary)
        self.assertEqual(summary.gross_sales, 10000.0)
        self.assertEqual(summary.operating_expenses, 25000.0)
        self.assertEqual(summary.estimated_profit, -15000.0)
        self.assertEqual(summary.profit_margin_pct, -150.0)
        self.assertIn("deficit", summary.pulse_message)

        margin_score = compute_margin_score([summary])
        self.assertEqual(margin_score, 0)

    def test_out_of_order_timestamps(self):
        """Verifies that out-of-order transaction timestamps are grouped and handled correctly."""
        reversed_txs = list(reversed(self.sample_txs))
        series_original = calculate_multi_week_series(self.sample_txs, num_weeks=4)
        series_reversed = calculate_multi_week_series(reversed_txs, num_weeks=4)

        for s_orig, s_rev in zip(series_original, series_reversed):
            self.assertEqual(s_orig.week_label, s_rev.week_label)
            self.assertEqual(s_orig.gross_sales, s_rev.gross_sales)
            self.assertEqual(s_orig.operating_expenses, s_rev.operating_expenses)
            self.assertEqual(s_orig.estimated_profit, s_rev.estimated_profit)

    def test_bug1_weekly_summary_single_iso_week_and_null_debt_recovery(self):
        """
        Regression tests for BUG 1:
        1. current_week is ONE ISO week (at most 7 active trading days, Monday to Sunday).
        2. current_week is the most recent ISO week in sample data (2026-W40).
        3. history_series contains the 4 weeks before it (W36-W39) ordered oldest to newest, with NO overlap.
        4. pulse_message uses single week figures (not 33 days / 195k total).
        5. debt_recovery_rate is null and debt_recovery_score is neutral (15) when there are no debts.
        6. tier matches docs/API_CONTRACT.md ('Gold', 'Silver', 'Bronze', 'Needs Improvement').
        """
        test_biz = "biz_test_bug1_validation"
        db_client.clear_mock_store()
        for tx in self.sample_txs:
            tx_dict = {
                "business_id": test_biz,
                "receipt_number": tx.receipt_number,
                "completion_time": tx.completion_time,
                "details": tx.details,
                "amount": tx.amount,
                "direction": tx.direction.value,
                "running_balance": tx.running_balance,
                "status": tx.status,
                "category": tx.category.value,
                "categorization_method": tx.categorization_method
            }
            db_client.put_transaction(tx_dict)

        res = execute_weekly_summary(test_biz, {"weeks": 4})
        self.assertEqual(res["statusCode"], 200)
        body = res["body"]

        cw = body["current_week"]
        # 1. A week must NEVER have more than 7 active days (old behaviour returned 33)
        self.assertLessEqual(cw["active_trading_days"], 7)
        self.assertEqual(cw["active_trading_days"], 6)

        # 2. Most recent ISO week with transactions in data
        self.assertEqual(cw["week_label"], "2026-W40")
        self.assertEqual(cw["start_date"], "2026-09-28")
        self.assertEqual(cw["end_date"], "2026-10-04")
        self.assertEqual(cw["transaction_count"], 30)

        # 3. Pulse message uses single week figures
        self.assertEqual(cw["gross_sales"], 42917.44)
        self.assertIn("You made KSh 42,917 this week, profit KSh 22,922.", cw["pulse_message"])

        # 4. History series has 4 weeks before current_week, oldest to newest, no overlap
        history = body["history_series"]
        self.assertEqual(len(history), 4)
        hist_labels = [h["week_label"] for h in history]
        self.assertEqual(hist_labels, ["2026-W36", "2026-W37", "2026-W38", "2026-W39"])
        self.assertNotIn(cw["week_label"], hist_labels)

        # 5. Debt recovery rate is None/null when no debts exist
        score_res = calculate_biashara_score(test_biz, self.sample_txs, [])
        self.assertIsNone(score_res.debt_recovery_rate)
        self.assertEqual(score_res.debt_recovery_score, 15)

        # 6. Tier names match docs/API_CONTRACT.md
        self.assertIn(score_res.tier, ["Gold", "Silver", "Bronze", "Needs Improvement"])


if __name__ == "__main__":
    unittest.main()
