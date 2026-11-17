"use client";
import Link from "next/link";
import { motion, type Variants } from "motion/react";
import { FileUp, Lightbulb, MessageSquareText, TrendingDown, TrendingUp } from "lucide-react";
import { api } from "@/api/endpoints";
import type { WeekPoint } from "@/api/types";
import { PillarBars } from "@/components/PillarBars";
import { ScoreGauge } from "@/components/ScoreGauge";
import { EmptyState, ErrorState, LoadingBlock, Skeleton } from "@/components/StateViews";
import { TxRow } from "@/components/TxRow";
import { WeekTrend } from "@/components/WeekTrend";
import { useActiveDuka } from "@/hooks/useActiveDuka";
import { useApi } from "@/hooks/useApi";
import { formatDate, formatKSh } from "@/utils/format";

const TIER_COPY: Record<string, string> = {
  Gold: "Strong. Lenders will like this.",
  Silver: "Good. A few steps from Gold.",
  Bronze: "Fair. Keep building it.",
  "Needs Improvement": "Keep recording sales to build it up.",
};

const card: Variants = {
  hidden: { opacity: 0, y: 10 },
  show: (i: number) => ({ opacity: 1, y: 0, transition: { delay: i * 0.06, duration: 0.25, ease: [0.22, 1, 0.36, 1] as const } }),
};

