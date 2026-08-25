"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { ProvenanceTag } from "@/components/provenance-tag";
import { ErrorState, LoadingState } from "@/components/page-state";
import { ApiError, getDocumentDetail } from "@/lib/api";
import { formatDate, formatDateTime } from "@/lib/presentation";
import type { DocDetailEntry } from "@/types/api";

const ACTION_LABELS: Record<string, string> = {
  viewed: "Viewed",
  shared: "Shared with",
  submitted: "Submitted to",
  downloaded: "Downloaded",
};

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [doc, setDoc] = useState<DocDetailEntry | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getDocumentDetail(id)
      .then(setDoc)
      .catch((reason: unknown) => {
        if (reason instanceof Error && reason.name === "AbortError") return;
        setError(reason instanceof ApiError ? reason.message : "Something unexpected went wrong.");
      });
    return () => controller.abort();
  }, [id]);

  if (error) return <ErrorState message={error} />;
  if (!doc) return <LoadingState label="Loading document…" />;

  return (
    <div className="mx-auto max-w-3xl py-2 sm:py-3">
      <Link className="text-sm font-bold text-teal-700 hover:text-teal-900" href="/documents">
        ← My Documents
      </Link>

      <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">
              {doc.title}
            </h1>
            <p className="mt-1 text-sm text-slate-500 capitalize">{doc.document_type.replace(/_/g, " ")}</p>
          </div>
          <VerificationBadge status={doc.verification_status} />
        </div>

        <dl className="mt-6 grid gap-y-3 border-t border-slate-100 pt-5 text-sm sm:grid-cols-2">
          {doc.issuer && <MetaRow label="Issuer" value={doc.issuer} />}
          {doc.issued_at && <MetaRow label="Issued" value={formatDate(doc.issued_at)} />}
          {doc.valid_from && <MetaRow label="Valid from" value={formatDate(doc.valid_from)} />}
          {doc.valid_until && <MetaRow label="Valid until" value={formatDate(doc.valid_until)} />}
        </dl>

        <div className="mt-5 border-t border-slate-100 pt-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Provenance</p>
          <div className="mt-2">
            <ProvenanceTag source={doc.provenance_source} type={doc.provenance_type} />
          </div>
          <p className="mt-1 text-xs text-slate-400">Added {formatDateTime(doc.created_at)}</p>
        </div>

        {doc.source_task_id && doc.source_case_id ? (
          <div className="mt-3">
            <Link
              className="text-xs font-bold text-teal-700 hover:text-teal-900"
              href={`/life-events/${doc.source_case_id}`}
            >
              View originating case →
            </Link>
          </div>
        ) : null}
      </section>

      <section className="mt-8 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <h2 className="text-lg font-bold text-slate-950">Who accessed this</h2>
        {doc.usage_history.length === 0 ? (
          <p className="mt-3 text-sm text-slate-500">No access recorded yet.</p>
        ) : (
          <ol className="mt-4 space-y-3">
            {doc.usage_history.map((entry) => (
              <li
                className="flex items-start gap-3 rounded-xl border border-slate-100 bg-slate-50 p-3 text-sm"
                key={entry.id}
              >
                <span className="mt-0.5 text-slate-400 text-xs font-mono">
                  {formatDateTime(entry.accessed_at)}
                </span>
                <div>
                  <p className="font-medium text-slate-800">
                    {ACTION_LABELS[entry.action] ?? entry.action}
                    {entry.recipient ? ` ${entry.recipient}` : ""}
                  </p>
                  {entry.purpose ? (
                    <p className="mt-0.5 text-xs text-slate-500">{entry.purpose}</p>
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="mt-6 rounded-3xl border border-slate-100 bg-slate-50 p-5">
        <p className="text-sm font-bold text-slate-700">Actions</p>
        <div className="mt-3 flex flex-wrap gap-3">
          <button
            className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 hover:bg-slate-100"
            type="button"
          >
            Download
          </button>
          {doc.provenance_type === "user_uploaded" ? (
            <button
              className="rounded-xl border border-red-200 bg-white px-4 py-2 text-sm font-bold text-red-700 hover:bg-red-50"
              type="button"
            >
              Delete
            </button>
          ) : null}
        </div>
        <p className="mt-3 text-xs text-slate-400">
          Document sharing and deletion controls are coming in a future update.
        </p>
      </section>
    </div>
  );
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-medium text-slate-500">{label}</dt>
      <dd className="mt-0.5 text-slate-900">{value}</dd>
    </div>
  );
}

function VerificationBadge({ status }: { status: DocDetailEntry["verification_status"] }) {
  const styles: Record<DocDetailEntry["verification_status"], string> = {
    verified: "bg-teal-50 text-teal-800",
    pending: "bg-amber-50 text-amber-800",
    expired: "bg-orange-50 text-orange-800",
    rejected: "bg-red-50 text-red-800",
  };
  const labels: Record<DocDetailEntry["verification_status"], string> = {
    verified: "Verified ✓",
    pending: "Pending",
    expired: "Expired ⚠️",
    rejected: "Rejected",
  };
  return (
    <span className={`shrink-0 rounded-full px-3 py-1 text-sm font-semibold ${styles[status]}`}>
      {labels[status]}
    </span>
  );
}
