"""
Authentication & Password Hashing Tests
Verifies salted PBKDF2-HMAC-SHA256 hashing, shop registration, duplicate phone
protection, cross-device login, and password_hash redaction.
"""
import os
import sys
import unittest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi.testclient import TestClient
from local_server import app
from src.wrappers.db_client import db_client
from src.handlers.auth_handler import hash_password, verify_password

client = TestClient(app)


class TestAuthSecurity(unittest.TestCase):
    def setUp(self):
        db_client.clear_mock_store()

    def test_pbkdf2_salted_hashing(self):
        h1 = hash_password("SecurePass123")
        h2 = hash_password("SecurePass123")
        self.assertTrue(h1.startswith("pbkdf2_sha256$100000$"))
        self.assertNotEqual(h1, h2)  # unique random salt per hash
        self.assertTrue(verify_password("SecurePass123", h1))
        self.assertFalse(verify_password("WrongPass123", h1))

    def test_register_and_login_flow(self):
        reg_res = client.post("/auth/register", json={
            "shop_name": "Nairobi Tech Hub",
            "owner_name": "Paul Wachugu",
            "owner_phone": "0722 334 455",
            "password": "MyStrongPassword!",
            "till_number": "654321",
        })
        self.assertEqual(reg_res.status_code, 201)
        reg_data = reg_res.json()
        self.assertIn("token", reg_data)
        self.assertEqual(reg_data["business"]["shop_name"], "Nairobi Tech Hub")
        self.assertEqual(reg_data["business"]["owner_phone"], "+254722334455")
        self.assertNotIn("password_hash", reg_data["business"])
        biz_id = reg_data["business"]["business_id"]

        # Duplicate phone must return 409
        dup_res = client.post("/auth/register", json={
            "shop_name": "Duplicate Shop",
            "owner_name": "Paul",
            "owner_phone": "+254722334455",
            "password": "AnotherPassword1",
        })
        self.assertEqual(dup_res.status_code, 409)

        # Login with wrong password must return 401
        bad_login = client.post("/auth/login", json={
            "owner_phone": "0722334455",
            "password": "WrongPassword",
        })
        self.assertEqual(bad_login.status_code, 401)

        # Login with correct password returns same business_id and redacts hash
        good_login = client.post("/auth/login", json={
            "owner_phone": "0722 334 455",
            "password": "MyStrongPassword!",
        })
        self.assertEqual(good_login.status_code, 200)
        login_data = good_login.json()
        self.assertEqual(login_data["business"]["business_id"], biz_id)
        self.assertNotIn("password_hash", login_data["business"])


if __name__ == "__main__":
    unittest.main()
