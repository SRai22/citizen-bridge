"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AppHeader } from "@/components/app-header";
import { DocumentsPanel } from "@/components/documents-panel";
import { ErrorState, LoadingState } from "@/components/page-state";
import { StatusBadge } from "@/components/status-badge";
import { ApiError, getCase, getTaskRequirements } from "@/lib/api";
import { caseTitle, dependencySummary, formatDate } from "@/lib/presentation";
import type { CitizenCase, DocumentRequirement } from "@/types/api";

const DependencyGraph = dynamic(
  () => import("@/components/dependency-graph").then((m) => m.DependencyGraph),
  { ssr: false, loading: () => <div className="h-[360px] w-full animate-pulse rounded-2xl bg-slate-100" /> },
);

export default function CaseOverviewPage() {
  const { id } = useParams<{ id: string }>();
  const [citizenCase, setCitizenCase] = useState<CitizenCase | null>(null);
  const [requirementsByTask, setRequirementsByTask] = useState<
    Record<string, DocumentRequirement[]>
  >({});
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [view, setView] = useState<"list" | "graph">("list");

  useEffect(() => {
    const controller = new AbortController();
    getCase(id, controller.signal)
      .then(async (loadedCase) => {
        const requirements = await Promise.all(
          loadedCase.tasks.map(async (task) => [
            task.id,
            await getTaskRequirements(id, task.id, controller.signal),
          ] as const),
        );
        setRequirementsByTask(Object.fromEntries(requirements));
        setCitizenCase(loadedCase);
      })
      .catch((reason: unknown) => {
        if (reason instanceof Error && reason.name === "AbortError") return;
        setError(reason instanceof ApiError ? reason.message : "Something unexpected went wrong.");
      });
    return () => controller.abort();
  }, [attempt, id]);

  return (
    <div className="min-h-screen">
      <AppHeader />
      <main className="mx-auto max-w-5xl px-5 py-8 sm:px-8 sm:py-12">
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
        {!error && citizenCase ? (
          <>
            <nav className="mb-6 text-sm font-medium text-slate-500" aria-label="Breadcrumb">
              Your cases <span className="mx-2 text-slate-300">/</span> Overview
            </nav>
            <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
              <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-sm font-bold uppercase tracking-[0.16em] text-cyan-700">
                    Case overview
                  </p>
                  <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">
                    {caseTitle(citizenCase)}
                  </h1>
                  <p className="mt-3 text-sm text-slate-500">
                    Created {formatDate(citizenCase.created_at)} · Case #{citizenCase.id.slice(0, 8)}
                  </p>
                </div>
                <StatusBadge status={citizenCase.status} />
              </div>
            </section>

            <section className="mt-10" aria-labelledby="tasks-heading">
              <div className="mb-4 flex items-end justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-cyan-700">Your next steps</p>
                  <h2 id="tasks-heading" className="mt-1 text-2xl font-bold tracking-tight">
                    Tasks
                  </h2>
                </div>
                <div className="flex items-center gap-3">
                  <p className="text-sm text-slate-500">
                    {citizenCase.tasks.length} {citizenCase.tasks.length === 1 ? "task" : "tasks"}
                  </p>
                  <div className="flex rounded-lg border border-slate-200 bg-white p-0.5">
                    <button
                      onClick={() => setView("list")}
                      className={`rounded-md px-3 py-1.5 text-xs font-semibold transition ${view === "list" ? "bg-slate-900 text-white shadow-sm" : "text-slate-500 hover:text-slate-900"}`}
                      aria-pressed={view === "list"}
                    >
                      List
                    </button>
                    <button
                      onClick={() => setView("graph")}
                      className={`rounded-md px-3 py-1.5 text-xs font-semibold transition ${view === "graph" ? "bg-slate-900 text-white shadow-sm" : "text-slate-500 hover:text-slate-900"}`}
                      aria-pressed={view === "graph"}
                    >
                      Graph
                    </button>
                  </div>
                </div>
              </div>

              {view === "graph" && citizenCase.tasks.length > 0 && (
                <div className="mb-6">
                  <DependencyGraph tasks={citizenCase.tasks} caseId={citizenCase.id} />
                </div>
              )}

              {citizenCase.tasks.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-600">
                  No tasks have been added to this case yet.
                </div>
              ) : (
                <ol className="space-y-3">
                  {citizenCase.tasks.map((task, index) => (
                    <li key={task.id}>
                      <Link
                        className="group flex min-h-28 items-start gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-cyan-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-cyan-600 focus:ring-offset-2"
                        href={`/case/${citizenCase.id}/task/${task.id}`}
                      >
                        <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-slate-100 text-sm font-bold text-slate-600 group-hover:bg-cyan-50 group-hover:text-cyan-800">
                          {index + 1}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                            <span className="font-bold text-slate-950">{task.title}</span>
                            <StatusBadge status={task.status} />
                          </span>
                          <span className="mt-3 block text-sm leading-5 text-slate-500">
                            {dependencySummary(task, citizenCase.tasks)}
                          </span>
                        </span>
                        <span className="mt-1 hidden text-xl text-slate-300 transition group-hover:translate-x-1 group-hover:text-cyan-700 sm:block" aria-hidden="true">
                          →
                        </span>
                      </Link>
                    </li>
                  ))}
                </ol>
              )}
            </section>

            <DocumentsPanel
              citizenCase={citizenCase}
              requirementsByTask={requirementsByTask}
            />
          </>
        ) : null}
      </main>
    </div>
  );
}
