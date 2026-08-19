"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AppHeader } from "@/components/app-header";
import { ErrorState, LoadingState } from "@/components/page-state";
import { StatusBadge } from "@/components/status-badge";
import { ApiError, getCase, getTask } from "@/lib/api";
import { documentLabel, statusMessage, titleCase } from "@/lib/presentation";
import type { CitizenCase, TaskDetail } from "@/types/api";

export default function TaskDetailPage() {
  const { id, taskId } = useParams<{ id: string; taskId: string }>();
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [citizenCase, setCitizenCase] = useState<CitizenCase | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([getTask(id, taskId, controller.signal), getCase(id, controller.signal)])
      .then(([loadedTask, loadedCase]) => {
        setTask(loadedTask);
        setCitizenCase(loadedCase);
      })
      .catch((reason: unknown) => {
        if (reason instanceof Error && reason.name === "AbortError") return;
        setError(reason instanceof ApiError ? reason.message : "Something unexpected went wrong.");
      });
    return () => controller.abort();
  }, [attempt, id, taskId]);

  const tasksById = new Map(citizenCase?.tasks.map((candidate) => [candidate.id, candidate]) ?? []);

  return (
    <div className="min-h-screen">
      <AppHeader />
      <main className="mx-auto max-w-4xl px-5 py-8 sm:px-8 sm:py-12">
        {error ? (
          <ErrorState
            message={error}
            onRetry={() => {
              setError(null);
              setTask(null);
              setCitizenCase(null);
              setAttempt((value) => value + 1);
            }}
          />
        ) : null}
        {!error && (!task || !citizenCase) ? <LoadingState label="Loading task details…" /> : null}
        {!error && task && citizenCase ? (
          <>
            <Link
              className="inline-flex items-center gap-2 text-sm font-bold text-cyan-800 hover:text-cyan-950"
              href={`/case/${id}`}
            >
              <span aria-hidden="true">←</span> Back to case
            </Link>

            <article className="mt-6 overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
              <header className="border-b border-slate-200 p-6 sm:p-8">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-sm font-bold uppercase tracking-[0.16em] text-cyan-700">
                      {titleCase(task.workflow_id)}
                    </p>
                    <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">
                      {task.title}
                    </h1>
                  </div>
                  <StatusBadge status={task.status} />
                </div>
                <p className="mt-5 max-w-2xl text-base leading-7 text-slate-600">
                  {task.description ?? "Complete this step to move your case forward."}
                </p>
                <div className="mt-5 rounded-2xl bg-slate-50 px-4 py-3 text-sm font-medium text-slate-700">
                  {statusMessage(task.status)}
                </div>
              </header>

              <div className="grid gap-0 md:grid-cols-2">
                <section className="p-6 sm:p-8" aria-labelledby="documents-heading">
                  <h2 id="documents-heading" className="text-lg font-bold text-slate-950">
                    Required documents
                  </h2>
                  {task.required_documents.length ? (
                    <ul className="mt-5 space-y-4">
                      {task.required_documents.map((document) => (
                        <li className="flex gap-3" key={`${document.type}-${document.owner ?? "any"}`}>
                          <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-lg bg-cyan-50 text-sm text-cyan-800" aria-hidden="true">
                            ▤
                          </span>
                          <span>
                            <span className="block text-sm font-bold text-slate-900">
                              {documentLabel(document)}
                            </span>
                            {document.description ? (
                              <span className="mt-1 block text-sm leading-5 text-slate-500">
                                {document.description}
                              </span>
                            ) : null}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-4 text-sm text-slate-500">No documents are required.</p>
                  )}
                </section>

                <section className="border-t border-slate-200 p-6 sm:p-8 md:border-l md:border-t-0" aria-labelledby="dependencies-heading">
                  <h2 id="dependencies-heading" className="text-lg font-bold text-slate-950">
                    Dependencies
                  </h2>
                  {task.dependencies.length ? (
                    <ul className="mt-5 space-y-3">
                      {task.dependencies.map((dependency) => {
                        const prerequisite = tasksById.get(dependency.depends_on_task_id);
                        return (
                          <li className="rounded-xl border border-slate-200 p-4" key={dependency.id}>
                            <div className="flex items-center justify-between gap-3">
                              <span className="text-sm font-bold text-slate-900">
                                {prerequisite?.title ?? "Required task"}
                              </span>
                              {prerequisite ? <StatusBadge status={prerequisite.status} /> : null}
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  ) : (
                    <p className="mt-4 text-sm leading-6 text-slate-500">
                      This task has no prerequisites and can proceed independently.
                    </p>
                  )}
                </section>
              </div>
            </article>
          </>
        ) : null}
      </main>
    </div>
  );
}
