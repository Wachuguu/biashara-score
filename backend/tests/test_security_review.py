"""
Security Review Test Suite
Validates all security controls required for production readiness:
1. Rejection of X-Business-Id when MOCK_AWS=false (403 Forbidden).
2. Enforcement of verified authorizer claims (requestContext.authorizer.jwt.claims.sub) when MOCK_AWS=false.
3. Handlers never read business_id from body or headers in production mode.
4. Upload size limit (5MB) rejection (413 Payload Too Large).
5. Upload file type limit (.csv only) rejection (400 Invalid Statement Format).
6. Input validation across endpoints (PUT /business, POST /debts, PATCH /debts, GET /transactions, etc.).
7. Prevention of PII (names, phone numbers) leaking in logs or print statements.
8. CORS origin restrictions (never '*' in production).
"""
import os
import sys
import json
import io
import unittest
from contextlib import redirect_stdout

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from src.handlers.api_handler import lambda_handler
from src.handlers.utils import resolve_business_id, get_cors_headers
from src.handlers.statement_handler import execute_csv_upload, MAX_UPLOAD_BYTES
from src.handlers.debt_handler import execute_create_debt, execute_update_debt, execute_list_debts
from src.handlers.score_handler import execute_weekly_summary, execute_lender_pdf
from src.handlers.cron_handler import execute_weekly_sms_notification
from src.wrappers.sms_client import sms_client, mask_phone_number
from src.wrappers.db_client import db_client, DEFAULT_TEST_BUSINESS_ID


