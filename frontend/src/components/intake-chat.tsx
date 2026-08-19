"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { ProfileSummary } from "@/components/profile-summary";
import { ApiError, confirmIntake, sendIntakeMessage, startIntake } from "@/lib/api";
import type { IntakeHouseholdProfile } from "@/types/api";

interface ChatMessage {
  id: number;
  role: "user" | "system";
  content: string;
}

export function IntakeChat() {
  const router = useRouter();
  const nextMessageId = useRef(0);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [profile, setProfile] = useState<IntakeHouseholdProfile | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [starting, setStarting] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    startIntake(controller.signal)
      .then((response) => {
        setSessionId(response.session_id);
        setMessages([
          { id: nextMessageId.current++, role: "system", content: response.message },
        ]);
        setStarting(false);
      })
      .catch((reason: unknown) => {
        if (reason instanceof Error && reason.name === "AbortError") return;
        setError(messageFor(reason));
        setStarting(false);
      });
    return () => controller.abort();
  }, [attempt]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = message.trim();
    if (!content || !sessionId || busy) return;

    const userMessage = { id: nextMessageId.current++, role: "user" as const, content };
    setMessages((current) => [...current, userMessage]);
    setMessage("");
    setError(null);
    setBusy(true);
    try {
      const response = await sendIntakeMessage(sessionId, content);
      const systemMessage = {
        id: nextMessageId.current++,
        role: "system" as const,
        content: response.message,
      };
      setMessages((current) => [...current, systemMessage]);
      setProfile(response.profile);
    } catch (reason) {
      setMessages((current) => current.filter(({ id }) => id !== userMessage.id));
      setMessage(content);
      setError(messageFor(reason));
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirm() {
    if (!sessionId || busy) return;
    setError(null);
    setBusy(true);
    try {
      const confirmation = await confirmIntake(sessionId);
      router.push(`/case/${encodeURIComponent(confirmation.case_id)}`);
    } catch (reason) {
      setError(messageFor(reason));
      setBusy(false);
    }
  }

  if (profile) {
    return (
      <ProfileSummary
        busy={busy}
        error={error}
        onClarify={() => {
          setError(null);
          setProfile(null);
        }}
        onConfirm={handleConfirm}
        profile={profile}
      />
    );
  }

  return (
    <section aria-labelledby="intake-heading" className="flex min-h-[36rem] flex-col">
      <div className="border-b border-stone-200 px-5 py-6 sm:px-8">
        <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-700">
          A few questions to get started
        </p>
        <h1 id="intake-heading" className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">
          Tell us what your family needs
        </h1>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Take your time. Your answers help us find the right Karnataka services and next steps.
        </p>
      </div>

      <div
        aria-live="polite"
        className="flex flex-1 flex-col gap-4 overflow-y-auto bg-stone-50/70 p-5 sm:p-8"
        role="log"
      >
        {starting ? (
          <p className="text-sm text-slate-500" role="status">
            Starting a private conversation…
          </p>
        ) : null}
        {messages.map((chatMessage) => (
          <div
            className={`flex ${chatMessage.role === "user" ? "justify-end" : "justify-start"}`}
            key={chatMessage.id}
          >
            <p
              className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm sm:max-w-[70%] ${
                chatMessage.role === "user"
                  ? "rounded-br-md bg-teal-800 text-white"
                  : "rounded-bl-md border border-stone-200 bg-white text-slate-700"
              }`}
            >
              {chatMessage.content}
            </p>
          </div>
        ))}
        {busy ? (
          <div className="flex justify-start" role="status">
            <p className="rounded-2xl rounded-bl-md border border-stone-200 bg-white px-4 py-3 text-sm text-slate-500 shadow-sm">
              Thinking<span aria-hidden="true">…</span>
            </p>
          </div>
        ) : null}
        {error ? (
          <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-800" role="alert">
            {error}
          </p>
        ) : null}
      </div>

      <form className="border-t border-stone-200 bg-white p-4 sm:p-6" onSubmit={handleSubmit}>
        <div className="flex gap-3">
          <label className="sr-only" htmlFor="intake-message">
            Your message
          </label>
          <input
            autoComplete="off"
            className="min-w-0 flex-1 rounded-xl border border-stone-300 bg-white px-4 py-3 text-base outline-none transition placeholder:text-slate-400 focus:border-teal-600 focus:ring-2 focus:ring-teal-100 disabled:bg-stone-100"
            disabled={!sessionId || starting || busy}
            id="intake-message"
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Type your answer…"
            value={message}
          />
          <button
            className="rounded-xl bg-teal-800 px-5 py-3 text-sm font-bold text-white transition hover:bg-teal-700 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!message.trim() || !sessionId || starting || busy}
            type="submit"
          >
            Send
          </button>
        </div>
        {!starting && !sessionId ? (
          <button
            className="mt-3 text-sm font-bold text-teal-800 underline-offset-4 hover:underline"
            onClick={() => {
              setError(null);
              setStarting(true);
              setAttempt((value) => value + 1);
            }}
            type="button"
          >
            Try again
          </button>
        ) : null}
      </form>
    </section>
  );
}

function messageFor(reason: unknown): string {
  return reason instanceof ApiError
    ? reason.message
    : "Something unexpected went wrong. Please try again.";
}
