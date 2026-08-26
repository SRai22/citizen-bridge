"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { ProvenanceTag } from "@/components/provenance-tag";
import { EmptyState, ErrorState, ExpiredDocumentState, LoadingState } from "@/components/page-state";
import { ApiError, getDocuments, uploadDocument } from "@/lib/api";
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
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

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

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    setUploading(true);
    setUploadError(null);
    try {
      await uploadDocument({
        title: String(values.get("title")),
        document_type: String(values.get("document_type")),
        proof_category: String(values.get("proof_category")) as DocCategory,
        issuer: String(values.get("issuer")) || undefined,
        valid_until: values.get("valid_until") ? `${String(values.get("valid_until"))}T00:00:00` : undefined,
      });
      form.reset();
      setGroups(null);
      setAttempt((value) => value + 1);
    } catch (reason) {
      setUploadError(reason instanceof ApiError ? reason.message : "Could not add this document.");
    } finally {
      setUploading(false);
    }
  }

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
        <div className="mt-8"><EmptyState title="Keep reusable documents together" description="Documents will appear here as you use services. You can also upload your existing documents." action={{ label: "Upload a document", href: "/documents#upload" }} /></div>
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
      <details className="mt-8 rounded-2xl border border-teal-200 bg-teal-50 p-5" id="upload" open>
        <summary className="cursor-pointer font-bold text-teal-900">Upload an existing document</summary>
        {uploadError ? <p className="mt-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-800" role="alert">{uploadError} Please review the details and try again.</p> : null}
        <form className="mt-5 grid gap-4 sm:grid-cols-2" onSubmit={upload}>
          <label className="text-sm font-semibold text-slate-700">Document name<input className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2" name="title" required /></label>
          <label className="text-sm font-semibold text-slate-700">Document type<input className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2" name="document_type" placeholder="e.g. voter_id" required /></label>
          <label className="text-sm font-semibold text-slate-700">Category<select className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2" name="proof_category">{(Object.keys(CATEGORY_META) as DocCategory[]).map((category) => <option key={category} value={category}>{CATEGORY_META[category].label}</option>)}</select></label>
          <label className="text-sm font-semibold text-slate-700">Issuer (optional)<input className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2" name="issuer" /></label>
          <label className="text-sm font-semibold text-slate-700">Valid until (optional)<input className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2" name="valid_until" type="date" /></label>
          <button className="self-end rounded-xl bg-teal-700 px-4 py-2.5 text-sm font-bold text-white disabled:opacity-60" disabled={uploading} type="submit">{uploading ? "Adding…" : "Add document"}</button>
        </form>
      </details>
    </div>
  );
}

function DocumentCard({ doc }: { doc: DocEntry }) {
  if (doc.verification_status === "expired") {
    return <li><ExpiredDocumentState documentName={doc.title} expired={doc.valid_until ? formatDate(doc.valid_until) : "before today"} /></li>;
  }
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
