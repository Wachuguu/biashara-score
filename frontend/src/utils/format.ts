const kshFmt = new Intl.NumberFormat("en-KE", { maximumFractionDigits: 0 });

/** "KSh 14,200". Negative values get a real minus sign: "−KSh 3,251". */
export function formatKSh(value: number | null | undefined): string {
  const n = typeof value === "number" && Number.isFinite(value) ? value : 0;
  const rounded = Math.round(n);
  const body = `KSh ${kshFmt.format(Math.abs(rounded))}`;
  return rounded < 0 ? `−${body}` : body;
}

/** Axis-friendly: 14k, 1.2M */
export function formatCompact(value: number): string {
  const a = Math.abs(value);
  const sign = value < 0 ? "−" : "";
  if (a >= 1_000_000) return `${sign}${(a / 1_000_000).toFixed(a >= 10_000_000 ? 0 : 1).replace(/\.0$/, "")}M`;
  if (a >= 1_000) return `${sign}${Math.round(a / 1_000)}k`;
  return `${sign}${Math.round(a)}`;
}

// Backend timestamps are shop-local times written with a "Z" suffix (from the
// M-Pesa CSV), so render them in UTC to show the time exactly as on the statement.
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const pad = (n: number) => String(n).padStart(2, "0");

function toDate(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatDate(iso: string | null | undefined): string {
  const d = toDate(iso);
  return d ? `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}` : "—";
}

export function formatDateTime(iso: string | null | undefined): string {
  const d = toDate(iso);
  return d ? `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}, ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}` : "—";
}

export function daysSince(iso: string | null | undefined): number | null {
  const d = toDate(iso);
  if (!d) return null;
  return Math.floor((Date.now() - d.getTime()) / 86_400_000);
}

/** "2026-W40" -> "W40" */
export function shortWeek(label: string): string {
  const m = /W(\d+)$/.exec(label);
  return m ? `W${Number(m[1])}` : label;
}

/** Mirrors backend regex in local_server.py / debt_handler.py */
export function isValidKenyanPhone(raw: string): boolean {
  const cleaned = raw.trim().replace(/[\s-]/g, "");
  return /^(\+?254|0)?[17]\d{8}$/.test(cleaned);
}

/** "John Otieno 254731829405" -> "John Otieno" */
export function counterpartyName(raw: string | null | undefined, fallback = ""): string {
  if (!raw) return fallback;
  const name = raw.replace(/\s*\+?\d{9,}\s*$/, "").trim();
  return name || raw;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
