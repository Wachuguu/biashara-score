"""
End-to-End (E2E) Verification Test Suite
Tests:
1. Full user journey with valid workflow:
   - Update business profile
   - Upload sample M-Pesa CSV statement (150 transactions)
   - Re-upload same CSV to verify 100% deduplication (all 150 skipped)
   - Create customer debt in Kitabu ya Deni
   - Ingest matching repayment SMS and verify automatic debt reconciliation to CLEARED
   - Retrieve financial weekly summary & multi-week series
   - Calculate Biashara Credit Score and verify 4 pillars and valid tier names
   - Download lender verification PDF report
   - Dispatch weekly summary SMS notification
2. Bad input handling & validation enforcement:
   - Empty CSV file
   - Wrong CSV columns / missing M-Pesa headers
   - Non-CSV file uploads (wrong extension & binary content)
   - Very large files exceeding 5MB limit
   - Invalid Kenyan phone numbers
   - Negative and zero debt amounts
   - Missing X-Business-Id on protected endpoints
3. Strict API contract response schema verification (field names, tier names, and error envelopes).
"""
import os
import sys
import unittest
from datetime import datetime

# Set up paths
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
ROOT_DIR = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["MOCK_AWS"] = "true"
os.environ["ENVIRONMENT"] = "dev"

from fastapi.testclient import TestClient
from local_server import app
from src.wrappers.db_client import db_client, DEFAULT_TEST_BUSINESS_ID


