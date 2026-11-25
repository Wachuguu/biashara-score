"""
Biashara Score — Model Context Protocol (MCP) Server & Copilot Handler
Implements JSON-RPC 2.0 MCP (initialize, tools/list, tools/call) over HTTP or stdio,
exposing live credit scoring, cashflow, debt ledger, and lender underwriting tools.
"""
import json
import re
from typing import Any, Dict, List

from src.wrappers.db_client import DEFAULT_TEST_BUSINESS_ID
from src.handlers.score_handler import execute_score, execute_weekly_summary
from src.handlers.debt_handler import execute_list_debts, execute_create_debt

MCP_PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {
    "name": "biashara-score-mcp",
    "version": "1.0.0",
}

MCP_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "get_business_score",
        "description": "Retrieve the 0-100 Biashara Score, credit tier (Gold/Silver/Bronze/Needs Improvement), 4-pillar breakdown, and coaching tips for a shop.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "business_id": {"type": "string", "description": "Unique shop ID (defaults to active shop)."}
            },
        },
    },
    {
        "name": "get_weekly_cashflow",
        "description": "Retrieve weekly gross sales, operating expenses, and estimated net profit in KSh over N weeks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "business_id": {"type": "string", "description": "Unique shop ID."},
                "weeks": {"type": "integer", "description": "Number of weeks to summarize (1-12).", "default": 4},
            },
        },
    },
    {
        "name": "get_debt_ledger",
        "description": "Retrieve the shop's Customer Debt Ledger: outstanding balances, cleared totals, and debt recovery rate.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "business_id": {"type": "string", "description": "Unique shop ID."}
            },
        },
    },
    {
        "name": "record_customer_debt",
        "description": "Log a new customer credit entry into the shop's Customer Debt Ledger.",
        "inputSchema": {
            "type": "object",
            "required": ["debtor_name", "debtor_phone", "amount_owed"],
            "properties": {
                "business_id": {"type": "string", "description": "Unique shop ID."},
                "debtor_name": {"type": "string", "description": "Customer full name."},
                "debtor_phone": {"type": "string", "description": "Kenyan phone number (e.g. 0712345678 or +254712345678)."},
                "amount_owed": {"type": "number", "description": "Amount owed in KSh."},
                "items_summary": {"type": "string", "description": "Items taken on credit.", "default": "Shop goods"},
            },
        },
    },
    {
        "name": "evaluate_loan_readiness",
        "description": "Lender & SACCO underwriting tool: evaluates whether a shop qualifies for a requested loan amount in KSh based on Biashara Score, weekly net profit, and debt recovery.",
        "inputSchema": {
            "type": "object",
            "required": ["requested_amount_kes"],
            "properties": {
                "business_id": {"type": "string", "description": "Unique shop ID."},
                "requested_amount_kes": {"type": "number", "description": "Requested loan amount in KSh."},
            },
        },
    },
]


def _unwrap(handler_res: Dict[str, Any]) -> Dict[str, Any]:
    body = handler_res.get("body", {})
    return body if isinstance(body, dict) else {"raw": body}


