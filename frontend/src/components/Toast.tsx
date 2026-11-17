"use client";
import { createContext, useCallback, useContext, useRef, useState } from "react";
import { AnimatePresence, m } from "motion/react";
import { CircleAlert, CircleCheck } from "lucide-react";

type Tone = "success" | "error";
interface ToastItem {
  id: number;
  message: string;
  tone: Tone;
}

const ToastCtx = createContext<(message: string, tone?: Tone) => void>(() => {});

export function useToast() {
  return useContext(ToastCtx);
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toast, setToast] = useState<ToastItem | null>(null);
  const timer = useRef<number | undefined>(undefined);

  const show = useCallback((message: string, tone: Tone = "success") => {
    window.clearTimeout(timer.current);
    setToast({ id: Date.now(), message, tone });
    timer.current = window.setTimeout(() => setToast(null), tone === "error" ? 4500 : 2600);
  }, []);

  return (
    <ToastCtx.Provider value={show}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-[calc(theme(spacing.nav)+var(--safe-bottom)+0.75rem)] z-[45] flex justify-center px-4">
        <AnimatePresence>
          {toast && (
            <m.div
              key={toast.id}
              initial={{ opacity: 0, y: 12, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, transition: { duration: 0.15 } }}
              transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
              className={`pointer-events-auto flex max-w-sm items-center gap-2 rounded-md border-2 px-4 py-3 font-bold shadow-sheet ${
                toast.tone === "success" ? "border-leaf bg-card text-ink" : "border-chili bg-chili-soft text-ink"
              }`}
            >
              {toast.tone === "success" ? (
                <m.span initial={{ scale: 0.4 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 500, damping: 18 }}>
                  <CircleCheck aria-hidden className="h-6 w-6 text-leaf" />
                </m.span>
              ) : (
                <CircleAlert aria-hidden className="h-6 w-6 shrink-0 text-chili" />
              )}
              <span>{toast.message}</span>
            </m.div>
          )}
        </AnimatePresence>
      </div>
    </ToastCtx.Provider>
  );
}
