"""
Daraja M-Pesa Integration Tests
Verifies C2B validation, C2B confirmation, auto debt-reconciliation,
and live payment simulation.
"""
import unittest
import os
import sys
import json

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from src.wrappers.db_client import db_client, DEFAULT_TEST_BUSINESS_ID
from src.wrappers.daraja_client import daraja_client
from src.handlers.daraja_handler import (
    execute_c2b_validation,
    execute_c2b_confirmation,
    execute_simulate_payment,
    execute_load_sample_statement
)
from src.handlers.debt_handler import execute_create_debt
from src.core.models import DebtStatus


class TestDarajaIntegration(unittest.TestCase):
    def setUp(self):
        db_client.clear_mock_store()
        self.biz_id = DEFAULT_TEST_BUSINESS_ID

    def test_c2b_validation_webhook(self):
        """Safaricom C2B validation must return ResultCode 0 Accepted."""
        res = execute_c2b_validation({"TransID": "RKT12345", "TransAmount": "500.00"})
        self.assertEqual(res["ResultCode"], 0)
        self.assertEqual(res["ResultDesc"], "Accepted")

    def test_c2b_confirmation_ingestion(self):
        """Safaricom C2B confirmation must create a SALES transaction."""
        payload = {
            "TransactionType": "Customer Buy Goods",
            "TransID": "SK99XYZ001",
            "TransTime": "20261125123000",
            "TransAmount": "2500.00",
            "BusinessShortCode": "789123",
            "BillRefNumber": "",
            "MSISDN": "254712345678",
            "FirstName": "Grace",
            "LastName": "Muthoni"
        }
        res = execute_c2b_confirmation(payload, target_business_id=self.biz_id)
        self.assertEqual(res["ResultCode"], 0)
        self.assertFalse(res["debt_matched"])

        txs = db_client.get_transactions_for_business(self.biz_id)
        matching = [t for t in txs if t["receipt_number"] == "SK99XYZ001"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["amount"], 2500.0)
        self.assertEqual(matching[0]["category"], "SALES")
        self.assertEqual(matching[0]["counterparty"], "Grace Muthoni")

    def test_c2b_confirmation_auto_reconciles_customer_debt(self):
        """When an incoming M-Pesa C2B payment matches a customer debt, it auto-clears the debt."""
        # 1. Create a customer debt for Peter Kamau (0722998877) owing 1,600
        debt_res = execute_create_debt(self.biz_id, {
            "debtor_name": "Peter Kamau",
            "debtor_phone": "0722 998 877",
            "amount_owed": 1600.0,
            "items_summary": "1 bale unga, 2kg sugar"
        })
        debt_id = debt_res["body"]["debt_id"]

        # 2. Simulate customer paying KSh 1,600 from that phone
        payload = {
            "TransactionType": "Customer Buy Goods",
            "TransID": "SK99DEBT01",
            "TransTime": "20261125134500",
            "TransAmount": "1600.00",
            "BusinessShortCode": "789123",
            "BillRefNumber": "",
            "MSISDN": "254722998877",
            "FirstName": "Peter",
            "LastName": "Kamau"
        }
        res = execute_c2b_confirmation(payload, target_business_id=self.biz_id)
        self.assertEqual(res["ResultCode"], 0)
        self.assertTrue(res["debt_matched"])

        # 3. Verify debt status is now CLEARED
        updated_debts = db_client.get_debts_for_business(self.biz_id)
        target = [d for d in updated_debts if d["debt_id"] == debt_id][0]
        self.assertEqual(target["status"], DebtStatus.CLEARED.value)
        self.assertEqual(target["balance_remaining"], 0.0)
        self.assertEqual(target["amount_cleared"], 1600.0)

    def test_simulate_payment_endpoint(self):
        """The simulation endpoint produces an instant transaction for interactive demos."""
        res = execute_simulate_payment(self.biz_id, {
            "amount": 3500.0,
            "phone": "+254701234567",
            "customer_name": "David Mwangi"
        })
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["simulated"])
        self.assertEqual(res["payload"]["TransAmount"], "3500.00")

    def test_load_sample_statement(self):
        """1-Click sample statement loader imports the full dataset."""
        res = execute_load_sample_statement(self.biz_id)
        self.assertEqual(res["status"], "success")
        self.assertGreaterEqual(res["imported"], 100)


if __name__ == "__main__":
    unittest.main()
