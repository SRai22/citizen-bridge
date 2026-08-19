"use client";

import { KeyboardEvent, useEffect, useRef } from "react";

import type { ApprovalRequest } from "@/types/api";

interface ApprovalDetail {
  label: string;
  value: string;
}

interface ApprovalDialogProps {
  approval: ApprovalRequest;
  details: ApprovalDetail[];
  busyAction: "approve" | "cancel" | null;
  error: string | null;
  onApprove: () => void;
  onCancel: () => void;
}

export function ApprovalDialog({
  approval,
  details,
  busyAction,
  error,
  onApprove,
  onCancel,
}: ApprovalDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const approveRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    approveRef.current?.focus();
    return () => previouslyFocused?.focus();
  }, []);

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape" && !busyAction) {
      event.preventDefault();
      onCancel();
      return;
    }
    if (event.key !== "Tab") return;
    const controls = Array.from(
      dialogRef.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") ?? [],
    );
    if (!controls.length) return;
    const first = controls[0];
    const last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  const summary =
    typeof approval.context.summary === "string"
      ? approval.context.summary
      : approval.action_description;

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-end bg-slate-950/55 p-0 backdrop-blur-sm sm:place-items-center sm:p-6"
      role="presentation"
    >
      <div
        aria-describedby="approval-description"
        aria-labelledby="approval-title"
        aria-modal="true"
        className="max-h-[92vh] w-full overflow-y-auto rounded-t-3xl bg-white p-6 shadow-2xl sm:max-w-xl sm:rounded-3xl sm:p-8"
        onKeyDown={handleKeyDown}
        ref={dialogRef}
        role="dialog"
      >
        <span className="grid size-11 place-items-center rounded-2xl bg-amber-50 text-xl text-amber-800" aria-hidden="true">
          ✓
        </span>
        <h2 id="approval-title" className="mt-5 text-2xl font-bold tracking-tight text-slate-950">
          Confirm this submission
        </h2>
        <p id="approval-description" className="mt-2 text-sm leading-6 text-slate-600">
          {summary}
        </p>

        <dl className="mt-6 divide-y divide-slate-200 rounded-2xl border border-slate-200 bg-slate-50 px-4">
          {details.map((detail) => (
            <div className="grid gap-1 py-3 sm:grid-cols-[9rem_1fr] sm:gap-4" key={detail.label}>
              <dt className="text-xs font-bold uppercase tracking-wide text-slate-500">
                {detail.label}
              </dt>
              <dd className="break-words text-sm font-medium text-slate-900">{detail.value}</dd>
            </div>
          ))}
        </dl>

        {error ? (
          <p className="mt-5 rounded-xl bg-rose-50 px-4 py-3 text-sm font-medium text-rose-800" role="alert">
            {error}
          </p>
        ) : null}

        <div className="mt-7 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button
            className="min-h-11 rounded-xl border border-slate-300 px-5 text-sm font-bold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-cyan-600 focus:ring-offset-2 disabled:opacity-60"
            disabled={busyAction !== null}
            onClick={onCancel}
            type="button"
          >
            {busyAction === "cancel" ? "Cancelling…" : "Cancel"}
          </button>
          <button
            className="min-h-11 rounded-xl bg-cyan-700 px-5 text-sm font-bold text-white transition hover:bg-cyan-800 focus:outline-none focus:ring-2 focus:ring-cyan-600 focus:ring-offset-2 disabled:opacity-60"
            disabled={busyAction !== null}
            onClick={onApprove}
            ref={approveRef}
            type="button"
          >
            {busyAction === "approve" ? "Submitting…" : "Approve & submit"}
          </button>
        </div>
      </div>
    </div>
  );
}
