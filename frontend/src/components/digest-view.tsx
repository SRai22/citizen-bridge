"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ErrorState, LoadingState } from "@/components/page-state";
import { ApiError, getDigest } from "@/lib/api";
import { formatDateTime } from "@/lib/presentation";
import type { DigestResponse, NotificationItem } from "@/types/api";

export function DigestView({ week }: { week?: string }) {
  const [digest, setDigest] = useState<DigestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDigest(week)
      .then((res) => { if (!cancelled) setDigest(res); })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof ApiError ? reason.message : "Something unexpected went wrong.");
      });
    return () => { cancelled = true; };
  }, [week]);

  if (error) return <ErrorState message={error} />;
  if (!digest) return <LoadingState label="Loading your digest…" />;

  const total =
    digest.ready_actions.length +
    digest.new_opportunities.length +
    digest.status_updates.length +
    digest.completions.length;

  return (
    <div className="mx-auto max-w-3xl py-2 sm:py-3">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-700">Weekly summary</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">📬 {digest.week}</h1>
        {total === 0 ? (
          <p className="mt-4 text-sm text-slate-500">No activity this week.</p>
        ) : (
          <p className="mt-2 text-sm text-slate-500">{total} update{total !== 1 ? "s" : ""} this week</p>
        )}
      </section>

      <div className="mt-6 space-y-6">
        <DigestSection
          items={digest.ready_actions}
          linkLabel="Go to task →"
          linkResolver={taskLink}
          title="Ready for Action"
        />
        <DigestSection
          items={digest.new_opportunities}
          linkLabel="Go to benefits →"
          linkResolver={() => "/benefits"}
          title="New Opportunities"
        />
        <DigestSection
          items={digest.status_updates}
          linkLabel="View →"
          linkResolver={caseLink}
          title="Status Updates"
        />
        <DigestSection
          items={digest.completions}
          linkLabel="View →"
          linkResolver={caseLink}
          title="Completed this week"
        />
      </div>

      {total > 0 ? (
        <div className="mt-8 text-center">
          <Link className="text-sm font-bold text-teal-700 hover:text-teal-900" href="/activity">
            View all activity →
          </Link>
        </div>
      ) : null}
    </div>
  );
}

function DigestSection({
  items,
  linkLabel,
  linkResolver,
  title,
}: {
  items: NotificationItem[];
  linkLabel: string;
  linkResolver: (item: NotificationItem) => string;
  title: string;
}) {
  if (!items.length) return null;

  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-bold text-slate-950">{title}</h2>
      <ol className="mt-4 space-y-3">
        {items.slice(0, 5).map((item) => (
          <li className="flex items-start justify-between gap-4" key={item.id}>
            <div className="min-w-0">
              <p className="font-medium text-slate-900">{item.title}</p>
              <p className="mt-0.5 text-sm text-slate-500">{item.body}</p>
              <p className="mt-0.5 text-xs text-slate-400">{formatDateTime(item.created_at)}</p>
            </div>
            <Link
              className="shrink-0 text-sm font-bold text-teal-700 hover:text-teal-900"
              href={linkResolver(item)}
            >
              {linkLabel}
            </Link>
          </li>
        ))}
        {items.length > 5 ? (
          <li className="text-sm text-slate-400">+{items.length - 5} more</li>
        ) : null}
      </ol>
    </section>
  );
}

function taskLink(item: NotificationItem): string {
  const caseId = item.data.case_id as string | undefined;
  const taskId = item.data.task_id as string | undefined;
  if (caseId && taskId) return `/life-events/${caseId}/task/${taskId}`;
  if (caseId) return `/life-events/${caseId}`;
  return "/life-events";
}

function caseLink(item: NotificationItem): string {
  const caseId = item.data.case_id as string | undefined;
  return caseId ? `/life-events/${caseId}` : "/life-events";
}
