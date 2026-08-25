"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { ErrorState, LoadingState } from "@/components/page-state";
import { StatusBadge } from "@/components/status-badge";
import { ApiError, getCaseOverview } from "@/lib/api";
import type { CaseOverview, CaseTask } from "@/types/api";

const groups: Array<[keyof CaseOverview["tasks_by_group"], string]> = [
  ["ready", "Ready now"],
  ["waiting", "In progress"],
  ["blocked", "Coming next"],
  ["completed", "Completed"],
];

export default function CaseOverviewPage() {
  const { id } = useParams<{ id: string }>();
  const [citizenCase, setCitizenCase] = useState<CaseOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getCaseOverview(id, controller.signal)
      .then(setCitizenCase)
      .catch((reason: unknown) => {
        if (reason instanceof Error && reason.name === "AbortError") return;
        setError(reason instanceof ApiError ? reason.message : "Something unexpected went wrong.");
      });
    return () => controller.abort();
  }, [attempt, id]);

  return (
    <div className="mx-auto max-w-5xl py-2 sm:py-3">
        {error ? (
          <ErrorState
            message={error}
            onRetry={() => {
              setError(null);
              setCitizenCase(null);
              setAttempt((value) => value + 1);
            }}
          />
        ) : null}
        {!error && !citizenCase ? <LoadingState label="Loading your case…" /> : null}
        {citizenCase ? (
          <>
            <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
              <p className="text-sm font-bold uppercase tracking-[0.16em] text-cyan-700">Case overview</p>
              <div className="mt-2 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h1 className="text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">{citizenCase.title}</h1>
                  <p className="mt-3 text-sm text-slate-500">Case #{citizenCase.case_id.slice(0, 8)} · You are the {citizenCase.my_role}</p>
                </div>
                <StatusBadge status={citizenCase.status} />
              </div>
              <p className="mt-6 text-sm font-semibold text-slate-700">
                {citizenCase.progress.completed} of {citizenCase.progress.total} tasks completed
              </p>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100" aria-label="Case progress" role="progressbar" aria-valuemax={citizenCase.progress.total} aria-valuemin={0} aria-valuenow={citizenCase.progress.completed}>
                <div className="h-full rounded-full bg-teal-600" style={{ width: `${citizenCase.progress.total ? (citizenCase.progress.completed / citizenCase.progress.total) * 100 : 0}%` }} />
              </div>
            </section>

            <div className="mt-8 space-y-8">
              {groups.map(([key, title]) => {
                const tasks = citizenCase.tasks_by_group[key];
                return tasks.length ? <TaskGroup key={key} tasks={tasks} title={title} /> : null;
              })}
            </div>
          </>
        ) : null}
    </div>
  );
}

function TaskGroup({ tasks, title }: { tasks: CaseTask[]; title: string }) {
  return (
    <section>
      <h2 className="text-xl font-bold text-slate-950">{title}</h2>
      <ol className="mt-3 space-y-3">
        {tasks.map((task) => (
          <li className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" key={task.task_id}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="font-bold text-slate-950">{task.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-600">{task.blocked_reason ?? task.description}</p>
              </div>
              <StatusBadge status={task.status} />
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
