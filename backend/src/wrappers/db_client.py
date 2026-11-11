"""
DynamoDB Client Wrapper
Provides a unified interface with automatic local in-memory mocking when MOCK_AWS=true.
Allows Dev 1, 2, and 3 to build without AWS credentials.
"""
import os
from typing import Dict, Any, List, Optional

MOCK_MODE = os.getenv("MOCK_AWS", "true").lower() == "true"

# Local in-memory store for offline development
_LOCAL_STORE: Dict[str, Dict[str, Any]] = {
    "businesses": {},
    "transactions": {},
    "debts": {}
}


class DatabaseClient:
    def __init__(self):
        self.mock = MOCK_MODE
        if not self.mock:
            import boto3
            self.dynamodb = boto3.resource("dynamodb")
            self.tx_table = self.dynamodb.Table(os.getenv("DYNAMODB_TRANSACTIONS_TABLE", "biashara-transactions-dev"))
            self.biz_table = self.dynamodb.Table(os.getenv("DYNAMODB_BUSINESS_TABLE", "biashara-businesses-dev"))
            self.debt_table = self.dynamodb.Table(os.getenv("DYNAMODB_DEBTS_TABLE", "biashara-debts-dev"))

    def put_transaction(self, tx_dict: Dict[str, Any]) -> None:
        if self.mock:
            key = f"{tx_dict['business_id']}#{tx_dict['receipt_number']}"
            _LOCAL_STORE["transactions"][key] = tx_dict
            return
        self.tx_table.put_item(Item=tx_dict)

    def get_transactions_for_business(self, business_id: str) -> List[Dict[str, Any]]:
        if self.mock:
            return [v for k, v in _LOCAL_STORE["transactions"].items() if v.get("business_id") == business_id]
        from boto3.dynamodb.conditions import Key
        response = self.tx_table.query(KeyConditionExpression=Key("business_id").eq(business_id))
        return response.get("Items", [])


# Shared singleton instance
db_client = DatabaseClient()
