export function LoadingState({ label }: { label: string }) {
  return (
    <div className="grid min-h-[55vh] place-items-center" role="status">
      <div className="text-center">
        <span className="mx-auto block size-8 animate-spin rounded-full border-2 border-slate-200 border-t-cyan-700" />
        <p className="mt-4 text-sm font-medium text-slate-600">{label}</p>
      </div>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="mx-auto mt-20 max-w-lg rounded-3xl border border-rose-200 bg-white p-8 text-center shadow-sm">
      <span className="mx-auto grid size-11 place-items-center rounded-full bg-rose-50 text-xl text-rose-700">
        !
      </span>
      <h1 className="mt-4 text-xl font-bold text-slate-950">We couldn&apos;t load this page</h1>
      <p className="mt-2 text-sm leading-6 text-slate-600">{message}</p>
      <button
        className="mt-6 rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-cyan-600 focus:ring-offset-2"
        onClick={onRetry}
        type="button"
      >
        Try again
      </button>
    </div>
  );
}
