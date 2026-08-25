import { formatDate, formatDateTime } from "@/lib/presentation";
import type { CaseTask } from "@/types/api";

export function WaitingState({ task }: { task: CaseTask }) {
  const wait = task.wait_state;
  if (wait?.stages_known && wait.stages.length) return <TimelineWait wait={wait} />;
  return <StatusCardWait wait={wait ?? null} />;
}

type WaitData = NonNullable<CaseTask["wait_state"]>;

function TimelineWait({ wait }: { wait: WaitData }) {
  const currentIdx = wait.stages.findIndex((s) => s.id === wait.current_stage);
  const overdue = wait.is_overdue;
  const stages = wait.stages;

  return (
    <div className="mt-4">
      <ol aria-label="Application stages" className="flex items-start">
        {stages.map((stage, idx) => {
          const done = idx < currentIdx;
          const active = idx === currentIdx;
          const last = idx === stages.length - 1;
          return (
            <li className="flex min-w-0 flex-1 flex-col items-center" key={stage.id}>
              <div className="flex w-full items-center">
                <div
                  className={`relative z-10 size-3 shrink-0 rounded-full border-2 transition-colors ${
                    done
                      ? "border-teal-600 bg-teal-600"
                      : active
                        ? overdue
                          ? "border-amber-500 bg-amber-100 ring-2 ring-amber-200"
                          : "border-teal-600 bg-teal-100 ring-2 ring-teal-100"
                        : "border-slate-300 bg-white"
                  }`}
                />
                {!last && (
                  <div
                    className={`h-0.5 flex-1 ${idx < currentIdx ? "bg-teal-600" : "bg-slate-200"}`}
                  />
                )}
              </div>
              <span
                className={`mt-1.5 max-w-[6rem] text-center text-[0.65rem] leading-tight ${
                  active
                    ? overdue
                      ? "font-bold text-amber-700"
                      : "font-bold text-teal-800"
                    : done
                      ? "text-teal-700"
                      : "text-slate-400"
                }`}
              >
                {stage.label}
              </span>
            </li>
          );
        })}
      </ol>
      <p
        className={`mt-3 text-xs ${overdue ? "font-medium text-amber-700" : "text-slate-500"}`}
      >
        {overdue
          ? "Taking longer than usual. We're monitoring this."
          : wait.estimated_wait?.max_days
            ? `Usually ${wait.estimated_wait.min_days ?? 1}–${wait.estimated_wait.max_days} working days`
            : null}
        {wait.last_update && !overdue && (
          <span className="text-slate-400"> · Updated {formatDate(wait.last_update)}</span>
        )}
      </p>
      <p className="mt-1 text-xs text-slate-400">We&apos;ll notify you when there&apos;s an update.</p>
    </div>
  );
}

function StatusCardWait({ wait }: { wait: WaitData | null }) {
  const overdue = wait?.is_overdue;
  const estimate = wait?.estimated_wait;

  return (
    <div
      className={`mt-3 rounded-xl border p-3 text-sm ${
        overdue ? "border-amber-200 bg-amber-50" : "border-slate-100 bg-slate-50"
      }`}
    >
      <p className="font-medium text-slate-700">
        Status:{" "}
        <span className={overdue ? "text-amber-700" : "text-slate-600"}>
          {wait?.status_label ?? "Processing"}
        </span>
      </p>
      {estimate?.max_days ? (
        <p className="mt-1 text-slate-500">
          Typical wait: {estimate.min_days ?? 1}–{estimate.max_days} working days
        </p>
      ) : null}
      {wait?.submitted_at ? (
        <p className="mt-1 text-slate-500">Submitted: {formatDate(wait.submitted_at)}</p>
      ) : null}
      {wait?.last_update ? (
        <p className="mt-1 text-slate-500">Last update: {formatDateTime(wait.last_update)}</p>
      ) : null}
      {overdue ? (
        <p className="mt-2 font-medium text-amber-700">
          Taking longer than usual. We&apos;re monitoring.
        </p>
      ) : null}
      <p className="mt-2 text-slate-400">📱 We&apos;ll notify you when there&apos;s an update.</p>
    </div>
  );
}