class TestSecurityControls(unittest.TestCase):
    def setUp(self):
        db_client.clear_mock_store()

    # ========================================================================
    # 1. Multi-Tenancy & Authorization in Production Mode (MOCK_AWS=false)
    # ========================================================================
    def test_x_business_id_strictly_rejected_when_mock_aws_false(self):
        """When MOCK_AWS=false, any request sending X-Business-Id must be rejected with 403 Forbidden."""
        os.environ["MOCK_AWS"] = "false"
        try:
            event = {
                "rawPath": "/business",
                "httpMethod": "GET",
                "headers": {
                    "x-business-id": "biz_injected_attacker",
                    "authorization": "Bearer dummy_token"
                },
                "requestContext": {
                    "authorizer": {
                        "jwt": {
                            "claims": {"sub": "biz_genuine_user"}
                        }
                    }
                }
            }
            res = lambda_handler(event, None)
            self.assertEqual(res["statusCode"], 403)
            body = json.loads(res["body"])
            self.assertEqual(body["error"]["code"], "FORBIDDEN")
            self.assertIn("X-Business-Id header is forbidden", body["error"]["message"])
        finally:
            os.environ["MOCK_AWS"] = "true"

    def test_missing_verified_authorizer_claims_rejected_when_mock_aws_false(self):
        """When MOCK_AWS=false, missing verified authorizer sub claim must be rejected with 401 Unauthorized."""
        os.environ["MOCK_AWS"] = "false"
        try:
            # Event without authorizer claims
            event = {
                "rawPath": "/business",
                "httpMethod": "GET",
                "headers": {
                    "authorization": "Bearer some_unverified_token"
                },
                "requestContext": {}
            }
            res = lambda_handler(event, None)
            self.assertEqual(res["statusCode"], 401)
            body = json.loads(res["body"])
            self.assertEqual(body["error"]["code"], "UNAUTHORIZED")
            self.assertIn("Missing verified authorizer claims", body["error"]["message"])
        finally:
            os.environ["MOCK_AWS"] = "true"

    def test_verified_authorizer_claims_accepted_when_mock_aws_false(self):
        """When MOCK_AWS=false, business_id is extracted exclusively from requestContext.authorizer.jwt.claims.sub."""
        os.environ["MOCK_AWS"] = "false"
        try:
            verified_sub = "biz_cognito_verified_999"
            event = {
                "rawPath": "/business",
                "httpMethod": "GET",
                "headers": {
                    "authorization": "Bearer valid_jwt"
                },
                "requestContext": {
                    "authorizer": {
                        "jwt": {
                            "claims": {"sub": verified_sub}
                        }
                    }
                }
            }
            res = lambda_handler(event, None)
            self.assertEqual(res["statusCode"], 200)
            body = json.loads(res["body"])
            self.assertEqual(body["business_id"], verified_sub)
        finally:
            os.environ["MOCK_AWS"] = "true"

    # ========================================================================
    # 2. Upload Size and Type Limits
    # ========================================================================
    def test_upload_size_limit_rejection(self):
        """Statement upload exceeding 5MB must be rejected with 413 Payload Too Large."""
        oversized_content = "Receipt No.,Completion Time,Details,Transaction Status,Paid In,Withdrawn,Balance\n" + (
            "SK01YUUM7K,2026-09-01 12:49:00,Customer Transfer,Completed,1600.00,,50106.98\n" * 70000
        )
        self.assertGreater(len(oversized_content.encode("utf-8")), MAX_UPLOAD_BYTES)

        res = execute_csv_upload("biz_test", oversized_content, filename="large_statement.csv")
        self.assertEqual(res["statusCode"], 413)
        self.assertEqual(res["body"]["error"]["code"], "PAYLOAD_TOO_LARGE")

    def test_upload_file_type_limit_rejection(self):
        """Statement upload with non-csv extension must be rejected with 400 Invalid Statement Format."""
        res = execute_csv_upload("biz_test", "content", filename="malicious_payload.exe")
        self.assertEqual(res["statusCode"], 400)
        self.assertEqual(res["body"]["error"]["code"], "INVALID_STATEMENT_FORMAT")
        self.assertIn("Unsupported file type", res["body"]["error"]["message"])

    # ========================================================================
    # 3. Input Validation Across Endpoints
    # ========================================================================
    def test_put_business_validation(self):
        """PUT /business validates phone number and till number formats."""
        # Invalid phone
        event_bad_phone = {
            "rawPath": "/business",
            "httpMethod": "PUT",
            "body": json.dumps({"owner_phone": "invalid_phone_string"})
        }
        res_phone = lambda_handler(event_bad_phone, None)
        self.assertEqual(res_phone["statusCode"], 400)
        self.assertEqual(json.loads(res_phone["body"])["error"]["code"], "VALIDATION_ERROR")

        # Invalid till
        event_bad_till = {
            "rawPath": "/business",
            "httpMethod": "PUT",
            "body": json.dumps({"till_number": "not_digits"})
        }
        res_till = lambda_handler(event_bad_till, None)
        self.assertEqual(res_till["statusCode"], 400)

        # Unknown field
        event_unknown = {
            "rawPath": "/business",
            "httpMethod": "PUT",
            "body": json.dumps({"admin_access": True})
        }
        res_unknown = lambda_handler(event_unknown, None)
        self.assertEqual(res_unknown["statusCode"], 400)

    def test_debts_validation(self):
        """POST /debts and PATCH /debts validate amounts and fields."""
        # Missing name
        res_no_name = execute_create_debt("biz_test", {"amount_owed": 500})
        self.assertEqual(res_no_name["statusCode"], 400)

        # Negative amount owed
        res_neg_owed = execute_create_debt("biz_test", {"debtor_name": "John", "amount_owed": -200})
        self.assertEqual(res_neg_owed["statusCode"], 400)

        # Create valid debt for patch test
        res_created = execute_create_debt("biz_test", {"debtor_name": "John Doe", "amount_owed": 1000})
        self.assertEqual(res_created["statusCode"], 201)
        debt_id = res_created["body"]["debt_id"]

        # Negative amount to clear in PATCH
        res_neg_clear = execute_update_debt("biz_test", debt_id, {"amount_to_clear": -50})
        self.assertEqual(res_neg_clear["statusCode"], 400)
        self.assertEqual(res_neg_clear["body"]["error"]["code"], "VALIDATION_ERROR")

        # Invalid status in GET /debts query
        res_bad_status = execute_list_debts("biz_test", {"status": "INVALID_STATUS"})
        self.assertEqual(res_bad_status["statusCode"], 400)

    def test_query_param_validation(self):
        """Summary and lender PDF query parameters validate bounds and formats."""
        # Non-integer weeks
        res_bad_weeks = execute_weekly_summary("biz_test", {"weeks": "not_a_number"})
        self.assertEqual(res_bad_weeks["statusCode"], 400)

        # Invalid PDF format
        res_bad_fmt = execute_lender_pdf("biz_test", {"format": "unsupported_fmt"})
        self.assertEqual(res_bad_fmt["statusCode"], 400)

    # ========================================================================
    # 4. No Personal Data (PII) in Logs
    # ========================================================================
    def test_phone_number_masked_and_names_not_in_logs(self):
        """sms_client log outputs must mask phone numbers and not output owner names."""
        phone = "+254712345678"
        masked = mask_phone_number(phone)
        self.assertEqual(masked, "+254***78")

        buf = io.StringIO()
        with redirect_stdout(buf):
            sms_client.send_sms(phone, "Habari Mary! Sales KSh 10,000")
        output = buf.getvalue()

        # Full phone number must not appear in output
        self.assertNotIn("+254712345678", output)
        self.assertIn("+254***78", output)
        # Message body containing personal name Mary must not appear in stdout log
        self.assertNotIn("Habari Mary", output)

    # ========================================================================
    # 5. CORS Header Restrictions
    # ========================================================================
    def test_cors_not_wildcard_in_production(self):
        """CORS headers must NEVER return '*' in production mode."""
        os.environ["MOCK_AWS"] = "false"
        os.environ["ENVIRONMENT"] = "prod"
        os.environ["CORS_ALLOWED_ORIGIN"] = "https://app.biasharascore.com"
        try:
            headers = get_cors_headers("http://malicious-site.com")
            self.assertEqual(headers["Access-Control-Allow-Origin"], "https://app.biasharascore.com")
            self.assertNotEqual(headers["Access-Control-Allow-Origin"], "*")
            self.assertNotIn("X-Business-Id", headers["Access-Control-Allow-Headers"])
        finally:
            os.environ["MOCK_AWS"] = "true"
            os.environ["ENVIRONMENT"] = "dev"


if __name__ == "__main__":
    unittest.main()
