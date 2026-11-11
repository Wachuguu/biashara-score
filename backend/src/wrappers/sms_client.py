"""
Africa's Talking SMS Client Wrapper
Dispatches weekly summary SMS messages in Kenya, or prints to stdout when MOCK_AWS=true.
"""
import os
from typing import Dict, Any

MOCK_MODE = os.getenv("MOCK_AWS", "true").lower() == "true"


class AfricaTalkingSMSClient:
    def __init__(self):
        self.mock = MOCK_MODE
        self.username = os.getenv("AFRICAS_TALKING_USERNAME", "sandbox")
        self.api_key = os.getenv("AFRICAS_TALKING_API_KEY", "")
        self.sender_id = os.getenv("AFRICAS_TALKING_SENDER_ID", "BIASHARA")

    def send_sms(self, phone_number: str, message: str) -> Dict[str, Any]:
        """
        Sends an SMS to a Kenyan phone number (+254...).
        """
        if self.mock or not self.api_key:
            print(f"[LOCAL SMS MOCK to {phone_number}]: {message}")
            return {
                "status": "success",
                "recipient": phone_number,
                "message": message,
                "mode": "mock"
            }

        import requests
        url = "https://api.africastalking.com/version1/messaging"
        headers = {
            "ApiKey": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "username": self.username,
            "to": phone_number,
            "message": message,
            "from": self.sender_id
        }
        response = requests.post(url, headers=headers, data=data, timeout=10)
        return response.json()


sms_client = AfricaTalkingSMSClient()
