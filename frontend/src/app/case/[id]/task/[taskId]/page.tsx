"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ErrorState, LoadingState } from "@/components/page-state";
import { RejectionReplan } from "@/components/rejection-replan";
import { StatusBadge } from "@/components/status-badge";
import { TaskSubmissionForm } from "@/components/task-submission-form";
import {
  ApiError,
  getCaseOverview,
  getTask,
  getTaskRequirements,
  prepareTask,
  updateTaskInput,
} from "@/lib/api";
import { documentLabel, formatDateTime, statusMessage, titleCase } from "@/lib/presentation";
import type {
  ApprovalRequest,
  CaseOverview,
  CitizenCase,
  DocumentRequirement,
  ExternalApplication,
  TaskDetail,
} from "@/types/api";

type BusyAction = "prepare" | null;

function isApprovalRequest(
  outcome: ApprovalRequest | ExternalApplication,
): outcome is ApprovalRequest {
  return "action_description" in outcome;
}

function errorMessage(reason: unknown): string {
  return reason instanceof ApiError ? reason.message : "Something unexpected went wrong.";
}

function resultError(application: ExternalApplication): string | null {
  if (application.status !== "rejected" && application.status !== "error") return null;
  const message = application.response_payload.message;
  if (typeof message === "string") return message;
  const data = application.response_payload.data;
  if (data && typeof data === "object") {
    const reason = (data as Record<string, unknown>).reason;
    if (typeof reason === "string") return reason;
  }
  return "The authority could not accept this submission. Review the details and try again.";
}

