"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ErrorState, LoadingState } from "@/components/page-state";
import {
  ApiError,
  applyForBenefit,
  getActiveBenefits,
  getBenefitOpportunities,
} from "@/lib/api";
import { formatDate } from "@/lib/presentation";
import type { ActiveBenefit, BenefitOpportunity } from "@/types/api";

export default function BenefitsPage() {
  const router = useRouter();
  const [active, setActive] = useState<ActiveBenefit[] | null>(null);
  const [opportunities, setOpportunities] = useState<BenefitOpportunity[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [applying, setApplying] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      getActiveBenefits(controller.signal),
      getBenefitOpportunities(controller.signal),
    ])
      .then(([activeResponse, opportunityResponse]) => {
        setActive(activeResponse.benefits);
        setOpportunities(opportunityResponse.benefits);
      })
      .catch((reason: unknown) => {
        if (reason instanceof Error && reason.name === "AbortError") return;
        setError(reason instanceof ApiError ? reason.message : "Something unexpected went wrong.");
      });
    return () => controller.abort();
  }, [attempt]);

  async function apply(benefitId: string) {
    setApplying(benefitId);
    setError(null);
    try {
      const result = await applyForBenefit(benefitId);
      router.push(`/case/${result.case.case_id}`);
    } catch (reason) {
      setApplying(null);
      setError(reason instanceof ApiError ? reason.message : "The application could not be started.");
    }
  }

  if (error && (!active || !opportunities)) {
    return (
      <ErrorState
        message={error}
        onRetry={() => {
          setError(null);
          setActive(null);
          setOpportunities(null);
          setAttempt((value) => value + 1);
        }}
      />
    );
  }
  if (!active || !opportunities) return <LoadingState label="Checking your benefits…" />;

  return (
    <div className="mx-auto max-w-5xl py-2 sm:py-3">
      <header className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-700">Eligibility</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">My Benefits</h1>
        <p className="mt-3 text-sm text-slate-500">
          Track support you receive and discover schemes matched to your verified information.
        </p>
      </header>

      {error ? <p className="mt-5 rounded-xl bg-red-50 p-4 text-sm text-red-800">{error}</p> : null}

      <section className="mt-8" aria-labelledby="active-benefits">
        <h2 id="active-benefits" className="text-xl font-bold text-slate-950">Active benefits</h2>
        {active.length ? (
          <ul className="mt-3 grid gap-4 sm:grid-cols-2">
            {active.map((benefit) => (
              <li key={benefit.benefit_id} className="rounded-2xl border border-teal-200 bg-teal-50 p-5">
                <div className="flex items-start justify-between gap-3">
                  <h3 className="font-bold text-slate-950">{benefit.name}</h3>
                  <span className="rounded-full bg-white px-2 py-1 text-xs font-bold capitalize text-teal-800">{benefit.status}</span>
                </div>
                <p className="mt-2 text-lg font-bold text-teal-900">{benefit.amount}</p>
                <p className="mt-2 text-sm text-slate-600">Since {formatDate(benefit.started_at)} · {benefit.authority}</p>
                {benefit.next_payment_at ? <p className="mt-1 text-sm text-slate-600">Next payment {formatDate(benefit.next_payment_at)}</p> : null}
                <Link className="mt-4 inline-block text-sm font-bold text-teal-800" href={`/case/${benefit.case_id}`}>View case →</Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600">You do not have any active benefits yet. Ready applications will appear below.</p>
        )}
      </section>

      <section className="mt-8" aria-labelledby="benefit-opportunities">
        <h2 id="benefit-opportunities" className="text-xl font-bold text-slate-950">Opportunities for you</h2>
        {opportunities.length ? (
          <ul className="mt-3 space-y-4">
            {opportunities.map((benefit) => (
              <OpportunityCard applying={applying === benefit.id} benefit={benefit} key={benefit.id} onApply={() => void apply(benefit.id)} />
            ))}
          </ul>
        ) : (
          <div className="mt-3 rounded-2xl border border-slate-200 bg-white p-6">
            <p className="font-bold text-slate-950">No matches yet</p>
            <p className="mt-1 text-sm text-slate-600">Add more profile details so we can check additional schemes.</p>
            <Link className="mt-4 inline-block text-sm font-bold text-teal-700" href="/onboarding">Complete your profile →</Link>
          </div>
        )}
      </section>
    </div>
  );
}

function OpportunityCard({ benefit, applying, onApply }: { benefit: BenefitOpportunity; applying: boolean; onApply: () => void }) {
  const ready = benefit.readiness.percentage === 100;
  return (
    <li className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col justify-between gap-4 sm:flex-row">
        <div>
          <h3 className="font-bold text-slate-950">{benefit.name}</h3>
          <p className="mt-1 text-sm text-slate-600">{benefit.description}</p>
          <p className="mt-2 font-bold text-teal-800">{benefit.amount}</p>
          <p className="mt-1 text-xs text-slate-500">{benefit.source}</p>
        </div>
        {ready ? (
          <button className="h-fit shrink-0 rounded-xl bg-teal-700 px-5 py-2.5 text-sm font-bold text-white disabled:opacity-60" disabled={applying} onClick={onApply} type="button">{applying ? "Starting…" : "Apply now"}</button>
        ) : (
          <Link className="h-fit shrink-0 rounded-xl border border-teal-700 px-5 py-2.5 text-sm font-bold text-teal-800" href="/onboarding">Complete requirements</Link>
        )}
      </div>
      <div className="mt-5">
        <div className="flex justify-between text-sm"><span>Application readiness</span><strong>{benefit.readiness.percentage}%</strong></div>
        <div aria-label={`${benefit.name} readiness`} aria-valuemax={100} aria-valuemin={0} aria-valuenow={benefit.readiness.percentage} className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200" role="progressbar">
          <div className="h-full rounded-full bg-teal-600" style={{ width: `${benefit.readiness.percentage}%` }} />
        </div>
      </div>
      <details className="mt-4 text-sm">
        <summary className="cursor-pointer font-bold text-teal-800">Why this match and what is missing</summary>
        <ul className="mt-3 space-y-2 text-slate-600">
          {benefit.eligibility.rule_results.map((rule) => (
            <li key={rule.field}>
              <span className="font-semibold capitalize">{rule.field.replaceAll("_", " ")}</span>: {rule.status}
              {rule.source ? ` · ${rule.source.type.replaceAll("_", " ")}${rule.source.verified ? " (verified)" : ""}` : ""}
            </li>
          ))}
          {benefit.readiness.documents.missing.map((document) => <li key={document}>Missing document: {document.replaceAll("_", " ")}</li>)}
        </ul>
        {benefit.readiness.documents.missing.length ? <Link className="mt-3 inline-block font-bold text-teal-700" href="/documents">Add documents →</Link> : null}
      </details>
    </li>
  );
}
