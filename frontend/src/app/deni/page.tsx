"use client";
import { useEffect, useState } from "react";
import { m } from "motion/react";
import { BookOpen, Phone, Plus, Search } from "lucide-react";
import { api } from "@/api/endpoints";
import { errorMessage } from "@/api/client";
import type { Debt, DebtStatus } from "@/api/types";
import { Button } from "@/components/Button";
import { Sheet } from "@/components/Sheet";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/StateViews";
import { useToast } from "@/components/Toast";
import { useActiveDuka } from "@/hooks/useActiveDuka";
import { useApi } from "@/hooks/useApi";
import { daysSince, formatDate, formatKSh, isValidKenyanPhone } from "@/utils/format";

const FILTERS: { value: DebtStatus | null; label: string }[] = [
  { value: null, label: "All" },
  { value: "UNPAID", label: "Unpaid" },
  { value: "PARTIAL", label: "Part paid" },
  { value: "CLEARED", label: "Paid" },
];

const STATUS_BADGE: Record<DebtStatus, { label: string; cls: string }> = {
  UNPAID: { label: "Unpaid", cls: "bg-chili-soft text-chili border-chili/50" },
  PARTIAL: { label: "Part paid", cls: "bg-maize-soft text-ink border-maize-deep" },
  CLEARED: { label: "Paid", cls: "bg-leaf-soft text-leaf border-leaf/50" },
};

export default function DeniPage() {
  const toast = useToast();
  const { id } = useActiveDuka();
  const [status, setStatus] = useState<DebtStatus | null>(null);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [adding, setAdding] = useState(false);
  const [paying, setPaying] = useState<Debt | null>(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const t = window.setTimeout(() => setSearch(query.trim()), 300);
    return () => window.clearTimeout(t);
  }, [query]);

  const debts = useApi(id ? `debts:${id}:${status ?? ""}:${search}:${refresh}` : null, () => api.listDebts({ status, search }));
  const list = debts.data?.debts ?? [];
  const s = debts.data?.summary;
  const filtered = status !== null || search !== "";

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl leading-none">Kitabu ya Deni</h1>
          <p className="text-ink-soft">Who owes you, and how much.</p>
        </div>
        <Button onClick={() => setAdding(true)} size="lg" className="w-full sm:w-auto">
          <Plus aria-hidden className="h-5 w-5" /> Add deni
        </Button>
      </div>

      {s && (
        <dl className="grid grid-cols-2 gap-2">
          <div className="col-span-2 rounded-md border-2 border-ink bg-card p-3">
            <dt className="text-sm font-bold">Customers owe you</dt>
            <dd className="font-display text-4xl font-black text-chili">{formatKSh(s.total_outstanding_amount)}</dd>
          </div>
          <div className="rounded-md bg-card p-3">
            <dt className="text-sm font-bold">Collected</dt>
            <dd className="whitespace-nowrap font-display text-xl font-extrabold">{formatKSh(s.total_cleared_amount)}</dd>
          </div>
          <div className="rounded-md bg-card p-3">
            <dt className="text-sm font-bold">Late (30+ days)</dt>
            <dd className="font-display text-xl font-extrabold">{s.delinquent_count === 1 ? "1 customer" : `${s.delinquent_count} customers`}</dd>
          </div>
        </dl>
      )}

      <div className="space-y-2">
        <label className="relative block">
          <span className="sr-only">Search by name or phone</span>
          <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-ink-soft" />
          <input className="field pl-10" type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search name or phone" />
        </label>
        <div className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4">
          {FILTERS.map((f) => (
            <button
              key={f.label}
              type="button"
              aria-pressed={status === f.value}
              onClick={() => setStatus(f.value)}
              className={`min-h-[40px] shrink-0 rounded-full border-2 px-4 text-sm font-bold ${status === f.value ? "border-ink bg-ink text-white" : "border-ink/30 bg-card"}`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <section aria-label="Debts" className="ruled overflow-hidden rounded-lg border-2 border-ink">
        {debts.loading && !debts.data ? (
          <div className="py-2 pl-10 pr-4">
            <LoadingBlock label="Loading deni" lines={4} />
          </div>
        ) : debts.error ? (
          <div className="py-4 pl-10 pr-4">
            <ErrorState message={debts.error} onRetry={debts.reload} />
          </div>
        ) : list.length === 0 ? (
          <EmptyState
            icon={BookOpen}
            title={filtered ? "No match" : "Kitabu is empty"}
            body={filtered ? "Try another name or filter." : "When a customer takes goods on credit, add it here so you never forget."}
            action={
              !filtered && (
                <Button onClick={() => setAdding(true)}>
                  <Plus aria-hidden className="h-5 w-5" /> Add deni
                </Button>
              )
            }
          />
        ) : (
          <ul className="divide-y-2 divide-rule">
            {list.map((d, i) => (
              <m.li key={d.debt_id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 8) * 0.04, duration: 0.2 }}>
                <DebtRow debt={d} onPay={() => setPaying(d)} />
              </m.li>
            ))}
          </ul>
        )}
      </section>

      <AddDebtSheet
        open={adding}
        onClose={() => setAdding(false)}
        onSaved={(d) => {
          setAdding(false);
          toast(`Deni saved for ${d.debtor_name}`);
          setRefresh((n) => n + 1);
        }}
      />
      <RepaySheet
        debt={paying}
        onClose={() => setPaying(null)}
        onSaved={(d) => {
          setPaying(null);
          toast(d.status === "CLEARED" ? `${d.debtor_name} has paid in full` : "Payment saved");
          setRefresh((n) => n + 1);
        }}
      />
    </div>
  );
}

