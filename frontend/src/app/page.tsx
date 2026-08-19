"use client";

import { useEffect, useState } from "react";

type Health = { status: string };

export default function Home() {
  const [apiStatus, setApiStatus] = useState("checking");

  useEffect(() => {
    const controller = new AbortController();

    fetch("/api/health", { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("Health check failed");
        return response.json() as Promise<Health>;
      })
      .then(({ status }) => setApiStatus(status))
      .catch((error: unknown) => {
        if (error instanceof Error && error.name !== "AbortError") setApiStatus("unavailable");
      });

    return () => controller.abort();
  }, []);

  return (
    <main className="grid min-h-screen place-items-center px-6">
      <section className="max-w-xl text-center">
        <p className="mb-3 text-sm font-semibold uppercase tracking-[0.2em] text-blue-700">
          Public services, connected
        </p>
        <h1 className="text-5xl font-bold tracking-tight">Citizen Bridge</h1>
        <p className="mt-5 text-lg text-slate-600">
          Your agent across all Indian public services.
        </p>
        <p className="mt-8 text-sm text-slate-500" aria-live="polite">
          API status: {apiStatus}
        </p>
      </section>
    </main>
  );
}
