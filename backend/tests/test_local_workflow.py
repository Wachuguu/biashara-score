"""
Sample Local Workflow Verification Test
Uses Python's standard library unittest (compatible with pytest).
Runs 100% offline with zero AWS credentials.
Proves that Devs 1, 2, and 3 can develop, mock, and test locally.
"""
import os
import sys
import csv
import unittest

# Ensure backend directory is in path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
ROOT_DIR = os.path.dirname(BACKEND_DIR)
sys.path.insert(0, BACKEND_DIR)

# Set sample path relative to root
os.environ["LOCAL_SAMPLE_DATA_PATH"] = os.path.join(ROOT_DIR, "sample-data", "mpesa_statement.csv")
os.environ["MOCK_AWS"] = "true"

from src.wrappers.s3_client import s3_client
from src.wrappers.db_client import db_client
from src.wrappers.llm_client import llm_client
from src.wrappers.sms_client import sms_client


class TestLocalDevelopmentWorkflow(unittest.TestCase):

    def test_sample_csv_exists_and_has_150_transactions(self):
        """Verify sample CSV is readable and contains realistic headers and 150 rows."""
        content = s3_client.get_statement_content("mock-key")
        self.assertNotEqual(content, "", "Sample CSV content should not be empty")
        
        lines = content.strip().split("\n")
        reader = csv.DictReader(lines)
        rows = list(reader)
        
        self.assertEqual(len(rows), 150, f"Expected 150 sample rows, got {len(rows)}")
        first_row = rows[0]
        self.assertIn("Receipt No.", first_row)
        self.assertIn("Details", first_row)
        self.assertIn("Paid In", first_row)
        self.assertIn("Withdrawn", first_row)
        self.assertIn("Balance", first_row)

    def test_mock_dynamo_db_wrapper(self):
        """Verify db_client handles in-memory writes and reads without AWS."""
        sample_tx = {
            "business_id": "test_duka_1",
            "receipt_number": "SK01TEST01",
            "amount": 1500.0,
            "category": "SALES"
        }
        db_client.put_transaction(sample_tx)
        results = db_client.get_transactions_for_business("test_duka_1")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["receipt_number"], "SK01TEST01")

    def test_mock_llm_bedrock_wrapper(self):
        """Verify llm_client falls back to deterministic mock offline."""
        res = llm_client.classify_unclear_transaction(
            details="Unknown Hardware Merchant",
            direction="OUT",
            amount=2500.0
        )
        self.assertEqual(res["category"], "INVENTORY")
        self.assertGreaterEqual(res["confidence"], 0.8)

    def test_mock_africa_talking_sms_wrapper(self):
        """Verify sms_client works offline without network call."""
        res = sms_client.send_sms("+254712345678", "Habari! Your weekly profit is KSh 3,100")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["mode"], "mock")


if __name__ == "__main__":
    unittest.main()
