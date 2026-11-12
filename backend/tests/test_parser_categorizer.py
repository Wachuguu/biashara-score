"""
Unit tests for Workstream A: Parser & Categorizer Engine
Pure Python tests - 100% offline, zero AWS credentials required.
"""
import os
import unittest
from backend.src.core.models import (
    Transaction,
    TransactionDirection,
    TransactionCategory,
)
from backend.src.core.parser import (
    parse_csv_statement,
    parse_sms_message,
    parse_multiple_sms,
)
from backend.src.core.categorizer import (
    match_rule_based_category,
    categorize_transaction,
    categorize_batch,
)

SAMPLE_CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "sample-data",
    "mpesa_statement.csv",
)


class TestParserAndCategorizer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(SAMPLE_CSV_PATH, "r", encoding="utf-8-sig") as f:
            cls.sample_csv_content = f.read()

    def test_parse_csv_statement_all_150_rows(self):
        """Verify parse_csv_statement parses all 150 transactions from sample CSV."""
        txs = parse_csv_statement(self.sample_csv_content, business_id="biz_test_duka")
        self.assertEqual(len(txs), 150, f"Expected 150 transactions, got {len(txs)}")

        # Check first transaction attributes
        first_tx = txs[0]
        self.assertEqual(first_tx.receipt_number, "SK01YUUM7K")
        self.assertAlmostEqual(first_tx.amount, 1606.98)
        self.assertEqual(first_tx.direction, TransactionDirection.IN)
        self.assertEqual(first_tx.business_id, "biz_test_duka")
        self.assertEqual(first_tx.source, "CSV_UPLOAD")
        self.assertIn("John Otieno", first_tx.counterparty)

    def test_sample_csv_categorization_and_coverage(self):
        """
        Verify categorize_batch accurately categorizes key sample statement rows
        and achieves >= 95% coverage with rules alone.
        """
        txs = parse_csv_statement(self.sample_csv_content)
        categorized = categorize_batch(txs)

        # Row 1: Till payment -> SALES
        self.assertEqual(categorized[0].category, TransactionCategory.SALES)
        self.assertEqual(categorized[0].categorization_method, "RULE_BASED")

        # Row 5 (index 4): Landlord Joseph Njuguna Shop Rent September -> RENT
        rent_tx = next(t for t in categorized if "Landlord" in t.details)
        self.assertEqual(rent_tx.category, TransactionCategory.RENT)

        # Bidco Africa Distributors -> INVENTORY
        bidco_tx = next(t for t in categorized if "Bidco" in t.details)
        self.assertEqual(bidco_tx.category, TransactionCategory.INVENTORY)

        # Airtime Purchase -> AIRTIME
        airtime_tx = next(t for t in categorized if "Airtime Purchase" in t.details)
        self.assertEqual(airtime_tx.category, TransactionCategory.AIRTIME)

        # Debt settlement -> DEBT_RECOVERY
        debt_tx = next(t for t in categorized if "Maina Duka Debt Settled" in t.details)
        self.assertEqual(debt_tx.category, TransactionCategory.DEBT_RECOVERY)

        # Coverage check: >= 95% rule-based match
        rule_matched = [t for t in categorized if t.category != TransactionCategory.UNCATEGORIZED]
        coverage_pct = (len(rule_matched) / len(categorized)) * 100.0
        print(f"\nRule-based resolution on sample CSV: {len(rule_matched)}/{len(categorized)} ({coverage_pct:.1f}%)")
        self.assertGreaterEqual(coverage_pct, 95.0, f"Coverage {coverage_pct:.1f}% is below 95%")

    def test_parse_multiple_sms_block(self):
        """Verify parse_multiple_sms splits and parses multi-message text blocks."""
        sms_block = """
        SK01YUUM7K Confirmed. You have received Ksh1,600.00 from John Otieno 254731829405 on 1/9/26 at 12:49 PM. New M-PESA balance is Ksh50,106.98. Transaction cost, Ksh0.00.

        SK067BQRKW Confirmed. You have received Ksh1,526.05 from Teacher Maina 254719283746 on 3/9/26 at 3:01 AM. Maina Duka Debt Settled. New M-PESA balance is Ksh41,691.42.

        SK09GF0VY6 Confirmed. You have sent Ksh2,479.42 to Bidco Africa Distributors 771234 on 3/9/26 at 11:10 AM. New M-PESA balance is Ksh42,039.06.
        """
        parsed = parse_multiple_sms(sms_block, business_id="biz_duka_1")
        self.assertEqual(len(parsed), 3)

        self.assertEqual(parsed[0].receipt_number, "SK01YUUM7K")
        self.assertEqual(parsed[0].direction, TransactionDirection.IN)
        self.assertAlmostEqual(parsed[0].amount, 1600.0)

        self.assertEqual(parsed[1].receipt_number, "SK067BQRKW")
        self.assertEqual(parsed[1].direction, TransactionDirection.IN)
        self.assertAlmostEqual(parsed[1].amount, 1526.05)

        self.assertEqual(parsed[2].receipt_number, "SK09GF0VY6")
        self.assertEqual(parsed[2].direction, TransactionDirection.OUT)
        self.assertAlmostEqual(parsed[2].amount, 2479.42)

    def test_messy_hand_written_cases_b101_to_b110(self):
        """
        Tests the 10 realistic, hand-written Kenyan transactions from Section 2.1.4:
        B101 to B110 must parse and categorize accurately without exceptions.
        """
        cases = [
            (
                "B101",
                "B101 Confirmed. Ksh 450.00 paid to KPLC PREPAID for account 1428392019 via Paybill 888880 on 12/9/26.",
                TransactionDirection.OUT,
                450.00,
                TransactionCategory.UTILITIES,
            ),
            (
                "B102",
                "B102 Confirmed. You have sent Ksh3,200.00 to Unga Limited 222111 on 12/9/26.",
                TransactionDirection.OUT,
                3200.00,
                TransactionCategory.INVENTORY,
            ),
            (
                "B103",
                "B103 Confirmed. You have received Ksh 850.00 from John Kamau 0712345678 on 12/9/26.",
                TransactionDirection.IN,
                850.00,
                TransactionCategory.SALES,
            ),
            (
                "B104",
                "B104 Confirmed. Ksh500.00 of airtime bought on 13/9/26 at 8:00 AM.",
                TransactionDirection.OUT,
                500.00,
                TransactionCategory.AIRTIME,
            ),
            (
                "B105",
                "B105 Confirmed. Transfer of Ksh12,000.00 to Landlord Mutua for Duka Rent Oct on 13/9/26.",
                TransactionDirection.OUT,
                12000.00,
                TransactionCategory.RENT,
            ),
            (
                "B106",
                "B106 Confirmed. Ksh 2,000.00 sent to Self / Personal Draw Mama Mary on 13/9/26.",
                TransactionDirection.OUT,
                2000.00,
                TransactionCategory.OWNER_DRAW,
            ),
            (
                "B107",
                "B107 Confirmed. Received Ksh 1,100.00 from Dennis Omondi deni ya unga cleared on 14/9/26.",
                TransactionDirection.IN,
                1100.00,
                TransactionCategory.DEBT_RECOVERY,
            ),
            (
                "B108",
                "B108 Confirmed. Ksh 4,500.00 sent to Brookside Dairies Milk Supplies on 14/9/26.",
                TransactionDirection.OUT,
                4500.00,
                TransactionCategory.INVENTORY,
            ),
            (
                "B109",
                "B109 Confirmed. Ksh 650.00 paid to Nairobi City Water and Sewerage on 15/9/26.",
                TransactionDirection.OUT,
                650.00,
                TransactionCategory.UTILITIES,
            ),
            (
                "B110",
                "B110 Confirmed. Received Ksh 350.00 from Mama Boi 0728192837 for sukuma wiki on 15/9/26.",
                TransactionDirection.IN,
                350.00,
                TransactionCategory.SALES,
            ),
        ]

        for code, text, expected_dir, expected_amt, expected_cat in cases:
            with self.subTest(code=code):
                tx = parse_sms_message(text, business_id="biz_duka_1")
                self.assertEqual(tx.receipt_number, code, f"Receipt code mismatch for {code}")
                self.assertEqual(tx.direction, expected_dir, f"Direction mismatch for {code}")
                self.assertAlmostEqual(tx.amount, expected_amt, delta=0.01, msg=f"Amount mismatch for {code}")

                categorized_tx = categorize_transaction(tx)
                self.assertEqual(
                    categorized_tx.category,
                    expected_cat,
                    f"Category mismatch for {code}: got {categorized_tx.category}, expected {expected_cat}",
                )
                self.assertEqual(categorized_tx.categorization_method, "RULE_BASED")

    def test_keyword_collision_edge_cases(self):
        """
        Verify that supplier keywords paying the till remain SALES,
        customer names containing 'Airtime' do not falsely trigger AIRTIME,
        and inbound debt notes trigger DEBT_RECOVERY.
        """
        # 1. Supplier name paying till -> Inbound till is SALES
        tx_till_supplier = Transaction(
            receipt_number="SK_TILL_01",
            completion_time="2026-09-10T10:00:00Z",
            details="Customer Payment to Till 789123 - Farmer's Choice 254712345678",
            amount=1500.0,
            direction=TransactionDirection.IN,
            running_balance=50000.0,
        )
        cat_supplier = categorize_transaction(tx_till_supplier)
        self.assertEqual(cat_supplier.category, TransactionCategory.SALES)

        # 2. Customer name with 'Airtime' paying till -> SALES, not AIRTIME
        tx_airtime_name = Transaction(
            receipt_number="SK_TILL_02",
            completion_time="2026-09-10T11:00:00Z",
            details="Customer Payment to Till 789123 - Grace Airtime 254712345678",
            amount=500.0,
            direction=TransactionDirection.IN,
            running_balance=50500.0,
        )
        cat_airtime = categorize_transaction(tx_airtime_name)
        self.assertEqual(cat_airtime.category, TransactionCategory.SALES)

        # 3. Inbound till with debt note -> DEBT_RECOVERY
        tx_till_debt = Transaction(
            receipt_number="SK_TILL_03",
            completion_time="2026-09-10T12:00:00Z",
            details="Customer Payment to Till 789123 - Dennis Omondi deni cleared",
            amount=1000.0,
            direction=TransactionDirection.IN,
            running_balance=51500.0,
        )
        cat_debt = categorize_transaction(tx_till_debt)
        self.assertEqual(cat_debt.category, TransactionCategory.DEBT_RECOVERY)

    def test_llm_fallback_invoked_when_unmatched(self):
        """Verify that an ambiguous transaction calls the LLM fallback and sets BEDROCK_HAIKU method."""
        ambiguous_tx = Transaction(
            receipt_number="SK99XYZ001",
            completion_time="2026-09-15T10:00:00Z",
            details="Transfer to Unknown Hardware Merchant",
            amount=2500.0,
            direction=TransactionDirection.OUT,
            running_balance=10000.0,
        )

        def mock_llm_fallback(details: str, direction: str, amount: float):
            return {"category": "INVENTORY", "confidence": 0.95}

        result = categorize_transaction(ambiguous_tx, llm_fallback_fn=mock_llm_fallback)
        self.assertEqual(result.category, TransactionCategory.INVENTORY)
        self.assertEqual(result.categorization_method, "BEDROCK_HAIKU")

    def test_csv_formatting_quirks(self):
        """Verify handling of UTF-8 BOM, Windows CRLF, comma amounts, and empty rows."""
        messy_csv = (
            "\ufeffReceipt No.,Completion Time,Details,Transaction Status,Paid In,Withdrawn,Balance\r\n"
            "SK99A1,2026-09-01 10:00:00,Customer Payment to Till 789123 - John Kamau,Completed,\"1,500.50\",,50,000.00\r\n"
            "\r\n"
            "SK99A2,2026-09-01 11:00:00,Buy Goods to Pembe Flour Mills,Completed,,\"3,200.00\",46,800.00\r\n"
            "   \r\n"
        )
        txs = parse_csv_statement(messy_csv)
        self.assertEqual(len(txs), 2)
        self.assertEqual(txs[0].receipt_number, "SK99A1")
        self.assertAlmostEqual(txs[0].amount, 1500.50)
        self.assertEqual(txs[0].direction, TransactionDirection.IN)

        self.assertEqual(txs[1].receipt_number, "SK99A2")
        self.assertAlmostEqual(txs[1].amount, 3200.00)
        self.assertEqual(txs[1].direction, TransactionDirection.OUT)


if __name__ == "__main__":
    unittest.main()
