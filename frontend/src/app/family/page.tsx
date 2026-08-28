"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { EmptyState, ErrorState, LoadingState } from "@/components/page-state";
import { ApiError, addFamilyMember, getCaseOverview, getCases, getFamily, removeFamilyMember, updateFamilyMember } from "@/lib/api";
import { formatDate } from "@/lib/presentation";
import type { CaseOverview, FamilyMember } from "@/types/api";

export default function FamilyPage() {
  const [members, setMembers] = useState<FamilyMember[] | null>(null);
  const [cases, setCases] = useState<CaseOverview[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([getFamily(controller.signal), getCases(controller.signal)])
      .then(async ([family, caseList]) => {
        const details = await Promise.all(caseList.cases.map((item) => getCaseOverview(item.case_id, controller.signal)));
        setMembers(family);
        setCases(details);
      })
      .catch((reason: unknown) => {
        if (reason instanceof Error && reason.name === "AbortError") return;
        setError(reason instanceof ApiError ? reason.message : "Something unexpected went wrong.");
      });
    return () => controller.abort();
  }, [attempt]);

  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const member = await addFamilyMember({ name: String(form.get("name")), relationship: String(form.get("relationship")), date_of_birth: String(form.get("date_of_birth")) || null, phone: String(form.get("phone")) || null, is_deceased: form.get("is_deceased") === "on", source: "manual" });
      setMembers((current) => [...(current ?? []), member]);
      event.currentTarget.reset();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Could not add this family member.");
    }
  }

  async function edit(member: FamilyMember, event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const updated = await updateFamilyMember(member.id, { name: String(form.get("name")), relationship: String(form.get("relationship")), date_of_birth: String(form.get("date_of_birth")) || null, phone: String(form.get("phone")) || null, is_deceased: form.get("is_deceased") === "on" });
      setMembers((current) => current?.map((item) => item.id === updated.id ? updated : item) ?? []);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Could not update this family member.");
    }
  }

  async function remove(member: FamilyMember) {
    try {
      await removeFamilyMember(member.id);
      setMembers((current) => current?.filter((item) => item.id !== member.id) ?? []);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Could not remove this family member.");
    }
  }

  if (error && !members) return <ErrorState message={error} onRetry={() => { setError(null); setAttempt((value) => value + 1); }} />;
  if (!members) return <LoadingState label="Loading your family…" />;

  return (
    <div className="mx-auto max-w-5xl py-2 sm:py-3">
      <header className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-700">Household</p>
        <h1 className="mt-2 text-3xl font-bold text-slate-950 sm:text-4xl">My Family</h1>
        <p className="mt-3 text-sm text-slate-600">People connected to your services and the cases you coordinate for them.</p>
      </header>
      {error ? <p className="mt-4 rounded-xl bg-rose-50 p-4 text-sm text-rose-800">{error}</p> : null}
      {members.length ? (
        <ul className="mt-8 space-y-4">
          {members.map((member) => {
            const linkedCases = cases.filter((item) => item.subject?.person_id === member.id);
            const activeCases = linkedCases.filter((item) => item.status !== "completed" && item.status !== "abandoned");
            const verified = member.source === "intake" && linkedCases.some((item) => item.status === "completed");
            const pendingVerification = member.source === "intake" && !verified;
            return (
              <li className={`rounded-2xl border p-5 shadow-sm ${pendingVerification ? "border-amber-300 bg-amber-50" : verified ? "border-emerald-300 bg-emerald-50" : "border-slate-200 bg-white"}`} key={member.id}>
                <div className="flex flex-col justify-between gap-3 sm:flex-row">
                  <div>
                    <h2 className="text-lg font-bold text-slate-950">{member.name}{member.is_deceased ? " (Late)" : ""}</h2>
                    <p className="mt-1 text-sm capitalize text-slate-600">{member.relationship}{member.date_of_birth ? ` · ${age(member.date_of_birth)} years` : ""}</p>
                    {pendingVerification ? <p className="mt-2 inline-flex rounded-full bg-amber-200 px-3 py-1 text-xs font-bold text-amber-950">Pending identity and certificate verification</p> : null}
                    {verified ? <p className="mt-2 inline-flex rounded-full bg-emerald-200 px-3 py-1 text-xs font-bold text-emerald-950">Verified through completed workflow ✓</p> : null}
                    <p className="mt-2 text-sm text-slate-600">{activeCases.length ? `Active cases: ${activeCases.length} (${activeCases.map((item) => item.title).join(", ")})` : "No active cases"}</p>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-2">
                    <span className="text-xs text-slate-500">Added {formatDate(member.created_at)} · {member.source === "intake" ? "From intake" : "Self-asserted"}</span>
                    <Link className="text-sm font-bold text-teal-700 hover:text-teal-900" href={`/family/${member.id}`}>View details →</Link>
                  </div>
                </div>
                <details className="mt-4 border-t border-slate-100 pt-4">
                  <summary className="cursor-pointer text-sm font-bold text-teal-800">View details and edit</summary>
                  <p className="mt-3 text-sm text-slate-600">Your authority: Case Coordinator for linked cases. Financial transactions and legal declarations require the person or their legal guardian.</p>
                  <MemberForm member={member} onSubmit={(event) => void edit(member, event)} />
                  <button className="mt-3 text-sm font-bold text-rose-700" onClick={() => void remove(member)} type="button">Remove from family</button>
                </details>
              </li>
            );
          })}
        </ul>
      ) : <div className="mt-8"><EmptyState title="Add people you help" description="Add family members when you need to manage services involving them. You can also add them anytime." action={{ label: "+ Add family member", href: "/family#add-family" }} /></div>}
      <details className="mt-6 rounded-2xl border border-teal-200 bg-teal-50 p-5" id="add-family" open={!members.length}>
        <summary className="cursor-pointer font-bold text-teal-900">+ Add a family member</summary>
        <MemberForm onSubmit={(event) => void add(event)} />
      </details>
    </div>
  );
}

