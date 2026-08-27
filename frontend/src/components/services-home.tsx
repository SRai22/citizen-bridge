"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { IntakeChat } from "@/components/intake-chat";
import { EmptyState, ErrorState, LoadingState } from "@/components/page-state";
import { ApiError, getCases, getCatalogServices, getCategories, getSession } from "@/lib/api";
import type { AuthSession, CatalogService, LifeEventCategory } from "@/types/api";

const serviceGroups = [
  ["certificates", "Certificates"],
  ["utilities", "Utilities"],
  ["benefits", "Benefits & Pensions"],
  ["property", "Property"],
  ["identity", "Identity"],
] as const;

const DEMO_INTAKE_CATEGORIES = new Set(["bereavement", "new_baby", "marriage"]);

export function ServicesHome() {
  const router = useRouter();
  const [session, setSession] = useState<AuthSession | null>(null);
  const [categories, setCategories] = useState<LifeEventCategory[]>([]);
  const [services, setServices] = useState<CatalogService[]>([]);
  const [selected, setSelected] = useState<LifeEventCategory | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [browseOpen, setBrowseOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [activeCases, setActiveCases] = useState(0);
  const [showTip, setShowTip] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([getSession(controller.signal), getCategories(), getCatalogServices(), getCases(controller.signal)])
      .then(([currentSession, categoryResponse, serviceResponse, caseResponse]) => {
        if (!currentSession.name || !currentSession.date_of_birth || !currentSession.city) {
          router.replace("/onboarding");
          return;
        }
        setSession(currentSession);
        setCategories(categoryResponse.categories);
        setServices(serviceResponse.services);
        const active = caseResponse.cases.filter((item) => item.status !== "completed" && item.status !== "abandoned").length;
        setActiveCases(active);
        const tipKey = "citizen-bridge:home-tip-seen";
        if (active === 0 && !localStorage.getItem(tipKey)) {
          setShowTip(true);
          localStorage.setItem(tipKey, "true");
        }
      })
      .catch((reason: unknown) => {
        if (reason instanceof Error && reason.name === "AbortError") return;
        if (reason instanceof ApiError && reason.status === 401) {
          router.replace("/login");
          return;
        }
        setError(reason instanceof ApiError ? reason.message : "Something unexpected went wrong.");
      });
    return () => controller.abort();
  }, [attempt, router]);

  const visibleCategories = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    if (!needle) return categories;
    return categories.filter((category) =>
      `${category.title} ${category.subtitle} ${category.description}`
        .toLocaleLowerCase()
        .includes(needle),
    );
  }, [categories, query]);

  if (error) {
    return <ErrorState message={error} onRetry={() => { setError(null); setAttempt((value) => value + 1); }} />;
  }
  if (!session) return <LoadingState label="Loading your services…" />;
  if (selected && chatOpen) {
    return <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm"><IntakeChat categoryId={selected.id} /></div>;
  }
  if (selected) {
    return (
      <section className="mx-auto max-w-2xl rounded-3xl border border-slate-200 bg-white p-7 shadow-sm sm:p-10">
        <button className="text-sm font-bold text-teal-800" onClick={() => setSelected(null)} type="button">← Back to services</button>
        <CategoryIcon name={selected.icon} />
        <p className="mt-6 text-sm font-bold uppercase tracking-[0.16em] text-teal-700">Your next step</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">{selected.title}</h1>
        <p className="mt-4 text-lg leading-8 text-slate-600">We’ll help you handle {selected.title.toLocaleLowerCase()}. Let’s understand your situation.</p>
        <button
          className="mt-8 rounded-xl bg-teal-700 px-6 py-3.5 font-bold text-white hover:bg-teal-800"
          onClick={() => {
            if (DEMO_INTAKE_CATEGORIES.has(selected.id)) setChatOpen(true);
            else router.push(`/services/coming-soon/${encodeURIComponent(selected.id)}`);
          }}
          type="button"
        >
          {DEMO_INTAKE_CATEGORIES.has(selected.id)
            ? "Start conversation →"
            : "View demo availability →"}
        </button>
      </section>
    );
  }

  return (
    <>
      <section className="overflow-hidden rounded-3xl bg-slate-950 px-6 py-8 text-white shadow-lg sm:px-9 sm:py-10">
        <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-300">My Services</p>
        <h1 className="mt-3 max-w-2xl text-3xl font-bold tracking-tight sm:text-4xl">Welcome, {session.name}</h1>
        <p className="mt-3 max-w-2xl text-base leading-7 text-slate-300">Tell us what changed. Citizen Bridge will organize the services, documents, and next steps into one clear plan.</p>
        <label className="mt-7 block max-w-xl" htmlFor="service-search">
          <span className="sr-only">Search for a service</span>
          <input className="w-full rounded-xl border border-white/15 bg-white px-4 py-3 text-slate-950 outline-none placeholder:text-slate-400 focus:ring-2 focus:ring-teal-300" id="service-search" onChange={(event) => setQuery(event.target.value)} placeholder="Search for a service..." type="search" value={query} />
        </label>
      </section>

      <section className="mt-8" aria-labelledby="start-service-heading">
        <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-700">Start a service</p>
        <h2 className="mt-1 text-2xl font-bold text-slate-950" id="start-service-heading">What changed in your life?</h2>
        {activeCases === 0 ? <div className="mt-5"><EmptyState title="Browse services by life situation" description="Browse government services organized by life situation. Start when you need help." action={{ label: "Browse services", href: "/services#service-options" }} /></div> : null}
        {showTip ? <aside className="mt-5 flex items-start justify-between gap-4 rounded-2xl border border-cyan-200 bg-cyan-50 p-4 text-sm leading-6 text-cyan-950"><p>💡 <strong>Tip:</strong> Choose a life situation below to see how we can help. Most citizens start with something specific, such as family paperwork or applying for a benefit.</p><button aria-label="Dismiss tip" className="shrink-0 font-bold" onClick={() => setShowTip(false)} type="button">×</button></aside> : null}
        {visibleCategories.length ? (
          <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-4" id="service-options">
            {visibleCategories.map((category) => (
              <button className="group min-h-48 rounded-2xl border border-slate-200 bg-white p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-teal-500 hover:shadow-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700" key={category.id} onClick={() => { setShowTip(false); setSelected(category); }} type="button">
                <CategoryIcon name={category.icon} small />
                <span className="mt-4 block text-base font-bold text-slate-950 group-hover:text-teal-800 sm:text-lg">{category.title}</span>
                <span className="mt-2 block text-xs leading-5 text-slate-600 sm:text-sm">{category.subtitle}</span>
              </button>
            ))}
          </div>
        ) : <p className="mt-5 rounded-2xl border border-slate-200 bg-white p-6 text-slate-600">No life events match “{query}”. Try a service name such as pension or electricity.</p>}
      </section>

      <section className="mt-8 border-t border-slate-200 pt-6">
        <button aria-expanded={browseOpen} className="font-bold text-teal-800 hover:text-teal-950" onClick={() => setBrowseOpen((open) => !open)} type="button">{browseOpen ? "Hide service types ↑" : "Or browse by service type →"}</button>
        {browseOpen ? <ServiceBrowser categories={categories} onSelect={(cat) => { setSelected(cat); setBrowseOpen(false); }} services={services} /> : null}
      </section>
    </>
  );
}

