"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { fieldsForTask } from "@/components/task-submission-form";
import { ApiError, approveSubmission, getTask, getTaskRequirements, rejectSubmission } from "@/lib/api";
import { documentLabel, formatDateTime } from "@/lib/presentation";
import type { ApprovalRequest, DocumentRequirement, ExternalApplication, TaskDetail } from "@/types/api";

export function ApprovalReview({ approvalId, caseId, taskId }: { approvalId?: string; caseId: string; taskId: string }) {
  const router = useRouter();
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [approval, setApproval] = useState<ApprovalRequest | null>(null);
  const [documents, setDocuments] = useState<DocumentRequirement[]>([]);
  const [receipt, setReceipt] = useState<ExternalApplication | null>(null);
  const [busy, setBusy] = useState<"submit" | "cancel" | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      getTask(caseId, taskId, controller.signal),
      getTaskRequirements(caseId, taskId, controller.signal),
    ])
      .then(([loadedTask, requirements]) => {
        const pending = loadedTask.approval_requests.find((candidate) =>
          approvalId ? candidate.id === approvalId : candidate.status === "pending",
        );
        if (!pending) throw new ApiError("This submission is no longer awaiting approval.", 409);
        setTask(loadedTask);
        setApproval(pending);
        setDocuments(requirements);
      })
      .catch((reason: unknown) => {
        if (reason instanceof Error && reason.name === "AbortError") return;
        setError(reason instanceof ApiError ? reason.message : "Something unexpected went wrong.");
      });
    return () => controller.abort();
  }, [approvalId, caseId, taskId]);

  const taskHref = `/life-events/${caseId}/task/${taskId}`;
  const caseHref = `/life-events/${caseId}`;
  if (receipt) return <Receipt application={receipt} caseHref={caseHref} />;
  if (!task || !approval) return <ReviewLoading error={error} taskHref={taskHref} />;
  const currentApproval = approval;

  const input = currentApproval.context.input_data && typeof currentApproval.context.input_data === "object"
    ? currentApproval.context.input_data as Record<string, unknown>
    : task.input_data;
  const details = fieldsForTask(task).flatMap((field) => {
    const value = input[field.name];
    return typeof value === "string" && value.trim() ? [{ label: field.label, value }] : [];
  });
  const authority = currentApproval.action_description.split(" to ").at(-1) ?? "the responsible authority";

  async function cancel() {
    setBusy("cancel");
    setError(null);
    try {
      await rejectSubmission(currentApproval.id);
      router.push(taskHref);
    } catch (reason) {
      setError(messageFor(reason));
      setBusy(null);
    }
  }

  async function submit() {
    setBusy("submit");
    setError(null);
    try {
      setReceipt(await approveSubmission(currentApproval.id));
    } catch (reason) {
      setError(messageFor(reason));
      setBusy(null);
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-6 sm:px-8 sm:py-10">
      <div className="mx-auto max-w-4xl">
        <Link className="text-sm font-bold text-teal-800" href={taskHref}>← Cancel</Link>
        <p className="mt-8 text-sm font-bold uppercase tracking-[0.16em] text-teal-700">Review before submitting</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">You’re about to submit:</h1>

        <article className="mt-7 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-9">
          <h2 className="text-2xl font-bold text-slate-950">{task.title}</h2>
          <p className="mt-2 text-sm font-semibold text-slate-600">To: {authority}</p>

          <section className="mt-7 border-t border-slate-200 pt-6" aria-labelledby="key-fields-heading">
            <h3 className="font-bold text-slate-950" id="key-fields-heading">Key fields</h3>
            <dl className="mt-3 divide-y divide-slate-100">
              {details.map((detail) => <div className="grid gap-1 py-3 sm:grid-cols-[12rem_1fr]" key={detail.label}><dt className="text-sm font-semibold text-slate-500">{detail.label}</dt><dd className="break-words text-sm font-bold text-slate-900">{detail.value}</dd></div>)}
            </dl>
          </section>

          <section className="mt-6 border-t border-slate-200 pt-6" aria-labelledby="attached-heading">
            <h3 className="font-bold text-slate-950" id="attached-heading">Attached documents</h3>
            {documents.length ? <ul className="mt-3 space-y-2">{documents.map((document) => <li className="text-sm text-slate-700" key={`${document.type}-${document.owner}`}>• {documentLabel(document)} <span className="text-slate-500">(source: {document.status === "satisfied" ? "your verified documents" : "provided by you"})</span></li>)}</ul> : <p className="mt-3 text-sm text-slate-500">No documents are attached.</p>}
          </section>

          <p className="mt-6 rounded-xl bg-teal-50 p-4 text-sm text-teal-900">Data from: details you provided for this application and your verified Citizen Bridge documents.</p>
        </article>

        <p className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm font-semibold text-amber-950">This action cannot be undone once submitted to {authority}.</p>
        <p className="mt-3 text-sm text-slate-500">High-risk payments, declarations, and eSign actions will require an additional PIN verification step.</p>
        {error ? <p className="mt-4 rounded-xl bg-rose-50 p-4 text-sm text-rose-800" role="alert">{error}</p> : null}
        <div className="mt-7 flex flex-col-reverse gap-3 sm:flex-row sm:justify-between">
          <button className="rounded-xl border border-slate-300 px-6 py-3 font-bold text-slate-700" disabled={busy !== null} onClick={cancel} type="button">{busy === "cancel" ? "Cancelling…" : "Cancel"}</button>
          <button className="rounded-xl bg-teal-700 px-6 py-3 font-bold text-white hover:bg-teal-800 disabled:opacity-60" disabled={busy !== null} onClick={submit} type="button">{busy === "submit" ? "Submitting…" : "Confirm & Submit →"}</button>
        </div>
      </div>
    </main>
  );
}

