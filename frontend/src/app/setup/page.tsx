"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { m } from "motion/react";
import { Check, ChevronRight, Store } from "lucide-react";
import { api } from "@/api/endpoints";
import { errorMessage } from "@/api/client";
import { Button } from "@/components/Button";
import { ErrorState } from "@/components/StateViews";
import { useToast } from "@/components/Toast";
import { isValidKenyanPhone } from "@/utils/format";
import { DEMO_BUSINESS_ID, getActiveId, getProfiles, newBusinessId, saveProfile, setActiveId, type Profile } from "@/utils/profile";

interface FormState {
  shop_name: string;
  owner_name: string;
  owner_phone: string;
  till_number: string;
}
const EMPTY: FormState = { shop_name: "", owner_name: "", owner_phone: "", till_number: "" };

export default function SetupPage() {
  const router = useRouter();
  const toast = useToast();
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [activeId, setActive] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY);
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({});
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

  function validate(f: FormState) {
    const e: typeof errors = {};
    if (!f.shop_name.trim()) e.shop_name = "Enter your shop name";
    if (!f.owner_name.trim()) e.owner_name = "Enter your name";
    if (!isValidKenyanPhone(f.owner_phone)) e.owner_phone = "Use a Safaricom number like 0712 345 678";
    if (f.till_number && !/^\d{5,7}$/.test(f.till_number.trim())) e.till_number = "Till number is 5 to 7 digits";
    return e;
  }

  async function onSubmit(ev: React.FormEvent) {
    ev.preventDefault();
    const e = validate(form);
    setErrors(e);
    if (Object.keys(e).length) return;
    setSaving(true);
    setServerError(null);
    const id = newBusinessId();
    try {
      const biz = await api.putBusiness(
        {
          shop_name: form.shop_name.trim(),
          owner_name: form.owner_name.trim(),
          owner_phone: form.owner_phone.replace(/[\s-]/g, ""),
          till_number: form.till_number.trim() || null,
        },
        id,
      );
      saveProfile({ business_id: biz.business_id, shop_name: biz.shop_name, owner_name: biz.owner_name });
      setActiveId(biz.business_id);
      toast("Shop saved");
      router.push("/import");
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

  const set = (k: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((f) => ({ ...f, [k]: e.target.value }));
    if (errors[k]) setErrors((x) => ({ ...x, [k]: undefined }));
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
            Your shops
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
              Add another shop
            </Button>
          )}
        </section>
      )}

      {serverError && <ErrorState message={serverError} />}

      {showForm && (
        <section aria-labelledby="new-shop">
          <h2 id="new-shop" className="mb-1 text-2xl">
            New shop
          </h2>
          <p className="mb-4 text-ink-soft">Takes one minute. You can change it later.</p>
          <form noValidate onSubmit={onSubmit} className="space-y-4">
            <Field label="Shop name" error={errors.shop_name}>
              <input className="field" value={form.shop_name} onChange={set("shop_name")} placeholder="Mama Mary Provisions" autoComplete="organization" maxLength={80} />
            </Field>
            <Field label="Your name" error={errors.owner_name}>
              <input className="field" value={form.owner_name} onChange={set("owner_name")} placeholder="Mary Wambui" autoComplete="name" maxLength={80} />
            </Field>
            <Field label="Phone (for weekly SMS)" error={errors.owner_phone}>
              <input className="field num" value={form.owner_phone} onChange={set("owner_phone")} placeholder="0712 345 678" inputMode="tel" autoComplete="tel" maxLength={16} />
            </Field>
            <Field label="M-Pesa till number (optional)" error={errors.till_number}>
              <input className="field num" value={form.till_number} onChange={set("till_number")} placeholder="789123" inputMode="numeric" maxLength={7} />
            </Field>
            <Button type="submit" size="lg" block loading={saving}>
              Save shop
            </Button>
          </form>
        </section>
      )}

      <section className="border-t-2 border-dashed border-rule pt-6">
        <p className="mb-3 text-ink-soft">Just looking? Open the demo shop and load the sample statement.</p>
        <Button variant="ghost" block onClick={openDemo} loading={demoLoading}>
          Open demo shop
        </Button>
      </section>
    </div>
  );
}

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactElement }) {
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
