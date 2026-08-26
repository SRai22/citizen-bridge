"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { ErrorState, LoadingState } from "@/components/page-state";
import { ApiError, getSession, updateProfile } from "@/lib/api";
import type { AuthSession } from "@/types/api";

export default function ProfilePage() {
  const [profile, setProfile] = useState<AuthSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getSession(controller.signal)
      .then(setProfile)
      .catch((reason: unknown) => {
        if (reason instanceof Error && reason.name === "AbortError") return;
        setError(reason instanceof ApiError ? reason.message : "Could not load your profile.");
      });
    return () => controller.abort();
  }, [attempt]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const updated = await updateProfile({
        name: String(values.get("name")),
        date_of_birth: String(values.get("date_of_birth")),
        city: String(values.get("city")),
        state: String(values.get("state")),
        phone: String(values.get("phone")) || undefined,
      });
      setProfile(updated);
      setSaved(true);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Could not save your profile.");
    } finally {
      setBusy(false);
    }
  }

  if (error && !profile) return <ErrorState message={error} onRetry={() => { setError(null); setAttempt((value) => value + 1); }} />;
  if (!profile) return <LoadingState label="Loading your profile…" />;

  return (
    <div className="mx-auto max-w-3xl py-2 sm:py-3">
      <Link className="text-sm font-bold text-teal-800 hover:text-teal-950" href="/services">← Back to My Services</Link>
      <section className="mt-5 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-700">Your account</p>
        <h1 className="mt-2 text-3xl font-bold text-slate-950 sm:text-4xl">My Profile</h1>
        <p className="mt-3 text-sm text-slate-600">Keep your basic details current so services can reuse them.</p>
        {error ? <p className="mt-5 rounded-xl bg-rose-50 p-3 text-sm text-rose-800" role="alert">{error}</p> : null}
        {saved ? <p className="mt-5 rounded-xl bg-emerald-50 p-3 text-sm font-semibold text-emerald-800" role="status">Profile saved.</p> : null}
        <form className="mt-7 grid gap-5 sm:grid-cols-2" onSubmit={save}>
          <Field defaultValue={profile.name ?? ""} label="Full name" name="name" required />
          <Field defaultValue={profile.date_of_birth ?? ""} label="Date of birth" name="date_of_birth" required type="date" />
          <Field defaultValue={profile.city ?? ""} label="City / District" name="city" required />
          <Field defaultValue={profile.state ?? "Karnataka"} label="State" name="state" required />
          <Field defaultValue={profile.phone ?? ""} label="Phone number" name="phone" type="tel" />
          <button className="self-end rounded-xl bg-teal-700 px-5 py-3 text-sm font-bold text-white hover:bg-teal-800 disabled:opacity-60" disabled={busy} type="submit">{busy ? "Saving…" : "Save profile"}</button>
        </form>
        <Link className="mt-7 inline-block text-sm font-bold text-teal-800 hover:underline" href="/settings/data-controls">Privacy and data controls →</Link>
      </section>
    </div>
  );
}

function Field({ label, name, ...input }: { label: string; name: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return <label className="text-sm font-semibold text-slate-700">{label}<input className="mt-1 block w-full rounded-xl border border-slate-300 px-3 py-2.5 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100" name={name} {...input} /></label>;
}
