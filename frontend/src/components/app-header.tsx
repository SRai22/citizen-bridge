import Link from "next/link";

export function AppHeader() {
  return (
    <header className="border-b border-slate-200/80 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-5 py-4 sm:px-8">
        <Link className="flex items-center gap-3 font-bold tracking-tight text-slate-950" href="/">
          <span className="grid size-9 place-items-center rounded-xl bg-cyan-700 text-sm text-white">
            CB
          </span>
          Citizen Bridge
        </Link>
        <span className="text-xs font-semibold uppercase tracking-[0.14em] text-teal-700">Phase 0</span>
      </div>
    </header>
  );
}
