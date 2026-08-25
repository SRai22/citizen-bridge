import Link from "next/link";

export default function DataControlsPage() {
  return (
    <div className="mx-auto max-w-2xl py-2 sm:py-3">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-700">Settings</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">My Data Controls</h1>
        <p className="mt-3 text-sm text-slate-500">
          You control your data. Every action here is logged in your{" "}
          <Link className="font-bold text-teal-700 hover:text-teal-900" href="/activity">
            activity log
          </Link>
          .
        </p>
      </section>

      <div className="mt-6 divide-y divide-slate-100 overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <ControlRow
          title="Download my data"
          description="Export all your profile, documents, and activity history as a file."
          action="Download"
          comingSoon
        />
        <ControlRow
          title="Revoke document sharing"
          description="See and revoke active sharing permissions for your documents."
          action="Manage sharing"
          comingSoon
        />
        <ControlRow
          title="Withdraw active applications"
          description="Withdraw applications that haven't been processed yet."
          action="Withdraw"
          comingSoon
        />
        <ControlRow
          title="Delete my account"
          description="Permanently delete your account and all platform data. Government submissions already made cannot be recalled."
          action="Delete account"
          destructive
          comingSoon
        />
      </div>

      <p className="mt-4 text-center text-xs text-slate-400">
        Full data controls are coming in a future update. Activity log and document provenance are available now.
      </p>
    </div>
  );
}

function ControlRow({
  action,
  comingSoon,
  description,
  destructive,
  title,
}: {
  action: string;
  comingSoon?: boolean;
  description: string;
  destructive?: boolean;
  title: string;
}) {
  return (
    <div className="flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <p className={`font-bold ${destructive ? "text-red-700" : "text-slate-950"}`}>{title}</p>
        <p className="mt-1 text-sm text-slate-500">{description}</p>
        {comingSoon ? (
          <span className="mt-2 inline-block rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-500">
            Coming soon
          </span>
        ) : null}
      </div>
      <button
        className={`shrink-0 cursor-not-allowed rounded-xl px-4 py-2.5 text-sm font-bold opacity-50 ${
          destructive
            ? "border border-red-200 text-red-700"
            : "border border-slate-200 text-slate-700"
        }`}
        disabled
        type="button"
      >
        {action}
      </button>
    </div>
  );
}
