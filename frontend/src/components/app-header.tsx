"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";

import { resetDemo, seedDemo } from "@/lib/api";

export function AppHeader() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  const handleReset = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    try {
      await resetDemo();
      router.push("/");
      router.refresh();
    } catch {
      // best-effort — the page will still navigate
    } finally {
      setBusy(false);
    }
  }, [busy, router]);

  const handleSeed = useCallback(
    async (state: "initial" | "after_death_cert" | "after_bescom_rejection") => {
      if (busy) return;
      setBusy(true);
      try {
        await resetDemo();
        const result = await seedDemo(state);
        router.push(`/case/${result.case_id}`);
      } catch {
        // If seed fails after reset, go to intake
        router.push("/");
        router.refresh();
      } finally {
        setBusy(false);
      }
    },
    [busy, router],
  );

  return (
    <header className="border-b border-slate-200/80 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-5 py-4 sm:px-8">
        <Link className="flex items-center gap-3 font-bold tracking-tight text-slate-950" href="/">
          <span className="grid size-9 place-items-center rounded-xl bg-cyan-700 text-sm text-white">
            CB
          </span>
          Citizen Bridge
        </Link>
        <div className="flex items-center gap-2">
          <div className="relative group">
            <button
              onClick={() => handleSeed("initial")}
              disabled={busy}
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-cyan-300 hover:text-cyan-700 disabled:opacity-50"
            >
              {busy ? "…" : "Seed"}
            </button>
            <div className="invisible absolute right-0 top-full z-10 mt-1 flex min-w-40 flex-col gap-0.5 rounded-lg border border-slate-200 bg-white p-1 shadow-lg group-hover:visible">
              <button onClick={() => handleSeed("initial")} className="rounded-md px-3 py-1.5 text-left text-xs text-slate-700 hover:bg-slate-50">Fresh start</button>
              <button onClick={() => handleSeed("after_death_cert")} className="rounded-md px-3 py-1.5 text-left text-xs text-slate-700 hover:bg-slate-50">After death cert</button>
              <button onClick={() => handleSeed("after_bescom_rejection")} className="rounded-md px-3 py-1.5 text-left text-xs text-slate-700 hover:bg-slate-50">After BESCOM rejection</button>
            </div>
          </div>
          <button
            onClick={handleReset}
            disabled={busy}
            className="rounded-lg border border-rose-200 bg-white px-3 py-1.5 text-xs font-semibold text-rose-600 transition hover:border-rose-300 hover:bg-rose-50 disabled:opacity-50"
          >
            {busy ? "…" : "Reset"}
          </button>
        </div>
      </div>
    </header>
  );
}
