import { FormEvent, useEffect, useState } from "react";

import { addFamilyMember, getFamily } from "@/lib/api";
import type { IntakeHouseholdProfile } from "@/types/api";
import type { FamilyMember } from "@/types/api";

interface ProfileSummaryProps {
  profile: IntakeHouseholdProfile;
  busy: boolean;
  error: string | null;
  categoryId?: string;
  onConfirm: (subject?: "self" | FamilyMember | null) => void;
  onClarify: () => void;
}

export function ProfileSummary({
  profile,
  busy,
  categoryId = "bereavement",
  error,
  onConfirm,
  onClarify,
}: ProfileSummaryProps) {
  const [family, setFamily] = useState<FamilyMember[]>([]);
  const [subject, setSubject] = useState("self");
  const inferred = categoryId === "bereavement";
  useEffect(() => {
    if (!inferred) void getFamily().then(setFamily);
  }, [inferred]);

  async function addInline(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const member = await addFamilyMember({
      name: String(form.get("name")),
      relationship: String(form.get("relationship")),
      source: "manual",
    });
    setFamily((current) => [...current, member]);
    setSubject(member.id);
    event.currentTarget.reset();
  }
  const assets = [
    ["BESCOM connection", profile.assets.bescom],
    ["Ration card", profile.assets.ration_card],
    ["Property", profile.assets.property],
  ] as const;

  return (
    <section aria-labelledby="profile-summary-heading" className="p-5 sm:p-8">
      <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-700">
        Ready to review
      </p>
      <h2
        id="profile-summary-heading"
        className="mt-2 text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl"
      >
        Here&apos;s what I understood
      </h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
        Please check these details before I create your family&apos;s service plan.
      </p>

      <div className="mt-7 grid gap-4 sm:grid-cols-2">
        {!inferred ? (
          <fieldset className="rounded-2xl border border-teal-200 bg-teal-50 p-5 sm:col-span-2">
            <legend className="px-1 font-bold text-slate-950">Who is this service for?</legend>
            <label className="mt-3 flex gap-2 text-sm"><input checked={subject === "self"} name="subject" onChange={() => setSubject("self")} type="radio" /> For me</label>
            {family.map((member) => <label className="mt-2 flex gap-2 text-sm" key={member.id}><input checked={subject === member.id} name="subject" onChange={() => setSubject(member.id)} type="radio" /> {member.name} ({member.relationship})</label>)}
            <details className="mt-3">
              <summary className="cursor-pointer text-sm font-bold text-teal-800">+ Add a family member or someone else</summary>
              <form className="mt-3 flex flex-col gap-2 sm:flex-row" onSubmit={(event) => void addInline(event)}>
                <input aria-label="Person name" className="rounded-xl border border-slate-300 px-3 py-2 text-sm" name="name" placeholder="Name" required />
                <input aria-label="Relationship" className="rounded-xl border border-slate-300 px-3 py-2 text-sm" name="relationship" placeholder="Relationship" required />
                <button className="rounded-xl bg-teal-700 px-4 py-2 text-sm font-bold text-white" type="submit">Add and select</button>
              </form>
            </details>
          </fieldset>
        ) : null}
        <article className="rounded-2xl border border-stone-200 bg-stone-50 p-5">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-stone-500">Deceased</p>
          <h3 className="mt-2 text-lg font-bold text-slate-950">{profile.deceased.name}</h3>
          <p className="mt-1 text-sm capitalize text-slate-600">
            {profile.deceased.relationship} · {profile.deceased.occupation}
          </p>
          <p className="mt-3 text-sm text-slate-600">
            Pension: <span className="font-semibold capitalize">{profile.deceased.pension_status}</span>
          </p>
        </article>

        <article className="rounded-2xl border border-stone-200 bg-stone-50 p-5">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-stone-500">Location</p>
          <h3 className="mt-2 text-lg font-bold text-slate-950">
            {profile.location.city}, {profile.location.state}
          </h3>
          <p className="mt-3 text-sm text-slate-600">
            Services will be matched to this location.
          </p>
        </article>

        <article className="rounded-2xl border border-stone-200 bg-stone-50 p-5 sm:col-span-2">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-stone-500">
            Surviving household
          </p>
          <ul className="mt-3 grid gap-2 sm:grid-cols-2">
            {profile.surviving_members.map((member, index) => (
              <li className="rounded-xl bg-white px-4 py-3 text-sm text-slate-700" key={`${member.name}-${index}`}>
                <span className="font-bold text-slate-950">{member.name}</span>
                <span className="capitalize"> · {member.relationship}</span>
              </li>
            ))}
          </ul>
        </article>

        <article className="rounded-2xl border border-stone-200 bg-stone-50 p-5 sm:col-span-2">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-stone-500">
            Connections and assets
          </p>
          <ul className="mt-3 flex flex-wrap gap-2">
            {assets.map(([label, present]) => (
              <li
                className={`rounded-full px-3 py-1.5 text-sm font-semibold ${
                  present ? "bg-teal-100 text-teal-900" : "bg-stone-200 text-stone-600"
                }`}
                key={label}
              >
                {present ? "✅" : "☐"} {label}
              </li>
            ))}
          </ul>
        </article>
      </div>

      {error ? (
        <p className="mt-5 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-800" role="alert">
          {error}
        </p>
      ) : null}

      <div className="mt-7 flex flex-col gap-3 sm:flex-row">
        <button
          className="rounded-xl bg-teal-800 px-5 py-3 text-sm font-bold text-white transition hover:bg-teal-700 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2 disabled:cursor-wait disabled:opacity-60"
          disabled={busy}
          onClick={() => onConfirm(inferred ? null : subject === "self" ? "self" : family.find((member) => member.id === subject))}
          type="button"
        >
          {busy ? "Creating your plan…" : "Looks correct, create my plan"}
        </button>
        <button
          className="rounded-xl px-5 py-3 text-sm font-bold text-slate-700 transition hover:bg-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-600 focus:ring-offset-2 disabled:opacity-60"
          disabled={busy}
          onClick={onClarify}
          type="button"
        >
          Something&apos;s wrong, let me clarify
        </button>
      </div>
    </section>
  );
}
