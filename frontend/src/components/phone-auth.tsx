"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, getSession, requestPhoneOtp, verifyPhoneOtp } from "@/lib/api";

export function PhoneAuth({ intent }: { intent: "login" | "register" }) {
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [demoCode, setDemoCode] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const title = intent === "login" ? "Welcome back" : "Create your account";

  async function send(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const response = await requestPhoneOtp(phone, intent);
      setDemoCode(response.demo_code);
      setSent(true);
    } catch (reason) {
      setError(messageFor(reason));
    } finally {
      setBusy(false);
    }
  }

  async function verify(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await verifyPhoneOtp(phone, code, intent);
      if (result.is_new_user) {
        router.replace("/onboarding");
        return;
      }
      const session = await getSession();
      router.replace(session.name && session.date_of_birth && session.city ? "/services" : "/onboarding");
    } catch (reason) {
      setError(messageFor(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-slate-950 px-4 py-8">
      <section className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl sm:p-9">
        <Link className="text-sm font-bold text-teal-800" href="/">← Home</Link>
        <p className="mt-8 text-sm font-bold uppercase tracking-[0.16em] text-teal-700">Citizen Bridge</p>
        <h1 className="mt-2 text-3xl font-bold text-slate-950">{title}</h1>
        <p className="mt-3 text-sm leading-6 text-slate-600">Use your mobile number and a one-time password. No password to remember.</p>
        {error ? <p className="mt-5 rounded-xl bg-rose-50 p-3 text-sm text-rose-800" role="alert">{error}</p> : null}
        {!sent ? (
          <form className="mt-7" onSubmit={send}>
            <label className="text-sm font-bold text-slate-800" htmlFor="auth-phone">Mobile number</label>
            <div className="mt-2 flex rounded-xl border border-slate-300 focus-within:border-teal-600 focus-within:ring-2 focus-within:ring-teal-100"><span className="grid px-4 text-slate-500" style={{ placeItems: "center" }}>+91</span><input autoComplete="tel-national" className="min-w-0 flex-1 rounded-r-xl px-3 py-3.5 outline-none" id="auth-phone" inputMode="tel" onChange={(event) => setPhone(event.target.value)} placeholder="XXXXX XXXXX" required value={phone}/></div>
            <button className="mt-6 w-full rounded-xl bg-teal-700 px-5 py-3.5 font-bold text-white hover:bg-teal-800 disabled:opacity-60" disabled={busy} type="submit">{busy ? "Sending…" : "Send OTP"}</button>
          </form>
        ) : (
          <form className="mt-7" onSubmit={verify}>
            <p className="text-sm text-slate-600">Code sent to <strong>{phone}</strong>. <button className="font-bold text-teal-800" onClick={() => { setSent(false); setCode(""); setError(null); }} type="button">Change</button></p>
            {demoCode ? <p className="mt-4 rounded-xl bg-teal-50 p-3 text-sm text-teal-900" role="status">Demo OTP: <strong>{demoCode}</strong></p> : null}
            <label className="mt-5 block text-sm font-bold text-slate-800" htmlFor="auth-code">One-time password</label>
            <input autoComplete="one-time-code" className="mt-2 block w-full rounded-xl border border-slate-300 px-4 py-3.5 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100" id="auth-code" inputMode="numeric" maxLength={6} onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))} required value={code}/>
            <button className="mt-6 w-full rounded-xl bg-teal-700 px-5 py-3.5 font-bold text-white hover:bg-teal-800 disabled:opacity-60" disabled={busy || code.length !== 6} type="submit">{busy ? "Verifying…" : intent === "login" ? "Log in" : "Register"}</button>
          </form>
        )}
        <p className="mt-6 text-center text-sm text-slate-600">{intent === "login" ? "New to Citizen Bridge?" : "Already have an account?"} <Link className="font-bold text-teal-800" href={intent === "login" ? "/register" : "/login"}>{intent === "login" ? "Register" : "Log in"}</Link></p>
      </section>
    </main>
  );
}

function messageFor(reason: unknown) {
  return reason instanceof ApiError ? reason.message : "Something went wrong. Please try again.";
}
