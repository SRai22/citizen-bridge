"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { DependencyGraph, type DependencyGraphTask } from "@/components/dependency-graph";
import { CoordinatorBanner } from "@/components/coordinator-banner";
import { ErrorState, LoadingState } from "@/components/page-state";
import { StatusBadge } from "@/components/status-badge";
import { WaitingState } from "@/components/waiting-state";
import { ApiError, getCaseOverview } from "@/lib/api";
import { formatDate, formatDateTime } from "@/lib/presentation";
import type { CaseOverview, CaseTask } from "@/types/api";

export default function CaseOverviewPage() {
  const { id } = useParams<{ id: string }>();
  const [citizenCase, setCitizenCase] = useState<CaseOverview | null>(null);
  const [graphOpen, setGraphOpen] = useState(false);
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

  const allTasks = useMemo(
    () => citizenCase ? Object.values(citizenCase.tasks_by_group).flat() : [],
    [citizenCase],
  );
  const graphTasks: DependencyGraphTask[] = allTasks.map((task) => ({
    id: task.task_id,
    title: task.title,
    status: task.status,
    dependencies: task.blocked_by_task_ids.map((taskId) => ({ depends_on_task_id: taskId })),
  }));

  if (error) {
    return <ErrorState message={error} onRetry={() => { setError(null); setCitizenCase(null); setAttempt((value) => value + 1); }} />;
  }
  if (!citizenCase) return <LoadingState label="Loading your case…" />;

  return (
    <div className="mx-auto max-w-5xl py-2 sm:py-3">
      <CoordinatorBanner citizenCase={citizenCase} />
      <section className={`${citizenCase.my_role === "coordinator" ? "mt-4 " : ""}rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8`}>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-4">
            <span aria-hidden="true" className="grid size-12 shrink-0 place-items-center rounded-2xl bg-teal-50 text-2xl text-teal-800">◎</span>
            <div>
              <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-700">Active life event</p>
              <h1 className="mt-1 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">{citizenCase.title}</h1>
              <p className="mt-3 text-sm text-slate-500">Created {formatDate(citizenCase.created_at)} · {citizenCase.progress.completed} of {citizenCase.progress.total} completed</p>
            </div>
          </div>
          <StatusBadge status={citizenCase.status} />
        </div>
        <div aria-label="Case progress" aria-valuemax={citizenCase.progress.total} aria-valuemin={0} aria-valuenow={citizenCase.progress.completed} className="mt-6 h-2 overflow-hidden rounded-full bg-slate-100" role="progressbar">
          <div className="h-full rounded-full bg-teal-600" style={{ width: `${citizenCase.progress.total ? (citizenCase.progress.completed / citizenCase.progress.total) * 100 : 0}%` }} />
        </div>
      </section>

      {!allTasks.length ? (
        <section className="mt-8 rounded-3xl border border-slate-200 bg-white p-10 text-center">
          <p className="text-lg font-bold text-slate-950">Setting up your action plan...</p>
          <p className="mt-2 text-sm text-slate-500">Your tasks will appear here shortly.</p>
        </section>
      ) : graphOpen ? (
        <section className="mt-8">
          <button className="mb-4 text-sm font-bold text-teal-800" onClick={() => setGraphOpen(false)} type="button">← Back to list</button>
          <DependencyGraph caseId={id} tasks={graphTasks} />
        </section>
      ) : (
        <div className="mt-8 space-y-8">
          <TaskGroup caseId={id} kind="ready" tasks={citizenCase.tasks_by_group.ready} title="What to do next" />
          <TaskGroup caseId={id} kind="waiting" tasks={citizenCase.tasks_by_group.waiting} title="Waiting" />
          <TaskGroup allTasks={allTasks} caseId={id} kind="blocked" tasks={citizenCase.tasks_by_group.blocked} title="Blocked" />
          {citizenCase.tasks_by_group.completed.length ? (
            <details className="rounded-2xl border border-slate-200 bg-white p-5">
              <summary className="cursor-pointer text-xl font-bold text-slate-950">Completed ({citizenCase.tasks_by_group.completed.length})</summary>
              <TaskGroup caseId={id} compact kind="completed" tasks={citizenCase.tasks_by_group.completed} title="Completed tasks" />
            </details>
          ) : null}
          <button className="text-sm font-bold text-teal-800 hover:text-teal-950" onClick={() => setGraphOpen(true)} type="button">View dependency graph →</button>
        </div>
      )}
    </div>
  );
}

function TaskGroup({ allTasks = [], caseId, compact = false, kind, tasks, title }: {
  allTasks?: CaseTask[];
  caseId: string;
  compact?: boolean;
  kind: "ready" | "waiting" | "blocked" | "completed";
  tasks: CaseTask[];
  title: string;
}) {
  if (!tasks.length) return null;
  return (
    <section className={compact ? "mt-4" : undefined}>
      <h2 className={compact ? "sr-only" : "text-xl font-bold text-slate-950"}>{title}</h2>
      <ol className={`${compact ? "mt-0" : "mt-3"} space-y-3`}>
        {tasks.map((task) => <TaskCard allTasks={allTasks} caseId={caseId} kind={kind} key={task.task_id} task={task} />)}
      </ol>
    </section>
  );
}

function TaskCard({ allTasks, caseId, kind, task }: { allTasks: CaseTask[]; caseId: string; kind: "ready" | "waiting" | "blocked" | "completed"; task: CaseTask }) {
  const href = `/life-events/${caseId}/task/${task.task_id}`;
  const dependencies = task.blocked_by_task_ids.map((taskId) => allTasks.find((candidate) => candidate.task_id === taskId)?.title ?? "a required earlier task");
  if (kind === "blocked") {
    return (
      <li><details className="rounded-2xl border border-slate-200 bg-slate-100 p-5 text-slate-600"><summary className="cursor-pointer font-bold text-slate-800">{task.title}</summary><p className="mt-3 text-sm">Needs: {dependencies.join(", ")}</p><p className="mt-2 text-sm">{task.blocked_reason ?? "Complete the required task before starting this one."}</p></details></li>
    );
  }
  return (
    <li className={`rounded-2xl bg-white p-5 ${kind === "ready" ? "border-2 border-teal-500 shadow-md" : "border border-slate-200 shadow-sm"}`}>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="font-bold text-slate-950">{kind === "completed" ? "✓ " : ""}{task.title}</h3>
          {task.description ? <p className="mt-2 text-sm leading-6 text-slate-600">{task.description}</p> : null}
          {kind === "waiting" ? <WaitingState task={task} /> : null}
          {kind === "completed" && task.completed_at ? <p className="mt-2 text-sm text-slate-500">Completed {formatDateTime(task.completed_at)}</p> : null}
        </div>
        {kind === "ready" ? <Link className="shrink-0 rounded-xl bg-teal-700 px-4 py-2.5 text-sm font-bold text-white hover:bg-teal-800" href={href}>Start this →</Link> : <StatusBadge status={task.status} />}
      </div>
    </li>
  );
}
