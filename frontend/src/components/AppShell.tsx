"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { BookOpen, FileText, Store, Upload, type LucideIcon } from "lucide-react";
import { useActiveDuka } from "@/hooks/useActiveDuka";

const NAV: { href: string; label: string; icon: LucideIcon }[] = [
  { href: "/dashboard", label: "Home", icon: Store },
  { href: "/import", label: "Import", icon: Upload },
  { href: "/deni", label: "Deni", icon: BookOpen },
  { href: "/report", label: "Report", icon: FileText },
];

const OPEN_ROUTES = ["/", "/setup", "/offline"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { ready, id, profile } = useActiveDuka();
  const isOpenRoute = OPEN_ROUTES.includes(pathname);

  useEffect(() => {
    if (ready && !id && !isOpenRoute) router.replace("/setup");
  }, [ready, id, isOpenRoute, router]);

  const showChrome = !isOpenRoute;

  return (
    <>
      {showChrome && (
        <header className="sticky top-0 z-30 border-b-2 border-ink bg-paper/95 pt-[var(--safe-top)] backdrop-blur">
          <div className="mx-auto flex h-14 max-w-app items-center justify-between gap-3 px-4">
            <span className="truncate font-display text-xl font-extrabold">{profile?.shop_name ?? "Biashara Score"}</span>
            <Link href="/setup" className="inline-flex min-h-tap shrink-0 items-center rounded-md px-2 text-sm font-bold text-cobalt underline-offset-4 hover:underline">
              Change duka
            </Link>
          </div>
        </header>
      )}

      <main className={`mx-auto w-full max-w-app px-4 ${showChrome ? "pb-[calc(theme(spacing.nav)+var(--safe-bottom)+1.5rem)] pt-4" : "py-6"}`}>
        {children}
      </main>

      {showChrome && (
        <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-40 border-t-2 border-ink bg-card pb-[var(--safe-bottom)]">
          <ul className="mx-auto grid h-nav max-w-app grid-cols-4">
            {NAV.map(({ href, label, icon: Icon }) => {
              const active = pathname === href || pathname.startsWith(href + "/");
              return (
                <li key={href}>
                  <Link
                    href={href}
                    aria-current={active ? "page" : undefined}
                    className={`relative flex h-full flex-col items-center justify-center gap-0.5 text-xs font-bold ${active ? "text-ink" : "text-ink-soft"}`}
                  >
                    {active && <span aria-hidden className="absolute inset-x-5 top-0 h-1 rounded-b-sm bg-maize-deep" />}
                    <Icon aria-hidden className={`h-6 w-6 ${active ? "stroke-[2.5]" : ""}`} />
                    {label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      )}
    </>
  );
}
