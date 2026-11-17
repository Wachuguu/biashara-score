"use client";
import { ChevronDown } from "lucide-react";
import type { Transaction } from "@/api/types";
import { CATEGORY_META } from "@/utils/categories";
import { counterpartyName, formatDateTime, formatKSh } from "@/utils/format";

export function CategoryChip({ category, asButton }: { category: Transaction["category"]; asButton?: boolean }) {
  const meta = CATEGORY_META[category] ?? CATEGORY_META.UNCATEGORIZED;
  const Icon = meta.icon;
  return (
    <span className={`inline-flex items-center gap-1 rounded-sm border px-2 py-0.5 text-xs font-bold ${meta.chip}`}>
      <Icon aria-hidden className="h-3.5 w-3.5" />
      {meta.label}
      {asButton && <ChevronDown aria-hidden className="h-3.5 w-3.5" />}
    </span>
  );
}

export function TxRow({ tx, onCategoryClick }: { tx: Transaction; onCategoryClick?: (tx: Transaction) => void }) {
  const isIn = tx.direction === "IN";
  const name = counterpartyName(tx.counterparty, tx.details);
  const corrected = tx.categorization_method === "USER_CORRECTED";
  return (
    <div className="flex items-start gap-3 py-3">
      <div className="min-w-0 flex-1">
        <p className="truncate font-bold">{name}</p>
        <p className="num text-xs text-ink-soft">{formatDateTime(tx.completion_time)}</p>
        <div className="mt-1.5 flex flex-wrap items-center gap-2">
          {onCategoryClick ? (
            <button
              type="button"
              onClick={() => onCategoryClick(tx)}
              className="-my-2 inline-flex min-h-tap items-center"
              aria-label={`Category: ${CATEGORY_META[tx.category]?.label ?? tx.category}. Change`}
            >
              <CategoryChip category={tx.category} asButton />
            </button>
          ) : (
            <CategoryChip category={tx.category} />
          )}
          {corrected && <span className="text-xs font-bold text-cobalt">Fixed by you</span>}
        </div>
      </div>
      <p className={`num shrink-0 text-right font-display text-xl font-extrabold ${isIn ? "text-leaf" : "text-ink"}`}>
        <span className="sr-only">{isIn ? "Money in" : "Money out"} </span>
        {isIn ? "+" : "−"}
        {formatKSh(tx.amount)}
      </p>
    </div>
  );
}
