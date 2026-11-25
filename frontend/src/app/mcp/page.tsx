"use client";
import { useState } from "react";
import { Bot, Send, Sparkles, Terminal } from "lucide-react";
import { api } from "@/api/endpoints";
import { errorMessage } from "@/api/client";
import { Button } from "@/components/Button";
import { ErrorState } from "@/components/StateViews";
import { useActiveDuka } from "@/hooks/useActiveDuka";

const PRESETS = [
  "Can this shop qualify for a KSh 50,000 loan?",
  "Show weekly cashflow and profit",
  "Check customer debt ledger",
  "What is our Biashara Score?",
  "Add debt for Jane Wanjiku 0722112233 amount 2500",
];

interface CopilotResult {
  query: string;
  tool_used: string;
  answer: string;
  mcp_request: Record<string, unknown>;
  mcp_response: Record<string, unknown>;
}

export default function McpCopilotPage() {
  const { profile } = useActiveDuka();
  const [query, setQuery] = useState(PRESETS[0]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CopilotResult | null>(null);
  const [showTrace, setShowTrace] = useState(true);

  async function runQuery(text?: string) {
    const q = (text ?? query).trim();
    if (!q) return;
    if (text) setQuery(text);
    setBusy(true);
    setError(null);
    try {
      const res = await api.mcpCopilot(q);
      setResult(res);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2">
          <Bot aria-hidden className="h-7 w-7 text-cobalt" />
          <h1 className="text-3xl">MCP Copilot</h1>
        </div>
        <p className="text-ink-soft">
          Model Context Protocol (JSON-RPC 2.0) underwriting &amp; shop assistant for {profile?.shop_name ?? "Geomin Routers"}.
        </p>
      </div>

      <section className="panel space-y-3 p-4">
        <p className="flex items-center gap-1.5 text-sm font-bold text-ink">
          <Sparkles aria-hidden className="h-4 w-4 text-cobalt" /> Quick Prompts (1-Tap Demo)
        </p>
        <div className="flex flex-wrap gap-2">
          {PRESETS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => runQuery(p)}
              className="rounded-md border-2 border-rule bg-paper px-3 py-1.5 text-left text-xs font-bold text-ink hover:border-cobalt hover:bg-cobalt-soft/30"
            >
              {p}
            </button>
          ))}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            runQuery();
          }}
          className="flex flex-col gap-2 pt-2 sm:flex-row"
        >
          <input
            className="field flex-1"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask a lender or shop question..."
            maxLength={300}
          />
          <Button type="submit" size="md" loading={busy} className="shrink-0">
            <Send aria-hidden className="h-4 w-4" />
            Run MCP Tool
          </Button>
        </form>
        {error && <ErrorState message={error} compact />}
      </section>

      {result && (
        <section className="space-y-4">
          <div className="rounded-sign border-3 border-ink bg-maize p-4 shadow-board">
            <p className="text-xs font-extrabold uppercase tracking-wider text-ink-soft">
              MCP Tool Executed: <span className="text-cobalt">{result.tool_used}</span>
            </p>
            <p className="mt-2 text-lg font-bold text-ink">{result.answer}</p>
          </div>

          <div className="panel p-4">
            <button
              type="button"
              onClick={() => setShowTrace((v) => !v)}
              className="flex w-full items-center justify-between text-sm font-bold text-ink"
            >
              <span className="flex items-center gap-2">
                <Terminal aria-hidden className="h-4 w-4 text-cobalt" />
                Live JSON-RPC 2.0 Protocol Trace
              </span>
              <span className="text-xs text-cobalt">{showTrace ? "Hide" : "Show"}</span>
            </button>

            {showTrace && (
              <div className="mt-3 space-y-3">
                <div>
                  <p className="text-xs font-bold text-ink-soft">Request (tools/call):</p>
                  <pre className="mt-1 overflow-x-auto rounded-md border border-rule bg-paper p-3 text-xs text-ink">
                    {JSON.stringify(result.mcp_request, null, 2)}
                  </pre>
                </div>
                <div>
                  <p className="text-xs font-bold text-ink-soft">Response (structuredContent):</p>
                  <pre className="mt-1 max-h-72 overflow-auto rounded-md border border-rule bg-paper p-3 text-xs text-ink">
                    {JSON.stringify(result.mcp_response, null, 2)}
                  </pre>
                </div>
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
