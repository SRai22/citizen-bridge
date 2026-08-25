"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { ErrorState, LoadingState } from "@/components/page-state";
import { ApiError, getNotifications } from "@/lib/api";
import { formatDateTime } from "@/lib/presentation";
import type { NotificationItem } from "@/types/api";

type Filter = "all" | "documents" | "submissions" | "sharing" | "security";

const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "documents", label: "Documents" },
  { id: "submissions", label: "Submissions" },
  { id: "sharing", label: "Sharing" },
  { id: "security", label: "Security" },
];

function matchesFilter(item: NotificationItem, filter: Filter): boolean {
  if (filter === "all") return true;
  const t = item.notification_type.toLowerCase();
  if (filter === "documents") return t.includes("document") || t.includes("cert");
  if (filter === "submissions") return t.includes("task") || t.includes("case") || t.includes("application");
  if (filter === "sharing") return t.includes("share") || t.includes("shared");
  if (filter === "security") return t.includes("login") || t.includes("security") || t.includes("auth") || t.includes("account");
  return false;
}

function groupByDate(items: NotificationItem[]): { label: string; items: NotificationItem[] }[] {
  const groups = new Map<string, NotificationItem[]>();
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86_400_000);

  for (const item of items) {
    const d = new Date(item.created_at);
    const itemDay = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    let label: string;
    if (itemDay.getTime() === today.getTime()) label = "Today";
    else if (itemDay.getTime() === yesterday.getTime()) label = "Yesterday";
    else label = itemDay.toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" });
    const existing = groups.get(label) ?? [];
    existing.push(item);
    groups.set(label, existing);
  }
  return Array.from(groups.entries()).map(([label, items]) => ({ label, items }));
}

function activityIcon(type: string): string {
  if (type.includes("document")) return "▤";
  if (type.includes("task") || type.includes("submit")) return "✓";
  if (type.includes("case")) return "◎";
  if (type.includes("share")) return "↗";
  if (type.includes("login") || type.includes("security")) return "🔒";
  if (type.includes("benefit")) return "◇";
  return "·";
}

function deepLink(item: NotificationItem): string | null {
  const caseId = item.data.case_id as string | undefined;
  const taskId = item.data.task_id as string | undefined;
  const docId = item.data.document_id as string | undefined;
  if (docId) return `/documents/${docId}`;
  if (caseId && taskId) return `/life-events/${caseId}/task/${taskId}`;
  if (caseId) return `/life-events/${caseId}`;
  return null;
}

export default function ActivityPage() {
  const [notifications, setNotifications] = useState<NotificationItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    getNotifications({ limit: 100 })
      .then((res) => setNotifications(res.notifications))
      .catch((reason: unknown) => {
        setError(reason instanceof ApiError ? reason.message : "Something unexpected went wrong.");
      });
  }, [attempt]);

  const filtered = useMemo(
    () => (notifications ?? []).filter((item) => matchesFilter(item, filter)),
    [notifications, filter],
  );

  const groups = useMemo(() => groupByDate(filtered), [filtered]);

  if (error) {
    return (
      <ErrorState
        message={error}
        onRetry={() => {
          setError(null);
          setNotifications(null);
          setAttempt((v) => v + 1);
        }}
      />
    );
  }
  if (!notifications) return <LoadingState label="Loading activity…" />;

  return (
    <div className="mx-auto max-w-3xl py-2 sm:py-3">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-700">What changed</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">
          Recent Activity
        </h1>
        <p className="mt-2 text-sm text-slate-500">
          Your complete record of submissions, document access, and account events.
        </p>
      </section>

      <nav aria-label="Activity filter" className="mt-6 flex gap-2 overflow-x-auto pb-1">
        {FILTERS.map((f) => (
          <button
            className={`shrink-0 rounded-full px-4 py-2 text-sm font-semibold transition-colors ${
              filter === f.id
                ? "bg-teal-700 text-white"
                : "bg-white text-slate-700 border border-slate-200 hover:border-teal-300"
            }`}
            key={f.id}
            onClick={() => setFilter(f.id)}
            type="button"
          >
            {f.label}
          </button>
        ))}
      </nav>

      {groups.length === 0 ? (
        <section className="mt-8 rounded-3xl border border-slate-200 bg-white p-10 text-center">
          <p className="text-slate-600">No activity to show for this filter.</p>
        </section>
      ) : (
        <div className="mt-6 space-y-8">
          {groups.map((group) => (
            <section key={group.label}>
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500">
                {group.label}
              </h2>
              <ol className="mt-3 space-y-2">
                {group.items.map((item) => {
                  const link = deepLink(item);
                  return (
                    <li
                      className="flex items-start gap-3 rounded-2xl border border-slate-100 bg-white p-4 shadow-sm"
                      key={item.id}
                    >
                      <span
                        aria-hidden="true"
                        className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-xl bg-slate-50 text-sm"
                      >
                        {activityIcon(item.notification_type)}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-slate-900">{item.title}</p>
                        <p className="mt-0.5 text-sm text-slate-500">{item.body}</p>
                        <p className="mt-1 text-xs text-slate-400">
                          {formatDateTime(item.created_at)}
                        </p>
                      </div>
                      {link ? (
                        <Link
                          className="shrink-0 text-sm font-bold text-teal-700 hover:text-teal-900"
                          href={link}
                        >
                          →
                        </Link>
                      ) : null}
                    </li>
                  );
                })}
              </ol>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

