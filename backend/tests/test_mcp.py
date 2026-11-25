"""
Model Context Protocol (MCP) & Copilot Integration Tests
Verifies JSON-RPC 2.0 initialize, tools/list, tools/call, loan underwriting,
debt logging, and default Geomin Routers / John Doe profile.
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
from src.wrappers.db_client import db_client, DEFAULT_TEST_BUSINESS_ID
from src.handlers.mcp_handler import handle_mcp_jsonrpc, execute_mcp_copilot
from src.handlers.daraja_handler import execute_load_sample_statement

client = TestClient(app)


class TestMcpIntegration(unittest.TestCase):
    def setUp(self):
        db_client.clear_mock_store()
        self.biz_id = DEFAULT_TEST_BUSINESS_ID

    def test_default_demo_shop_is_geomin_routers(self):
        biz = db_client.get_business(self.biz_id)
        self.assertIsNotNone(biz)
        self.assertEqual(biz["shop_name"], "Geomin Routers")
        self.assertEqual(biz["owner_name"], "John Doe")

    def test_mcp_initialize_and_tools_list(self):
        init_res = handle_mcp_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(init_res["result"]["protocolVersion"], "2024-11-05")
        self.assertEqual(init_res["result"]["serverInfo"]["name"], "biashara-score-mcp")

        list_res = handle_mcp_jsonrpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tool_names = [t["name"] for t in list_res["result"]["tools"]]
        self.assertIn("get_business_score", tool_names)
        self.assertIn("evaluate_loan_readiness", tool_names)
        self.assertIn("record_customer_debt", tool_names)
        self.assertEqual(len(tool_names), 5)

    def test_mcp_evaluate_loan_readiness_with_sample_data(self):
        execute_load_sample_statement(self.biz_id)
        rpc_res = handle_mcp_jsonrpc({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "evaluate_loan_readiness",
                "arguments": {"requested_amount_kes": 50000}
            }
        }, default_business_id=self.biz_id)

        structured = rpc_res["result"]["structuredContent"]
        self.assertFalse(rpc_res["result"]["isError"])
        self.assertEqual(structured["requested_amount_kes"], 50000)
        self.assertGreater(structured["biashara_score"], 50)
        self.assertIn(structured["decision"], ["APPROVED", "APPROVED_WITH_CAP", "CONDITIONAL"])

    def test_mcp_copilot_routes_prompts_and_records_debt(self):
        res_debt = execute_mcp_copilot(self.biz_id, "Add debt for Jane Wanjiku 0722112233 amount 2500")
        self.assertEqual(res_debt["tool_used"], "record_customer_debt")
        self.assertIn("Jane Wanjiku", res_debt["answer"])

        debts = db_client.get_debts_for_business(self.biz_id)
        self.assertEqual(len(debts), 1)
        self.assertEqual(debts[0]["amount_owed"], 2500.0)

        res_loan = client.post("/mcp/copilot", json={"query": "Can Geomin Routers qualify for a KSh 30,000 loan?"})
        self.assertEqual(res_loan.status_code, 200)
        self.assertEqual(res_loan.json()["tool_used"], "evaluate_loan_readiness")

    def test_mcp_copilot_handles_lowercase_names_and_typos(self):
        res = execute_mcp_copilot(self.biz_id, "add debt fot mwangi 0729809412 amount 34000")
        self.assertEqual(res["tool_used"], "record_customer_debt")
        self.assertIn("Mwangi", res["answer"])
        self.assertIn("34,000", res["answer"])
        self.assertNotIn("Jane Wanjiku", res["answer"])


if __name__ == "__main__":
    unittest.main()
