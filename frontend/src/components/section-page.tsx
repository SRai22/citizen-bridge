export function SectionPage({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-9">
      <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-700">{eyebrow}</p>
      <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">
        {title}
      </h1>
      <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">{description}</p>
    </section>
  );
}