function Receipt({ application, caseHref }: { application: ExternalApplication; caseHref: string }) {
  const [showDemoApproval, setShowDemoApproval] = useState(false);
  const reference = application.external_reference_id ?? application.id;
  const submitted = application.submitted_at ?? application.responded_at ?? application.updated_at;
  const demoApproved = application.status === "approved";

  useEffect(() => {
    if (!demoApproved) return;
    // DEMO ONLY: keep the sent-for-approval screen visible before revealing the simulated
    // authority decision. Remove this timer when real approval status updates drive the UI.
    const timer = window.setTimeout(() => setShowDemoApproval(true), 600);
    return () => window.clearTimeout(timer);
  }, [demoApproved]);

  if (demoApproved && showDemoApproval) {
    return (
      <main className="grid min-h-screen place-items-center bg-emerald-50 px-4 py-10">
        <section className="w-full max-w-2xl rounded-3xl border border-emerald-200 bg-white p-7 shadow-sm sm:p-10">
          <span aria-hidden="true" className="grid size-14 place-items-center rounded-full bg-emerald-700 text-2xl text-white">✓</span>
          <p className="mt-6 text-sm font-bold uppercase tracking-[0.16em] text-emerald-700">Demo authority response</p>
          <h1 className="mt-2 text-3xl font-bold text-emerald-950">Approved</h1>
          <p className="mt-3 text-slate-600">For demo purposes, the authority automatically approved this application.</p>
          <p className="mt-7 text-sm font-semibold text-slate-500">Reference</p>
          <p className="mt-1 break-all text-2xl font-bold text-slate-950">{reference}</p>
          <Link className="mt-8 inline-flex rounded-xl bg-emerald-700 px-6 py-3 font-bold text-white hover:bg-emerald-800" href={caseHref}>Next →</Link>
        </section>
      </main>
    );
  }

  return (
    <main className="grid min-h-screen place-items-center bg-cyan-50 px-4 py-10">
      <section className="w-full max-w-2xl rounded-3xl border border-cyan-200 bg-white p-7 shadow-sm sm:p-10">
        <span aria-hidden="true" className="grid size-14 place-items-center rounded-full bg-cyan-700 text-2xl text-white">✓</span>
        <h1 className="mt-6 text-3xl font-bold text-cyan-950">Sent for approval</h1>
        <p className="mt-7 text-sm font-semibold text-slate-500">Reference</p>
        <p className="mt-1 break-all text-2xl font-bold text-slate-950">{reference}</p>
        <p className="mt-3 text-sm text-slate-600">Submitted: {formatDateTime(submitted)}</p>
        {demoApproved ? <p className="mt-8 rounded-2xl bg-amber-50 p-4 text-sm font-semibold text-amber-950" role="status">Demo mode: the authority is automatically reviewing this submission now.</p> : <><h2 className="mt-8 text-xl font-bold text-slate-950">What happens next</h2><p className="mt-3 text-sm leading-6 text-slate-600">The responsible authority will review your submission and Citizen Bridge will show its response here.</p><Link className="mt-8 inline-flex rounded-xl bg-cyan-700 px-6 py-3 font-bold text-white hover:bg-cyan-800" href={caseHref}>Back to case overview</Link></>}
      </section>
    </main>
  );
}

function ReviewLoading({ error, taskHref }: { error: string | null; taskHref: string }) {
  return <main className="grid min-h-screen place-items-center bg-slate-50 p-6">{error ? <section className="text-center"><h1 className="text-2xl font-bold text-slate-950">Review unavailable</h1><p className="mt-3 text-slate-600" role="alert">{error}</p><Link className="mt-5 inline-block font-bold text-teal-800" href={taskHref}>Back to task</Link></section> : <p role="status">Preparing your review…</p>}</main>;
}

function messageFor(reason: unknown) {
  return reason instanceof ApiError ? reason.message : "Something unexpected went wrong.";
}