export default function TaskDetailPage() {
  const { id, taskId } = useParams<{ id: string; taskId: string }>();
  const router = useRouter();
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [citizenCase, setCitizenCase] = useState<CaseOverview | CitizenCase | null>(null);
  const [requirements, setRequirements] = useState<DocumentRequirement[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<BusyAction>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      getTask(id, taskId, controller.signal),
      getCaseOverview(id, controller.signal),
      getTaskRequirements(id, taskId, controller.signal),
    ])
      .then(([loadedTask, loadedCase, loadedRequirements]) => {
        setTask(loadedTask);
        setCitizenCase(loadedCase);
        setRequirements(loadedRequirements);
        const pendingApproval = loadedTask.approval_requests.find(
          (candidate) => candidate.status === "pending",
        );
        if (pendingApproval) {
          router.replace(
            `/life-events/${encodeURIComponent(id)}/task/${encodeURIComponent(taskId)}/review?approval=${encodeURIComponent(pendingApproval.id)}`,
          );
        }
      })
      .catch((reason: unknown) => {
        if (reason instanceof Error && reason.name === "AbortError") return;
        setLoadError(errorMessage(reason));
      });
    return () => controller.abort();
  }, [attempt, id, router, taskId]);

  async function refreshData() {
    const [loadedTask, loadedCase, loadedRequirements] = await Promise.all([
      getTask(id, taskId),
      getCaseOverview(id),
      getTaskRequirements(id, taskId),
    ]);
    setTask(loadedTask);
    setCitizenCase(loadedCase);
    setRequirements(loadedRequirements);
  }

  async function handlePrepare(values: Record<string, unknown>) {
    if (!task) return;
    setBusyAction("prepare");
    setActionError(null);
    setNotice(null);
    try {
      // Declare all required documents as user-provided for submission validation
      const documentsProvided = (task.required_documents ?? []).map((d) => d.type);
      const input = { ...values, ...(documentsProvided.length ? { documents_provided: documentsProvided } : {}) };
      await updateTaskInput(id, taskId, input);
      const outcome = await prepareTask(id, taskId);
      await refreshData();
      if (isApprovalRequest(outcome)) {
        router.push(
          `/life-events/${encodeURIComponent(id)}/task/${encodeURIComponent(taskId)}/review?approval=${encodeURIComponent(outcome.id)}`,
        );
      } else {
        const failure = resultError(outcome);
        setActionError(failure);
        if (!failure) setNotice("Submission completed successfully.");
      }
    } catch (reason) {
      setActionError(errorMessage(reason));
    } finally {
      setBusyAction(null);
    }
  }

  const caseTasks = !citizenCase
    ? []
    : "tasks_by_group" in citizenCase
      ? Object.values(citizenCase.tasks_by_group).flat().map((candidate) => ({
          id: candidate.task_id,
          workflow_id: candidate.workflow_id,
          title: candidate.title,
          status: candidate.status,
        }))
      : citizenCase.tasks;
  const tasksById = new Map(caseTasks.map((candidate) => [candidate.id, candidate]));
  const displayedRequirements = [...requirements];
  const requirementTypes = new Set(displayedRequirements.map((requirement) => requirement.type));
  for (const dependency of task?.dependencies ?? []) {
    const prerequisite = tasksById.get(dependency.depends_on_task_id);
    if (
      prerequisite?.workflow_id === "legal_heir_certificate" &&
      !requirementTypes.has(prerequisite.workflow_id)
    ) {
      displayedRequirements.push({
        type: prerequisite.workflow_id,
        owner: "applicant",
        description: `Produced by ${prerequisite.title}.`,
        status: citizenCase && "documents" in citizenCase && citizenCase.documents.some(
          (document) =>
            document.document_type === prerequisite.workflow_id &&
            document.verification_status !== "rejected",
        )
          ? "satisfied"
          : "missing",
      });
    }
  }
  const latestFailure = task?.external_applications.findLast(
    (application) => application.status === "rejected" || application.status === "error",
  );
  const failureMessage = latestFailure ? resultError(latestFailure) : null;

  return (
    <div className="mx-auto max-w-4xl py-2 sm:py-3">
        {loadError ? (
          <ErrorState
            message={loadError}
            onRetry={() => {
              setLoadError(null);
              setTask(null);
              setCitizenCase(null);
              setAttempt((value) => value + 1);
            }}
          />
        ) : null}
        {!loadError && (!task || !citizenCase) ? (
          <LoadingState label="Loading task details…" />
        ) : null}
        {!loadError && task && citizenCase ? (
          <>
            <Link
              className="inline-flex items-center gap-2 text-sm font-bold text-cyan-800 hover:text-cyan-950"
              href={`/life-events/${id}`}
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
                {task.status === "completed" ? (
                  <div className="mt-5 flex items-start gap-3 rounded-2xl bg-emerald-50 px-4 py-4 text-emerald-900" role="status">
                    <span className="grid size-7 shrink-0 place-items-center rounded-full bg-emerald-700 text-sm text-white" aria-hidden="true">
                      ✅
                    </span>
                    <div>
                      <p className="text-sm font-bold">Task completed</p>
                      {task.completed_at ? (
                        <p className="mt-1 text-sm text-emerald-800">
                          Completed {formatDateTime(task.completed_at)}
                        </p>
                      ) : null}
                    </div>
                  </div>
                ) : null}
                {notice ? (
                  <p className="mt-5 rounded-xl bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800" role="status">
                    {notice}
                  </p>
                ) : null}
                {failureMessage ? (
                  <>
                    <div className="mt-5 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-4 text-rose-900" role="alert">
                      <p className="text-sm font-bold">Submission needs attention</p>
                      <p className="mt-1 text-sm leading-6">{failureMessage}</p>
                    </div>
                    {task.status === "failed" && latestFailure?.status === "rejected" ? (
                      <RejectionReplan caseId={id} taskId={taskId} />
                    ) : null}
                  </>
                ) : null}
              </header>

              <div className="grid gap-0 md:grid-cols-2">
                <section className="p-6 sm:p-8" aria-labelledby="documents-heading">
                  <h2 id="documents-heading" className="text-lg font-bold text-slate-950">
                    Available documents
                  </h2>
                  {displayedRequirements.length ? (
                    <ul className="mt-5 space-y-4">
                      {displayedRequirements.map((document) => {
                        const available = document.status === "satisfied";
                        const producer = caseTasks.find(
                          (candidate) => candidate.workflow_id === document.type,
                        );
                        return (
                          <li
                            className="flex gap-3"
                            key={`${document.type}-${document.owner ?? "any"}`}
                          >
                          <span className="mt-0.5 text-base" aria-hidden="true">
                            {available ? "✅" : "☐"}
                          </span>
                          <span>
                            <span className="block text-sm font-bold text-slate-900">
                              Required: {documentLabel(document)}
                            </span>
                            <span
                              className={`mt-1 block text-xs font-semibold ${available ? "text-emerald-700" : "text-slate-500"}`}
                            >
                              {available ? "Available" : "Not yet obtained"}
                            </span>
                            {!available ? (
                              <span className="mt-1 block text-xs text-slate-500">
                                {producer ? (
                                  <>
                                    Produced by:{" "}
                                    <Link
                                      className="font-semibold text-cyan-800"
                                      href={`/life-events/${id}/task/${producer.id}`}
                                    >
                                      {producer.title}
                                    </Link>
                                  </>
                                ) : "You provide this document"}
                              </span>
                            ) : null}
                            {document.description ? (
                              <span className="mt-1 block text-sm leading-5 text-slate-500">
                                {document.description}
                              </span>
                            ) : null}
                          </span>
                        </li>
                        );
                      })}
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

              <TaskSubmissionForm
                busy={busyAction === "prepare"}
                error={actionError}
                key={task.id}
                onSubmit={handlePrepare}
                task={task}
              />

              {task.produced_documents.length ? (
                <section className="border-t border-slate-200 bg-slate-50/70 p-6 sm:p-8" aria-labelledby="produced-documents-heading">
                  <h2 id="produced-documents-heading" className="text-xl font-bold text-slate-950">
                    Documents
                  </h2>
                  <ul className="mt-5 grid gap-3 sm:grid-cols-2">
                    {task.produced_documents.map((document) => (
                      <li className="rounded-2xl border border-emerald-200 bg-white p-4" key={document.id}>
                        <div className="flex items-start gap-3">
                          <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-emerald-50 text-emerald-800" aria-hidden="true">
                            ✅
                          </span>
                          <div>
                            <p className="text-sm font-bold text-slate-950">
                              {titleCase(document.document_type)}
                            </p>
                            <p className="mt-1 text-xs text-slate-500">
                              {document.issuer ?? "Official document"}
                            </p>
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
            </article>
          </>
        ) : null}
    </div>
  );
}