export default function DashboardPage() {
  const { id } = useActiveDuka();
  const score = useApi(id ? `score:${id}` : null, () => api.score());
  const weekly = useApi(id ? `weekly:${id}` : null, () => api.weeklySummary(6));
  const recent = useApi(id ? `recent:${id}` : null, () => api.listTransactions({ limit: 6 }));

  const noData = recent.data?.total_count === 0;

  if (noData) {
    return (
      <div className="panel mt-4">
        <EmptyState
          icon={FileUp}
          title="No sales yet"
          body="Import your M-Pesa statement or paste SMS messages. Your Biashara Score appears here."
          action={
            <Link href="/import" className="inline-flex min-h-[52px] items-center rounded-md bg-cobalt px-5 text-lg font-bold text-white">
              Import M-Pesa
            </Link>
          }
        />
      </div>
    );
  }

  const weeks: WeekPoint[] = weekly.data ? trimLeadingEmpty([...weekly.data.history_series, weekly.data.current_week]) : [];
  const cw = weekly.data?.current_week;

  return (
    <div className="space-y-5">
      {/* Hero: the painted signboard */}
      <motion.section custom={0} variants={card} initial="hidden" animate="show" aria-labelledby="score-h" className="rounded-sign border-3 border-ink bg-maize px-4 pb-5 pt-4 shadow-board">
        <h1 id="score-h" className="text-2xl leading-none">
          Biashara Score
        </h1>
        {score.loading && !score.data ? (
          <div className="py-6">
            <Skeleton className="mx-auto h-32 w-56 bg-ink/10" />
          </div>
        ) : score.error ? (
          <div className="pt-3">
            <ErrorState message={score.error} onRetry={score.reload} />
          </div>
        ) : score.data ? (
          <>
            <div className="mt-2">
              <ScoreGauge score={score.data.total_score} />
            </div>
            <div className="mt-3 text-center">
              <p className="inline-block rounded-sm border-2 border-ink bg-card px-3 py-0.5 font-display text-xl font-extrabold">{score.data.tier}</p>
              <p className="mt-1 font-bold">{TIER_COPY[score.data.tier] ?? ""}</p>
            </div>
          </>
        ) : null}
      </motion.section>

      {/* This week */}
      <motion.section custom={1} variants={card} initial="hidden" animate="show" className="panel p-4" aria-labelledby="week-h">
        <div className="mb-3 flex items-baseline justify-between gap-2">
          <h2 id="week-h" className="text-2xl">
            This week
          </h2>
          {cw && (
            <span className="num text-sm text-ink-soft">
              {formatDate(cw.start_date)} to {formatDate(cw.end_date)}
            </span>
          )}
        </div>
        {weekly.loading && !weekly.data ? (
          <LoadingBlock label="Loading this week" />
        ) : weekly.error ? (
          <ErrorState message={weekly.error} onRetry={weekly.reload} />
        ) : cw ? (
          <>
            <dl className="grid grid-cols-2 gap-3">
              <Stat label="Sales" sw="Mauzo" value={formatKSh(cw.gross_sales)} />
              <Stat label="Spent" sw="Matumizi" value={formatKSh(cw.operating_expenses)} />
              <div className="col-span-2 rounded-md border-2 border-ink bg-paper p-3">
                <dt className="flex items-center gap-1.5 text-sm font-bold">
                  {cw.estimated_profit >= 0 ? <TrendingUp aria-hidden className="h-5 w-5 text-leaf" /> : <TrendingDown aria-hidden className="h-5 w-5 text-chili" />}
                  {cw.estimated_profit >= 0 ? "Profit" : "Loss"} <span className="font-normal text-ink-soft">(Faida)</span>
                </dt>
                <dd className="font-display text-4xl font-black">{formatKSh(cw.estimated_profit)}</dd>
                <dd className="text-sm text-ink-soft">
                  {cw.active_trading_days} selling days, {cw.transaction_count} transactions
                </dd>
              </div>
            </dl>
            {cw.pulse_message && (
              <p className="mt-3 flex gap-2 text-sm text-ink-soft">
                <MessageSquareText aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />
                <span>
                  Sunday SMS: <q>{cw.pulse_message}</q>
                </span>
              </p>
            )}
          </>
        ) : null}
      </motion.section>

      {/* Score pillars + tips */}
      {score.data && (
        <motion.section custom={2} variants={card} initial="hidden" animate="show" className="panel p-4" aria-labelledby="pillars-h">
          <h2 id="pillars-h" className="mb-3 text-2xl">
            What builds your score
          </h2>
          <PillarBars score={score.data} />
          {score.data.actionable_tips.length > 0 && (
            <div className="mt-5 rounded-md bg-maize-soft p-3">
              <h3 className="mb-2 text-xl">How to raise it</h3>
              <ul className="space-y-2">
                {score.data.actionable_tips.slice(0, 3).map((t) => (
                  <li key={t} className="flex gap-2 text-sm">
                    <Lightbulb aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />
                    <span>{t}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </motion.section>
      )}

      {/* Trend */}
      {weeks.length > 1 && (
        <motion.section custom={3} variants={card} initial="hidden" animate="show" className="panel p-4" aria-labelledby="trend-h">
          <h2 id="trend-h" className="mb-2 text-2xl">
            Last {weeks.length} weeks
          </h2>
          <WeekTrend weeks={weeks} />
        </motion.section>
      )}

      {/* Recent */}
      <motion.section custom={4} variants={card} initial="hidden" animate="show" className="panel px-4 pt-4" aria-labelledby="recent-h">
        <div className="flex items-baseline justify-between">
          <h2 id="recent-h" className="text-2xl">
            Recent
          </h2>
          <Link href="/import#transactions" className="inline-flex min-h-tap items-center text-sm font-bold text-cobalt underline underline-offset-4">
            See all
          </Link>
        </div>
        {recent.loading && !recent.data ? (
          <div className="pb-4">
            <LoadingBlock label="Loading transactions" lines={4} />
          </div>
        ) : recent.error ? (
          <div className="pb-4">
            <ErrorState message={recent.error} onRetry={recent.reload} />
          </div>
        ) : (
          <ul className="divide-y-2 divide-rule">
            {recent.data?.transactions.map((tx) => (
              <li key={tx.receipt_number}>
                <TxRow tx={tx} />
              </li>
            ))}
          </ul>
        )}
      </motion.section>
    </div>
  );
}

function Stat({ label, sw, value }: { label: string; sw: string; value: string }) {
  return (
    <div className="rounded-md bg-paper p-3">
      <dt className="text-sm font-bold">
        {label} <span className="font-normal text-ink-soft">({sw})</span>
      </dt>
      <dd className="whitespace-nowrap font-display text-xl font-extrabold min-[380px]:text-2xl">{value}</dd>
    </div>
  );
}

/** Drop empty weeks before the shop's first transaction so the chart starts at real data. */
function trimLeadingEmpty(weeks: WeekPoint[]): WeekPoint[] {
  const first = weeks.findIndex((w) => w.gross_sales !== 0 || w.operating_expenses !== 0);
  return first === -1 ? [] : weeks.slice(first);
}
