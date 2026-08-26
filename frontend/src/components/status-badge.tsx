import type { CaseStatus, TaskStatus } from "@/types/api";

type Status = CaseStatus | TaskStatus;

const STATUS_CONFIG: Record<Status, { label: string; className: string; symbol?: string }> = {
  intake: {
    label: "Intake",
    className: "bg-amber-50 text-amber-800 ring-amber-200",
    symbol: "⏳",
  },
  active: { label: "Active", className: "bg-cyan-50 text-cyan-800 ring-cyan-200", symbol: "⏳" },
  abandoned: {
    label: "Closed",
    className: "bg-slate-100 text-slate-600 ring-slate-200",
    symbol: "🔴",
  },
  pending: { label: "Waiting", className: "bg-slate-100 text-slate-600 ring-slate-200", symbol: "☐" },
  ready: { label: "Ready", className: "bg-emerald-50 text-emerald-800 ring-emerald-200", symbol: "☐" },
  in_progress: {
    label: "In progress",
    className: "bg-violet-50 text-violet-800 ring-violet-200",
    symbol: "⏳",
  },
  awaiting_approval: {
    label: "Needs approval",
    className: "bg-amber-50 text-amber-800 ring-amber-200",
    symbol: "⏳",
  },
  submitted: {
    label: "Submitted",
    className: "bg-blue-50 text-blue-800 ring-blue-200",
    symbol: "⏳",
  },
  completed: {
    label: "Completed",
    className: "bg-emerald-50 text-emerald-800 ring-emerald-200",
    symbol: "✅",
  },
  failed: {
    label: "Failed",
    className: "bg-rose-50 text-rose-800 ring-rose-200",
    symbol: "🔴",
  },
  blocked: { label: "Blocked", className: "bg-rose-50 text-rose-800 ring-rose-200", symbol: "🔴" },
  cancelled: { label: "Withdrawn", className: "bg-slate-100 text-slate-600 ring-slate-200", symbol: "—" },
};

export function StatusBadge({ status }: { status: Status }) {
  const config = STATUS_CONFIG[status];
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold ring-1 ring-inset ${config.className}`}
    >
      {config.symbol ? <span aria-hidden="true">{config.symbol}</span> : null}
      {config.label}
    </span>
  );
}