class TestBiasharaScoreE2EJourney(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.sample_csv_path = os.path.join(ROOT_DIR, "sample-data", "mpesa_statement.csv")
        with open(cls.sample_csv_path, "r", encoding="utf-8") as f:
            cls.sample_csv_bytes = f.read().encode("utf-8")

    def setUp(self):
        db_client.clear_mock_store()
        self.test_biz = "biz_e2e_journey_test"
        self.auth_headers = {"X-Business-Id": self.test_biz}

    def _assert_valid_error_envelope(self, data, expected_code=None):
        """Verifies error responses conform strictly to API_CONTRACT.md Section 1.2."""
        self.assertIn("error", data, f"Expected 'error' envelope in response: {data}")
        err = data["error"]
        self.assertIn("code", err)
        self.assertIn("message", err)
        self.assertIn("details", err)
        self.assertIn("timestamp", err)
        self.assertIsInstance(err["details"], list)
        if expected_code:
            self.assertEqual(err["code"], expected_code)

    # ========================================================================
    # 1. Full Journey: Success Workflow
    # ========================================================================
    def test_full_journey_success(self):
        # --------------------------------------------------------------------
        # Step 1: Set Business Profile (PUT /business)
        # --------------------------------------------------------------------
        profile_payload = {
            "shop_name": "Mama Mary Wholesale & Retail",
            "owner_name": "Mary Wambui Kamau",
            "owner_phone": "+254712345678",
            "till_number": "789123"
        }
        res_put = self.client.put("/business", json=profile_payload, headers=self.auth_headers)
        self.assertEqual(res_put.status_code, 200, res_put.text)
        biz_data = res_put.json()
        self.assertEqual(biz_data["business_id"], self.test_biz)
        self.assertEqual(biz_data["shop_name"], "Mama Mary Wholesale & Retail")
        self.assertEqual(biz_data["owner_name"], "Mary Wambui Kamau")
        self.assertEqual(biz_data["owner_phone"], "+254712345678")
        self.assertEqual(biz_data["till_number"], "789123")
        self.assertIn("created_at", biz_data)

        # Verify profile via GET /business
        res_get_biz = self.client.get("/business", headers=self.auth_headers)
        self.assertEqual(res_get_biz.status_code, 200)
        self.assertEqual(res_get_biz.json()["shop_name"], "Mama Mary Wholesale & Retail")

        # --------------------------------------------------------------------
        # Step 2: Upload M-Pesa CSV Statement First Time (POST /statements/upload)
        # --------------------------------------------------------------------
        files_first = {
            "file": ("mpesa_statement.csv", self.sample_csv_bytes, "text/csv")
        }
        res_upload1 = self.client.post("/statements/upload", files=files_first, headers=self.auth_headers)
        self.assertEqual(res_upload1.status_code, 200, res_upload1.text)
        upload1_data = res_upload1.json()

        # Check response shape strictly against API_CONTRACT.md Section 2.2.1
        self.assertEqual(upload1_data["status"], "success")
        self.assertEqual(upload1_data["business_id"], self.test_biz)
        self.assertEqual(upload1_data["statement_filename"], "mpesa_statement.csv")
        self.assertEqual(upload1_data["imported"], 150)
        self.assertEqual(upload1_data["skipped_duplicates"], 0)
        self.assertIn("categories_breakdown", upload1_data)
        self.assertIn("date_range", upload1_data)
        self.assertIn("start", upload1_data["date_range"])
        self.assertIn("end", upload1_data["date_range"])

        # Check all 8 required category breakdown keys
        required_categories = [
            "SALES", "INVENTORY", "UTILITIES", "RENT",
            "DEBT_RECOVERY", "OWNER_DRAW", "AIRTIME", "UNCATEGORIZED"
        ]
        for cat in required_categories:
            self.assertIn(cat, upload1_data["categories_breakdown"])

        # --------------------------------------------------------------------
        # Step 3: Upload SAME CSV Second Time — All 150 must be skipped as duplicates
        # --------------------------------------------------------------------
        files_second = {
            "file": ("mpesa_statement.csv", self.sample_csv_bytes, "text/csv")
        }
        res_upload2 = self.client.post("/statements/upload", files=files_second, headers=self.auth_headers)
        self.assertEqual(res_upload2.status_code, 200, res_upload2.text)
        upload2_data = res_upload2.json()
        self.assertEqual(upload2_data["status"], "success")
        self.assertEqual(upload2_data["imported"], 0)
        self.assertEqual(upload2_data["skipped_duplicates"], 150)

        # --------------------------------------------------------------------
        # Step 4: Add a Customer Debt to Kitabu ya Deni (POST /debts)
        # --------------------------------------------------------------------
        debt_payload = {
            "debtor_name": "Dennis Omondi",
            "debtor_phone": "+254728192837",
            "amount_owed": 2100.0,
            "items_summary": "2x Unga Pembe, 1x Cooking Oil 1L",
            "due_date": "2026-10-01T18:00:00Z"
        }
        res_debt = self.client.post("/debts", json=debt_payload, headers=self.auth_headers)
        self.assertEqual(res_debt.status_code, 201, res_debt.text)
        created_debt = res_debt.json()

        # Check response shape against API_CONTRACT.md Section 2.4.1
        self.assertIn("debt_id", created_debt)
        self.assertEqual(created_debt["business_id"], self.test_biz)
        self.assertEqual(created_debt["debtor_name"], "Dennis Omondi")
        self.assertEqual(created_debt["debtor_phone"], "+254728192837")
        self.assertEqual(created_debt["amount_owed"], 2100.0)
        self.assertEqual(created_debt["amount_cleared"], 0.0)
        self.assertEqual(created_debt["balance_remaining"], 2100.0)
        self.assertEqual(created_debt["status"], "UNPAID")
        self.assertEqual(created_debt["repayment_history"], [])
        debt_id = created_debt["debt_id"]

        # --------------------------------------------------------------------
        # Step 5: Upload/Paste Matching Repayment SMS (POST /statements/sms)
        # --------------------------------------------------------------------
        repayment_sms = (
            "SK99REPAY1 Confirmed. You have received Ksh2,100.00 from Dennis Omondi "
            "254728192837 on 5/10/26 at 2:15 PM. Dennis deni cleared. New M-PESA balance is Ksh55,000.00."
        )
        res_sms = self.client.post("/statements/sms", json={"sms_text": repayment_sms}, headers=self.auth_headers)
        self.assertEqual(res_sms.status_code, 201, res_sms.text)
        sms_data = res_sms.json()

        self.assertEqual(sms_data["status"], "success")
        self.assertEqual(sms_data["imported"], 1)
        self.assertEqual(sms_data["skipped_duplicates"], 0)
        self.assertEqual(sms_data["debts_auto_matched"], 1)
        reconciled_tx = sms_data["transactions"][0]
        self.assertEqual(reconciled_tx["receipt_number"], "SK99REPAY1")
        self.assertEqual(reconciled_tx["category"], "DEBT_RECOVERY")
        self.assertEqual(reconciled_tx["debt_matched_id"], debt_id)

        # Verify debt record is now CLEARED in Kitabu ya Deni
        res_debts_list = self.client.get("/debts", headers=self.auth_headers)
        self.assertEqual(res_debts_list.status_code, 200)
        debts_list_data = res_debts_list.json()
        matched_debt = next((d for d in debts_list_data["debts"] if d["debt_id"] == debt_id), None)
        self.assertIsNotNone(matched_debt)
        self.assertEqual(matched_debt["status"], "CLEARED")
        self.assertEqual(matched_debt["balance_remaining"], 0.0)
        self.assertEqual(matched_debt["amount_cleared"], 2100.0)
        self.assertEqual(len(matched_debt["repayment_history"]), 1)
        self.assertEqual(matched_debt["repayment_history"][0]["receipt_number"], "SK99REPAY1")

        # --------------------------------------------------------------------
        # Step 6: Fetch Weekly Summary & Historical Series (GET /summary/weekly)
        # --------------------------------------------------------------------
        res_summary = self.client.get("/summary/weekly?weeks=4", headers=self.auth_headers)
        self.assertEqual(res_summary.status_code, 200, res_summary.text)
        summary_data = res_summary.json()

        # Check response shape against API_CONTRACT.md Section 2.3.1
        self.assertEqual(summary_data["business_id"], self.test_biz)
        self.assertEqual(summary_data["currency"], "KSh")
        self.assertIn("current_week", summary_data)
        self.assertIn("history_series", summary_data)

        cw = summary_data["current_week"]
        self.assertIn("week_label", cw)
        self.assertIn("start_date", cw)
        self.assertIn("end_date", cw)
        self.assertIn("gross_sales", cw)
        self.assertIn("operating_expenses", cw)
        self.assertIn("estimated_profit", cw)
        self.assertIn("profit_margin_pct", cw)
        self.assertIn("active_trading_days", cw)
        self.assertLessEqual(cw["active_trading_days"], 7, "A single ISO week must not have > 7 active trading days")
        self.assertEqual(cw["week_label"], "2026-W41")
        self.assertIn("transaction_count", cw)
        self.assertIn("expense_breakdown", cw)
        self.assertIn("pulse_message", cw)
        self.assertGreater(cw["gross_sales"], 0)

        self.assertIsInstance(summary_data["history_series"], list)
        self.assertGreaterEqual(len(summary_data["history_series"]), 1)
        # Ensure no overlap with current_week
        hist_week_labels = [h["week_label"] for h in summary_data["history_series"]]
        self.assertNotIn(cw["week_label"], hist_week_labels)
        first_hist = summary_data["history_series"][0]
        self.assertIn("week_label", first_hist)
        self.assertIn("gross_sales", first_hist)
        self.assertIn("operating_expenses", first_hist)
        self.assertIn("estimated_profit", first_hist)
        self.assertIn("profit_margin_pct", first_hist)

        # --------------------------------------------------------------------
        # Step 7: Fetch Biashara Credit Score (GET /score & POST /score/calculate)
        # --------------------------------------------------------------------
        res_score = self.client.get("/score", headers=self.auth_headers)
        self.assertEqual(res_score.status_code, 200, res_score.text)
        score_data = res_score.json()

        # Check response shape against API_CONTRACT.md Section 2.5.1
        self.assertEqual(score_data["business_id"], self.test_biz)
        self.assertIn("total_score", score_data)
        self.assertIn("tier", score_data)
        self.assertIn("consistency_score", score_data)
        self.assertIn("growth_score", score_data)
        self.assertIn("expense_ratio_score", score_data)
        self.assertIn("debt_recovery_score", score_data)
        self.assertIn("weekly_turnover_avg", score_data)
        self.assertIn("weekly_profit_avg", score_data)
        self.assertIn("debt_recovery_rate", score_data)
        self.assertIn("computed_at", score_data)
        self.assertIn("actionable_tips", score_data)

        # Value bounds and arithmetic consistency
        self.assertTrue(0 <= score_data["total_score"] <= 100)
        self.assertEqual(
            score_data["total_score"],
            score_data["consistency_score"] + score_data["growth_score"] +
            score_data["expense_ratio_score"] + score_data["debt_recovery_score"]
        )
        valid_tiers = ["Gold", "Silver", "Bronze", "Needs Improvement"]
        self.assertIn(score_data["tier"], valid_tiers, f"Tier '{score_data['tier']}' not in {valid_tiers}")
        self.assertGreaterEqual(len(score_data["actionable_tips"]), 2)

        # Verify on-demand POST /score/calculate returns same valid structure
        res_calc = self.client.post("/score/calculate", headers=self.auth_headers)
        self.assertEqual(res_calc.status_code, 200)
        self.assertEqual(res_calc.json()["total_score"], score_data["total_score"])

        # --------------------------------------------------------------------
        # Step 8: Download Lender-Ready PDF Report (GET /reports/lender-pdf)
        # --------------------------------------------------------------------
        res_pdf = self.client.get("/reports/lender-pdf", headers=self.auth_headers)
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf.headers.get("content-type"), "application/pdf")
        self.assertIn("attachment", res_pdf.headers.get("content-disposition", ""))
        self.assertTrue(res_pdf.content.startswith(b"%PDF-"))
        self.assertGreater(len(res_pdf.content), 3000)

        # --------------------------------------------------------------------
        # Step 9: Weekly SMS Dispatch (POST /notifications/weekly-sms)
        # --------------------------------------------------------------------
        sms_dispatch_payload = {
            "override_phone": "+254712345678",
            "week_label": "2026-W36"
        }
        res_sms_disp = self.client.post(
            "/notifications/weekly-sms",
            json=sms_dispatch_payload,
            headers=self.auth_headers
        )
        self.assertEqual(res_sms_disp.status_code, 200, res_sms_disp.text)
        disp_data = res_sms_disp.json()

        # Check response shape against API_CONTRACT.md Section 2.6.1
        self.assertEqual(disp_data["status"], "success")
        self.assertEqual(disp_data["business_id"], self.test_biz)
        self.assertEqual(disp_data["recipient_phone"], "+254712345678")
        self.assertIn("sms_text", disp_data)
        self.assertIn("Habari", disp_data["sms_text"])
        self.assertIn("provider_response", disp_data)
        self.assertEqual(disp_data["provider_response"]["mode"], "mock")
        self.assertIn("dispatched_at", disp_data)

    # ========================================================================
    # 2. Bad Input Tests
    # ========================================================================
    def test_bad_input_empty_file(self):
        """Empty file upload should return HTTP 400 INVALID_STATEMENT_FORMAT."""
        files = {"file": ("empty.csv", b"", "text/csv")}
        res = self.client.post("/statements/upload", files=files, headers=self.auth_headers)
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self._assert_valid_error_envelope(data, expected_code="INVALID_STATEMENT_FORMAT")

    def test_bad_input_wrong_columns(self):
        """CSV file with non-M-Pesa columns should return HTTP 400 INVALID_STATEMENT_FORMAT."""
        wrong_csv = "Item,Price,Quantity\nMilk,60,2\nBread,65,1\n"
        files = {"file": ("wrong_cols.csv", wrong_csv.encode("utf-8"), "text/csv")}
        res = self.client.post("/statements/upload", files=files, headers=self.auth_headers)
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self._assert_valid_error_envelope(data, expected_code="INVALID_STATEMENT_FORMAT")
        self.assertIn("The uploaded CSV file is missing required M-Pesa header columns.", data["error"]["message"])
        self.assertTrue(any("Receipt No." in d.get("issue", "") for d in data["error"].get("details", [])))

    def test_bad_input_non_csv_file(self):
        """Non-CSV file upload (e.g. PDF or binary) should return HTTP 400 INVALID_STATEMENT_FORMAT."""
        # Non-csv extension
        pdf_bytes = b"%PDF-1.4 mock binary pdf content"
        files_pdf = {"file": ("statement.pdf", pdf_bytes, "application/pdf")}
        res_pdf = self.client.post("/statements/upload", files=files_pdf, headers=self.auth_headers)
        self.assertEqual(res_pdf.status_code, 400)
        self._assert_valid_error_envelope(res_pdf.json(), expected_code="INVALID_STATEMENT_FORMAT")

        # Binary null bytes in .csv
        binary_bytes = b"Receipt No.,Details\x00\x01\x02\nSK01,Test"
        files_bin = {"file": ("binary.csv", binary_bytes, "text/csv")}
        res_bin = self.client.post("/statements/upload", files=files_bin, headers=self.auth_headers)
        self.assertEqual(res_bin.status_code, 400)
        self._assert_valid_error_envelope(res_bin.json(), expected_code="INVALID_STATEMENT_FORMAT")

    def test_bad_input_very_large_file(self):
        """Files exceeding 5MB limit should return HTTP 400 or 413 error envelope."""
        # Generate 5.5MB dummy content
        oversized_content = ("Receipt No.,Completion Time,Details,Paid In,Withdrawn,Balance\n" +
                             ("SK01TEST,2026-09-01 12:00:00,Customer Till,100.00,,5000.00\n" * 100000))
        oversized_bytes = oversized_content.encode("utf-8")
        self.assertGreater(len(oversized_bytes), 5 * 1024 * 1024)

        files = {"file": ("large_statement.csv", oversized_bytes, "text/csv")}
        res = self.client.post("/statements/upload", files=files, headers=self.auth_headers)
        self.assertIn(res.status_code, [400, 413])
        data = res.json()
        self._assert_valid_error_envelope(data)
        self.assertIn(data["error"]["code"], ["VALIDATION_ERROR", "PAYLOAD_TOO_LARGE"])

    def test_bad_input_invalid_phone_numbers(self):
        """Invalid phone numbers across debts, profile and SMS should be rejected with HTTP 400 VALIDATION_ERROR."""
        invalid_phones = ["12345", "not-a-phone", "+12345678901", "0201234567"]

        for bad_phone in invalid_phones:
            # 1. Kitabu ya Deni: POST /debts
            bad_debt = {
                "debtor_name": "Test Debtor",
                "debtor_phone": bad_phone,
                "amount_owed": 1500.0
            }
            res_debt = self.client.post("/debts", json=bad_debt, headers=self.auth_headers)
            self.assertEqual(res_debt.status_code, 400, f"Expected 400 for debtor_phone '{bad_phone}'")
            self._assert_valid_error_envelope(res_debt.json(), expected_code="VALIDATION_ERROR")

            # 2. Business Profile: PUT /business
            res_biz = self.client.put("/business", json={"owner_phone": bad_phone}, headers=self.auth_headers)
            self.assertEqual(res_biz.status_code, 400, f"Expected 400 for owner_phone '{bad_phone}'")
            self._assert_valid_error_envelope(res_biz.json(), expected_code="VALIDATION_ERROR")

            # 3. Weekly SMS: POST /notifications/weekly-sms
            res_sms = self.client.post(
                "/notifications/weekly-sms",
                json={"override_phone": bad_phone},
                headers=self.auth_headers
            )
            self.assertEqual(res_sms.status_code, 400, f"Expected 400 for override_phone '{bad_phone}'")
            self._assert_valid_error_envelope(res_sms.json(), expected_code="VALIDATION_ERROR")

    def test_bad_input_negative_and_zero_debt_amounts(self):
        """Negative and zero amounts in debts should return HTTP 400 VALIDATION_ERROR."""
        # 1. Negative amount_owed in POST /debts
        neg_debt = {
            "debtor_name": "Test Debtor",
            "debtor_phone": "+254712345678",
            "amount_owed": -500.0
        }
        res_neg = self.client.post("/debts", json=neg_debt, headers=self.auth_headers)
        self.assertEqual(res_neg.status_code, 400)
        self._assert_valid_error_envelope(res_neg.json(), expected_code="VALIDATION_ERROR")

        # Zero amount_owed
        zero_debt = {
            "debtor_name": "Test Debtor",
            "debtor_phone": "+254712345678",
            "amount_owed": 0.0
        }
        res_zero = self.client.post("/debts", json=zero_debt, headers=self.auth_headers)
        self.assertEqual(res_zero.status_code, 400)
        self._assert_valid_error_envelope(res_zero.json(), expected_code="VALIDATION_ERROR")

        # Create valid debt for PATCH test
        valid_debt = {
            "debtor_name": "Test Debtor",
            "debtor_phone": "+254712345678",
            "amount_owed": 1000.0
        }
        res_valid = self.client.post("/debts", json=valid_debt, headers=self.auth_headers)
        self.assertEqual(res_valid.status_code, 201)
        debt_id = res_valid.json()["debt_id"]

        # 2. Negative amount_to_clear in PATCH /debts/{debt_id}
        patch_neg = {"amount_to_clear": -300.0}
        res_patch_neg = self.client.patch(f"/debts/{debt_id}", json=patch_neg, headers=self.auth_headers)
        self.assertEqual(res_patch_neg.status_code, 400)
        self._assert_valid_error_envelope(res_patch_neg.json(), expected_code="VALIDATION_ERROR")

    def test_missing_x_business_id_mock_fallback_and_prod_rejection(self):
        """
        In mock mode (MOCK_AWS=true), missing X-Business-Id falls back to DEFAULT_TEST_BUSINESS_ID (biz_7a8b9c0d1e2f).
        In production mode (MOCK_AWS=false), X-Business-Id is rejected with 403, and Bearer auth is required (401).
        """
        # 1. Mock Mode: Missing header falls back to default test business
        res_biz = self.client.get("/business")
        self.assertEqual(res_biz.status_code, 200)
        self.assertEqual(res_biz.json()["business_id"], DEFAULT_TEST_BUSINESS_ID)

        res_score = self.client.get("/score")
        self.assertEqual(res_score.status_code, 200)

        res_summary = self.client.get("/summary/weekly")
        self.assertEqual(res_summary.status_code, 200)

        # 2. Production Mode: Header rejected (403), Bearer auth required (401)
        os.environ["MOCK_AWS"] = "false"
        try:
            # Request sending X-Business-Id must be rejected with 403 Forbidden
            res_forbidden = self.client.get("/business", headers={"X-Business-Id": "biz_attack"})
            self.assertEqual(res_forbidden.status_code, 403)
            self._assert_valid_error_envelope(res_forbidden.json(), expected_code="FORBIDDEN")

            # Request without X-Business-Id or Bearer auth must be rejected with 401 Unauthorized
            res_unauth = self.client.get("/business")
            self.assertEqual(res_unauth.status_code, 401)
            self._assert_valid_error_envelope(res_unauth.json(), expected_code="UNAUTHORIZED")
        finally:
            os.environ["MOCK_AWS"] = "true"

        # 3. Public endpoint /health does NOT require X-Business-Id in any mode
        res_health = self.client.get("/health")
        self.assertEqual(res_health.status_code, 200)
        self.assertEqual(res_health.json()["status"], "healthy")


if __name__ == "__main__":
    unittest.main()
