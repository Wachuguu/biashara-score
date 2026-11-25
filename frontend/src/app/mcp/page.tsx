"use client";
import { useState } from "react";
import { Send, Sparkles, Terminal } from "lucide-react";
import { api } from "@/api/endpoints";
import { errorMessage } from "@/api/client";
import { Button } from "@/components/Button";
import { ErrorState } from "@/components/StateViews";
import { useActiveDuka } from "@/hooks/useActiveDuka";

const PRESETS = [
  "Can I qualify for a KSh 50,000 loan?",
  "How much profit did I make this week?",
  "Who owes me money right now?",
  "What is my Biashara Score?",
  "Add debt for Jane Wanjiku 0722112233 amount 2500",
];

interface ChatMessage {
  id: string;
  role: "user" | "nia";
  text: string;
  toolUsed?: string;
  mcpRequest?: Record<string, unknown>;
  mcpResponse?: Record<string, unknown>;
}

export default function NiaAssistantPage() {
  const { profile } = useActiveDuka();
  const shopName = profile?.shop_name ?? "Geomin Routers";
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "nia",
      text: `Hello! I am Nia, your business assistant for ${shopName}. Ask me about your weekly profit, customer debts, Biashara Score, or whether your shop qualifies for a loan.`,
    },
  ]);
  const [showDevTrace, setShowDevTrace] = useState(false);

  async function sendMessage(text?: string) {
    const q = (text ?? query).trim();
    if (!q || busy) return;
    if (!text) setQuery("");
    setBusy(true);
    setError(null);

    const userMsg: ChatMessage = { id: `u-${Date.now()}`, role: "user", text: q };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const res = await api.mcpCopilot(q);
      const niaMsg: ChatMessage = {
        id: `n-${Date.now()}`,
        role: "nia",
        text: res.answer,
        toolUsed: res.tool_used,
        mcpRequest: res.mcp_request,
        mcpResponse: res.mcp_response,
      };
      setMessages((prev) => [...prev, niaMsg]);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const latestTrace = [...messages].reverse().find((m) => m.role === "nia" && m.mcpRequest);

  return (
    <div className="space-y-5">
      <div>
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-full border-2 border-ink bg-maize font-display text-lg font-black text-ink">
            N
          </span>
          <div>
            <h1 className="text-2xl leading-tight">Nia</h1>
            <p className="text-xs text-ink-soft">Your shop&apos;s financial &amp; loan assistant</p>
          </div>
        </div>
      </div>

      {/* Chat Conversation Feed */}
      <section className="panel flex flex-col gap-3 p-4">
        <div className="max-h-[420px] space-y-3 overflow-y-auto pr-1">
          {messages.map((m) => (
            <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[85%] rounded-md px-3.5 py-2.5 text-sm leading-relaxed ${
                  m.role === "user"
                    ? "border-2 border-ink bg-cobalt text-white font-medium"
                    : "border-2 border-ink bg-paper text-ink"
                }`}
              >
                {m.role === "nia" && (
                  <p className="mb-1 text-[11px] font-extrabold uppercase tracking-wide text-cobalt">Nia</p>
                )}
                <p>{m.text}</p>
              </div>
            </div>
          ))}
          {busy && (
            <div className="flex justify-start">
              <div className="rounded-md border-2 border-rule bg-paper px-3.5 py-2 text-xs font-bold text-ink-soft">
                Nia is checking your shop records...
              </div>
            </div>
          )}
        </div>

        {/* Quick-Tap Chips */}
        <div className="border-t border-rule pt-3">
          <p className="mb-2 flex items-center gap-1 text-xs font-bold text-ink-soft">
            <Sparkles aria-hidden className="h-3.5 w-3.5 text-cobalt" /> Try asking:
          </p>
          <div className="flex flex-wrap gap-1.5">
            {PRESETS.map((p) => (
              <button
                key={p}
                type="button"
                disabled={busy}
                onClick={() => sendMessage(p)}
                className="rounded-full border border-rule bg-paper px-3 py-1 text-left text-xs font-bold text-ink hover:border-cobalt hover:bg-cobalt-soft/30 disabled:opacity-50"
              >
                {p}
              </button>
            ))}
          </div>
        </div>

        {/* Chat Input */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            sendMessage();
          }}
          className="flex gap-2 pt-1"
        >
          <input
            className="field flex-1"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask Nia about sales, debts, or loans..."
            maxLength={300}
          />
          <Button type="submit" size="md" loading={busy} className="shrink-0" aria-label="Send message">
            <Send aria-hidden className="h-4 w-4" />
            Send
          </Button>
        </form>
        {error && <ErrorState message={error} compact />}
      </section>

      {/* Hidden by default (Abstraction): Optional toggle for technical judges / partner banks */}
      {latestTrace && (
        <div className="pt-1">
          <button
            type="button"
            onClick={() => setShowDevTrace((v) => !v)}
            className="flex items-center gap-1.5 text-xs font-bold text-ink-soft hover:text-cobalt"
          >
            <Terminal aria-hidden className="h-3.5 w-3.5" />
            {showDevTrace ? "Hide Bank / Partner MCP API Trace" : "For Banks & Developers: View Live MCP Query"}
          </button>
          {showDevTrace && (
            <div className="panel mt-2 space-y-2 p-3">
              <p className="text-xs font-bold text-ink-soft">
                Under the hood, Nia (and partner banks like KCB) query Biashara Score via JSON-RPC 2.0 MCP (<code className="text-cobalt">POST /mcp</code>):
              </p>
              <pre className="max-h-60 overflow-auto rounded border border-rule bg-paper p-2 text-[11px] text-ink">
                {JSON.stringify({ request: latestTrace.mcpRequest, response: latestTrace.mcpResponse }, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
