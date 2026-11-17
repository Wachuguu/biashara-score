"use client";
import { useRef, useState } from "react";
import Link from "next/link";
import { AnimatePresence, m } from "motion/react";
import { FileUp, MessageSquareText, ReceiptText } from "lucide-react";
import { api } from "@/api/endpoints";
import { errorMessage } from "@/api/client";
import { CATEGORIES, type Category, type Transaction } from "@/api/types";
import { Button } from "@/components/Button";
import { CategoryPicker } from "@/components/CategoryPicker";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/StateViews";
import { useToast } from "@/components/Toast";
import { TxRow } from "@/components/TxRow";
import { useActiveDuka } from "@/hooks/useActiveDuka";
import { useApi } from "@/hooks/useApi";
import { CATEGORY_META } from "@/utils/categories";
import { formatBytes, formatDate } from "@/utils/format";

const MAX_BYTES = 5 * 1024 * 1024;
const PAGE = 50;
const MAX_LIMIT = 200; // backend max; cursor is not honoured server-side yet

type Mode = "csv" | "sms";
interface ImportSummary {
  imported: number;
  skipped: number;
  matched: number;
  range?: { start: string; end: string };
}

export default function ImportPage() {
  const toast = useToast();
  const { id } = useActiveDuka();
  const [mode, setMode] = useState<Mode>("csv");
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [sms, setSms] = useState("");
  const [busy, setBusy] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [summary, setSummary] = useState<ImportSummary | null>(null);
  const [filter, setFilter] = useState<Category | null>(null);
  const [limit, setLimit] = useState(PAGE);
  const [picking, setPicking] = useState<Transaction | null>(null);
  const [refresh, setRefresh] = useState(0);
  const fileInput = useRef<HTMLInputElement>(null);

  const txs = useApi(id ? `tx:${id}:${filter ?? "all"}:${limit}:${refresh}` : null, () => api.listTransactions({ limit, category: filter }));

  function pickFile(f: File | null) {
    setSubmitError(null);
    setSummary(null);
    if (!f) return setFile(null);
    if (!/\.csv$/i.test(f.name)) {
      setFile(null);
      return setFileError("Choose the M-Pesa statement saved as a .csv file.");
    }
    if (f.size > MAX_BYTES) {
      setFile(null);
      return setFileError(`This file is ${formatBytes(f.size)}. The limit is 5 MB.`);
    }
    setFileError(null);
    setFile(f);
  }

  async function submit() {
    setBusy(true);
    setSubmitError(null);
    try {
      if (mode === "csv" && file) {
        const r = await api.uploadStatement(file);
        setSummary({ imported: r.imported, skipped: r.skipped_duplicates, matched: r.debts_auto_matched, range: r.date_range });
        toast(`${r.imported} transactions imported`);
        setFile(null);
        if (fileInput.current) fileInput.current.value = "";
      } else if (mode === "sms" && sms.trim()) {
        const r = await api.pasteSms(sms);
        setSummary({ imported: r.imported, skipped: r.skipped_duplicates, matched: r.debts_auto_matched });
        toast(r.imported === 1 ? "1 message added" : `${r.imported} messages added`);
        if (r.imported > 0) setSms("");
      }
      setFilter(null);
      setLimit(PAGE);
      setRefresh((n) => n + 1);
    } catch (e) {
      setSubmitError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function changeCategory(tx: Transaction, category: Category) {
    setPicking(null);
    if (tx.category === category) return;
    const swap = (c: Category, method: string) =>
      txs.setData((d) =>
        d ? { ...d, transactions: d.transactions.map((t) => (t.receipt_number === tx.receipt_number ? { ...t, category: c, categorization_method: method } : t)) } : d,
      );
    swap(category, "USER_CORRECTED");
    try {
      await api.setCategory(tx.receipt_number, category);
      toast(`Saved as ${CATEGORY_META[category].label}`);
    } catch (e) {
      swap(tx.category, tx.categorization_method);
      toast(errorMessage(e), "error");
    }
  }

  const canSubmit = mode === "csv" ? !!file : sms.trim().length > 0;
  const list = txs.data?.transactions ?? [];
  const total = txs.data?.total_count ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl">Import M-Pesa</h1>
        <p className="text-ink-soft">Add your statement or paste SMS messages. We sort them for you.</p>
      </div>

      <div role="tablist" aria-label="Import method" className="grid grid-cols-2 gap-1 rounded-md border-2 border-ink bg-card p-1">
        {(
          [
            ["csv", "Statement file", FileUp],
            ["sms", "Paste SMS", MessageSquareText],
          ] as const
        ).map(([value, label, Icon]) => (
          <button
            key={value}
            role="tab"
            type="button"
            aria-selected={mode === value}
            onClick={() => {
              setMode(value);
              setSubmitError(null);
            }}
            className={`flex min-h-[44px] items-center justify-center gap-2 rounded-sm font-bold transition-colors duration-200 ${mode === value ? "bg-maize text-ink" : "text-ink-soft"}`}
          >
            <Icon aria-hidden className="h-5 w-5" />
            {label}
          </button>
        ))}
      </div>

      <section className="panel p-4">
        {mode === "csv" ? (
          <div className="space-y-3">
            <label className="flex min-h-[120px] cursor-pointer flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed border-ink/50 bg-paper px-4 py-5 text-center hover:border-cobalt">
              <FileUp aria-hidden className="h-8 w-8 text-cobalt" />
              {file ? (
                <span>
                  <span className="block break-all font-bold">{file.name}</span>
                  <span className="text-sm text-ink-soft">{formatBytes(file.size)}. Tap to choose another.</span>
                </span>
              ) : (
                <span>
                  <span className="block font-bold">Choose statement (.csv)</span>
                  <span className="text-sm text-ink-soft">From the M-Pesa app or Safaricom portal. Up to 5 MB.</span>
                </span>
              )}
              <input ref={fileInput} type="file" accept=".csv,text/csv" className="sr-only" onChange={(e) => pickFile(e.target.files?.[0] ?? null)} />
            </label>
            {fileError && (
              <p role="alert" className="text-sm font-bold text-chili">
                {fileError}
              </p>
            )}
          </div>
        ) : (
          <label className="block">
            <span className="label">Paste one or more M-Pesa messages</span>
            <textarea
              className="field min-h-[160px] py-2 leading-snug"
              value={sms}
              onChange={(e) => setSms(e.target.value)}
              placeholder="SK01YUUM7K Confirmed. You have received Ksh1,600.00 from John Otieno 254731829405 on 1/9/26 at 12:49 PM…"
              maxLength={20000}
            />
          </label>
        )}

        <Button className="mt-4" size="lg" block disabled={!canSubmit} loading={busy} onClick={submit}>
          {mode === "csv" ? "Import statement" : "Add messages"}
        </Button>
        {submitError && (
          <div className="mt-3">
            <ErrorState message={submitError} compact />
          </div>
        )}
      </section>

      <AnimatePresence>
        {summary && (
          <m.section
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.22 }}
            aria-live="polite"
            className="rounded-md border-2 border-leaf bg-leaf-soft p-4"
          >
            <p className="font-display text-2xl font-extrabold">{summary.imported === 1 ? "1 transaction added" : `${summary.imported} transactions added`}</p>
            <ul className="mt-1 space-y-0.5 text-sm">
              {summary.skipped > 0 && <li>{summary.skipped} were already saved, so we skipped them.</li>}
              {summary.matched > 0 && <li>{summary.matched} matched a customer&apos;s deni and were marked paid.</li>}
              {summary.range && (
                <li>
                  Covers {formatDate(summary.range.start)} to {formatDate(summary.range.end)}.
                </li>
              )}
            </ul>
            <Link href="/dashboard" className="mt-3 inline-flex min-h-tap items-center font-bold text-cobalt underline underline-offset-4">
              See your score
            </Link>
          </m.section>
        )}
      </AnimatePresence>

      <section id="transactions" aria-labelledby="tx-heading" className="scroll-mt-20">
        <h2 id="tx-heading" className="text-2xl">
          Check categories
        </h2>
        <p className="mb-3 text-sm text-ink-soft">Wrong category? Tap it to fix. Your score updates.</p>

        <div className="no-scrollbar -mx-4 mb-2 flex gap-2 overflow-x-auto px-4 pb-1">
          {[null, ...CATEGORIES].map((c) => {
            const active = filter === c;
            return (
              <button
                key={c ?? "all"}
                type="button"
                aria-pressed={active}
                onClick={() => {
                  setFilter(c);
                  setLimit(PAGE);
                }}
                className={`min-h-[40px] shrink-0 rounded-full border-2 px-3 text-sm font-bold ${active ? "border-ink bg-ink text-white" : "border-ink/30 bg-card text-ink"}`}
              >
                {c ? CATEGORY_META[c].label : "All"}
              </button>
            );
          })}
        </div>

        <div className="panel px-4">
          {txs.loading && !txs.data ? (
            <LoadingBlock label="Loading transactions" lines={5} />
          ) : txs.error ? (
            <div className="py-4">
              <ErrorState message={txs.error} onRetry={txs.reload} />
            </div>
          ) : list.length === 0 ? (
            <EmptyState
              icon={ReceiptText}
              title={filter ? "None here" : "No transactions yet"}
              body={filter ? `No ${CATEGORY_META[filter].label.toLowerCase()} transactions.` : "Import your statement above to see them here."}
            />
          ) : (
            <ul className="divide-y-2 divide-rule">
              {list.map((tx, i) => (
                <m.li
                  key={tx.receipt_number}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: Math.min(i, 8) * 0.03, duration: 0.2 }}
                >
                  <TxRow tx={tx} onCategoryClick={setPicking} />
                </m.li>
              ))}
            </ul>
          )}
        </div>
        {list.length > 0 && (
          <p className="mt-2 text-center text-sm text-ink-soft">
            Showing {list.length} of {total}
          </p>
        )}
        {total > list.length && limit < MAX_LIMIT && (
          <Button variant="secondary" block className="mt-2" loading={txs.loading} onClick={() => setLimit((l) => Math.min(l + PAGE * 2, MAX_LIMIT))}>
            Show more
          </Button>
        )}
      </section>

      <CategoryPicker tx={picking} onClose={() => setPicking(null)} onPick={changeCategory} />
    </div>
  );
}
