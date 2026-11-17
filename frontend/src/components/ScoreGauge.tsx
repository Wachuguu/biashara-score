"use client";
import { useEffect, useState } from "react";
import { animate, motion, useReducedMotion } from "motion/react";

const R = 84;
const CX = 100;
const CY = 100;
const ARC = `M ${CX - R} ${CY} A ${R} ${R} 0 0 1 ${CX + R} ${CY}`;
const TIER_TICKS = [50, 65, 80]; // Bronze / Silver / Gold cut-offs from score_engine.py

function pointAt(pct: number, radius: number) {
  const a = Math.PI * (1 - pct / 100);
  return { x: CX + radius * Math.cos(a), y: CY - radius * Math.sin(a) };
}

/** Semicircle meter, 0–100. Ink fill on a lighter ink track (sits on the maize signboard). */
export function ScoreGauge({ score }: { score: number }) {
  const value = Math.max(0, Math.min(100, Math.round(score)));
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(reduce ? value : 0);

  useEffect(() => {
    if (reduce) {
      setShown(value);
      return;
    }
    const controls = animate(0, value, { duration: 0.4, ease: [0.22, 1, 0.36, 1], onUpdate: (v) => setShown(Math.round(v)) });
    return () => controls.stop();
  }, [value, reduce]);

  return (
    <figure className="relative mx-auto w-full max-w-[280px]" aria-label={`Biashara Score ${value} out of 100`}>
      <svg viewBox="0 0 200 112" className="block w-full" aria-hidden>
        <path d={ARC} fill="none" stroke="#14213D" strokeOpacity={0.14} strokeWidth={18} strokeLinecap="round" />
        {value > 0 && (
          <motion.path
            d={ARC}
            fill="none"
            stroke="#14213D"
            strokeWidth={18}
            strokeLinecap="round"
            initial={{ pathLength: reduce ? value / 100 : 0 }}
            animate={{ pathLength: value / 100 }}
            transition={{ duration: reduce ? 0 : 0.4, ease: [0.22, 1, 0.36, 1] }}
          />
        )}
        {TIER_TICKS.map((t) => {
          const a = pointAt(t, R - 13);
          const b = pointAt(t, R + 13);
          return <line key={t} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#F2C230" strokeWidth={3} />;
        })}
      </svg>
      <figcaption className="absolute inset-x-0 bottom-0 flex flex-col items-center">
        <span className="font-display text-sign font-black leading-none">{shown}</span>
        <span className="text-sm font-bold">out of 100</span>
      </figcaption>
    </figure>
  );
}
