import Link from "next/link";

import type { CaseOverview } from "@/types/api";

export function CoordinatorBanner({ citizenCase }: { citizenCase: CaseOverview }) {
  if (citizenCase.my_role !== "coordinator" || !citizenCase.subject) return null;
  return (
    <aside className="rounded-2xl border border-cyan-200 bg-cyan-50 p-4 text-cyan-950" aria-label="Coordinator context">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <p className="font-bold">Acting for: {citizenCase.subject.name} ({citizenCase.subject.relationship})</p>
          <p className="mt-1 text-sm">Your role: Case Coordinator · You can gather documents, prepare information, submit, and track progress.</p>
        </div>
        <Link className="shrink-0 text-sm font-bold text-cyan-800 underline-offset-4 hover:underline" href="/">Switch to my services</Link>
      </div>
      {citizenCase.limitations.length ? (
        <p className="mt-3 border-t border-cyan-200 pt-3 text-sm">
          Some actions require the person or their legal guardian: {citizenCase.limitations.join("; ")}.
        </p>
      ) : null}
    </aside>
  );
}