function DebtRow({ debt: d, onPay }: { debt: Debt; onPay: () => void }) {
  const badge = STATUS_BADGE[d.status] ?? STATUS_BADGE.UNPAID;
  const paidPct = d.amount_owed > 0 ? Math.min(100, (d.amount_cleared / d.amount_owed) * 100) : 0;
  const age = daysSince(d.created_at);
  const late = d.status !== "CLEARED" && age !== null && age > 30;
  const lastPay = d.repayment_history[d.repayment_history.length - 1];
  return (
    <div className="py-3 pl-10 pr-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-lg font-bold">{d.debtor_name}</p>
          <a href={`tel:${d.debtor_phone}`} className="num inline-flex min-h-[32px] items-center gap-1 text-sm text-cobalt">
            <Phone aria-hidden className="h-3.5 w-3.5" />
            {d.debtor_phone}
          </a>
        </div>
        <div className="shrink-0 text-right">
          <p className={`whitespace-nowrap font-display text-2xl font-extrabold ${d.status === "CLEARED" ? "text-ink-soft line-through decoration-2" : ""}`}>
            {formatKSh(d.status === "CLEARED" ? d.amount_owed : d.balance_remaining)}
          </p>
          <span className={`inline-block rounded-sm border px-2 text-xs font-bold ${badge.cls}`}>{badge.label}</span>
        </div>
      </div>
      {d.items_summary && <p className="mt-1 text-sm text-ink-soft">{d.items_summary}</p>}
      {d.status === "PARTIAL" && (
        <div className="mt-2">
          <div className="h-2 overflow-hidden rounded-full bg-chart-track" role="meter" aria-label="Paid so far" aria-valuemin={0} aria-valuemax={d.amount_owed} aria-valuenow={d.amount_cleared}>
            <div className="h-full rounded-full bg-chart-profit" style={{ width: `${paidPct}%` }} />
          </div>
          <p className="num mt-1 text-xs text-ink-soft">
            Paid {formatKSh(d.amount_cleared)} of {formatKSh(d.amount_owed)}
          </p>
        </div>
      )}
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-ink-soft">
          Taken {formatDate(d.created_at)}
          {d.due_date && `, due ${formatDate(d.due_date)}`}
          {late && <span className="font-bold text-chili">, over 30 days</span>}
          {lastPay && d.status !== "UNPAID" && `. Last paid ${formatDate(lastPay.date)}`}
        </p>
        {d.status !== "CLEARED" && (
          <Button variant="secondary" onClick={onPay}>
            Record payment
          </Button>
        )}
      </div>
    </div>
  );
}

