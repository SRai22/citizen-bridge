"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { acceptRemediation, ApiError, interpretRejection } from "@/lib/api";
import { titleCase } from "@/lib/presentation";
import type { RejectionInterpretation } from "@/types/api";

interface RejectionReplanProps {
  caseId: string;
  taskId: string;
  taskName: string;
}

function errorMessage(reason: unknown): string {
  return reason instanceof ApiError ? reason.message : "Something unexpected went wrong.";
}

export function RejectionReplan({ caseId, taskId, taskName }: RejectionReplanProps) {
  const router = useRouter();
  const [interpretation, setInterpretation] = useState<RejectionInterpretation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [accepting, setAccepting] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    interpretRejection(caseId, taskId, controller.signal)
      .then(setInterpretation)
      .catch((reason: unknown) => {
        if (reason instanceof Error && reason.name === "AbortError") return;
        setError(errorMessage(reason));
      });
    return () => controller.abort();
  }, [attempt, caseId, taskId]);

  async function handleAccept() {
    if (!interpretation) return;
    setAccepting(true);
    setError(null);
    try {
      await acceptRemediation(caseId, interpretation.remediation);
      router.push(`/case/${encodeURIComponent(caseId)}`);
    } catch (reason) {
      setError(errorMessage(reason));
      setAccepting(false);
    }
  }

  if (dismissed) return null;

  return (
    <div className="mt-4 space-y-4">
      <section className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4" aria-labelledby="system-analysis-heading">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-amber-800">⚠️ {taskName} was not successful</p>
        <h2 id="system-analysis-heading" className="mt-1 text-base font-bold text-slate-950">
          What happened
        </h2>
        {interpretation ? (
          <p className="mt-2 text-sm leading-6 text-slate-700">{interpretation.explanation}</p>
        ) : error ? (
          <div className="mt-2">
            <p className="text-sm text-rose-800" role="alert">{error}</p>
            <button
              className="mt-3 text-sm font-bold text-cyan-800 hover:text-cyan-950"
              onClick={() => {
                setError(null);
                setAttempt((value) => value + 1);
              }}
              type="button"
            >
              Try analysis again
            </button>
          </div>
        ) : (
          <p className="mt-2 text-sm text-slate-600" role="status">Analyzing the rejection…</p>
        )}
      </section>

      {interpretation ? (
        <section className="rounded-2xl border border-cyan-200 bg-cyan-50 px-4 py-4" aria-labelledby="proposed-action-heading">
          <h2 id="proposed-action-heading" className="text-base font-bold text-slate-950">
            What you can do
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-700">
            Add “Obtain {titleCase(interpretation.remediation.workflow_id)}” to your plan and make it a prerequisite for this task.
          </p>
          {error ? <p className="mt-3 text-sm text-rose-800" role="alert">{error}</p> : null}
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button
              className="rounded-xl bg-cyan-800 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-cyan-900 disabled:cursor-wait disabled:opacity-65"
              disabled={accepting}
              onClick={handleAccept}
              type="button"
            >
              {accepting ? "Updating your plan…" : "Add this to my plan"}
            </button>
            <button
              className="rounded-xl px-4 py-2.5 text-sm font-bold text-slate-600 hover:bg-white hover:text-slate-950 disabled:opacity-50"
              disabled={accepting}
              onClick={() => setDismissed(true)}
              type="button"
            >
              Dismiss
            </button>
            <a className="rounded-xl px-4 py-2.5 text-sm font-bold text-teal-800 hover:bg-white" href="mailto:support@citizenbridge.in">I need help with this</a>
          </div>
        </section>
      ) : null}
    </div>
  );
}
