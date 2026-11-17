"use client";
import { useMemo, useState } from "react";
import { m } from "motion/react";
import type { WeekPoint } from "@/api/types";
import { formatCompact, formatKSh, shortWeek } from "@/utils/format";
import { useWidth } from "@/utils/useWidth";

const SALES = "#3556C4";
const PROFIT = "#1F8A52";
const H = 168;
const PAD = { top: 22, right: 4, bottom: 26, left: 36 };

function niceStep(range: number) {
  const raw = range / 3;
  const mag = Math.pow(10, Math.floor(Math.log10(raw || 1)));
  const n = raw / mag;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * mag;
}

/** Column with a 4px rounded data-end and a square baseline end. */
function colPath(x: number, w: number, y0: number, y1: number) {
  const up = y1 <= y0;
  const h = Math.abs(y1 - y0);
  const r = Math.min(4, w / 2, h);
  if (h < 0.5) return "";
  if (up) return `M${x},${y0} V${y1 + r} Q${x},${y1} ${x + r},${y1} H${x + w - r} Q${x + w},${y1} ${x + w},${y1 + r} V${y0} Z`;
  return `M${x},${y0} V${y1 - r} Q${x},${y1} ${x + r},${y1} H${x + w - r} Q${x + w},${y1} ${x + w},${y1 - r} V${y0} Z`;
}

/** Weekly sales and profit, one shared KSh axis. Tap a week to read its values. */
export function WeekTrend({ weeks }: { weeks: WeekPoint[] }) {
  const { ref, width } = useWidth<HTMLDivElement>();
  const [sel, setSel] = useState(weeks.length - 1);
  const selected = weeks[Math.min(sel, weeks.length - 1)];

  const geo = useMemo(() => {
    const maxV = Math.max(1, ...weeks.map((w) => Math.max(w.gross_sales, w.estimated_profit)));
    const minV = Math.min(0, ...weeks.map((w) => w.estimated_profit));
    const step = niceStep(maxV - minV);
    const top = Math.ceil(maxV / step) * step;
    const bottom = Math.floor(minV / step) * step;
    const plotH = H - PAD.top - PAD.bottom;
    const y = (v: number) => PAD.top + ((top - v) / (top - bottom)) * plotH;
    const ticks: number[] = [];
    for (let t = bottom; t <= top + 1e-6; t += step) ticks.push(t);
    const plotW = width - PAD.left - PAD.right;
    const band = plotW / weeks.length;
    const barW = Math.min(24, (band - 14) / 2);
    return { y, ticks, band, barW };
  }, [weeks, width]);

  const last = weeks.length - 1;

  return (
    <div>
      <div className="mb-2 flex gap-4 text-sm font-bold" aria-hidden>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-sm" style={{ background: SALES }} /> Sales
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-sm" style={{ background: PROFIT }} /> Profit
        </span>
      </div>
      <div ref={ref} className="w-full">
        <svg width={width} height={H} role="img" aria-label="Weekly sales and profit chart. Table below." className="block overflow-visible">
          {geo.ticks.map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={width - PAD.right} y1={geo.y(t)} y2={geo.y(t)} stroke={t === 0 ? "#3D4A66" : "#E4E8F0"} strokeWidth={1} />
              <text x={PAD.left - 6} y={geo.y(t)} dy="0.32em" textAnchor="end" className="num fill-ink-soft text-[11px]">
                {formatCompact(t)}
              </text>
            </g>
          ))}
          {weeks.map((w, i) => {
            const cx = PAD.left + geo.band * i + geo.band / 2;
            const xs = cx - geo.barW - 1; // 2px surface gap between the pair
            const xp = cx + 1;
            const y0 = geo.y(0);
            const isSel = i === sel;
            return (
              <g key={w.week_label} opacity={isSel ? 1 : 0.55}>
                <m.path
                  d={colPath(xs, geo.barW, y0, geo.y(w.gross_sales))}
                  fill={SALES}
                  style={{ originY: 1 }}
                  initial={{ scaleY: 0 }}
                  animate={{ scaleY: 1 }}
                  transition={{ duration: 0.3, delay: i * 0.04 }}
                />
                <m.path
                  d={colPath(xp, geo.barW, y0, geo.y(w.estimated_profit))}
                  fill={PROFIT}
                  style={{ originY: w.estimated_profit >= 0 ? 1 : 0 }}
                  initial={{ scaleY: 0 }}
                  animate={{ scaleY: 1 }}
                  transition={{ duration: 0.3, delay: i * 0.04 + 0.03 }}
                />
                {i === last && (
                  <text x={xs + geo.barW / 2} y={geo.y(w.gross_sales) - 6} textAnchor="middle" className="num fill-ink text-[11px] font-bold">
                    {formatCompact(w.gross_sales)}
                  </text>
                )}
                <text x={cx} y={H - 8} textAnchor="middle" className={`text-[11px] ${isSel ? "fill-ink font-bold" : "fill-ink-soft"}`}>
                  {i === last ? "This wk" : shortWeek(w.week_label)}
                </text>
                <rect
                  x={cx - geo.band / 2}
                  y={0}
                  width={geo.band}
                  height={H}
                  fill="transparent"
                  tabIndex={0}
                  role="button"
                  aria-label={`${shortWeek(w.week_label)}: sales ${formatKSh(w.gross_sales)}, profit ${formatKSh(w.estimated_profit)}`}
                  onClick={() => setSel(i)}
                  onMouseEnter={() => setSel(i)}
                  onFocus={() => setSel(i)}
                  className="cursor-pointer outline-none"
                />
              </g>
            );
          })}
        </svg>
      </div>
      {selected && (
        <p aria-live="polite" className="mt-2 rounded-md bg-paper px-3 py-2 text-sm">
          <span className="font-bold">{sel === last ? "This week" : `Week ${shortWeek(selected.week_label).slice(1)}`}</span>
          <span className="num block">
            Sales {formatKSh(selected.gross_sales)}, profit {formatKSh(selected.estimated_profit)}
          </span>
        </p>
      )}
      <details className="mt-2 text-sm">
        <summary className="inline-flex min-h-tap cursor-pointer items-center font-bold text-cobalt">Show as table</summary>
        <table className="num mt-1 w-full text-left">
          <thead>
            <tr className="border-b-2 border-rule text-ink-soft">
              <th className="py-1 font-bold">Week</th>
              <th className="py-1 text-right font-bold">Sales</th>
              <th className="py-1 text-right font-bold">Spent</th>
              <th className="py-1 text-right font-bold">Profit</th>
            </tr>
          </thead>
          <tbody>
            {weeks.map((w) => (
              <tr key={w.week_label} className="border-b border-rule">
                <td className="py-1">{shortWeek(w.week_label)}</td>
                <td className="py-1 text-right">{formatKSh(w.gross_sales)}</td>
                <td className="py-1 text-right">{formatKSh(w.operating_expenses)}</td>
                <td className="py-1 text-right">{formatKSh(w.estimated_profit)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}
