"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { EmptyState, ErrorState, LoadingState } from "@/components/page-state";
import { ApiError, getActivity } from "@/lib/api";
import type { ActivityEntry } from "@/types/api";

type Filter = "all" | "cases" | "documents" | "benefits" | "security";
const filters: Array<{ id: Filter; label: string }> = [
  { id: "all", label: "All" }, { id: "cases", label: "Cases" },
  { id: "documents", label: "Documents" }, { id: "benefits", label: "Benefits" },
  { id: "security", label: "Security" },
];

export default function ActivityPage() {
  const [filter, setFilter] = useState<Filter>("all");
  const [items, setItems] = useState<ActivityEntry[] | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getActivity({ category: filter === "all" ? undefined : filter, days: 7, limit: 20, signal: controller.signal })
      .then((response) => { setItems(response.activities); setHasMore(response.has_more); })
      .catch((reason: unknown) => {
        if (reason instanceof Error && reason.name === "AbortError") return;
        setError(reason instanceof ApiError ? reason.message : "Something unexpected went wrong.");
      });
    return () => controller.abort();
  }, [attempt, filter]);

  const groups = useMemo(() => groupByDay(items ?? []), [items]);
  async function loadMore() {
    if (!items) return;
    setLoadingMore(true);
    try {
      const response = await getActivity({ category: filter === "all" ? undefined : filter, days: 90, limit: 20, offset: items.length });
      setItems([...items, ...response.activities]);
      setHasMore(response.has_more);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Something unexpected went wrong.");
    } finally { setLoadingMore(false); }
  }

  if (error) return <ErrorState message={error} onRetry={() => { setError(null); setAttempt((value) => value + 1); }} />;
  if (!items) return <LoadingState label="Loading activity…" />;

  return (
    <div className="mx-auto max-w-3xl py-2 sm:py-3">
      <header className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-700">Your receipt book</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">Recent Activity</h1>
        <p className="mt-2 text-sm text-slate-500">A simple timeline of what happened across your services.</p>
      </header>

      <div aria-label="Activity filters" className="mt-6 flex gap-2 overflow-x-auto pb-1" role="tablist">
        {filters.map((option) => <button aria-selected={filter === option.id} className={`shrink-0 rounded-full px-4 py-2 text-sm font-semibold ${filter === option.id ? "bg-teal-700 text-white" : "border border-slate-200 bg-white text-slate-700"}`} key={option.id} onClick={() => { setItems(null); setFilter(option.id); }} role="tab" type="button">{option.label}</button>)}
      </div>

      {groups.length ? groups.map((group) => (
        <section className="mt-8" key={group.label}>
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500">{group.label}</h2>
          <ol className="mt-3 space-y-2">
            {group.items.map((item) => <li className="flex items-start gap-3 rounded-2xl border border-slate-100 bg-white p-4 shadow-sm" key={item.id}>
              <span aria-hidden="true" className="grid size-9 shrink-0 place-items-center rounded-xl bg-teal-50">{icon(item.activity_type)}</span>
              <div className="min-w-0 flex-1"><p className="font-medium text-slate-950">{item.title}</p>{item.description ? <p className="mt-0.5 text-sm text-slate-500">{item.description}</p> : null}<time className="mt-1 block text-xs text-slate-400" dateTime={item.occurred_at}>{formatTime(item.occurred_at)}</time></div>
              <Link aria-label={`View ${item.title}`} className="shrink-0 text-sm font-bold text-teal-700" href={deepLink(item)}>→</Link>
            </li>)}
          </ol>
        </section>
      )) : <div className="mt-8"><EmptyState title="No activity yet" description={filter === "all" ? "Your activity will appear here as you use the platform." : "No activity appears in this category yet. It will fill naturally as you use services."} /></div>}

      {hasMore ? <button className="mx-auto mt-8 block rounded-xl border border-slate-300 bg-white px-5 py-2.5 text-sm font-bold text-slate-700" disabled={loadingMore} onClick={loadMore} type="button">{loadingMore ? "Loading…" : "Load more"}</button> : null}
    </div>
  );
}

function deepLink(item: ActivityEntry): string {
  if (item.document_id) return `/documents/${item.document_id}`;
  if (item.case_id && item.task_id) return `/life-events/${item.case_id}/task/${item.task_id}`;
  if (item.case_id) return `/life-events/${item.case_id}`;
  if (item.category === "benefits") return "/benefits";
  if (item.category === "security") return "/settings/data-controls";
  return "/activity";
}

function icon(type: string): string {
  if (type === "task_completed") return "✅";
  if (type === "task_failed") return "⚠️";
  if (type.startsWith("task_")) return "✓";
  if (type === "case_completed") return "🎉";
  if (type.startsWith("case_")) return "📋";
  if (type.startsWith("document_")) return "📄";
  if (type.startsWith("benefit_")) return "🎯";
  if (type.startsWith("profile_")) return "👤";
  return "🔒";
}

function groupByDay(items: ActivityEntry[]) {
  const groups = new Map<string, ActivityEntry[]>();
  for (const item of items) {
    const date = new Date(item.occurred_at);
    const today = new Date();
    const daysAgo = Math.floor((startOfDay(today).getTime() - startOfDay(date).getTime()) / 86_400_000);
    const label = daysAgo === 0 ? "Today" : daysAgo === 1 ? "Yesterday" : date.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
    groups.set(label, [...(groups.get(label) ?? []), item]);
  }
  return Array.from(groups, ([label, grouped]) => ({ label, items: grouped }));
}

function startOfDay(date: Date) { return new Date(date.getFullYear(), date.getMonth(), date.getDate()); }
function formatTime(value: string) { return new Date(value).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" }); }
