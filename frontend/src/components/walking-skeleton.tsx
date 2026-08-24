"use client";

import { FormEvent, useEffect, useState } from "react";

import { IntakeChat } from "@/components/intake-chat";
import {
  ApiError,
  getCategories,
  getSession,
  login,
  register,
  type RegistrationInput,
} from "@/lib/api";
import type { LifeEventCategory } from "@/types/api";

type Stage = "checking" | "auth" | "catalog" | "intake";

const initialRegistration: RegistrationInput = {
  username: "",
  password: "",
  name: "",
  date_of_birth: "",
  city: "Bengaluru",
  state: "Karnataka",
};

export function WalkingSkeleton() {
  const [stage, setStage] = useState<Stage>("checking");
  const [mode, setMode] = useState<"register" | "login">("register");
  const [registration, setRegistration] = useState(initialRegistration);
  const [credentials, setCredentials] = useState({ username: "", password: "" });
  const [categories, setCategories] = useState<LifeEventCategory[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getSession(controller.signal)
      .then(loadCatalog)
      .catch((reason: unknown) => {
        if (reason instanceof Error && reason.name === "AbortError") return;
        setStage("auth");
      });
    return () => controller.abort();
  }, []);

  async function loadCatalog() {
    const response = await getCategories();
    setCategories(response.categories);
    setStage("catalog");
  }

  async function handleRegister(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await register(registration);
      setCredentials({ username: registration.username, password: "" });
      setNotice("Account created. Sign in to continue.");
      setMode("login");
    } catch (reason) {
      setError(messageFor(reason));
    } finally {
      setBusy(false);
    }
  }

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(credentials.username, credentials.password);
      await loadCatalog();
    } catch (reason) {
      setError(messageFor(reason));
    } finally {
      setBusy(false);
    }
  }

  if (stage === "checking") {
    return <p className="p-10 text-center text-sm text-slate-500" role="status">Checking your session…</p>;
  }
  if (stage === "intake") return <IntakeChat />;
  if (stage === "catalog") {
    return (
      <section className="p-6 sm:p-9" aria-labelledby="catalog-heading">
        <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-700">Life events</p>
        <h1 className="mt-2 text-3xl font-bold" id="catalog-heading">How can we help?</h1>
        <p className="mt-2 text-sm text-slate-600">Choose what changed and we’ll build one clear plan.</p>
        <div className="mt-7 grid gap-4">
          {categories.map((category) => (
            <button
              className="rounded-2xl border border-stone-200 p-5 text-left transition hover:border-teal-500 hover:bg-teal-50"
              key={category.id}
              onClick={() => setStage("intake")}
              type="button"
            >
              <span className="block text-lg font-bold text-slate-950">{category.title}</span>
              <span className="mt-1 block text-sm leading-6 text-slate-600">{category.description}</span>
            </button>
          ))}
        </div>
      </section>
    );
  }

  const inputClass = "rounded-xl border border-stone-300 px-4 py-3 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100";
  return (
    <section className="p-6 sm:p-9" aria-labelledby="auth-heading">
      <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-700">Secure access</p>
      <h1 className="mt-2 text-3xl font-bold" id="auth-heading">
        {mode === "register" ? "Create your account" : "Sign in"}
      </h1>
      {notice ? <p className="mt-4 rounded-xl bg-teal-50 p-3 text-sm text-teal-900" role="status">{notice}</p> : null}
      {error ? <p className="mt-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-800" role="alert">{error}</p> : null}
      {mode === "register" ? (
        <form className="mt-6 grid gap-4 sm:grid-cols-2" onSubmit={handleRegister}>
          <input aria-label="Full name" className={inputClass} onChange={(event) => setRegistration({ ...registration, name: event.target.value })} placeholder="Full name" required value={registration.name} />
          <input aria-label="Username" className={inputClass} minLength={3} onChange={(event) => setRegistration({ ...registration, username: event.target.value })} placeholder="Username" required value={registration.username} />
          <input aria-label="Date of birth" className={inputClass} onChange={(event) => setRegistration({ ...registration, date_of_birth: event.target.value })} required type="date" value={registration.date_of_birth} />
          <input aria-label="City" className={inputClass} onChange={(event) => setRegistration({ ...registration, city: event.target.value })} placeholder="City" required value={registration.city} />
          <input aria-label="State" className={inputClass} onChange={(event) => setRegistration({ ...registration, state: event.target.value })} placeholder="State" value={registration.state} />
          <input aria-label="Password" className={inputClass} minLength={8} onChange={(event) => setRegistration({ ...registration, password: event.target.value })} placeholder="Password" required type="password" value={registration.password} />
          <button className="rounded-xl bg-teal-800 px-5 py-3 font-bold text-white disabled:opacity-50 sm:col-span-2" disabled={busy} type="submit">{busy ? "Creating…" : "Create account"}</button>
        </form>
      ) : (
        <form className="mt-6 grid gap-4" onSubmit={handleLogin}>
          <input aria-label="Username" className={inputClass} onChange={(event) => setCredentials({ ...credentials, username: event.target.value })} required value={credentials.username} />
          <input aria-label="Password" className={inputClass} onChange={(event) => setCredentials({ ...credentials, password: event.target.value })} required type="password" value={credentials.password} />
          <button className="rounded-xl bg-teal-800 px-5 py-3 font-bold text-white disabled:opacity-50" disabled={busy} type="submit">{busy ? "Signing in…" : "Sign in"}</button>
        </form>
      )}
      <button
        className="mt-5 text-sm font-bold text-teal-800 underline-offset-4 hover:underline"
        onClick={() => { setError(null); setNotice(null); setMode(mode === "register" ? "login" : "register"); }}
        type="button"
      >
        {mode === "register" ? "Already registered? Sign in" : "Need an account? Register"}
      </button>
    </section>
  );
}

function messageFor(reason: unknown) {
  return reason instanceof ApiError ? reason.message : "Something unexpected went wrong.";
}
