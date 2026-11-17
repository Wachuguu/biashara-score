"use client";
import { useEffect, useId, useRef } from "react";
import { AnimatePresence, m } from "motion/react";
import { X } from "lucide-react";

interface SheetProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}

/** Bottom sheet on phones, centred dialog from 768px. */
export function Sheet({ open, onClose, title, children }: SheetProps) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && closeRef.current();
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const t = window.setTimeout(() => {
      const first = panelRef.current?.querySelector<HTMLElement>("input, textarea, select, [data-autofocus]");
      (first ?? panelRef.current)?.focus();
    }, 60);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
      window.clearTimeout(t);
    };
  }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-end justify-center md:items-center md:p-6">
          <m.div
            className="absolute inset-0 bg-ink/50"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            onClick={onClose}
            aria-hidden
          />
          <m.div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            tabIndex={-1}
            className="relative max-h-[92dvh] w-full max-w-lg overflow-y-auto rounded-t-lg border-2 border-b-0 border-ink bg-card px-4 pt-3 shadow-sheet pb-safe outline-none md:rounded-lg md:border-b-2 md:pb-5"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%", transition: { duration: 0.18, ease: [0.4, 0, 1, 1] } }}
            transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="mx-auto mb-2 h-1.5 w-12 rounded-full bg-rule md:hidden" aria-hidden />
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 id={titleId} className="text-2xl">
                {title}
              </h2>
              <button
                type="button"
                onClick={onClose}
                className="-mr-2 inline-flex min-h-tap min-w-tap items-center justify-center rounded-md text-ink-soft hover:bg-paper"
                aria-label="Close"
              >
                <X className="h-6 w-6" />
              </button>
            </div>
            {children}
          </m.div>
        </div>
      )}
    </AnimatePresence>
  );
}