function ServiceBrowser({
  categories,
  onSelect,
  services,
}: {
  categories: LifeEventCategory[];
  onSelect: (category: LifeEventCategory) => void;
  services: CatalogService[];
}) {
  return (
    <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {serviceGroups.map(([id, title]) => {
        const matches = services.filter((service) => service.category === id);
        return (
          <section className="rounded-2xl border border-slate-200 bg-white p-5" key={id}>
            <h3 className="font-bold text-slate-950">{title}</h3>
            {matches.length ? (
              <ul className="mt-3 space-y-2 text-sm text-slate-600">
                {matches.map((service) => {
                  const cat = categories.find((c) => c.id === service.category);
                  return (
                    <li key={service.id}>
                      {cat ? (
                        <button
                          className="text-left text-teal-700 underline-offset-2 hover:underline"
                          onClick={() => onSelect(cat)}
                          type="button"
                        >
                          {service.name}
                        </button>
                      ) : (
                        service.name
                      )}
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="mt-3 text-sm text-slate-500">More services coming soon.</p>
            )}
          </section>
        );
      })}
    </div>
  );
}

const iconPaths: Record<string, string> = {
  dove: "M4 12c5 0 6-7 9-7 0 4 3 5 7 5-3 5-8 8-16 7",
  baby: "M8 10a4 4 0 1 0 8 0M7 17c2-2 8-2 10 0",
  home: "m3 11 9-8 9 8v9h-6v-6H9v6H3z",
  briefcase: "M4 8h16v11H4zM9 8V5h6v3",
  rings: "M9 8a5 5 0 1 0 0 8M15 8a5 5 0 1 1 0 8",
  building: "M5 21V4h10v17M9 8h2m-2 4h2m-2 4h2m6 5V10h3v11",
  education: "m3 9 9-5 9 5-9 5zM7 12v5c3 2 7 2 10 0v-5",
  senior: "M12 7a2 2 0 1 0 0-4 2 2 0 0 0 0 4Zm0 2v5m0 0-4 7m4-7 4 3m-4-5-4 2",
};

function CategoryIcon({ name, small = false }: { name: string; small?: boolean }) {
  return (
    <span className={`grid ${small ? "size-10" : "mt-8 size-14"} place-items-center rounded-xl bg-teal-50 text-teal-800`}>
      <svg aria-hidden="true" className={small ? "size-6" : "size-8"} fill="none" viewBox="0 0 24 24"><path d={iconPaths[name] ?? iconPaths.home} stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" /></svg>
    </span>
  );
}
