"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { ErrorState, LoadingState } from "@/components/page-state";
import { StatusBadge } from "@/components/status-badge";
import { ApiError, getCaseOverview, getCases, getFamily, removeFamilyMember, updateFamilyMember } from "@/lib/api";
import { formatDate } from "@/lib/presentation";
import type { CaseOverview, FamilyMember } from "@/types/api";

export default function FamilyMemberDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [member, setMember] = useState<FamilyMember | null | "not_found">(null);
  const [cases, setCases] = useState<CaseOverview[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [editError, setEditError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([getFamily(controller.signal), getCases(controller.signal)])
      .then(async ([family, caseList]) => {
        const found = family.find((m) => m.id === id);
        if (!found) { setMember("not_found"); return; }
        setMember(found);
        // Only fetch overviews for coordinator cases — those are the ones with a subject
        const coordCases = caseList.cases.filter((c) => c.my_role === "coordinator");
        const overviews = await Promise.all(
          coordCases.map((c) => getCaseOverview(c.case_id, controller.signal)),
        );
        setCases(overviews.filter((o) => o.subject?.person_id === id));
      })
      .catch((reason: unknown) => {
        if (reason instanceof Error && reason.name === "AbortError") return;
        setError(reason instanceof ApiError ? reason.message : "Something unexpected went wrong.");
      });
    return () => controller.abort();
  }, [attempt, id]);

  async function handleEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!member || member === "not_found") return;
    const form = new FormData(event.currentTarget);
    try {
      const updated = await updateFamilyMember(member.id, {
        name: String(form.get("name")),
        relationship: String(form.get("relationship")),
        date_of_birth: String(form.get("date_of_birth")) || null,
        phone: String(form.get("phone")) || null,
        is_deceased: form.get("is_deceased") === "on",
      });
      setMember(updated);
      setEditError(null);
    } catch (reason) {
      setEditError(reason instanceof ApiError ? reason.message : "Could not save changes.");
    }
  }

  async function handleRemove() {
    if (!member || member === "not_found") return;
    try {
      await removeFamilyMember(member.id);
      router.push("/family");
    } catch (reason) {
      setEditError(reason instanceof ApiError ? reason.message : "Could not remove this member.");
    }
  }

  if (error) {
    return (
      <ErrorState
        message={error}
        onRetry={() => { setError(null); setMember(null); setAttempt((v) => v + 1); }}
      />
    );
  }
  if (!member) return <LoadingState label="Loading family member…" />;
  if (member === "not_found") {
    return (
      <div className="mx-auto max-w-2xl py-8 text-center">
        <p className="text-slate-600">Family member not found.</p>
        <Link className="mt-4 inline-block text-sm font-bold text-teal-700" href="/family">← Back to My Family</Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl py-2 sm:py-3">
      <Link className="text-sm font-bold text-teal-800 hover:text-teal-950" href="/family">
        ← My Family
      </Link>

      {/* Member header */}
      <section className="mt-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-slate-950">
              {member.name}
              {member.is_deceased ? <span className="ml-2 text-xl text-slate-500">(Late)</span> : null}
            </h1>
            <p className="mt-2 text-sm capitalize text-slate-600">
              {member.relationship}
              {member.date_of_birth ? ` · ${age(member.date_of_birth)} years` : ""}
              {member.death_date ? ` · Passed ${formatDate(member.death_date)}` : ""}
            </p>
            <p className="mt-1 text-xs text-slate-400">
              Added {formatDate(member.created_at)} ·{" "}
              {member.source === "intake" ? "From intake" : "Added manually"}
            </p>
          </div>
        </div>
      </section>

      {/* Authority */}
      <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <h2 className="text-lg font-bold text-slate-950">Your authority</h2>
        <div className="mt-3 space-y-2 text-sm">
          <p className="text-slate-700">
            ✓ <span className="font-medium">Case Coordinator</span> for cases involving{" "}
            {member.name} — you can gather documents, prepare applications, and track progress.
          </p>
          <p className="text-slate-500">
            ✗ Financial transactions and legal declarations require {member.name} or their
            legal guardian directly.
          </p>
        </div>
      </section>

      {/* Active cases */}
      <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <h2 className="text-lg font-bold text-slate-950">Active services</h2>
        {cases.length ? (
          <ul className="mt-4 space-y-3">
            {cases.map((c) => (
              <li className="flex items-center justify-between gap-3 rounded-2xl border border-slate-100 p-4" key={c.case_id}>
                <div>
                  <p className="font-medium text-slate-900">{c.title}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {c.progress.completed} of {c.progress.total} tasks complete
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <StatusBadge status={c.status} />
                  <Link
                    className="text-sm font-bold text-teal-700 hover:text-teal-900"
                    href={`/life-events/${c.case_id}`}
                  >
                    View →
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-slate-500">No active cases for {member.name}.</p>
        )}
        <div className="mt-4">
          <Link className="text-sm font-bold text-teal-700 hover:text-teal-900" href="/">
            Start a service for {member.name} →
          </Link>
        </div>
      </section>

      {/* Documents link */}
      <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <h2 className="text-lg font-bold text-slate-950">Documents</h2>
        <p className="mt-2 text-sm text-slate-500">
          Documents produced by services involving {member.name} appear in My Documents.
        </p>
        <Link className="mt-3 inline-block text-sm font-bold text-teal-700 hover:text-teal-900" href="/documents">
          Go to My Documents →
        </Link>
      </section>

      {/* Edit */}
      <details className="mt-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <summary className="cursor-pointer font-bold text-slate-950">Edit details</summary>
        {editError ? (
          <p className="mt-3 rounded-xl bg-rose-50 p-3 text-sm text-rose-800">{editError}</p>
        ) : null}
        <form className="mt-4 grid gap-3 sm:grid-cols-2" onSubmit={(e) => void handleEdit(e)}>
          <label className="text-sm font-semibold text-slate-700">
            Name
            <input className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2" defaultValue={member.name} name="name" required />
          </label>
          <label className="text-sm font-semibold text-slate-700">
            Relationship
            <select className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2" defaultValue={member.relationship} name="relationship">
              <option value="parent">Parent</option>
              <option value="mother">Mother</option>
              <option value="father">Father</option>
              <option value="spouse">Spouse</option>
              <option value="sibling">Sibling</option>
              <option value="child">Child</option>
            </select>
          </label>
          <label className="text-sm font-semibold text-slate-700">
            Date of birth (optional)
            <input className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2" defaultValue={member.date_of_birth ?? ""} name="date_of_birth" type="date" />
          </label>
          <label className="text-sm font-semibold text-slate-700">
            Phone (optional)
            <input className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2" defaultValue={member.phone ?? ""} name="phone" type="tel" />
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input defaultChecked={member.is_deceased} name="is_deceased" type="checkbox" />
            Mark as deceased
          </label>
          <button className="rounded-xl bg-teal-700 px-4 py-2 text-sm font-bold text-white" type="submit">
            Save changes
          </button>
        </form>
        <div className="mt-6 border-t border-slate-100 pt-4">
          <button className="text-sm font-bold text-rose-700 hover:text-rose-900" onClick={() => void handleRemove()} type="button">
            Remove {member.name} from my family
          </button>
        </div>
      </details>
    </div>
  );
}

function age(dateOfBirth: string): number {
  const born = new Date(`${dateOfBirth}T00:00:00`);
  const today = new Date();
  return (
    today.getFullYear() -
    born.getFullYear() -
    (today < new Date(today.getFullYear(), born.getMonth(), born.getDate()) ? 1 : 0)
  );
}
