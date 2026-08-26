import Link from "next/link";

export default function Home() {
  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="mx-auto flex max-w-7xl items-center justify-between px-5 py-5 sm:px-8">
        <Link className="flex items-center gap-3 font-bold" href="/"><span className="grid size-10 place-items-center rounded-xl bg-teal-600 text-sm">CB</span>Citizen Bridge</Link>
        <div className="flex items-center gap-2"><Link className="rounded-xl px-4 py-2.5 text-sm font-bold hover:bg-white/10" href="/login">Log in</Link><Link className="rounded-xl bg-teal-500 px-4 py-2.5 text-sm font-bold text-slate-950 hover:bg-teal-400" href="/register">Register</Link></div>
      </header>
      <section className="mx-auto grid max-w-7xl gap-12 px-5 py-20 sm:px-8 lg:grid-cols-[1.2fr_0.8fr] lg:items-center lg:py-28">
        <div><p className="text-sm font-bold uppercase tracking-[0.18em] text-teal-300">Government services, made clearer</p><h1 className="mt-5 max-w-3xl text-4xl font-bold tracking-tight sm:text-6xl">One place for services, documents, benefits, and family.</h1><p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">Tell us what changed in your life. Citizen Bridge organizes the government steps and helps you move through them with confidence.</p><div className="mt-9 flex flex-wrap gap-3"><Link className="rounded-xl bg-teal-500 px-6 py-3.5 font-bold text-slate-950 hover:bg-teal-400" href="/register">Create an account</Link><Link className="rounded-xl border border-white/20 px-6 py-3.5 font-bold hover:bg-white/10" href="/login">Log in with phone</Link></div></div>
        <div className="grid gap-4 rounded-3xl border border-white/10 bg-white/5 p-6 sm:grid-cols-2"><Feature title="Clear next steps" text="See what is ready, waiting, or blocked."/><Feature title="Reusable documents" text="Keep records together across services."/><Feature title="Benefit discovery" text="Find support matched to your profile."/><Feature title="Family coordination" text="Manage services for people you help."/></div>
      </section>
    </main>
  );
}

function Feature({ title, text }: { title: string; text: string }) {
  return <article className="rounded-2xl bg-white p-5 text-slate-950"><span aria-hidden="true" className="text-teal-700">✓</span><h2 className="mt-3 font-bold">{title}</h2><p className="mt-1 text-sm leading-6 text-slate-600">{text}</p></article>;
}
