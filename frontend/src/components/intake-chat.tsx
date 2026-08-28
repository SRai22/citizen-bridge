"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { ProfileSummary } from "@/components/profile-summary";
import { ApiError, confirmIntake, getFamily, sendIntakeMessage, startIntake } from "@/lib/api";
import { workflowTitle } from "@/lib/presentation";
import type { IntakeProfile } from "@/types/api";
import type { FamilyMember } from "@/types/api";

interface ChatMessage {
  id: number;
  role: "user" | "system";
  content: string;
  action?: { label: string; href: string };
}

export function IntakeChat({ categoryId }: { categoryId: string }) {
  const router = useRouter();
  const nextMessageId = useRef(0);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [profile, setProfile] = useState<IntakeProfile | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [starting, setStarting] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [family, setFamily] = useState<FamilyMember[]>([]);
  const [selectedFamilyMember, setSelectedFamilyMember] = useState<FamilyMember | null>(null);
  const [inputType, setInputType] = useState<"text" | "date">("text");
  const [suggestedReplies, setSuggestedReplies] = useState<string[]>([]);
  const title = workflowTitle(categoryId);

  useEffect(() => {
    const controller = new AbortController();
    startIntake(categoryId, controller.signal)
      .then((response) => {
        setSessionId(response.conversation_id);
        setMessages([
          { id: nextMessageId.current++, role: "system", content: response.message },
        ]);
        setInputType(response.input_type ?? "text");
        setSuggestedReplies(response.suggested_replies ?? []);
        setStarting(false);
      })
      .catch((reason: unknown) => {
        if (reason instanceof Error && reason.name === "AbortError") return;
        setError(messageFor(reason));
        setStarting(false);
      });
    if (categoryId === "bereavement") {
      getFamily(controller.signal)
        .then((members) => setFamily(members.filter((member) => !member.is_deceased)))
        .catch(() => setFamily([]));
    }
    return () => controller.abort();
  }, [attempt, categoryId]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitMessage(message);
  }

  async function submitMessage(value: string, displayValue = value) {
    const content = value.trim();
    if (!content || !sessionId || busy) return;

    const userMessage = { id: nextMessageId.current++, role: "user" as const, content: displayValue };
    setMessages((current) => [...current, userMessage]);
    setMessage("");
    setError(null);
    setBusy(true);
    const redirect = boundaryRedirect(content);
    if (redirect) {
      setMessages((current) => [...current, { id: nextMessageId.current++, role: "system", ...redirect }]);
      setBusy(false);
      return;
    }
    try {
      const response = await sendIntakeMessage(sessionId, content);
      const systemMessage = {
        id: nextMessageId.current++,
        role: "system" as const,
        content: response.message,
      };
      setMessages((current) => [...current, systemMessage]);
      setInputType(response.input_type ?? "text");
      setSuggestedReplies(response.suggested_replies ?? []);
      setProfile(response.profile);
    } catch (reason) {
      setMessages((current) => current.filter(({ id }) => id !== userMessage.id));
      setMessage(displayValue);
      setError(messageFor(reason));
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirm(subject?: "self" | FamilyMember | null) {
    if (!sessionId || busy) return;
    setError(null);
    setBusy(true);
    try {
      const confirmation = await confirmIntake(
        sessionId,
        categoryId,
        subject ?? selectedFamilyMember,
      );
      router.push(`/life-events/${encodeURIComponent(confirmation.case_id)}`);
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
        categoryId={categoryId}
        onClarify={() => {
          setError(null);
          setProfile(null);
        }}
        onConfirm={handleConfirm}
        profile={profile}
      />
    );
  }

  const needsBirthDate = categoryId === "new_baby" && !messages.some(({ role }) => role === "user");
  const needsDeathDate = categoryId === "bereavement" && inputType === "date";
  const needsHospitalRecord = categoryId === "new_baby"
    && /upload the hospital birth report|upload the hospital.*discharge/i.test(messages[messages.length - 1]?.content ?? "");
  const needsDate = needsBirthDate || needsDeathDate;
  const latestDate = needsDate ? localDateValue(new Date()) : undefined;
  const showFamilyChoices = categoryId === "bereavement"
    && !messages.some(({ role }) => role === "user")
    && family.length > 0;

  return (
    <section aria-labelledby="intake-heading" className="flex min-h-[36rem] flex-col">
      <div className="border-b border-stone-200 px-5 py-6 sm:px-8">
        <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-700">
          {title} workflow
        </p>
        <h1 id="intake-heading" className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">
          {title}: a few questions to get started
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
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm sm:max-w-[70%] ${
                chatMessage.role === "user"
                  ? "rounded-br-md bg-teal-800 text-white"
                  : "rounded-bl-md border border-stone-200 bg-white text-slate-700"
              }`}
            >
              <p>{chatMessage.content}</p>
              {chatMessage.action ? <a className="mt-2 inline-block font-bold text-teal-800 underline-offset-2 hover:underline" href={chatMessage.action.href}>{chatMessage.action.label} →</a> : null}
            </div>
          </div>
        ))}
        {showFamilyChoices ? (
          <div className="flex flex-wrap gap-2" aria-label="Who passed away?">
            {family.map((member) => (
              <button
                aria-label={`${member.name}, ${member.relationship}`}
                className="rounded-xl border border-teal-700 bg-white px-4 py-2 text-left text-sm font-semibold text-teal-900 hover:bg-teal-50 disabled:opacity-50"
                disabled={busy || !sessionId}
                key={member.id}
                onClick={() => {
                  setSelectedFamilyMember(member);
                  const survivingFamily = family
                    .filter(({ id }) => id !== member.id)
                    .map(({ name, relationship }) => `${name} (${relationship})`)
                    .join(", ");
                  const answer = `${member.name}, my ${member.relationship}, passed away.`;
                  const savedContext = survivingFamily
                    ? ` My saved family profile lists these surviving household members: ${survivingFamily}. Treat their names and relationships as confirmed and do not ask for them again.`
                    : "";
                  void submitMessage(answer + savedContext, answer);
                }}
                type="button"
              >
                <span className="block">{member.name}</span>
                <span className="block text-xs font-normal capitalize text-slate-500">{member.relationship}</span>
              </button>
            ))}
          </div>
        ) : null}
        {suggestedReplies.length && !busy && !showFamilyChoices ? (
          <div className="flex flex-wrap gap-2" aria-label="Suggested replies">
            {suggestedReplies.map((reply) => (
              <button
                className="rounded-xl border border-teal-700 bg-white px-4 py-2 text-sm font-semibold text-teal-900 hover:bg-teal-50"
                key={reply}
                onClick={() => void submitMessage(reply)}
                type="button"
              >
                {reply}
              </button>
            ))}
          </div>
        ) : null}
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
          {needsHospitalRecord ? (
            <label className="flex min-h-12 flex-1 cursor-pointer items-center justify-center rounded-xl border-2 border-dashed border-teal-500 bg-teal-50 px-4 py-3 text-sm font-bold text-teal-900 hover:bg-teal-100">
              Upload hospital birth record
              <input
                accept=".pdf,image/*"
                className="sr-only"
                disabled={!sessionId || starting || busy}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void submitMessage(`I uploaded the hospital birth record: ${file.name}`, `Uploaded ${file.name}`);
                }}
                type="file"
              />
            </label>
          ) : (
            <>
              <label className="sr-only" htmlFor="intake-message">
                {needsBirthDate ? "Baby's date of birth" : needsDeathDate ? "Date of death" : "Your message"}
              </label>
              <input
                autoComplete="off"
                className="min-w-0 flex-1 rounded-xl border border-stone-300 bg-white px-4 py-3 text-base outline-none transition placeholder:text-slate-400 focus:border-teal-600 focus:ring-2 focus:ring-teal-100 disabled:bg-stone-100"
                disabled={!sessionId || starting || busy}
                id="intake-message"
                max={latestDate}
                onChange={(event) => setMessage(event.target.value)}
                placeholder={needsDate ? undefined : "Type your answer…"}
                type={needsDate ? "date" : "text"}
                value={message}
              />
              <button
                className="rounded-xl bg-teal-800 px-5 py-3 text-sm font-bold text-white transition hover:bg-teal-700 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={!message.trim() || !sessionId || starting || busy}
                type="submit"
              >
                Send
              </button>
            </>
          )}
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

function localDateValue(date: Date): string {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

function boundaryRedirect(message: string): Pick<ChatMessage, "content" | "action"> | null {
  const value = message.toLocaleLowerCase();
  if (/\b(task|application) (status|update)\b/.test(value)) return { content: "You can see the latest status and next step in Active Life Events.", action: { label: "Open Active Life Events", href: "/life-events" } };
  if (/\b(document|certificate)s?\b/.test(value) && /\b(upload|manage|find|where|view)\b/.test(value)) return { content: "My Documents is the right place to view, add, or manage documents.", action: { label: "Open My Documents", href: "/documents" } };
  if (/\b(setting|account|privacy|password)s?\b/.test(value)) return { content: "You'll find account and privacy controls in Settings.", action: { label: "Open Settings", href: "/settings/data-controls" } };
  return null;
}
