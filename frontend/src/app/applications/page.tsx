"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { EmptyState, ErrorState, LoadingState } from "@/components/page-state";
import { StatusBadge } from "@/components/status-badge";
import { ApiError, getCaseOverview, getCases, getCatalogServices } from "@/lib/api";
import { formatDateTime } from "@/lib/presentation";
import type { CaseOverview, CaseTask } from "@/types/api";

type Filter = "all" | "action" | "pending" | "completed";
type Application = { task: CaseTask; citizenCase: CaseOverview; authority: string };

const filters: Array<{ id: Filter; label: string }> = [
  { id: "all", label: "All" },
  { id: "action", label: "Action Needed" },
  { id: "pending", label: "Pending" },
  { id: "completed", label: "Completed" },
];

export default function ApplicationsPage() {
  const [applications, setApplications] = useState<Application[] | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([getCases(controller.signal), getCatalogServices()])
      .then(async ([caseList, catalog]) => {
        const cases = await Promise.all(caseList.cases.map((item) => getCaseOverview(item.case_id, controller.signal)));
        const authorities = new Map(catalog.services.map((service) => [service.workflow_id, service.authority]));
        setApplications(
          cases.flatMap((citizenCase) =>
            Object.values(citizenCase.tasks_by_group).flat().map((task) => ({
              task,
              citizenCase,
              authority: authorities.get(task.workflow_id) ?? "Responsible department",
            })),
          ),
        );
      })
      .catch((reason: unknown) => {
        if (reason instanceof Error && reason.name === "AbortError") return;
        setError(reason instanceof ApiError ? reason.message : "Something unexpected went wrong.");
      });
    return () => controller.abort();
  }, [attempt]);

  const visible = useMemo(() => (applications ?? [])
    .filter((item) => filter === "all" || category(item.task) === filter)
    .sort((left, right) => rank(left.task) - rank(right.task) || Date.parse(right.citizenCase.updated_at) - Date.parse(left.citizenCase.updated_at)), [applications, filter]);

  if (error) return <ErrorState message={error} onRetry={() => { setError(null); setApplications(null); setAttempt((value) => value + 1); }} />;
  if (!applications) return <LoadingState label="Loading your applications…" />;

  return (
    <div className="mx-auto max-w-5xl py-2 sm:py-3">
      <header className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-700">Across all cases</p>
        <h1 className="mt-2 text-3xl font-bold text-slate-950 sm:text-4xl">My Applications</h1>
        <p className="mt-3 text-sm text-slate-600">Everything ready, submitted, waiting, or completed in one place.</p>
      </header>

      <div className="mt-6 flex gap-2 overflow-x-auto" role="tablist" aria-label="Application filters">
        {filters.map((item) => (
          <button aria-selected={filter === item.id} className={`shrink-0 rounded-full px-4 py-2 text-sm font-bold ${filter === item.id ? "bg-teal-700 text-white" : "border border-slate-300 bg-white text-slate-700"}`} key={item.id} onClick={() => setFilter(item.id)} role="tab" type="button">{item.label}</button>
        ))}
      </div>

      {visible.length ? (
        <ol className="mt-6 space-y-3">
          {visible.map(({ task, citizenCase, authority }) => (
            <li className={`rounded-2xl border bg-white p-5 shadow-sm ${task.status === "blocked" ? "border-slate-200 opacity-75" : "border-slate-200"}`} key={task.task_id}>
              <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                <div>
                  <h2 className="font-bold text-slate-950">{task.title}</h2>
                  <p className="mt-1 text-sm text-slate-600">{authority} · From: {citizenCase.title}</p>
                  <Timing task={task} />
                  {task.status === "blocked" ? <p className="mt-2 text-sm text-slate-500">Needs: {task.blocked_reason ?? "an earlier application"}</p> : null}
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <StatusBadge status={task.status} />
                  {category(task) === "action" ? <Link className="rounded-xl bg-teal-700 px-4 py-2 text-sm font-bold text-white" href={`/life-events/${citizenCase.case_id}/task/${task.task_id}`}>Start →</Link> : <Link className="text-sm font-bold text-teal-800" href={`/life-events/${citizenCase.case_id}/task/${task.task_id}`}>View →</Link>}
                </div>
              </div>
            </li>
          ))}
        </ol>
      ) : applications.length ? (
        <p className="mt-6 rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-600">No applications match this filter.</p>
      ) : <div className="mt-6"><EmptyState title="No applications yet" description="You haven't started any applications yet. Applications will appear here once you begin a service." action={{ label: "Browse services →", href: "/" }} /></div>}
    </div>
  );
}

function category(task: CaseTask): Filter {
  if (task.status === "completed") return "completed";
  if (task.status === "submitted" || task.status === "awaiting_approval") return "pending";
  if (task.status === "ready" || task.status === "in_progress" || task.status === "failed") return "action";
  return "all";
}

function rank(task: CaseTask): number {
  return { action: 0, pending: 1, all: 2, completed: 3 }[category(task)];
}

function Timing({ task }: { task: CaseTask }) {
  if (task.completed_at) return <p className="mt-2 text-sm text-slate-500">Completed {formatDateTime(task.completed_at)}</p>;
  if (task.wait_state?.submitted_at) return <p className="mt-2 text-sm text-slate-500">Submitted {formatDateTime(task.wait_state.submitted_at)}{task.wait_summary ? ` · ${task.wait_summary}` : ""}</p>;
  return null;
}
