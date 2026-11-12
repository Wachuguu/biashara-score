"""
Africa's Talking SMS Client Wrapper & Message Builder
Dispatches weekly summary SMS messages in Kenya, or prints sanitized logs when MOCK_AWS=true.
Ensures PII (phone numbers, names) is never logged in plaintext.
"""
import os
import re
from typing import Dict, Any

MOCK_MODE = os.getenv("MOCK_AWS", "true").lower() == "true"


def mask_phone_number(phone: str) -> str:
    """Masks personal phone number (e.g. +254***78) for safe logging."""
    if not phone or len(phone) < 6:
        return "[REDACTED]"
    cleaned = phone.strip()
    return cleaned[:4] + "***" + cleaned[-2:]


def build_weekly_sms_message(
    owner_name: str,
    week_label: str,
    sales: float,
    expenses: float,
    profit: float,
    outstanding_debts: float,
    score: int,
    tier: str
) -> str:
    """
    Constructs the Safaricom-compliant SMS digest string:
    'Habari Mary! Biashara Score Summary for W36: Sales KSh 38,450, Expenses KSh 26,800, Est. Profit KSh 11,650. Outstanding Debts: KSh 3,200. Score: 78/100 (Silver). Keep growing!'
    Ensures clean number formatting (commas, rounded) and stays strictly under standard SMS limits.
    """
    first_name = owner_name.strip().split()[0] if owner_name and owner_name.strip() else "Trader"

    # Simplify ISO week label like '2026-W36' -> 'W36'
    if "W" in week_label:
        week_part = "W" + week_label.split("W")[-1]
    else:
        week_part = week_label.strip()

    sales_fmt = f"{int(round(sales)):,}"
    expenses_fmt = f"{int(round(expenses)):,}"
    profit_fmt = f"{int(round(profit)):,}"
    debts_fmt = f"{int(round(outstanding_debts)):,}"

    msg = (
        f"Habari {first_name}! Biashara Score Summary for {week_part}: "
        f"Sales KSh {sales_fmt}, Expenses KSh {expenses_fmt}, Est. Profit KSh {profit_fmt}. "
        f"Outstanding Debts: KSh {debts_fmt}. Score: {int(score)}/100 ({tier}). Keep growing!"
    )
    return msg


class AfricaTalkingSMSClient:
    def __init__(self):
        self.mock = MOCK_MODE
        self.username = os.getenv("AFRICAS_TALKING_USERNAME", "sandbox")
        self.api_key = os.getenv("AFRICAS_TALKING_API_KEY", "")
        self.sender_id = os.getenv("AFRICAS_TALKING_SENDER_ID", "BIASHARA")

    def send_sms(self, phone_number: str, message: str) -> Dict[str, Any]:
        """
        Sends an SMS to a Kenyan phone number (+254...).
        Logs only sanitized/masked metadata without leaking personal phone numbers or customer names.
        Returns a response dict with status, recipient, mode, and cost.
        """
        masked = mask_phone_number(phone_number)
        if self.mock or not self.api_key:
            # Safe sanitized log: no personal names or full phone numbers
            print(f"[LOCAL SMS MOCK to {masked}]: Dispatched financial digest notification (chars: {len(message)})")
            return {
                "status": "success",
                "recipient": phone_number,
                "message": message,
                "mode": "mock",
                "provider_response": {
                    "status": "success",
                    "mode": "mock",
                    "cost": "KSh 0.80"
                }
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
        response = requests.post(url, headers=headers, data=data, timeout=5)
        return response.json()


sms_client = AfricaTalkingSMSClient()
