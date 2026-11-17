/**
 * Duka profiles live on the device (localStorage). The backend has no
 * "create business" call in mock mode: a new business is created by sending
 * PUT /business with a fresh X-Business-Id.
 */
export interface Profile {
  business_id: string;
  shop_name: string;
  owner_name: string;
}

const PROFILES_KEY = "bs.profiles";
const ACTIVE_KEY = "bs.active";
export const PROFILE_EVENT = "bs:profile";

/** Seeded test business in backend/src/wrappers/db_client.py */
export const DEMO_BUSINESS_ID = "biz_7a8b9c0d1e2f";

function read<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage blocked (private mode) — app still works for this session */
  }
  try {
    window.dispatchEvent(new Event(PROFILE_EVENT));
  } catch {
    /* ignore */
  }
}

let memoryActive: string | null = null;

export function getProfiles(): Profile[] {
  const list = read<Profile[]>(PROFILES_KEY, []);
  return Array.isArray(list) ? list.filter((p) => p && typeof p.business_id === "string") : [];
}

export function saveProfile(p: Profile) {
  const list = getProfiles().filter((x) => x.business_id !== p.business_id);
  write(PROFILES_KEY, [p, ...list]);
}

export function getActiveId(): string | null {
  const id = read<string | null>(ACTIVE_KEY, memoryActive);
  return typeof id === "string" && id ? id : null;
}

export function setActiveId(id: string) {
  memoryActive = id;
  write(ACTIVE_KEY, id);
}

export function getActiveProfile(): Profile | null {
  const id = getActiveId();
  if (!id) return null;
  return getProfiles().find((p) => p.business_id === id) ?? null;
}

export function newBusinessId(): string {
  const bytes = new Uint8Array(6);
  crypto.getRandomValues(bytes);
  return "biz_" + Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}