def _evaluate_loan(business_id: str, requested_amount: float) -> Dict[str, Any]:
    score_data = _unwrap(execute_score(business_id))
    debt_data = _unwrap(execute_list_debts(business_id, {}))

    total_score = int(score_data.get("total_score", 0))
    tier = score_data.get("tier", "Needs Improvement")
    weekly_profit = float(score_data.get("weekly_profit_avg", 0.0))
    weekly_turnover = float(score_data.get("weekly_turnover_avg", 0.0))
    recovery_rate = score_data.get("debt_recovery_rate")

    safe_limit = round(max(weekly_profit * 3.0, weekly_turnover * 0.5), 2)
    if total_score >= 80:
        decision = "APPROVED" if requested_amount <= safe_limit or safe_limit == 0 else "APPROVED_WITH_CAP"
        risk = "LOW"
    elif total_score >= 65:
        decision = "APPROVED" if requested_amount <= safe_limit else "CONDITIONAL"
        risk = "MODERATE"
    elif total_score >= 50:
        decision = "CONDITIONAL"
        risk = "ELEVATED"
    else:
        decision = "DECLINED_INSUFFICIENT_HISTORY"
        risk = "HIGH"

    if weekly_turnover == 0 and weekly_profit == 0:
        decision = "NEEDS_STATEMENT_DATA"

    return {
        "business_id": business_id,
        "requested_amount_kes": requested_amount,
        "decision": decision,
        "risk_level": risk,
        "recommended_max_limit_kes": safe_limit,
        "biashara_score": total_score,
        "tier": tier,
        "weekly_turnover_avg_kes": weekly_turnover,
        "weekly_profit_avg_kes": weekly_profit,
        "debt_recovery_rate_pct": recovery_rate,
        "outstanding_debts_kes": debt_data.get("summary", {}).get("total_outstanding_amount", 0.0),
        "rationale": (
            f"Score {total_score}/100 ({tier}). Average weekly net profit is KSh {weekly_profit:,.0f} "
            f"on KSh {weekly_turnover:,.0f} turnover. Recommended safe 30-day working-capital limit: KSh {safe_limit:,.0f}."
        ),
    }


def call_mcp_tool(name: str, arguments: Dict[str, Any], default_business_id: str = DEFAULT_TEST_BUSINESS_ID) -> Dict[str, Any]:
    """Executes an MCP tool by name and returns structured result data."""
    biz_id = str(arguments.get("business_id") or default_business_id).strip()

    if name == "get_business_score":
        return _unwrap(execute_score(biz_id))

    if name == "get_weekly_cashflow":
        weeks = int(arguments.get("weeks") or 4)
        return _unwrap(execute_weekly_summary(biz_id, {"weeks": str(weeks)}))

    if name == "get_debt_ledger":
        return _unwrap(execute_list_debts(biz_id, {}))

    if name == "record_customer_debt":
        res = execute_create_debt(biz_id, {
            "debtor_name": arguments.get("debtor_name", ""),
            "debtor_phone": arguments.get("debtor_phone", ""),
            "amount_owed": arguments.get("amount_owed", 0),
            "items_summary": arguments.get("items_summary", "Shop goods"),
        })
        return _unwrap(res)

    if name == "evaluate_loan_readiness":
        req_amt = float(arguments.get("requested_amount_kes") or 50000)
        return _evaluate_loan(biz_id, req_amt)

    raise ValueError(f"Unknown MCP tool: {name}")


