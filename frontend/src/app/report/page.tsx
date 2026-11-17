"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AnimatePresence, m } from "motion/react";
import { BadgeCheck, CircleCheck, Download, FileText } from "lucide-react";
import { api } from "@/api/endpoints";
import { errorMessage } from "@/api/client";
import { Button } from "@/components/Button";
import { ErrorState, Skeleton } from "@/components/StateViews";
import { useActiveDuka } from "@/hooks/useActiveDuka";
import { useApi } from "@/hooks/useApi";

const INCLUDED = [
  "Your Biashara Score and tier",
  "Weekly sales and profit from M\u2011Pesa",
  "Average sale size and busy days",
  "Kitabu ya Deni health",
];

function fileName(shop?: string) {
  const safe = (shop || "Duka").replace(/[^\w]+/g, "_").replace(/^_|_$/g, "");
  return `Biashara_Score_Report_${safe || "Duka"}.pdf`;
}

export default function ReportPage() {
  const { id, profile } = useActiveDuka();
  const check = useApi(id ? `report-check:${id}` : null, () => api.listTransactions({ limit: 1 }));
  const [state, setState] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const urlRef = useRef<string | null>(null);

  useEffect(
    () => () => {
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    },
    [],
  );

  async function download() {
    setState("loading");
    setError(null);
    try {
      const blob = await api.lenderPdf();
      if (!blob.size) throw new Error("empty");
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
      const url = URL.createObjectURL(new Blob([blob], { type: "application/pdf" }));
      urlRef.current = url;
      const a = document.createElement("a");
      a.href = url;
      a.download = fileName(profile?.shop_name);
      document.body.appendChild(a);
      a.click();
      a.remove();
      setState("done");
    } catch (e) {
      setError(e instanceof Error && e.message === "empty" ? "The report came back empty. Try again." : errorMessage(e));
      setState("error");
    }
  }

  const noData = check.data?.total_count === 0;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-3xl">Lender report</h1>
        <p className="text-ink-soft">A one-page PDF for your bank, SACCO or microfinance loan officer.</p>
      </div>

      <section className="panel p-4">
        <div className="flex items-start gap-3">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-md border-2 border-ink bg-maize">
            <FileText aria-hidden className="h-6 w-6" />
          </span>
          <div>
            <p className="font-bold">{profile?.shop_name ?? "Your duka"}</p>
            <p className="text-sm text-ink-soft">Built from your M-Pesa records. A4, one page.</p>
          </div>
        </div>
        <h2 className="mt-4 text-xl">What the lender sees</h2>
        <ul className="mt-2 space-y-1.5">
          {INCLUDED.map((t) => (
            <li key={t} className="flex items-start gap-2">
              <BadgeCheck aria-hidden className="mt-0.5 h-5 w-5 shrink-0 text-leaf" />
              <span>{t}</span>
            </li>
          ))}
        </ul>
      </section>

      {check.loading && !check.data ? (
        <Skeleton className="h-[52px] w-full" />
      ) : noData ? (
        <div className="rounded-md border-2 border-maize-deep bg-maize-soft p-4">
          <p className="font-bold">Your report has no numbers yet.</p>
          <p className="text-sm">Import your M-Pesa statement first so lenders see real sales.</p>
          <Link href="/import" className="mt-2 inline-flex min-h-tap items-center font-bold text-cobalt underline underline-offset-4">
            Import M-Pesa
          </Link>
        </div>
      ) : null}

      <Button size="lg" block loading={state === "loading"} onClick={download} disabled={noData}>
        {state !== "loading" && <Download aria-hidden className="h-5 w-5" />}
        {state === "loading" ? "Preparing report" : "Download report (PDF)"}
      </Button>

      <AnimatePresence mode="wait">
        {state === "done" && (
          <m.div
            key="done"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            role="status"
            className="flex items-start gap-2 rounded-md border-2 border-leaf bg-leaf-soft p-3"
          >
            <CircleCheck aria-hidden className="h-6 w-6 shrink-0 text-leaf" />
            <div>
              <p className="font-bold">Report downloaded</p>
              <p className="text-sm">Find it in your phone&apos;s Downloads. Share it on WhatsApp or print it.</p>
              {urlRef.current && (
                <a href={urlRef.current} target="_blank" rel="noopener" className="mt-1 inline-flex min-h-tap items-center text-sm font-bold text-cobalt underline underline-offset-4">
                  Open report
                </a>
              )}
            </div>
          </m.div>
        )}
        {state === "error" && error && (
          <m.div key="err" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
            <ErrorState message={error} onRetry={download} />
          </m.div>
        )}
      </AnimatePresence>
    </div>
  );
}
