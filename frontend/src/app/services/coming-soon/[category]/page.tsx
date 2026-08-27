import Link from "next/link";

const TITLES: Record<string, string> = {
  address_change: "Moving to a New Address",
  retirement: "Lost Job or Retiring",
  property: "Property or Land",
  education: "Education",
  senior_services: "Senior Citizen Services",
};

export default async function ComingSoonPage({
  params,
}: {
  params: Promise<{ category: string }>;
}) {
  const { category } = await params;
  const title = TITLES[category] ?? "This service workflow";

  return (
    <section className="mx-auto max-w-2xl rounded-3xl border border-slate-200 bg-white p-7 shadow-sm sm:p-10">
      <p className="text-sm font-bold uppercase tracking-[0.16em] text-amber-700">
        Future scope
      </p>
      <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">
        {title}
      </h1>
      <p className="mt-4 text-lg leading-8 text-slate-600">
        This workflow will be implemented in a future release and is not part of the current
        demo.
      </p>
      <p className="mt-4 rounded-2xl bg-teal-50 p-4 text-sm leading-6 text-teal-950">
        The demo currently supports bereavement, new baby, and marriage workflows.
      </p>
      <Link
        className="mt-8 inline-flex rounded-xl bg-teal-700 px-6 py-3.5 font-bold text-white hover:bg-teal-800"
        href="/services"
      >
        ← Back to services
      </Link>
    </section>
  );
}
