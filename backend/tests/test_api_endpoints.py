"""
Comprehensive Unit & Integration Test Suite for Workstream D
Tests:
- API Handler (AWS Lambda entry point)
- Local Server (FastAPI TestClient)
- Endpoints:
  1. GET /health
  2. GET /business & PUT /business
  3. POST /statements/upload (CSV statement upload, deduplication, auto-reconciliation)
  4. POST /statements/sms (SMS text ingestion)
  5. GET /transactions (Filtering and pagination)
  6. GET /summary/weekly (Weekly performance pulse and multi-week series)
  7. POST /debts (Create debt record)
  8. GET /debts (List debts with summary recovery metrics)
  9. PATCH /debts/{debt_id} (Log repayment and update status)
  10. GET /score & POST /score/calculate (Biashara Credit Scoring)
  11. GET /reports/lender-pdf (Lender verification PDF download)
  12. POST /notifications/weekly-sms (Africa's Talking SMS digest)
- CORS validation for http://localhost:3000
- Multi-tenant tenant isolation via X-Business-Id
"""
import os
import sys
import json
import base64
import re
import unittest
from datetime import datetime, timezone

# Ensure backend root is in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
ROOT_DIR = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["MOCK_AWS"] = "true"
os.environ["ENVIRONMENT"] = "dev"

from fastapi.testclient import TestClient
from local_server import app
from src.handlers.api_handler import lambda_handler
from src.wrappers.db_client import db_client, DEFAULT_TEST_BUSINESS, DEFAULT_TEST_BUSINESS_ID


class TestApiEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.sample_csv_path = os.path.join(ROOT_DIR, "sample-data", "mpesa_statement.csv")
        with open(cls.sample_csv_path, "r", encoding="utf-8") as f:
            cls.sample_csv_content = f.read()

    def setUp(self):
        # Reset mock database store before each test
        db_client.clear_mock_store()

    # ========================================================================
    # 1. Health Check
    # ========================================================================
    def test_health_check_fastapi_and_lambda(self):
        # Test FastAPI endpoint
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["environment"], "dev")
        self.assertTrue(data["mock_aws"])

        # Test Lambda Handler
        lambda_event = {"rawPath": "/health", "httpMethod": "GET"}
        lambda_res = lambda_handler(lambda_event, None)
        self.assertEqual(lambda_res["statusCode"], 200)
        body = json.loads(lambda_res["body"])
        self.assertEqual(body["status"], "healthy")

    # ========================================================================
    # 2. CORS Preflight & Headers
    # ========================================================================
    def test_cors_headers_fastapi(self):
        headers = {
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-Business-Id, Content-Type"
        }
        res = self.client.options("/health", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("access-control-allow-origin"), "http://localhost:3000")

    def test_cors_headers_lambda(self):
        lambda_event = {
            "rawPath": "/statements/upload",
            "httpMethod": "OPTIONS",
            "headers": {"origin": "http://localhost:3000"}
        }
        lambda_res = lambda_handler(lambda_event, None)
        self.assertEqual(lambda_res["statusCode"], 200)
        self.assertIn("Access-Control-Allow-Origin", lambda_res["headers"])

    # ========================================================================
    # 3. Business Profile (GET & PUT)
    # ========================================================================
    def test_business_profile_get_and_put(self):
        test_biz_id = "biz_custom_duka"
        # 1. GET default profile
        res = self.client.get("/business", headers={"X-Business-Id": test_biz_id})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["business_id"], test_biz_id)

        # 2. PUT update profile
        update_payload = {
            "shop_name": "Mama Mary Wholesale Superette",
            "owner_name": "Mary Wambui Kamau",
            "owner_phone": "+254712345678",
            "till_number": "889900"
        }
        res_put = self.client.put("/business", json=update_payload, headers={"X-Business-Id": test_biz_id})
        self.assertEqual(res_put.status_code, 200)
        updated = res_put.json()
        self.assertEqual(updated["shop_name"], "Mama Mary Wholesale Superette")
        self.assertEqual(updated["till_number"], "889900")

        # 3. Verify persistence
        res_verify = self.client.get("/business", headers={"X-Business-Id": test_biz_id})
        self.assertEqual(res_verify.json()["shop_name"], "Mama Mary Wholesale Superette")

    # ========================================================================
    # 4. Statement Ingestion (CSV Upload & Deduplication)
    # ========================================================================
    def test_statement_upload_and_deduplication(self):
        test_biz = "biz_test_upload"

        # 1. Pre-seed a known debt to test auto-matching during CSV upload
        # Teacher Maina phone: +254719283746, debt: 1526.05
        debt_payload = {
            "debtor_name": "Teacher Maina",
            "debtor_phone": "+254719283746",
            "amount_owed": 1526.05,
            "items_summary": "1x Unga, Sugar"
        }
        debt_res = self.client.post("/debts", json=debt_payload, headers={"X-Business-Id": test_biz})
        self.assertEqual(debt_res.status_code, 201)
        created_debt = debt_res.json()
        self.assertEqual(created_debt["status"], "UNPAID")

        # 2. Upload sample CSV (150 rows)
        files = {"file": ("mpesa_statement.csv", self.sample_csv_content.encode("utf-8"), "text/csv")}
        res = self.client.post("/statements/upload", files=files, headers={"X-Business-Id": test_biz})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["imported"], 150)
        self.assertEqual(data["skipped_duplicates"], 0)
        self.assertGreaterEqual(data["debts_auto_matched"], 1)
        self.assertIn("SALES", data["categories_breakdown"])

        # 3. Verify that the open debt was automatically cleared by SK067BQRKW
        debts_res = self.client.get("/debts", headers={"X-Business-Id": test_biz})
        debts_data = debts_res.json()
        matched_debt = next((d for d in debts_data["debts"] if d["debt_id"] == created_debt["debt_id"]), None)
        self.assertIsNotNone(matched_debt)
        self.assertEqual(matched_debt["status"], "CLEARED")
        self.assertEqual(matched_debt["balance_remaining"], 0.0)

        # 4. Upload SAME CSV again — should skip all 150 as duplicates
        files_dup = {"file": ("mpesa_statement.csv", self.sample_csv_content.encode("utf-8"), "text/csv")}
        res_dup = self.client.post("/statements/upload", files=files_dup, headers={"X-Business-Id": test_biz})
        self.assertEqual(res_dup.status_code, 200)
        data_dup = res_dup.json()
        self.assertEqual(data_dup["imported"], 0)
        self.assertEqual(data_dup["skipped_duplicates"], 150)

    # ========================================================================
    # 5. Quick-Entry SMS Ingestion
    # ========================================================================
    def test_quick_entry_sms_ingestion(self):
        test_biz = "biz_test_sms"
        sms_text = (
            "SK01YUUM7K Confirmed. You have received Ksh1,600.00 from John Otieno 254731829405 on 1/9/26 at 12:49 PM. "
            "New M-PESA balance is Ksh50,106.98. Transaction cost, Ksh0.00.\n\n"
            "SK067BQRKW Confirmed. You have received Ksh1,526.05 from Teacher Maina 254719283746 on 3/9/26 at 3:01 AM. "
            "Maina Duka Debt Settled. New M-PESA balance is Ksh41,691.42."
        )

        res = self.client.post("/statements/sms", json={"sms_text": sms_text}, headers={"X-Business-Id": test_biz})
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["imported"], 2)
        self.assertEqual(data["skipped_duplicates"], 0)
        self.assertEqual(len(data["transactions"]), 2)

        # Duplicate check on SMS
        res_dup = self.client.post("/statements/sms", json={"sms_text": sms_text}, headers={"X-Business-Id": test_biz})
        self.assertEqual(res_dup.status_code, 201)
        self.assertEqual(res_dup.json()["skipped_duplicates"], 2)
        self.assertEqual(res_dup.json()["imported"], 0)

    # ========================================================================
    # 6. List Transactions with Filtering and Slicing
    # ========================================================================
    def test_list_transactions_filters(self):
        test_biz = "biz_test_tx_filter"
        files = {"file": ("mpesa_statement.csv", self.sample_csv_content.encode("utf-8"), "text/csv")}
        self.client.post("/statements/upload", files=files, headers={"X-Business-Id": test_biz})

        # 1. Default fetch
        res = self.client.get("/transactions?limit=20", headers={"X-Business-Id": test_biz})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total_count"], 150)
        self.assertEqual(len(data["transactions"]), 20)
        self.assertIsNotNone(data["next_cursor"])

        # 2. Filter by category
        res_rent = self.client.get("/transactions?category=RENT", headers={"X-Business-Id": test_biz})
        self.assertEqual(res_rent.status_code, 200)
        data_rent = res_rent.json()
        self.assertGreater(data_rent["total_count"], 0)
        for tx in data_rent["transactions"]:
            self.assertEqual(tx["category"], "RENT")

        # 3. Filter by direction
        res_out = self.client.get("/transactions?direction=OUT&limit=10", headers={"X-Business-Id": test_biz})
        self.assertEqual(res_out.status_code, 200)
        for tx in res_out.json()["transactions"]:
            self.assertEqual(tx["direction"], "OUT")

    # ========================================================================
    # 7. Kitabu ya Deni: Create, List & Update Debts
    # ========================================================================
    def test_kitabu_ya_deni_lifecycle(self):
        test_biz = "biz_kitabu_test"

        # 1. Create debt
        debt_payload = {
            "debtor_name": "Dennis Omondi (Mama Boi)",
            "debtor_phone": "0728192837",
            "amount_owed": 2100.0,
            "items_summary": "2x Unga Pembe, 1x Cooking Oil 1L",
            "due_date": "2026-09-16T18:00:00Z"
        }
        res_create = self.client.post("/debts", json=debt_payload, headers={"X-Business-Id": test_biz})
        self.assertEqual(res_create.status_code, 201)
        created = res_create.json()
        debt_id = created["debt_id"]
        self.assertEqual(created["debtor_phone"], "+254728192837")
        self.assertEqual(created["balance_remaining"], 2100.0)
        self.assertEqual(created["status"], "UNPAID")

        # 2. List debts
        res_list = self.client.get("/debts", headers={"X-Business-Id": test_biz})
        self.assertEqual(res_list.status_code, 200)
        list_data = res_list.json()
        self.assertEqual(list_data["summary"]["total_outstanding_amount"], 2100.0)
        self.assertEqual(list_data["summary"]["unpaid_count"], 1)

        # 3. Partial repayment via PATCH
        patch_payload_1 = {
            "amount_to_clear": 1000.0,
            "receipt_number": "SK067PARTIAL",
            "notes": "Partial cash payment"
        }
        res_patch1 = self.client.patch(f"/debts/{debt_id}", json=patch_payload_1, headers={"X-Business-Id": test_biz})
        self.assertEqual(res_patch1.status_code, 200)
        data_p1 = res_patch1.json()
        self.assertEqual(data_p1["balance_remaining"], 1100.0)
        self.assertEqual(data_p1["amount_cleared"], 1000.0)
        self.assertEqual(data_p1["status"], "PARTIAL")

        # 4. Settle remaining debt via PATCH
        patch_payload_2 = {
            "amount_to_clear": 1100.0,
            "receipt_number": "CASH_FINAL",
            "notes": "Balance cleared"
        }
        res_patch2 = self.client.patch(f"/debts/{debt_id}", json=patch_payload_2, headers={"X-Business-Id": test_biz})
        self.assertEqual(res_patch2.status_code, 200)
        data_p2 = res_patch2.json()
        self.assertEqual(data_p2["balance_remaining"], 0.0)
        self.assertEqual(data_p2["status"], "CLEARED")
        self.assertEqual(len(data_p2["repayment_history"]), 2)

    # ========================================================================
    # 8. Weekly Summary & Financial Pulse
    # ========================================================================
    def test_get_weekly_summary(self):
        test_biz = "biz_test_summary"
        files = {"file": ("mpesa_statement.csv", self.sample_csv_content.encode("utf-8"), "text/csv")}
        self.client.post("/statements/upload", files=files, headers={"X-Business-Id": test_biz})

        res = self.client.get("/summary/weekly?weeks=4", headers={"X-Business-Id": test_biz})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["currency"], "KSh")
        self.assertIn("current_week", data)
        self.assertIn("history_series", data)

        cw = data["current_week"]
        # Bug 1 verification: A week must never have more than 7 active trading days
        self.assertLessEqual(cw["active_trading_days"], 7, "A single ISO week must not have > 7 active trading days")
        self.assertEqual(cw["active_trading_days"], 6)
        self.assertEqual(cw["week_label"], "2026-W40")
        self.assertEqual(cw["start_date"], "2026-09-28")
        self.assertEqual(cw["end_date"], "2026-10-04")
        self.assertEqual(cw["transaction_count"], 30)
        self.assertEqual(cw["gross_sales"], 42917.44)
        self.assertIn("You made KSh 42,917 this week, profit KSh 22,922.", cw["pulse_message"])

        # History series must be trailing 4 weeks before current_week with NO overlap
        history = data["history_series"]
        self.assertEqual(len(history), 4)
        hist_labels = [h["week_label"] for h in history]
        self.assertEqual(hist_labels, ["2026-W36", "2026-W37", "2026-W38", "2026-W39"])
        self.assertNotIn(cw["week_label"], hist_labels)

        for h in history:
            self.assertLessEqual(h.get("active_trading_days", 0), 7)

    # ========================================================================
    # 9. Biashara Credit Scoring (GET & POST)
    # ========================================================================
    def test_credit_score_calculation(self):
        test_biz = "biz_test_score"
        files = {"file": ("mpesa_statement.csv", self.sample_csv_content.encode("utf-8"), "text/csv")}
        self.client.post("/statements/upload", files=files, headers={"X-Business-Id": test_biz})

        # GET /score
        res = self.client.get("/score", headers={"X-Business-Id": test_biz})
        self.assertEqual(res.status_code, 200)
        score_data = res.json()
        self.assertIn("total_score", score_data)
        self.assertIn("tier", score_data)
        self.assertIn(score_data["tier"], ["Gold", "Silver", "Bronze", "Needs Improvement"])
        # Requirement 4: debt_recovery_rate is null and debt_recovery_score is neutral (15) when there are no debts
        self.assertIsNone(score_data["debt_recovery_rate"])
        self.assertEqual(score_data["debt_recovery_score"], 15)
        self.assertTrue(0 <= score_data["total_score"] <= 100)
        self.assertEqual(
            score_data["total_score"],
            score_data["consistency_score"] + score_data["growth_score"] +
            score_data["expense_ratio_score"] + score_data["debt_recovery_score"]
        )
        self.assertGreaterEqual(len(score_data["actionable_tips"]), 2)

        # POST /score/calculate (force on-demand)
        res_post = self.client.post("/score/calculate", headers={"X-Business-Id": test_biz})
        self.assertEqual(res_post.status_code, 200)
        self.assertEqual(res_post.json()["total_score"], score_data["total_score"])

    # ========================================================================
    # 10. Lender-Ready PDF Report Download
    # ========================================================================
    def test_download_lender_pdf_report(self):
        test_biz = "biz_test_pdf"
        files = {"file": ("mpesa_statement.csv", self.sample_csv_content.encode("utf-8"), "text/csv")}
        self.client.post("/statements/upload", files=files, headers={"X-Business-Id": test_biz})

        # FastApi direct download
        res = self.client.get("/reports/lender-pdf", headers={"X-Business-Id": test_biz})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("content-type"), "application/pdf")
        self.assertTrue(res.content.startswith(b"%PDF-"))
        self.assertGreater(len(res.content), 2000)

        # Single page check
        self.assertEqual(len(re.findall(rb"/Type\s*/Page[^s]", res.content)), 1)
        pdf_text = res.content.decode("latin1", errors="ignore")
        self.assertIn("No customer credit recorded", pdf_text)
        self.assertIn("Prepared by Biashara Score from an uploaded M-Pesa statement. Figures are not verified by Safaricom or any financial institution.", pdf_text)
        clean_pdf_text = re.sub(r"(?i)\bnot verified\b", "", pdf_text)
        self.assertNotIn("verified", clean_pdf_text.lower())
        self.assertNotIn("certified", pdf_text.lower())
        self.assertIn("Last 4 weeks", pdf_text)
        self.assertIn("Gold 80+, Silver 65-79, Bronze 50-64, Needs Improvement below 50", pdf_text)

        # Lambda handler PDF event with base64 decoding check
        lambda_event = {
            "rawPath": "/reports/lender-pdf",
            "httpMethod": "GET",
            "headers": {"x-business-id": test_biz}
        }
        lambda_res = lambda_handler(lambda_event, None)
        self.assertEqual(lambda_res["statusCode"], 200)
        self.assertTrue(lambda_res.get("isBase64Encoded"))
        pdf_decoded = base64.b64decode(lambda_res["body"])
        self.assertTrue(pdf_decoded.startswith(b"%PDF-"))
        self.assertEqual(len(re.findall(rb"/Type\s*/Page[^s]", pdf_decoded)), 1)

    # ========================================================================
    # 11. SMS Notification Dispatch
    # ========================================================================
    def test_weekly_sms_notification(self):
        test_biz = "biz_test_sms_dispatch"
        files = {"file": ("mpesa_statement.csv", self.sample_csv_content.encode("utf-8"), "text/csv")}
        self.client.post("/statements/upload", files=files, headers={"X-Business-Id": test_biz})

        sms_payload = {
            "override_phone": "+254712345678",
            "week_label": "2026-W36"
        }
        res = self.client.post("/notifications/weekly-sms", json=sms_payload, headers={"X-Business-Id": test_biz})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["recipient_phone"], "+254712345678")
        self.assertIn("Habari", data["sms_text"])
        self.assertEqual(data["provider_response"]["mode"], "mock")

    # ========================================================================
    # 12. Tenant ID Resolution & Mode Enforcement (Mock vs Production)
    # ========================================================================
    def test_mock_mode_missing_x_business_id_fallback(self):
        """When MOCK_AWS=true, missing X-Business-Id falls back to DEFAULT_TEST_BUSINESS_ID (biz_7a8b9c0d1e2f)."""
        os.environ["MOCK_AWS"] = "true"

        # FastAPI endpoint GET /business without X-Business-Id
        res = self.client.get("/business")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["business_id"], DEFAULT_TEST_BUSINESS_ID)
        self.assertEqual(data["business_id"], "biz_7a8b9c0d1e2f")

        # Protected endpoints succeed without X-Business-Id
        self.assertEqual(self.client.get("/score").status_code, 200)
        self.assertEqual(self.client.get("/summary/weekly").status_code, 200)
        self.assertEqual(self.client.get("/debts").status_code, 200)
        self.assertEqual(self.client.get("/transactions").status_code, 200)
        self.assertEqual(self.client.get("/reports/lender-pdf").status_code, 200)

        # Lambda handler fallback
        lambda_event = {"rawPath": "/business", "httpMethod": "GET", "headers": {}}
        lambda_res = lambda_handler(lambda_event, None)
        self.assertEqual(lambda_res["statusCode"], 200)
        lambda_body = json.loads(lambda_res["body"])
        self.assertEqual(lambda_body["business_id"], DEFAULT_TEST_BUSINESS_ID)

    def test_production_mode_auth_and_header_rejection(self):
        """
        When MOCK_AWS=false:
        - X-Business-Id header is rejected with 403 Forbidden.
        - Bearer auth / verified claims are required (missing returns 401 Unauthorized).
        """
        os.environ["MOCK_AWS"] = "false"
        try:
            # 1. FastAPI local_server: X-Business-Id must return 403
            res_forbidden = self.client.get("/business", headers={"X-Business-Id": "biz_attacker"})
            self.assertEqual(res_forbidden.status_code, 403)
            self.assertEqual(res_forbidden.json()["error"]["code"], "FORBIDDEN")

            # 2. FastAPI local_server: Missing claims / Bearer token must return 401
            res_unauth = self.client.get("/business")
            self.assertEqual(res_unauth.status_code, 401)
            self.assertEqual(res_unauth.json()["error"]["code"], "UNAUTHORIZED")

            # 3. Lambda handler: X-Business-Id rejected with 403
            event_with_header = {
                "rawPath": "/business",
                "httpMethod": "GET",
                "headers": {"x-business-id": "biz_attacker"}
            }
            res_lambda_403 = lambda_handler(event_with_header, None)
            self.assertEqual(res_lambda_403["statusCode"], 403)

            # 4. Lambda handler: Missing authorizer claims returns 401
            event_no_auth = {
                "rawPath": "/business",
                "httpMethod": "GET",
                "headers": {}
            }
            res_lambda_401 = lambda_handler(event_no_auth, None)
            self.assertEqual(res_lambda_401["statusCode"], 401)
        finally:
            os.environ["MOCK_AWS"] = "true"

    def test_x_business_id_optional_header_declared_on_every_route(self):
        """Verifies X-Business-Id is declared as an optional header parameter on every route in OpenAPI docs."""
        openapi_schema = app.openapi()
        paths = openapi_schema.get("paths", {})
        self.assertGreater(len(paths), 0)

        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method in ["get", "post", "put", "patch", "delete"]:
                    params = operation.get("parameters", [])
                    header_params = [
                        p for p in params
                        if p.get("in") == "header" and p.get("name", "").lower() == "x-business-id"
                    ]
                    self.assertEqual(
                        len(header_params), 1,
                        f"Route {method.upper()} {path} must declare X-Business-Id header parameter."
                    )
                    self.assertEqual(header_params[0]["name"], "X-Business-Id")
                    self.assertFalse(
                        header_params[0].get("required", False),
                        f"Route {method.upper()} {path} X-Business-Id header must be optional (required=False)."
                    )


if __name__ == "__main__":
    unittest.main()