def handle_mcp_jsonrpc(payload: Dict[str, Any], default_business_id: str = DEFAULT_TEST_BUSINESS_ID) -> Dict[str, Any]:
    """Processes a standard JSON-RPC 2.0 MCP request."""
    req_id = payload.get("id")
    method = payload.get("method", "")
    params = payload.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            },
        }

    if method == "notifications/initialized":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": MCP_TOOLS},
        }

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments") or {}
        try:
            data = call_mcp_tool(tool_name, arguments, default_business_id=default_business_id)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(data, indent=2)}],
                    "structuredContent": data,
                    "isError": "error" in data,
                },
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": str(e)}],
                    "isError": True,
                },
            }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def execute_mcp_copilot(business_id: str, query: str) -> Dict[str, Any]:
    """
    Interactive Copilot endpoint for live pitch demos:
    Translates a natural-language question into a real MCP JSON-RPC `tools/call`
    and returns both the human-readable answer and the protocol trace.
    """
    q = (query or "").strip()
    q_low = q.lower()

    if any(k in q_low for k in ["loan", "qualify", "borrow", "underwrite", "lender", "credit limit"]):
        amt_match = re.search(r"(\d[\d,]{2,})", q)
        amt = float(amt_match.group(1).replace(",", "")) if amt_match else 50000.0
        tool_name = "evaluate_loan_readiness"
        tool_args: Dict[str, Any] = {"business_id": business_id, "requested_amount_kes": amt}

    elif any(k in q_low for k in ["add debt", "log debt", "record debt", "owes"]):
        phone_match = re.search(r"((?:\+?254|0)[17]\d{8})", q.replace(" ", ""))
        phone = phone_match.group(1) if phone_match else "0712345678"
        q_no_phone = re.sub(r"(?:\+?254|0)[17][\d\s-]{8,11}", " ", q_low)
        amt_match = re.search(r"(?:ksh|kes|amount)?\s*(\d[\d,]{1,6})", q_no_phone)
        amt = float(amt_match.group(1).replace(",", "")) if amt_match else 1500.0
        name_match = re.search(r"(?:for|debt)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", q)
        name = name_match.group(1) if name_match else "Jane Wanjiku"
        tool_name = "record_customer_debt"
        tool_args = {
            "business_id": business_id,
            "debtor_name": name,
            "debtor_phone": phone,
            "amount_owed": amt,
            "items_summary": "Logged via MCP Copilot",
        }

    elif any(k in q_low for k in ["cashflow", "profit", "sales", "weekly", "turnover", "revenue"]):
        tool_name = "get_weekly_cashflow"
        tool_args = {"business_id": business_id, "weeks": 4}

    elif any(k in q_low for k in ["debt", "deni", "owe", "recovery", "ledger"]):
        tool_name = "get_debt_ledger"
        tool_args = {"business_id": business_id}

    else:
        tool_name = "get_business_score"
        tool_args = {"business_id": business_id}

    rpc_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": tool_args},
    }
    rpc_response = handle_mcp_jsonrpc(rpc_request, default_business_id=business_id)
    data = rpc_response.get("result", {}).get("structuredContent", {})

    if tool_name == "evaluate_loan_readiness":
        answer = (
            f"Underwriting Decision: {data.get('decision')} (Risk: {data.get('risk_level')}). "
            f"{data.get('rationale')}"
        )
    elif tool_name == "record_customer_debt":
        if "error" in data:
            answer = f"Could not record debt: {data['error'].get('message')}"
        else:
            answer = (
                f"Recorded debt for {data.get('debtor_name')} ({data.get('debtor_phone')}) "
                f"of KSh {float(data.get('amount_owed', 0)):,.0f} into the Customer Debt Ledger."
            )
    elif tool_name == "get_weekly_cashflow":
        curr = data.get("current_week", {})
        answer = (
            f"Latest week ({curr.get('week_label', 'N/A')}): Gross Sales KSh {float(curr.get('gross_sales', 0)):,.0f}, "
            f"Operating Spend KSh {float(curr.get('operating_expenses', 0)):,.0f}, "
            f"Est. Profit KSh {float(curr.get('estimated_profit', 0)):,.0f}."
        )
    elif tool_name == "get_debt_ledger":
        s = data.get("summary", {})
        answer = (
            f"Debt Ledger: KSh {float(s.get('total_outstanding_amount', 0)):,.0f} outstanding across "
            f"{s.get('unpaid_count', 0)} unpaid customers. Recovery rate: {float(s.get('recovery_rate_pct', 0)):.1f}%."
        )
    else:
        answer = (
            f"Biashara Score: {data.get('total_score', 0)}/100 (Tier: {data.get('tier', 'N/A')}). "
            f"Weekly Avg Turnover: KSh {float(data.get('weekly_turnover_avg', 0)):,.0f}, "
            f"Weekly Avg Profit: KSh {float(data.get('weekly_profit_avg', 0)):,.0f}."
        )

    return {
        "query": q,
        "tool_used": tool_name,
        "answer": answer,
        "mcp_request": rpc_request,
        "mcp_response": rpc_response,
    }
