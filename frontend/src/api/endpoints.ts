import { request } from "./client";
import type {
  Business,
  BusinessInput,
  Category,
  Debt,
  DebtInput,
  DebtList,
  DebtStatus,
  Score,
  SmsResult,
  Transaction,
  TransactionList,
  UploadResult,
  WeeklySummaryResponse,
} from "./types";

export const api = {
  health: () => request<{ status: string; mock_aws: boolean }>("/health", { timeoutMs: 8_000 }),

  getBusiness: (businessId?: string) => request<Business>("/business", { businessId }),
  putBusiness: (input: BusinessInput, businessId?: string) =>
    request<Business>("/business", { method: "PUT", json: input, businessId }),

  registerAccount: (input: BusinessInput & { password: string }) =>
    request<{ token: string; business: Business }>("/auth/register", { method: "POST", json: input }),
  loginAccount: (input: { owner_phone: string; password: string }) =>
    request<{ token: string; business: Business }>("/auth/login", { method: "POST", json: input }),

  uploadStatement: (file: File) => {
    const form = new FormData();
    form.append("file", file, file.name);
    return request<UploadResult>("/statements/upload", { method: "POST", form, timeoutMs: 60_000 });
  },
  pasteSms: (smsText: string) => request<SmsResult>("/statements/sms", { method: "POST", json: { sms_text: smsText } }),

  listTransactions: (q: { limit?: number; category?: Category | null; direction?: "IN" | "OUT" } = {}) =>
    request<TransactionList>("/transactions", { query: { limit: q.limit ?? 50, category: q.category, direction: q.direction } }),
  /** Added on feat/frontend-pwa: PATCH /transactions/{receipt_number} */
  setCategory: (receipt: string, category: Category) =>
    request<Transaction>(`/transactions/${encodeURIComponent(receipt)}`, { method: "PATCH", json: { category } }),

  weeklySummary: (weeks = 6) => request<WeeklySummaryResponse>("/summary/weekly", { query: { weeks } }),

  listDebts: (q: { status?: DebtStatus | null; search?: string } = {}) =>
    request<DebtList>("/debts", { query: { status: q.status, search: q.search?.trim() } }),
  createDebt: (input: DebtInput) => request<Debt>("/debts", { method: "POST", json: input }),
  recordRepayment: (debtId: string, amount: number, notes?: string) =>
    request<Debt>(`/debts/${encodeURIComponent(debtId)}`, {
      method: "PATCH",
      json: { amount_to_clear: amount, receipt_number: "CASH_RECOVERY", notes: notes?.trim() || "Paid at the shop" },
    }),

  score: () => request<Score>("/score"),
  lenderPdf: () =>
    request<Blob>("/reports/lender-pdf", { query: { format: "binary" }, expect: "blob", timeoutMs: 60_000 }),

  // Safaricom Daraja M-Pesa Live Integration & Pitch Tools
  simulateMpesa: (input: { amount: number; phone?: string; customer_name?: string }) =>
    request<{ status: string; simulated: boolean; result: { debt_matched: boolean; transaction: any } }>("/mpesa/simulate", {
      method: "POST",
      json: input,
    }),
  loadSampleStatement: () =>
    request<{ status: string; imported: number; skipped_duplicates: number; debts_auto_matched: number }>("/statements/sample", {
      method: "POST",
    }),

  // Model Context Protocol (MCP) & Copilot
  mcpCopilot: (query: string) =>
    request<{
      query: string;
      tool_used: string;
      answer: string;
      mcp_request: Record<string, unknown>;
      mcp_response: Record<string, unknown>;
    }>("/mcp/copilot", {
      method: "POST",
      json: { query },
    }),
};
