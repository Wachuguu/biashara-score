"""
Safaricom Daraja M-Pesa API Client Wrapper
Supports OAuth 2.0, C2B URL Registration, C2B Transaction Simulation, and STK Push.
Pure Python with urllib (Zero external dependencies).
"""
import os
import json
import base64
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, Any, Optional
from datetime import datetime, timezone

# Standard Safaricom Daraja Sandbox credentials for developer testing
DEFAULT_SANDBOX_CONSUMER_KEY = os.getenv("DARAJA_CONSUMER_KEY", "b3w8GOGs4y4cK6sQzG6pG5AOG2vL8T3A")
DEFAULT_SANDBOX_CONSUMER_SECRET = os.getenv("DARAJA_CONSUMER_SECRET", "EwK4vA5Gz3A8xK7y")
DEFAULT_SANDBOX_SHORTCODE = os.getenv("DARAJA_SHORTCODE", "600988")
DEFAULT_SANDBOX_PASSKEY = os.getenv(
    "DARAJA_PASSKEY",
    "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919"
)


class DarajaClient:
    def __init__(
        self,
        consumer_key: Optional[str] = None,
        consumer_secret: Optional[str] = None,
        shortcode: Optional[str] = None,
        passkey: Optional[str] = None,
        env: Optional[str] = None,
    ):
        self.consumer_key = consumer_key or os.getenv("DARAJA_CONSUMER_KEY", DEFAULT_SANDBOX_CONSUMER_KEY)
        self.consumer_secret = consumer_secret or os.getenv("DARAJA_CONSUMER_SECRET", DEFAULT_SANDBOX_CONSUMER_SECRET)
        self.shortcode = shortcode or os.getenv("DARAJA_SHORTCODE", DEFAULT_SANDBOX_SHORTCODE)
        self.passkey = passkey or os.getenv("DARAJA_PASSKEY", DEFAULT_SANDBOX_PASSKEY)
        self.env = (env or os.getenv("DARAJA_ENV", "sandbox")).lower()

        if self.env == "production" or self.env == "prod":
            self.base_url = "https://api.safaricom.co.ke"
        else:
            self.base_url = "https://sandbox.safaricom.co.ke"

        self._token_cache: Optional[str] = None
        self._token_expiry: float = 0.0

    def get_access_token(self) -> str:
        """Fetches OAuth 2.0 Bearer access token from Safaricom."""
        now = datetime.now(timezone.utc).timestamp()
        if self._token_cache and now < (self._token_expiry - 60):
            return self._token_cache

        auth_str = f"{self.consumer_key}:{self.consumer_secret}"
        encoded_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
        url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"

        headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Accept": "application/json"
        }
        req = urllib.request.Request(url, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                data = json.loads(response.read().decode("utf-8"))
                token = data.get("access_token", "")
                expires_in = int(data.get("expires_in", 3599))
                self._token_cache = token
                self._token_expiry = now + expires_in
                return token
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            raise RuntimeError(f"Daraja OAuth Failed (HTTP {e.code}): {err_body}")
        except Exception as e:
            raise RuntimeError(f"Daraja OAuth Connection Error: {str(e)}")

    def register_c2b_urls(
        self,
        confirmation_url: str,
        validation_url: str,
        shortcode: Optional[str] = None,
        response_type: str = "Completed"
    ) -> Dict[str, Any]:
        """Registers C2B Confirmation and Validation URLs with Safaricom."""
        token = self.get_access_token()
        url = f"{self.base_url}/mpesa/c2b/v2/registerurl"
        payload = {
            "ShortCode": shortcode or self.shortcode,
            "ResponseType": response_type,
            "ConfirmationURL": confirmation_url,
            "ValidationURL": validation_url
        }

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=15) as res:
                return json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            return {"error": True, "code": e.code, "message": err_body}
        except Exception as e:
            return {"error": True, "message": str(e)}

    def simulate_c2b_transaction(
        self,
        amount: float,
        phone: str,
        shortcode: Optional[str] = None,
        bill_ref: str = "DukaSale",
        command_id: str = "CustomerBuyGoodsOnline"
    ) -> Dict[str, Any]:
        """
        Simulates an incoming C2B payment in Safaricom Sandbox.
        CommandID: CustomerBuyGoodsOnline (for Tills) or CustomerPayBillOnline (for Paybill).
        """
        token = self.get_access_token()
        url = f"{self.base_url}/mpesa/c2b/v1/simulate"

        # Standardize MSISDN (254...)
        clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
        if clean_phone.startswith("0"):
            clean_phone = "254" + clean_phone[1:]
        elif not clean_phone.startswith("254"):
            clean_phone = "254" + clean_phone

        payload = {
            "ShortCode": shortcode or self.shortcode,
            "CommandID": command_id,
            "Amount": int(amount),
            "Msisdn": clean_phone,
            "BillRefNumber": bill_ref
        }

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=15) as res:
                return json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            return {"error": True, "code": e.code, "message": err_body}
        except Exception as e:
            return {"error": True, "message": str(e)}

    def initiate_stk_push(
        self,
        phone: str,
        amount: float,
        account_ref: str = "DukaSale",
        callback_url: Optional[str] = None,
        shortcode: Optional[str] = None,
        passkey: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Initiates an M-Pesa Express (STK Push) prompt on customer phone."""
        token = self.get_access_token()
        url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"

        sc = shortcode or "174379"  # Default Daraja sandbox Paybill
        pk = passkey or self.passkey
        now_dt = datetime.now(timezone.utc)
        timestamp = now_dt.strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(f"{sc}{pk}{timestamp}".encode("utf-8")).decode("utf-8")

        clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
        if clean_phone.startswith("0"):
            clean_phone = "254" + clean_phone[1:]

        cb_url = callback_url or "https://app.biasharascore.com/api/mpesa/stkpush/callback"

        payload = {
            "BusinessShortCode": sc,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": clean_phone,
            "PartyB": sc,
            "PhoneNumber": clean_phone,
            "CallBackURL": cb_url,
            "AccountReference": account_ref,
            "TransactionDesc": f"Payment for {account_ref}"
        }

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=15) as res:
                return json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            return {"error": True, "code": e.code, "message": err_body}
        except Exception as e:
            return {"error": True, "message": str(e)}

    @staticmethod
    def generate_simulated_c2b_payload(
        amount: float,
        phone: str,
        first_name: str = "John",
        last_name: str = "Kamau",
        till_number: str = "789123",
        trans_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates an authentic Safaricom C2B Confirmation JSON payload.
        Used for instant demo simulation and offline testing without network lag.
        """
        now = datetime.now(timezone.utc)
        clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
        if clean_phone.startswith("0"):
            clean_phone = "254" + clean_phone[1:]
        elif not clean_phone.startswith("254"):
            clean_phone = "254" + clean_phone

        import random
        import string
        code_suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        tid = trans_id or f"SK{now.strftime('%d')}{code_suffix}"

        return {
            "TransactionType": "Customer Buy Goods",
            "TransID": tid,
            "TransTime": now.strftime("%Y%m%d%H%M%S"),
            "TransAmount": f"{amount:.2f}",
            "BusinessShortCode": till_number,
            "BillRefNumber": "",
            "InvoiceNumber": "",
            "OrgAccountBalance": "52850.00",
            "ThirdPartyTransID": "",
            "MSISDN": clean_phone,
            "FirstName": first_name.strip(),
            "MiddleName": "",
            "LastName": last_name.strip()
        }


daraja_client = DarajaClient()
