"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, getSession, register, updateProfile } from "@/lib/api";
import { InlineFieldError } from "@/components/page-state";

const STORAGE_KEY = "citizen-bridge:onboarding";
const MOCK_OTP = "123456";
type Step = 0 | 1 | 2 | 3;

interface SavedProgress {
  step: Step;
  phone: string;
  verified: boolean;
}

export function OnboardingFlow() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [step, setStep] = useState<Step>(0);
  const [phone, setPhone] = useState("");
  const [verified, setVerified] = useState(false);
  const [otpSent, setOtpSent] = useState(false);
  const [otp, setOtp] = useState("");
  const [cooldown, setCooldown] = useState(0);
  const [profile, setProfile] = useState({ name: "", dateOfBirth: "", city: "Bengaluru" });
  const [aadhaar, setAadhaar] = useState("");
  const [aadhaarLinked, setAadhaarLinked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getSession(controller.signal)
      .then((session) => {
        if (profileComplete(session)) {
          router.replace("/");
          return;
        }
        const saved = readProgress();
        setStep(saved && saved.step >= 2 ? saved.step : 2);
        setPhone(saved?.phone ?? session.phone ?? "");
        setVerified(true);
        setReady(true);
      })
      .catch((reason: unknown) => {
        if (reason instanceof Error && reason.name === "AbortError") return;
        const saved = readProgress();
        if (saved) {
          setStep(saved.step);
          setPhone(saved.phone);
          setVerified(saved.verified);
        }
        setReady(true);
      });
    return () => controller.abort();
  }, [router]);

  useEffect(() => {
    if (!ready) return;
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ step, phone, verified }));
  }, [phone, ready, step, verified]);

  useEffect(() => {
    if (cooldown === 0) return;
    const timer = window.setInterval(() => setCooldown((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [cooldown]);

  if (!ready) {
    return (
      <main className="grid min-h-screen place-items-center bg-slate-950 px-5 text-white">
        <p role="status">Checking your secure session…</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 px-4 py-6 sm:grid sm:place-items-center sm:px-8">
      <section className="mx-auto w-full max-w-xl overflow-hidden rounded-3xl bg-white shadow-2xl shadow-black/25">
        <header className="border-b border-slate-100 px-6 py-5 sm:px-9">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 font-bold text-slate-950">
              <span className="grid size-10 place-items-center rounded-xl bg-teal-600 text-sm text-white">
                CB
              </span>
              Citizen Bridge
            </div>
            <span className="text-sm font-semibold text-slate-500">Step {step + 1} of 4</span>
          </div>
          <div
            aria-label={`Onboarding progress: step ${step + 1} of 4`}
            aria-valuemax={4}
            aria-valuemin={1}
            aria-valuenow={step + 1}
            className="mt-5 grid grid-cols-4 gap-2"
            role="progressbar"
          >
            {[0, 1, 2, 3].map((item) => (
              <span
                className={`h-1.5 rounded-full ${item <= step ? "bg-teal-600" : "bg-slate-200"}`}
                key={item}
              />
            ))}
          </div>
        </header>

        <div className="px-6 py-8 sm:px-9 sm:py-10">
          {error && !error.includes("10-digit") && !error.includes("12-digit") ? (
            <p className="mb-5 rounded-xl bg-rose-50 p-3 text-sm text-rose-800" role="alert">
              {error}
            </p>
          ) : null}
          {step === 0 ? <Welcome onContinue={() => setStep(1)} /> : null}
          {step === 1 ? (
            <PhoneStep
              cooldown={cooldown}
              onBack={() => setStep(0)}
              onOtpChange={setOtp}
              onSend={() => {
                setError(null);
                if (!validPhone(phone)) {
                  setError("Enter a valid 10-digit Indian mobile number.");
                  return;
                }
                setOtpSent(true);
                setCooldown(30);
              }}
              onVerify={() => {
                setError(null);
                if (otp !== MOCK_OTP) {
                  setError("Invalid OTP. Try again.");
                  return;
                }
                setBusy(true);
                const digits = phoneDigits(phone);
                void register({
                  username: `phone_${digits}`,
                  password: `CB!${crypto.randomUUID()}`,
                  phone: `+91${digits}`,
                })
                  .then(() => {
                    setVerified(true);
                    setStep(2);
                  })
                  .catch((reason: unknown) => setError(messageFor(reason)))
                  .finally(() => setBusy(false));
              }}
              otp={otp}
              otpSent={otpSent}
              phone={phone}
              phoneError={error?.includes("10-digit") ? error : null}
              setPhone={setPhone}
              verifying={busy}
            />
          ) : null}
          {step === 2 ? (
            <ProfileStep
              busy={busy}
              onBack={() => setStep(1)}
              onSubmit={async (event) => {
                event.preventDefault();
                setBusy(true);
                setError(null);
                try {
                  await updateProfile({
                    name: profile.name,
                    date_of_birth: profile.dateOfBirth,
                    city: profile.city,
                    state: "Karnataka",
                  });
                  setStep(3);
                } catch (reason) {
                  setError(messageFor(reason));
                } finally {
                  setBusy(false);
                }
              }}
              profile={profile}
              setProfile={setProfile}
            />
          ) : null}
          {step === 3 ? (
            <AadhaarStep
              aadhaar={aadhaar}
              aadhaarError={error?.includes("12-digit") ? error : null}
              linked={aadhaarLinked}
              onAadhaarChange={setAadhaar}
              onBack={() => setStep(2)}
              onFinish={() => {
                localStorage.removeItem(STORAGE_KEY);
                router.replace("/");
              }}
              onLink={() => {
                setError(null);
                if (!/^\d{12}$/.test(aadhaar.replace(/\s/g, ""))) {
                  setError("Enter a valid 12-digit Aadhaar number.");
                  return;
                }
                setAadhaarLinked(true);
                setAadhaar("");
              }}
            />
          ) : null}
        </div>
      </section>
    </main>
  );
}

function Welcome({ onContinue }: { onContinue: () => void }) {
  return (
    <div>
      <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-700">Welcome</p>
      <h1 className="mt-3 text-4xl font-bold tracking-tight text-slate-950">
        Government services, made clearer
      </h1>
      <p className="mt-5 text-lg leading-8 text-slate-600">
        Citizen Bridge helps you navigate government services without the confusion.
      </p>
      <PrimaryButton onClick={onContinue}>Get Started</PrimaryButton>
    </div>
  );
}

function PhoneStep(props: {
  phone: string;
  phoneError: string | null;
  setPhone: (value: string) => void;
  otp: string;
  onOtpChange: (value: string) => void;
  otpSent: boolean;
  cooldown: number;
  onSend: () => void;
  onVerify: () => void;
  onBack: () => void;
  verifying: boolean;
}) {
  return (
    <div>
      <Eyebrow>Secure your account</Eyebrow>
      <h1 className="mt-2 text-3xl font-bold text-slate-950">Verify your phone</h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">
        We’ll use your number only for secure access and important service updates.
      </p>
      <label className="mt-6 block text-sm font-bold text-slate-800" htmlFor="phone">
        Mobile number
      </label>
      <div className={`mt-2 flex rounded-xl border bg-white focus-within:ring-2 ${props.phoneError ? "border-rose-500 focus-within:ring-rose-100" : "border-slate-300 focus-within:border-teal-600 focus-within:ring-teal-100"}`}>
        <span className="grid px-4 text-slate-500" style={{ placeItems: "center" }}>+91</span>
        <input
          aria-describedby={props.phoneError ? "phone-error" : undefined}
          aria-invalid={Boolean(props.phoneError)}
          autoComplete="tel-national"
          className="min-w-0 flex-1 rounded-r-xl px-3 py-3.5 outline-none"
          id="phone"
          inputMode="tel"
          onChange={(event) => props.setPhone(event.target.value)}
          placeholder="XXXXX XXXXX"
          value={props.phone}
        />
      </div>
      {props.phoneError ? <InlineFieldError id="phone-error">Please enter a valid 10-digit phone number.</InlineFieldError> : null}
      {!props.otpSent ? (
        <PrimaryButton onClick={props.onSend}>Send OTP</PrimaryButton>
      ) : (
        <>
          <p className="mt-4 rounded-xl bg-teal-50 p-3 text-sm text-teal-900" role="status">
            Demo OTP sent. Use <strong>{MOCK_OTP}</strong>.
          </p>
          <label className="mt-5 block text-sm font-bold text-slate-800" htmlFor="otp">
            One-time password
          </label>
          <input
            autoComplete="one-time-code"
            className={inputClass}
            id="otp"
            inputMode="numeric"
            maxLength={6}
            onChange={(event) => props.onOtpChange(event.target.value.replace(/\D/g, ""))}
            value={props.otp}
          />
          <PrimaryButton disabled={props.verifying} onClick={props.onVerify}>
            {props.verifying ? "Creating account…" : "Verify and continue"}
          </PrimaryButton>
          <button
            className="mt-4 text-sm font-bold text-teal-800 disabled:text-slate-400"
            disabled={props.cooldown > 0}
            onClick={props.onSend}
            type="button"
          >
            {props.cooldown > 0 ? `Resend OTP in ${props.cooldown}s` : "Resend OTP"}
          </button>
        </>
      )}
      <BackButton onClick={props.onBack} />
    </div>
  );
}

function ProfileStep(props: {
  profile: { name: string; dateOfBirth: string; city: string };
  setProfile: (value: { name: string; dateOfBirth: string; city: string }) => void;
  busy: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onBack: () => void;
}) {
  return (
    <form onSubmit={props.onSubmit}>
      <Eyebrow>Almost there</Eyebrow>
      <h1 className="mt-2 text-3xl font-bold text-slate-950">Tell us the basics</h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">
        This helps us match age-based eligibility and local service rules.
      </p>
      <label className={labelClass} htmlFor="full-name">Full name</label>
      <input className={inputClass} id="full-name" onChange={(event) => props.setProfile({ ...props.profile, name: event.target.value })} required value={props.profile.name} />
      <label className={labelClass} htmlFor="date-of-birth">Date of birth</label>
      <input className={inputClass} id="date-of-birth" max={new Date().toISOString().slice(0, 10)} onChange={(event) => props.setProfile({ ...props.profile, dateOfBirth: event.target.value })} required type="date" value={props.profile.dateOfBirth} />
      <label className={labelClass} htmlFor="city">City / District</label>
      <input className={inputClass} id="city" onChange={(event) => props.setProfile({ ...props.profile, city: event.target.value })} required value={props.profile.city} />
      <PrimaryButton disabled={props.busy} type="submit">{props.busy ? "Saving…" : "Continue"}</PrimaryButton>
      <BackButton onClick={props.onBack} />
    </form>
  );
}

function AadhaarStep(props: {
  aadhaar: string;
  aadhaarError: string | null;
  linked: boolean;
  onAadhaarChange: (value: string) => void;
  onLink: () => void;
  onFinish: () => void;
  onBack: () => void;
}) {
  return (
    <div>
      <Eyebrow>You’re all set</Eyebrow>
      <h1 className="mt-2 text-3xl font-bold text-slate-950">
        Link Aadhaar for faster matching
      </h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">
        This optional step helps us find benefits you’re eligible for. Linking is simulated in this
        MVP and the number is not stored.
      </p>
      {props.linked ? (
        <p className="mt-6 rounded-xl bg-emerald-50 p-4 text-sm font-semibold text-emerald-900" role="status">
          Aadhaar marked as linked for this onboarding session.
        </p>
      ) : (
        <>
          <label className={labelClass} htmlFor="aadhaar">Aadhaar number</label>
          <input aria-describedby={props.aadhaarError ? "aadhaar-error" : undefined} aria-invalid={Boolean(props.aadhaarError)} className={`${inputClass} ${props.aadhaarError ? "border-rose-500 focus:border-rose-500 focus:ring-rose-100" : ""}`} id="aadhaar" inputMode="numeric" maxLength={14} onChange={(event) => props.onAadhaarChange(event.target.value)} placeholder="XXXX XXXX XXXX" value={props.aadhaar} />
          {props.aadhaarError ? <InlineFieldError id="aadhaar-error">Please enter a valid 12-digit Aadhaar number.</InlineFieldError> : null}
          <PrimaryButton onClick={props.onLink}>Link Aadhaar</PrimaryButton>
        </>
      )}
      <button className="mt-4 w-full rounded-xl px-5 py-3 font-bold text-teal-800 hover:bg-teal-50" onClick={props.onFinish} type="button">
        {props.linked ? "Continue to My Services" : "Skip for now"}
      </button>
      <BackButton onClick={props.onBack} />
    </div>
  );
}

function PrimaryButton({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className="mt-6 w-full rounded-xl bg-teal-700 px-5 py-3.5 font-bold text-white shadow-sm hover:bg-teal-800 disabled:opacity-50" type="button" {...props}>{children}</button>;
}

function BackButton({ onClick }: { onClick: () => void }) {
  return <button className="mt-4 w-full py-2 text-sm font-semibold text-slate-500 hover:text-slate-800" onClick={onClick} type="button">Back</button>;
}

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-700">{children}</p>;
}

const inputClass = "mt-2 block w-full rounded-xl border border-slate-300 px-4 py-3.5 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100";
const labelClass = "mt-5 block text-sm font-bold text-slate-800";

function phoneDigits(value: string) {
  const digits = value.replace(/\D/g, "");
  return digits.startsWith("91") && digits.length === 12 ? digits.slice(2) : digits;
}

function validPhone(value: string) {
  return /^[6-9]\d{9}$/.test(phoneDigits(value));
}

function readProgress(): SavedProgress | null {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null") as SavedProgress | null;
    return value && [0, 1, 2, 3].includes(value.step) ? value : null;
  } catch {
    return null;
  }
}

function messageFor(reason: unknown) {
  return reason instanceof ApiError ? reason.message : "Something unexpected went wrong.";
}

function profileComplete(session: {
  name: string | null;
  date_of_birth?: string | null;
  city?: string | null;
}) {
  return Boolean(session.name && session.date_of_birth && session.city);
}
