"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ProvenanceTag } from "@/components/provenance-tag";
import { ErrorState, LoadingState } from "@/components/page-state";
import { StatusBadge } from "@/components/status-badge";
import { ApiError, getDocuments } from "@/lib/api";
import { formatDate } from "@/lib/presentation";
import type { DocCategory, DocEntry } from "@/types/api";

const CATEGORY_META: Record<DocCategory, { label: string; icon: string }> = {
  identity: { label: "Identity", icon: "🪪" },
  certificates: { label: "Certificates", icon: "📜" },
  address: { label: "Address Proof", icon: "🏠" },
  income: { label: "Income & Employment", icon: "💼" },
  family: { label: "Family", icon: "👨‍👩‍👧" },
};

export default function DocumentsPage() {
  const [groups, setGroups] = useState<Record<string, DocEntry[]> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getDocuments()
      .then((res) => setGroups(res.documents_by_category))
      .catch((reason: unknown) => {
        if (reason instanceof Error && reason.name === "AbortError") return;
        setError(reason instanceof ApiError ? reason.message : "Something unexpected went wrong.");
      });
    return () => controller.abort();
  }, [attempt]);

  if (error) {
    return (
      <ErrorState
        message={error}
        onRetry={() => {
          setError(null);
          setGroups(null);
          setAttempt((v) => v + 1);
        }}
      />
    );
  }
  if (!groups) return <LoadingState label="Loading your documents…" />;

  const totalDocs = Object.values(groups).flat().length;

  return (
    <div className="mx-auto max-w-5xl py-2 sm:py-3">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-700">Your records</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">
          My Documents
        </h1>
        <p className="mt-3 text-sm text-slate-500">{totalDocs} document{totalDocs !== 1 ? "s" : ""} across all categories</p>
      </section>

      {totalDocs === 0 ? (
        <section className="mt-8 rounded-3xl border border-slate-200 bg-white p-10 text-center">
          <p className="text-lg font-bold text-slate-950">No documents yet</p>
          <p className="mt-2 text-sm text-slate-500">
            Documents appear here as you complete services. You can also upload existing documents to
            reuse across services.
          </p>
          <button
            className="mt-6 rounded-xl bg-teal-700 px-5 py-2.5 text-sm font-bold text-white hover:bg-teal-800"
            type="button"
          >
            Upload a document
          </button>
        </section>
      ) : (
        <div className="mt-8 space-y-8">
          {(Object.keys(CATEGORY_META) as DocCategory[]).map((cat) => {
            const docs = groups[cat] ?? [];
            if (!docs.length) return null;
            const meta = CATEGORY_META[cat];
            return (
              <section key={cat}>
                <h2 className="flex items-center gap-2 text-xl font-bold text-slate-950">
                  <span>{meta.icon}</span> {meta.label}
                  <span className="ml-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
                    {docs.length}
                  </span>
                </h2>
                <ol className="mt-3 grid gap-3 sm:grid-cols-2">
                  {docs.map((doc) => (
                    <DocumentCard doc={doc} key={doc.id} />
                  ))}
                </ol>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}

function DocumentCard({ doc }: { doc: DocEntry }) {
  return (
    <li className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-bold text-slate-950">{doc.title}</h3>
        <VerificationBadge status={doc.verification_status} />
      </div>
      {doc.issuer ? (
        <p className="mt-1.5 text-sm text-slate-600">
          {doc.issuer}
          {doc.issued_at ? ` · ${formatDate(doc.issued_at)}` : ""}
        </p>
      ) : null}
      {doc.valid_until ? (
        <p className="mt-1 text-xs text-slate-500">Valid until {formatDate(doc.valid_until)}</p>
      ) : null}
      <div className="mt-3">
        <ProvenanceTag source={doc.provenance_source} type={doc.provenance_type} />
      </div>
      <div className="mt-3 flex items-center justify-between">
        <p className="text-xs text-slate-400">Added {formatDate(doc.created_at)}</p>
        <Link
          className="text-sm font-bold text-teal-700 hover:text-teal-900"
          href={`/documents/${doc.id}`}
        >
          View details →
        </Link>
      </div>
    </li>
  );
}

function VerificationBadge({ status }: { status: DocEntry["verification_status"] }) {
  const styles: Record<DocEntry["verification_status"], string> = {
    verified: "bg-teal-50 text-teal-800",
    pending: "bg-amber-50 text-amber-800",
    expired: "bg-orange-50 text-orange-800",
    rejected: "bg-red-50 text-red-800",
  };
  const labels: Record<DocEntry["verification_status"], string> = {
    verified: "Verified ✓",
    pending: "Pending",
    expired: "Expired ⚠️",
    rejected: "Rejected",
  };
  return (
    <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${styles[status]}`}>
      {labels[status]}
    </span>
  );
}

