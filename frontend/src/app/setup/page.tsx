"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { m } from "motion/react";
import { Check, ChevronRight, LogIn, Store, UserPlus } from "lucide-react";
import { api } from "@/api/endpoints";
import { errorMessage } from "@/api/client";
import { Button } from "@/components/Button";
import { ErrorState } from "@/components/StateViews";
import { useToast } from "@/components/Toast";
import { isValidKenyanPhone } from "@/utils/format";
import { DEMO_BUSINESS_ID, getActiveId, getProfiles, saveProfile, setActiveId, type Profile } from "@/utils/profile";

interface RegisterFormState {
  shop_name: string;
  owner_name: string;
  owner_phone: string;
  till_number: string;
  password: string;
}

interface LoginFormState {
  owner_phone: string;
  password: string;
}

const EMPTY_REGISTER: RegisterFormState = {
  shop_name: "",
  owner_name: "",
  owner_phone: "",
  till_number: "",
  password: "",
};

const EMPTY_LOGIN: LoginFormState = {
  owner_phone: "",
  password: "",
};

type AuthMode = "register" | "login";

export default function SetupPage() {
  const router = useRouter();
  const toast = useToast();
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [activeId, setActive] = useState<string | null>(null);
  const [authMode, setAuthMode] = useState<AuthMode>("register");
  const [regForm, setRegForm] = useState<RegisterFormState>(EMPTY_REGISTER);
  const [loginForm, setLoginForm] = useState<LoginFormState>(EMPTY_LOGIN);
  const [regErrors, setRegErrors] = useState<Partial<Record<keyof RegisterFormState, string>>>({});
  const [loginErrors, setLoginErrors] = useState<Partial<Record<keyof LoginFormState, string>>>({});
  const [saving, setSaving] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    const list = getProfiles();
    setProfiles(list);
    setActive(getActiveId());
    setShowForm(list.length === 0);
  }, []);

  function choose(p: Profile) {
    setActiveId(p.business_id);
    router.push("/dashboard");
  }

  function validateRegister(f: RegisterFormState) {
    const e: typeof regErrors = {};
    if (!f.shop_name.trim()) e.shop_name = "Enter your shop name";
    if (!f.owner_name.trim()) e.owner_name = "Enter your name";
    if (!isValidKenyanPhone(f.owner_phone)) e.owner_phone = "Use a Kenyan number like 0712 345 678";
    if (f.till_number && !/^\d{4,10}$/.test(f.till_number.trim())) e.till_number = "Till number is 4 to 10 digits";
    if (f.password.length < 6) e.password = "Password must be at least 6 characters";
    return e;
  }

  function validateLogin(f: LoginFormState) {
    const e: typeof loginErrors = {};
    if (!isValidKenyanPhone(f.owner_phone)) e.owner_phone = "Enter your registered phone number";
    if (!f.password) e.password = "Enter your password";
    return e;
  }

  async function onRegister(ev: React.FormEvent) {
    ev.preventDefault();
    const e = validateRegister(regForm);
    setRegErrors(e);
    if (Object.keys(e).length) return;
    setSaving(true);
    setServerError(null);
    try {
      const res = await api.registerAccount({
        shop_name: regForm.shop_name.trim(),
        owner_name: regForm.owner_name.trim(),
        owner_phone: regForm.owner_phone.replace(/[\s-]/g, ""),
        till_number: regForm.till_number.trim() || null,
        password: regForm.password,
      });
      const biz = res.business;
      try {
        window.localStorage.setItem("bs.token", res.token);
      } catch {
        /* ignore */
      }
      saveProfile({ business_id: biz.business_id, shop_name: biz.shop_name, owner_name: biz.owner_name });
      setActiveId(biz.business_id);
      toast("Account created & shop saved");
      router.push("/import");
    } catch (err) {
      setServerError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function onLogin(ev: React.FormEvent) {
    ev.preventDefault();
    const e = validateLogin(loginForm);
    setLoginErrors(e);
    if (Object.keys(e).length) return;
    setSaving(true);
    setServerError(null);
    try {
      const res = await api.loginAccount({
        owner_phone: loginForm.owner_phone.replace(/[\s-]/g, ""),
        password: loginForm.password,
      });
      const biz = res.business;
      try {
        window.localStorage.setItem("bs.token", res.token);
      } catch {
        /* ignore */
      }
      saveProfile({ business_id: biz.business_id, shop_name: biz.shop_name, owner_name: biz.owner_name });
      setActiveId(biz.business_id);
      toast(`Welcome back, ${biz.owner_name}`);
      router.push("/dashboard");
    } catch (err) {
      setServerError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function openDemo() {
    setDemoLoading(true);
    setServerError(null);
    try {
      const biz = await api.getBusiness(DEMO_BUSINESS_ID);
      saveProfile({ business_id: DEMO_BUSINESS_ID, shop_name: biz.shop_name, owner_name: biz.owner_name });
      setActiveId(DEMO_BUSINESS_ID);
      router.push("/dashboard");
    } catch (err) {
      setServerError(errorMessage(err));
    } finally {
      setDemoLoading(false);
    }
  }

  const setReg = (k: keyof RegisterFormState) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setRegForm((f) => ({ ...f, [k]: e.target.value }));
    if (regErrors[k]) setRegErrors((er) => ({ ...er, [k]: undefined }));
  };

  const setLogin = (k: keyof LoginFormState) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setLoginForm((f) => ({ ...f, [k]: e.target.value }));
    if (loginErrors[k]) setLoginErrors((er) => ({ ...er, [k]: undefined }));
  };

  return (
    <div className="space-y-8">
      <div className="rounded-sign border-3 border-ink bg-maize px-5 py-6 shadow-board">
        <p className="font-display text-xl font-extrabold">Biashara Score</p>
        <h1 className="mt-1 text-sign font-black">Welcome.</h1>
        <p className="mt-3 max-w-sm text-lg">See your real profit, track customer debts, and show lenders your shop is strong.</p>
      </div>

      {profiles.length > 0 && (
        <section aria-labelledby="your-shops">
          <h2 id="your-shops" className="mb-3 text-2xl">
            Your shops on this device
          </h2>
          <ul className="space-y-2">
            {profiles.map((p, i) => {
              const active = p.business_id === activeId;
              return (
                <m.li key={p.business_id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 6) * 0.04, duration: 0.2 }}>
                  <button
                    type="button"
                    onClick={() => choose(p)}
                    className={`flex min-h-[60px] w-full items-center gap-3 rounded-md border-2 px-4 py-3 text-left ${active ? "border-cobalt bg-cobalt-soft" : "border-ink bg-card hover:bg-paper"}`}
                  >
                    <Store aria-hidden className="h-6 w-6 shrink-0" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-bold">{p.shop_name}</span>
                      <span className="block truncate text-sm text-ink-soft">{p.owner_name}</span>
                    </span>
                    {active ? <Check aria-label="Open now" className="h-6 w-6 text-cobalt" /> : <ChevronRight aria-hidden className="h-6 w-6 text-ink-soft" />}
                  </button>
                </m.li>
              );
            })}
          </ul>
          {!showForm && (
            <Button variant="secondary" block className="mt-3" onClick={() => setShowForm(true)}>
              Sign in or create another shop
            </Button>
          )}
        </section>
      )}

      {serverError && <ErrorState message={serverError} />}

      {showForm && (
        <section aria-label="Shop account">
          <div role="tablist" className="mb-5 grid grid-cols-2 gap-1 rounded-md border-2 border-ink bg-card p-1">
            <button
              type="button"
              role="tab"
              aria-selected={authMode === "register"}
              onClick={() => {
                setAuthMode("register");
                setServerError(null);
              }}
              className={`flex min-h-[44px] items-center justify-center gap-2 rounded-sm font-bold transition-colors ${authMode === "register" ? "bg-maize text-ink" : "text-ink-soft"}`}
            >
              <UserPlus aria-hidden className="h-4 w-4" />
              Create shop
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={authMode === "login"}
              onClick={() => {
                setAuthMode("login");
                setServerError(null);
              }}
              className={`flex min-h-[44px] items-center justify-center gap-2 rounded-sm font-bold transition-colors ${authMode === "login" ? "bg-maize text-ink" : "text-ink-soft"}`}
            >
              <LogIn aria-hidden className="h-4 w-4" />
              Sign in
            </button>
          </div>

          {authMode === "register" ? (
            <form noValidate onSubmit={onRegister} className="space-y-4">
              <Field label="Shop name" error={regErrors.shop_name}>
                <input className="field" value={regForm.shop_name} onChange={setReg("shop_name")} placeholder="Geomin Routers" autoComplete="organization" maxLength={80} />
              </Field>
              <Field label="Your name" error={regErrors.owner_name}>
                <input className="field" value={regForm.owner_name} onChange={setReg("owner_name")} placeholder="John Doe" autoComplete="name" maxLength={80} />
              </Field>
              <Field label="Phone number (used to sign in)" error={regErrors.owner_phone}>
                <input className="field num" value={regForm.owner_phone} onChange={setReg("owner_phone")} placeholder="0712 345 678" inputMode="tel" autoComplete="tel" maxLength={16} />
              </Field>
              <Field label="Password (min 6 characters)" error={regErrors.password}>
                <input className="field" type="password" value={regForm.password} onChange={setReg("password")} placeholder="Create a password" autoComplete="new-password" maxLength={72} />
              </Field>
              <Field label="M-Pesa till number (optional)" error={regErrors.till_number}>
                <input className="field num" value={regForm.till_number} onChange={setReg("till_number")} placeholder="789123" inputMode="numeric" maxLength={10} />
              </Field>
              <Button type="submit" size="lg" block loading={saving}>
                Create account &amp; save shop
              </Button>
            </form>
          ) : (
            <form noValidate onSubmit={onLogin} className="space-y-4">
              <Field label="Registered phone number" error={loginErrors.owner_phone}>
                <input className="field num" value={loginForm.owner_phone} onChange={setLogin("owner_phone")} placeholder="0712 345 678" inputMode="tel" autoComplete="tel" maxLength={16} />
              </Field>
              <Field label="Password" error={loginErrors.password}>
                <input className="field" type="password" value={loginForm.password} onChange={setLogin("password")} placeholder="Enter your password" autoComplete="current-password" maxLength={72} />
              </Field>
              <Button type="submit" size="lg" block loading={saving}>
                Sign in to my shop
              </Button>
            </form>
          )}
        </section>
      )}

      <section className="border-t-2 border-dashed border-rule pt-6">
        <p className="mb-3 text-ink-soft">Just looking? Open the demo shop and load the sample statement.</p>
        <Button variant="ghost" block loading={demoLoading} onClick={openDemo}>
          Open demo shop (Geomin Routers)
        </Button>
      </section>
    </div>
  );
}

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {children}
      {error && (
        <span role="alert" className="mt-1 block text-sm font-bold text-chili">
          {error}
        </span>
      )}
    </label>
  );
}
