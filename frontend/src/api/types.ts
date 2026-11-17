// TypeScript mirrors of backend/src/core/models.py and docs/API_CONTRACT.md

export const CATEGORIES = [
  "SALES",
  "INVENTORY",
  "UTILITIES",
  "RENT",
  "DEBT_RECOVERY",
  "OWNER_DRAW",
  "AIRTIME",
  "UNCATEGORIZED",
] as const;
export type Category = (typeof CATEGORIES)[number];
export type Direction = "IN" | "OUT";

export interface Business {
  business_id: string;
  shop_name: string;
  owner_name: string;
  owner_phone: string;
  till_number?: string | null;
  created_at?: string;
}

export type BusinessInput = Omit<Business, "business_id" | "created_at">;

export interface Transaction {
  business_id?: string;
  receipt_number: string;
  completion_time: string;
  details: string;
  amount: number;
  direction: Direction;
  running_balance: number;
  status: string;
  category: Category;
  counterparty: string | null;
  categorization_method: string;
  debt_matched_id: string | null;
  source?: string;
}

export interface UploadResult {
  status: string;
  business_id: string;
  statement_filename: string;
  imported: number;
  skipped_duplicates: number;
  debts_auto_matched: number;
  categories_breakdown: Partial<Record<Category, number>>;
  date_range: { start: string; end: string };
}

export interface SmsResult {
  status: string;
  business_id: string;
  imported: number;
  skipped_duplicates: number;
  debts_auto_matched: number;
  transactions: Transaction[];
}

export interface TransactionList {
  business_id: string;
  total_count: number;
  next_cursor: string | null;
  transactions: Transaction[];
}

export interface WeekPoint {
  week_label: string;
  gross_sales: number;
  operating_expenses: number;
  estimated_profit: number;
  profit_margin_pct: number;
}

export interface WeekSummary extends WeekPoint {
  start_date: string;
  end_date: string;
  active_trading_days: number;
  transaction_count: number;
  expense_breakdown: Record<string, number>;
  pulse_message: string;
}

export interface WeeklySummaryResponse {
  business_id: string;
  currency: string;
  current_week: WeekSummary;
  history_series: WeekPoint[];
}

export type DebtStatus = "UNPAID" | "PARTIAL" | "CLEARED";

export interface Repayment {
  receipt_number: string;
  amount: number;
  date: string;
  notes?: string | null;
}

export interface Debt {
  debt_id: string;
  business_id: string;
  debtor_name: string;
  debtor_phone: string;
  amount_owed: number;
  amount_cleared: number;
  balance_remaining: number;
  status: DebtStatus;
  items_summary: string;
  created_at: string;
  due_date: string;
  repayment_history: Repayment[];
}

export interface DebtInput {
  debtor_name: string;
  debtor_phone: string;
  amount_owed: number;
  items_summary?: string;
  due_date?: string;
}

export interface DebtList {
  business_id: string;
  summary: {
    total_outstanding_amount: number;
    total_cleared_amount: number;
    recovery_rate_pct: number;
    unpaid_count: number;
    delinquent_count: number;
  };
  debts: Debt[];
}

export interface Score {
  business_id: string;
  total_score: number;
  tier: string;
  consistency_score: number;
  growth_score: number;
  expense_ratio_score: number;
  debt_recovery_score: number;
  weekly_turnover_avg: number;
  weekly_profit_avg: number;
  debt_recovery_rate: number | null;
  computed_at: string;
  actionable_tips: string[];
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: unknown[];
    timestamp?: string;
  };
}
