"use client";

import Image from "next/image";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ErrorState, InlineFieldError, LoadingState } from "@/components/page-state";
import { ApiError, getSession, updateProfile } from "@/lib/api";

export function OnboardingFlow() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [step, setStep] = useState<0 | 1>(0);
  const [profile, setProfile] = useState({ name: "", dateOfBirth: "", city: "Bengaluru" });
  const [aadhaar, setAadhaar] = useState("");
  const [aadhaarLinked, setAadhaarLinked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getSession(controller.signal)
      .then((session) => {
        if (session.name && session.date_of_birth && session.city) {
          router.replace("/services");
          return;
        }
        setProfile({
          name: session.name ?? "",
          dateOfBirth: session.date_of_birth ?? "",
          city: session.city ?? "Bengaluru",
        });
        setReady(true);
      })
      .catch((reason: unknown) => {
        if (reason instanceof Error && reason.name === "AbortError") return;
        if (reason instanceof ApiError && reason.status === 401) {
          router.replace("/");
          return;
        }
        setError(reason instanceof ApiError ? reason.message : "Could not load onboarding.");
        setReady(true);
      });
    return () => controller.abort();
  }, [router]);

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await updateProfile({ name: profile.name, date_of_birth: profile.dateOfBirth, city: profile.city, state: "Karnataka" });
      setStep(1);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Could not save your profile.");
    } finally {
      setBusy(false);
    }
  }

  if (!ready) return <LoadingState label="Checking your secure session…" />;
  if (error && step === 0 && !profile.name) return <ErrorState message={error} onRetry={() => location.reload()} />;

  return (
    <main className="min-h-screen bg-slate-950 px-4 py-6 sm:grid sm:place-items-center sm:px-8">
      <section className="mx-auto w-full max-w-xl overflow-hidden rounded-3xl bg-white shadow-2xl shadow-black/25">
        <header className="border-b border-slate-100 px-6 py-5 sm:px-9">
          <div className="flex items-center justify-between gap-4"><div className="flex items-center gap-3"><span className="grid size-10 place-items-center rounded-xl bg-teal-600 text-sm font-bold text-white">CB</span><Image alt="JanSetu" className="h-8 w-auto" height={32} priority src="/citizen-bridge-logo.png" width={96} /></div><span className="text-sm font-semibold text-slate-500">Step {step + 1} of 2</span></div>
          <div aria-label={`Onboarding progress: step ${step + 1} of 2`} aria-valuemax={2} aria-valuemin={1} aria-valuenow={step + 1} className="mt-5 grid grid-cols-2 gap-2" role="progressbar"><span className="h-1.5 rounded-full bg-teal-600"/><span className={`h-1.5 rounded-full ${step === 1 ? "bg-teal-600" : "bg-slate-200"}`}/></div>
        </header>
        <div className="px-6 py-8 sm:px-9 sm:py-10">
          {error ? <p className="mb-5 rounded-xl bg-rose-50 p-3 text-sm text-rose-800" role="alert">{error}</p> : null}
          {step === 0 ? <form onSubmit={saveProfile}><p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-700">Complete your profile</p><h1 className="mt-2 text-3xl font-bold text-slate-950">Tell us the basics</h1><p className="mt-3 text-sm leading-6 text-slate-600">We use these details to match services and avoid asking the same questions again.</p><Field label="Full name" onChange={(value) => setProfile({ ...profile, name: value })} required value={profile.name}/><Field label="Date of birth" onChange={(value) => setProfile({ ...profile, dateOfBirth: value })} required type="date" value={profile.dateOfBirth}/><Field label="City / District" onChange={(value) => setProfile({ ...profile, city: value })} required value={profile.city}/><button className="mt-6 w-full rounded-xl bg-teal-700 px-5 py-3.5 font-bold text-white hover:bg-teal-800 disabled:opacity-60" disabled={busy} type="submit">{busy ? "Saving…" : "Continue"}</button></form> : <div><p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-700">Optional</p><h1 className="mt-2 text-3xl font-bold text-slate-950">Link Aadhaar for faster matching</h1><p className="mt-3 text-sm leading-6 text-slate-600">This simulated MVP step helps match benefits. The number is not stored.</p>{aadhaarLinked ? <p className="mt-6 rounded-xl bg-emerald-50 p-4 text-sm font-semibold text-emerald-900" role="status">Aadhaar marked as linked for this session.</p> : <><Field label="Aadhaar number" onChange={setAadhaar} type="text" value={aadhaar}/>{error?.includes("12-digit") ? <InlineFieldError id="aadhaar-error">Please enter a valid 12-digit Aadhaar number.</InlineFieldError> : null}<button className="mt-6 w-full rounded-xl bg-teal-700 px-5 py-3.5 font-bold text-white" onClick={() => { setError(null); if (!/^\d{12}$/.test(aadhaar.replace(/\s/g, ""))) { setError("Please enter a valid 12-digit Aadhaar number."); return; } setAadhaarLinked(true); }} type="button">Link Aadhaar</button></>}<button className="mt-4 w-full rounded-xl px-5 py-3 font-bold text-teal-800 hover:bg-teal-50" onClick={() => router.replace("/services")} type="button">{aadhaarLinked ? "Continue to My Services" : "Skip for now"}</button><button className="mt-3 w-full py-2 text-sm font-semibold text-slate-500" onClick={() => setStep(0)} type="button">Back</button></div>}
        </div>
      </section>
    </main>
  );
}

function Field({ label, onChange, type = "text", value, required = false }: { label: string; onChange: (value: string) => void; type?: string; value: string; required?: boolean }) {
  const id = label.toLocaleLowerCase().replaceAll(/[^a-z]+/g, "-");
  return <><label className="mt-5 block text-sm font-bold text-slate-800" htmlFor={id}>{label}</label><input className="mt-2 block w-full rounded-xl border border-slate-300 px-4 py-3.5 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100" id={id} onChange={(event) => onChange(event.target.value)} required={required} type={type} value={value}/></>;
}