function AddDebtSheet({ open, onClose, onSaved }: { open: boolean; onClose: () => void; onSaved: (d: Debt) => void }) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [amount, setAmount] = useState("");
  const [items, setItems] = useState("");
  const [due, setDue] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setName("");
      setPhone("");
      setAmount("");
      setItems("");
      setDue("");
      setErrors({});
      setServerError(null);
    }
  }, [open]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const amt = Number(amount.replace(/,/g, ""));
    const errs: Record<string, string> = {};
    if (!name.trim()) errs.name = "Enter the customer's name";
    if (!isValidKenyanPhone(phone)) errs.phone = "Use a number like 0712 345 678";
    if (!Number.isFinite(amt) || amt <= 0) errs.amount = "Enter how much they owe";
    else if (amt > 10_000_000) errs.amount = "That amount is too large";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setSaving(true);
    setServerError(null);
    try {
      const d = await api.createDebt({
        debtor_name: name.trim(),
        debtor_phone: phone.replace(/[\s-]/g, ""),
        amount_owed: Math.round(amt * 100) / 100,
        items_summary: items.trim() || undefined,
        due_date: due ? `${due}T18:00:00Z` : undefined,
      });
      onSaved(d);
    } catch (err) {
      setServerError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet open={open} onClose={onClose} title="Add deni">
      <form noValidate onSubmit={submit} className="space-y-4 pb-2">
        <FormField label="Customer name" error={errors.name}>
          <input className="field" value={name} onChange={(e) => setName(e.target.value)} placeholder="Mama Boi" maxLength={100} autoComplete="off" />
        </FormField>
        <FormField label="Phone" error={errors.phone}>
          <input className="field num" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="0712 345 678" inputMode="tel" maxLength={16} />
        </FormField>
        <FormField label="Amount owed (KSh)" error={errors.amount}>
          <input className="field num text-xl font-bold" value={amount} onChange={(e) => setAmount(e.target.value.replace(/[^\d.,]/g, ""))} placeholder="0" inputMode="decimal" />
        </FormField>
        <FormField label="What they took (optional)">
          <input className="field" value={items} onChange={(e) => setItems(e.target.value)} placeholder="Unga 2kg, sugar 1kg" maxLength={200} />
        </FormField>
        <FormField label="Promised to pay by (optional)">
          <input className="field" type="date" value={due} onChange={(e) => setDue(e.target.value)} />
        </FormField>
        {serverError && <ErrorState message={serverError} compact />}
        <Button type="submit" size="lg" block loading={saving}>
          Save deni
        </Button>
      </form>
    </Sheet>
  );
}

function RepaySheet({ debt, onClose, onSaved }: { debt: Debt | null; onClose: () => void; onSaved: (d: Debt) => void }) {
  const [amount, setAmount] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (debt) {
      setAmount(String(Math.round(debt.balance_remaining)));
      setNotes("");
      setError(null);
    }
  }, [debt]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!debt) return;
    const amt = Number(amount.replace(/,/g, ""));
    if (!Number.isFinite(amt) || amt <= 0) return setError("Enter the amount paid");
    if (amt > debt.balance_remaining + 0.001) return setError(`They only owe ${formatKSh(debt.balance_remaining)}`);
    setSaving(true);
    setError(null);
    try {
      onSaved(await api.recordRepayment(debt.debt_id, amt, notes));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet open={debt !== null} onClose={onClose} title="Record payment">
      {debt && (
        <form noValidate onSubmit={submit} className="space-y-4 pb-2">
          <div className="rounded-md bg-paper p-3">
            <p className="font-bold">{debt.debtor_name}</p>
            <p className="text-sm">
              Still owes <span className="num font-bold">{formatKSh(debt.balance_remaining)}</span>
            </p>
          </div>
          <FormField label="Amount paid (KSh)">
            <input className="field num text-xl font-bold" value={amount} onChange={(e) => setAmount(e.target.value.replace(/[^\d.,]/g, ""))} inputMode="decimal" />
          </FormField>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setAmount(String(Math.round(debt.balance_remaining)))}>
              Full amount
            </Button>
            <Button variant="secondary" onClick={() => setAmount(String(Math.round(debt.balance_remaining / 2)))}>
              Half
            </Button>
          </div>
          <FormField label="Note (optional)">
            <input className="field" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Paid cash at the shop" maxLength={120} />
          </FormField>
          {error && <ErrorState message={error} compact />}
          <Button type="submit" size="lg" block loading={saving}>
            Save payment
          </Button>
        </form>
      )}
    </Sheet>
  );
}

function FormField({ label, error, children }: { label: string; error?: string; children: React.ReactElement }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {children}
      {error && (
        <span role="alert" className="mt-1 block text-sm font-bold text-chili">
          {error}
        </span>
      )}
    </label>
  );
}
