"use client";
import { m } from "motion/react";
import type { Score } from "@/api/types";

const PILLARS: { key: keyof Score; label: string; hint: string; max: number }[] = [
  { key: "consistency_score", label: "Cashflow consistency", hint: "Selling most days of the week", max: 30 },
  { key: "growth_score", label: "Sales volume", hint: "How much you sell each week", max: 25 },
  { key: "expense_ratio_score", label: "Operating margin", hint: "Spending kept below sales", max: 25 },
  { key: "debt_recovery_score", label: "Debt recovery", hint: "Customers paying their debt", max: 20 },
];

/** Four meters, each against its own maximum. One hue; values in text tokens. */
export function PillarBars({ score }: { score: Score }) {
  return (
    <ul className="space-y-4">
      {PILLARS.map((p, i) => {
        const v = Number(score[p.key]) || 0;
        const pct = Math.max(0, Math.min(1, v / p.max));
        return (
          <li key={p.key}>
            <div className="mb-1 flex items-baseline justify-between gap-3">
              <span>
                <span className="block font-bold leading-tight">{p.label}</span>
                <span className="block text-xs text-ink-soft">{p.hint}</span>
              </span>
              <span className="num shrink-0 font-bold">
                {v}
                <span className="text-ink-soft"> / {p.max}</span>
              </span>
            </div>
            <div
              className="h-2.5 overflow-hidden rounded-full bg-chart-track"
              role="meter"
              aria-label={p.label}
              aria-valuemin={0}
              aria-valuemax={p.max}
              aria-valuenow={v}
            >
              <m.div
                className="h-full origin-left rounded-full bg-chart-sales"
                style={{ width: `${pct * 100}%` }}
                initial={{ scaleX: 0 }}
                animate={{ scaleX: 1 }}
                transition={{ duration: 0.35, delay: 0.1 + i * 0.05, ease: [0.22, 1, 0.36, 1] }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