function MemberForm({ member, onSubmit }: { member?: FamilyMember; onSubmit: (event: FormEvent<HTMLFormElement>) => void }) {
  return (
    <form className="mt-4 grid gap-3 sm:grid-cols-2" onSubmit={onSubmit}>
      <label className="text-sm font-semibold text-slate-700">Name<input className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2" defaultValue={member?.name} name="name" required /></label>
      <label className="text-sm font-semibold text-slate-700">Relationship<select className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2" defaultValue={member?.relationship ?? "parent"} name="relationship"><option value="parent">Parent</option><option value="spouse">Spouse</option><option value="sibling">Sibling</option><option value="child">Child</option><option value="mother">Mother</option><option value="father">Father</option></select></label>
      <label className="text-sm font-semibold text-slate-700">Date of birth (optional)<input className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2" defaultValue={member?.date_of_birth ?? ""} name="date_of_birth" type="date" /></label>
      <label className="text-sm font-semibold text-slate-700">Phone for invitation (optional)<input className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2" defaultValue={member?.phone ?? ""} name="phone" type="tel" /></label>
      <label className="flex items-center gap-2 text-sm text-slate-700"><input defaultChecked={member?.is_deceased} name="is_deceased" type="checkbox" /> Mark as deceased</label>
      <button className="rounded-xl bg-teal-700 px-4 py-2 text-sm font-bold text-white" type="submit">{member ? "Save changes" : "Add family member"}</button>
    </form>
  );
}

function age(dateOfBirth: string): number {
  const born = new Date(`${dateOfBirth}T00:00:00`);
  const today = new Date();
  return today.getFullYear() - born.getFullYear() - (today < new Date(today.getFullYear(), born.getMonth(), born.getDate()) ? 1 : 0);
}
