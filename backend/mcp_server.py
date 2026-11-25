"""
Standalone stdio Model Context Protocol (MCP) Server for Biashara Score.
Connect from Claude Desktop, Cursor, or any MCP client via:
  PYTHONPATH=backend python backend/mcp_server.py
"""
import sys
import json
import os

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from src.handlers.mcp_handler import handle_mcp_jsonrpc


def main() -> None:
    for line in sys.stdin:
        raw = line.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
            response = handle_mcp_jsonrpc(payload)
            # Notifications without 'id' don't require a response
            if payload.get("id") is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
        except Exception as exc:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {exc}"},
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
