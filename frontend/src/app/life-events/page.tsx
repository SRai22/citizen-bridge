"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { EmptyState, ErrorState, LoadingState } from "@/components/page-state";
import { StatusBadge } from "@/components/status-badge";
import { ApiError, getCases } from "@/lib/api";
import type { CaseListItem } from "@/types/api";

export default function LifeEventsPage() {
  const [cases, setCases] = useState<CaseListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getCases(controller.signal)
      .then((response) => setCases(response.cases.filter((item) => item.status !== "completed" && item.status !== "abandoned")))
      .catch((reason: unknown) => {
        if (reason instanceof Error && reason.name === "AbortError") return;
        setError(reason instanceof ApiError ? reason.message : "Something unexpected went wrong.");
      });
    return () => controller.abort();
  }, [attempt]);

  if (error) return <ErrorState message={error} onRetry={() => { setError(null); setCases(null); setAttempt((value) => value + 1); }} />;
  if (!cases) return <LoadingState label="Loading your life events…" />;

  return (
    <div className="mx-auto max-w-5xl py-2 sm:py-3">
      <header className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-700">Coordinated plans</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">Active Life Events</h1>
        <p className="mt-3 text-sm text-slate-600">Your active service plans and their next steps, organized in one place.</p>
      </header>
      {cases.length ? <ol className="mt-8 grid gap-4 sm:grid-cols-2">{cases.map((item) => <li className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" key={item.case_id}><div className="flex items-start justify-between gap-3"><h2 className="font-bold text-slate-950">{item.title}</h2><StatusBadge status={item.status} /></div><p className="mt-3 text-sm text-slate-600">{item.progress.completed} of {item.progress.total} steps completed</p><Link className="mt-4 inline-block text-sm font-bold text-teal-800" href={`/life-events/${item.case_id}`}>View next steps →</Link></li>)}</ol> : <div className="mt-8"><EmptyState title="No active cases right now" description="Start when something comes up — we'll help you navigate it." action={{ label: "Start a new service →", href: "/" }} /></div>}
    </div>
  );
}
