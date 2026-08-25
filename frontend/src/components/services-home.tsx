"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { IntakeChat } from "@/components/intake-chat";
import { ErrorState, LoadingState } from "@/components/page-state";
import { ApiError, getCategories, getSession } from "@/lib/api";
import type { AuthSession, LifeEventCategory } from "@/types/api";

export function ServicesHome() {
  const router = useRouter();
  const [session, setSession] = useState<AuthSession | null>(null);
  const [categories, setCategories] = useState<LifeEventCategory[]>([]);
  const [intakeOpen, setIntakeOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([getSession(controller.signal), getCategories()])
      .then(([currentSession, response]) => {
        if (!currentSession.name || !currentSession.date_of_birth || !currentSession.city) {
          router.replace("/onboarding");
          return;
        }
        setSession(currentSession);
        setCategories(response.categories);
      })
      .catch((reason: unknown) => {
        if (reason instanceof Error && reason.name === "AbortError") return;
        if (reason instanceof ApiError && reason.status === 401) {
          router.replace("/onboarding");
          return;
        }
        setError(
          reason instanceof ApiError ? reason.message : "Something unexpected went wrong.",
        );
      });
    return () => controller.abort();
  }, [attempt, router]);

  if (error) {
    return (
      <ErrorState
        message={error}
        onRetry={() => {
          setError(null);
          setAttempt((value) => value + 1);
        }}
      />
    );
  }
  if (!session) return <LoadingState label="Loading your services…" />;
  if (intakeOpen) {
    return (
      <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <IntakeChat />
      </div>
    );
  }

  return (
    <>
      <section className="overflow-hidden rounded-3xl bg-slate-950 px-6 py-8 text-white shadow-lg sm:px-9 sm:py-10">
        <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-300">
          My Services
        </p>
        <h1 className="mt-3 max-w-2xl text-3xl font-bold tracking-tight sm:text-4xl">
          Welcome, {session.name}
        </h1>
        <p className="mt-3 max-w-2xl text-base leading-7 text-slate-300">
          Tell us what changed. Citizen Bridge will organize the services, documents, and next
          steps into one clear plan.
        </p>
      </section>

      <section className="mt-8" aria-labelledby="start-service-heading">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-700">
              Start a service
            </p>
            <h2 className="mt-1 text-2xl font-bold text-slate-950" id="start-service-heading">
              What changed in your life?
            </h2>
          </div>
        </div>
        <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {categories.map((category) => (
            <button
              className="group rounded-2xl border border-slate-200 bg-white p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-teal-500 hover:shadow-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700"
              key={category.id}
              onClick={() => setIntakeOpen(true)}
              type="button"
            >
              <span className="text-lg font-bold text-slate-950 group-hover:text-teal-800">
                {category.title}
              </span>
              <span className="mt-2 block text-sm leading-6 text-slate-600">
                {category.description}
              </span>
            </button>
          ))}
        </div>
      </section>
    </>
  );
}
