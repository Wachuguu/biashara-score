"use client";
import { CloudOff, RotateCw, type LucideIcon } from "lucide-react";
import { Button } from "./Button";

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`rounded-md bg-rule/60 motion-safe:animate-pulse ${className}`} />;
}

export function LoadingBlock({ label = "Loading", lines = 3 }: { label?: string; lines?: number }) {
  return (
    <div role="status" aria-live="polite" className="space-y-3 py-2">
      <span className="sr-only">{label}…</span>
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className={i === 0 ? "h-6 w-2/3" : "h-5 w-full"} />
      ))}
    </div>
  );
}

export function ErrorState({ message, onRetry, compact }: { message: string; onRetry?: () => void; compact?: boolean }) {
  return (
    <div role="alert" className={`flex flex-col items-start gap-3 rounded-md border-2 border-chili/50 bg-chili-soft ${compact ? "p-3" : "p-4"}`}>
      <div className="flex items-start gap-2 text-ink">
        <CloudOff aria-hidden className="mt-0.5 h-5 w-5 shrink-0 text-chili" />
        <p className="text-sm font-bold">{message}</p>
      </div>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          <RotateCw aria-hidden className="h-4 w-4" /> Try again
        </Button>
      )}
    </div>
  );
}

export function EmptyState({
  icon: Icon,
  title,
  body,
  action,
}: {
  icon: LucideIcon;
  title: string;
  body?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 px-4 py-8 text-center">
      <span className="flex h-14 w-14 items-center justify-center rounded-full border-2 border-ink bg-maize">
        <Icon aria-hidden className="h-7 w-7 text-ink" />
      </span>
      <h3 className="text-2xl">{title}</h3>
      {body && <p className="max-w-xs text-ink-soft">{body}</p>}
      {action}
    </div>
  );
}
