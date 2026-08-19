"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AppHeader } from "@/components/app-header";
import { ApprovalDialog } from "@/components/approval-dialog";
import { ErrorState, LoadingState } from "@/components/page-state";
import { StatusBadge } from "@/components/status-badge";
import {
  fieldsForTask,
  TaskFormField,
  TaskSubmissionForm,
} from "@/components/task-submission-form";
import {
  ApiError,
  approveSubmission,
  getCase,
  getTask,
  prepareTask,
  rejectSubmission,
  updateTaskInput,
} from "@/lib/api";
import { documentLabel, formatDateTime, statusMessage, titleCase } from "@/lib/presentation";
import type {
  ApprovalRequest,
  CitizenCase,
  ExternalApplication,
  TaskDetail,
} from "@/types/api";

type BusyAction = "prepare" | "approve" | "cancel" | null;
type ApprovalDetail = { label: string; value: string };

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

function detailsFromValues(
  task: TaskDetail,
  fields: TaskFormField[],
  values: Record<string, unknown>,
): ApprovalDetail[] {
  return [
    { label: "Action", value: task.title },
    ...fields.flatMap((field) => {
      const value = values[field.name];
      return typeof value === "string" && value.trim()
        ? [{ label: field.label, value: value.trim() }]
        : [];
    }),
  ];
}

export default function TaskDetailPage() {
  const { id, taskId } = useParams<{ id: string; taskId: string }>();
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [citizenCase, setCitizenCase] = useState<CitizenCase | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [approval, setApproval] = useState<ApprovalRequest | null>(null);
  const [approvalDetails, setApprovalDetails] = useState<ApprovalDetail[]>([]);
  const [busyAction, setBusyAction] = useState<BusyAction>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([getTask(id, taskId, controller.signal), getCase(id, controller.signal)])
      .then(([loadedTask, loadedCase]) => {
        setTask(loadedTask);
        setCitizenCase(loadedCase);
        const pendingApproval = loadedTask.approval_requests.find(
          (candidate) => candidate.status === "pending",
        );
        if (pendingApproval) {
          const inputData = pendingApproval.context.input_data;
          const values = inputData && typeof inputData === "object" ? inputData : {};
          setApproval(pendingApproval);
          setApprovalDetails(
            detailsFromValues(
              loadedTask,
              fieldsForTask(loadedTask),
              values as Record<string, unknown>,
            ),
          );
        }
      })
      .catch((reason: unknown) => {
        if (reason instanceof Error && reason.name === "AbortError") return;
        setLoadError(errorMessage(reason));
      });
    return () => controller.abort();
  }, [attempt, id, taskId]);

  async function refreshData() {
    const [loadedTask, loadedCase] = await Promise.all([getTask(id, taskId), getCase(id)]);
    setTask(loadedTask);
    setCitizenCase(loadedCase);
  }

  async function handlePrepare(values: Record<string, unknown>, fields: TaskFormField[]) {
    if (!task) return;
    setBusyAction("prepare");
    setActionError(null);
    setNotice(null);
    try {
      await updateTaskInput(id, taskId, values);
      const outcome = await prepareTask(id, taskId);
      await refreshData();
      if (isApprovalRequest(outcome)) {
        setApproval(outcome);
        setApprovalDetails(detailsFromValues(task, fields, values));
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

  async function handleApprove() {
    if (!approval) return;
    setBusyAction("approve");
    setActionError(null);
    try {
      const application = await approveSubmission(approval.id);
      setApproval(null);
      await refreshData();
      const failure = resultError(application);
      setActionError(failure);
      if (!failure) setNotice("Submission approved and completed successfully.");
    } catch (reason) {
      setActionError(errorMessage(reason));
    } finally {
      setBusyAction(null);
    }
  }

  async function handleCancel() {
    if (!approval) return;
    setBusyAction("cancel");
    setActionError(null);
    try {
      await rejectSubmission(approval.id);
      setApproval(null);
      await refreshData();
      setNotice("Submission cancelled. Your details are saved and the task is ready to edit.");
    } catch (reason) {
      setActionError(errorMessage(reason));
    } finally {
      setBusyAction(null);
    }
  }

  const tasksById = new Map(citizenCase?.tasks.map((candidate) => [candidate.id, candidate]) ?? []);
  const latestFailure = task?.external_applications.findLast(
    (application) => application.status === "rejected" || application.status === "error",
  );
  const failureMessage = latestFailure ? resultError(latestFailure) : null;

  return (
    <div className="min-h-screen">
      <AppHeader />
      <main className="mx-auto max-w-4xl px-5 py-8 sm:px-8 sm:py-12">
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
                {task.status === "completed" ? (
                  <div className="mt-5 flex items-start gap-3 rounded-2xl bg-emerald-50 px-4 py-4 text-emerald-900" role="status">
                    <span className="grid size-7 shrink-0 place-items-center rounded-full bg-emerald-700 text-sm text-white" aria-hidden="true">
                      ✓
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
                  <div className="mt-5 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-4 text-rose-900" role="alert">
                    <p className="text-sm font-bold">Submission needs attention</p>
                    <p className="mt-1 text-sm leading-6">{failureMessage}</p>
                  </div>
                ) : null}
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

              <TaskSubmissionForm
                busy={busyAction === "prepare"}
                error={approval ? null : actionError}
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
                            ✓
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
      </main>

      {approval ? (
        <ApprovalDialog
          approval={approval}
          busyAction={busyAction === "approve" || busyAction === "cancel" ? busyAction : null}
          details={approvalDetails}
          error={actionError}
          onApprove={handleApprove}
          onCancel={handleCancel}
        />
      ) : null}
    </div>
  );
}
