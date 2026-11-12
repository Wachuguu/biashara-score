"""
DynamoDB Client Wrapper
Provides a unified interface with automatic local in-memory mocking when MOCK_AWS=true.
Allows Dev 1, 2, 3, and 4 to build and test without AWS credentials.
"""
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

MOCK_MODE = os.getenv("MOCK_AWS", "true").lower() == "true"

DEFAULT_TEST_BUSINESS_ID = "biz_7a8b9c0d1e2f"

DEFAULT_TEST_BUSINESS = {
    "business_id": DEFAULT_TEST_BUSINESS_ID,
    "shop_name": "Mary's Family Provisions",
    "owner_name": "Mary Wambui",
    "owner_phone": "+254712345678",
    "till_number": "789123",
    "created_at": "2026-09-01T08:00:00Z"
}

# Local in-memory store for offline development
_LOCAL_STORE: Dict[str, Dict[str, Any]] = {
    "businesses": {
        DEFAULT_TEST_BUSINESS_ID: dict(DEFAULT_TEST_BUSINESS)
    },
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

    # -------------------------------------------------------------------------
    # Transactions
    # -------------------------------------------------------------------------
    def put_transaction(self, tx_dict: Dict[str, Any]) -> None:
        if self.mock:
            key = f"{tx_dict['business_id']}#{tx_dict['receipt_number']}"
            _LOCAL_STORE["transactions"][key] = dict(tx_dict)
            return
        self.tx_table.put_item(Item=tx_dict)

    def batch_put_transactions(self, tx_dicts: List[Dict[str, Any]]) -> None:
        if self.mock:
            for tx in tx_dicts:
                self.put_transaction(tx)
            return
        with self.tx_table.batch_writer() as batch:
            for tx in tx_dicts:
                batch.put_item(Item=tx)

    def get_transactions_for_business(self, business_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        if self.mock:
            results = [
                v for k, v in _LOCAL_STORE["transactions"].items()
                if v.get("business_id") == business_id
            ]
            # Sort newest first by completion_time
            results.sort(key=lambda x: x.get("completion_time", ""), reverse=True)
            return results[:limit]
        from boto3.dynamodb.conditions import Key
        response = self.tx_table.query(
            KeyConditionExpression=Key("business_id").eq(business_id),
            Limit=limit,
            ScanIndexForward=False
        )
        return response.get("Items", [])

    # -------------------------------------------------------------------------
    # Debts ("Kitabu ya Deni")
    # -------------------------------------------------------------------------
    def put_debt(self, debt_dict: Dict[str, Any]) -> None:
        if self.mock:
            key = f"{debt_dict['business_id']}#{debt_dict['debt_id']}"
            _LOCAL_STORE["debts"][key] = dict(debt_dict)
            return
        self.debt_table.put_item(Item=debt_dict)

    def get_debts_for_business(self, business_id: str) -> List[Dict[str, Any]]:
        if self.mock:
            debts = [
                v for k, v in _LOCAL_STORE["debts"].items()
                if v.get("business_id") == business_id
            ]
            debts.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return debts
        from boto3.dynamodb.conditions import Key
        response = self.debt_table.query(KeyConditionExpression=Key("business_id").eq(business_id))
        return response.get("Items", [])

    def get_debt_by_id(self, business_id: str, debt_id: str) -> Optional[Dict[str, Any]]:
        if self.mock:
            key = f"{business_id}#{debt_id}"
            return _LOCAL_STORE["debts"].get(key)
        response = self.debt_table.get_item(Key={"business_id": business_id, "debt_id": debt_id})
        return response.get("Item")

    def update_debt(self, business_id: str, debt_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock:
            key = f"{business_id}#{debt_id}"
            debt = _LOCAL_STORE["debts"].get(key)
            if not debt:
                raise KeyError(f"Debt with id {debt_id} not found")
            debt.update(updates)
            return dict(debt)
        # DynamoDB real update
        update_expr = "SET " + ", ".join(f"#{k} = :{k}" for k in updates.keys())
        expr_names = {f"#{k}": k for k in updates.keys()}
        expr_vals = {f":{k}": v for k, v in updates.items()}
        response = self.debt_table.update_item(
            Key={"business_id": business_id, "debt_id": debt_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_vals,
            ReturnValues="ALL_NEW"
        )
        return response.get("Attributes", {})

    # -------------------------------------------------------------------------
    # Businesses
    # -------------------------------------------------------------------------
    def get_business(self, business_id: str) -> Optional[Dict[str, Any]]:
        if self.mock:
            return _LOCAL_STORE["businesses"].get(business_id)
        response = self.biz_table.get_item(Key={"business_id": business_id})
        return response.get("Item")

    def put_business(self, business_dict: Dict[str, Any]) -> None:
        if self.mock:
            _LOCAL_STORE["businesses"][business_dict["business_id"]] = dict(business_dict)
            return
        self.biz_table.put_item(Item=business_dict)

    # -------------------------------------------------------------------------
    # Test Utilities
    # -------------------------------------------------------------------------
    def clear_mock_store(self) -> None:
        """Resets the mock storage, re-populating default test business."""
        _LOCAL_STORE["businesses"] = {
            DEFAULT_TEST_BUSINESS_ID: {
                "business_id": DEFAULT_TEST_BUSINESS_ID,
                "shop_name": "Mary's Family Provisions",
                "owner_name": "Mary Wambui",
                "owner_phone": "+254712345678",
                "till_number": "789123",
                "created_at": "2026-09-01T08:00:00Z"
            }
        }
        _LOCAL_STORE["transactions"] = {}
        _LOCAL_STORE["debts"] = {}


# Shared singleton instance
db_client = DatabaseClient()
