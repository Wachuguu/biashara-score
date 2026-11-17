"use client";
import { Check } from "lucide-react";
import { CATEGORIES, type Category, type Transaction } from "@/api/types";
import { CATEGORY_META } from "@/utils/categories";
import { counterpartyName, formatDateTime, formatKSh } from "@/utils/format";
import { Sheet } from "./Sheet";

export function CategoryPicker({ tx, onClose, onPick }: { tx: Transaction | null; onClose: () => void; onPick: (tx: Transaction, c: Category) => void }) {
  return (
    <Sheet open={tx !== null} onClose={onClose} title="Choose category">
      {tx && (
        <>
          <div className="mb-4 rounded-md bg-paper p-3">
            <p className="font-bold">{counterpartyName(tx.counterparty, tx.details)}</p>
            <p className="num text-sm text-ink-soft">
              {tx.direction === "IN" ? "Money in" : "Money out"}: {formatKSh(tx.amount)}, {formatDateTime(tx.completion_time)}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 pb-2">
            {CATEGORIES.map((c) => {
              const meta = CATEGORY_META[c];
              const Icon = meta.icon;
              const selected = tx.category === c;
              return (
                <button
                  key={c}
                  type="button"
                  data-autofocus={selected || undefined}
                  onClick={() => onPick(tx, c)}
                  aria-pressed={selected}
                  className={`relative flex min-h-[64px] items-center gap-2 rounded-md border-2 px-3 text-left ${selected ? "border-cobalt bg-cobalt-soft" : "border-ink/30 bg-card hover:border-ink"}`}
                >
                  <Icon aria-hidden className="h-5 w-5 shrink-0" />
                  <span className="min-w-0">
                    <span className="block font-bold leading-tight">{meta.label}</span>
                    <span className="block text-xs text-ink-soft">{meta.sw}</span>
                  </span>
                  {selected && <Check aria-hidden className="absolute right-2 top-2 h-4 w-4 text-cobalt" />}
                </button>
              );
            })}
          </div>
        </>
      )}
    </Sheet>
  );
}
