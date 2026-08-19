import { AppHeader } from "@/components/app-header";
import { IntakeChat } from "@/components/intake-chat";

export default function Home() {
  return (
    <div className="min-h-screen">
      <AppHeader />
      <main className="mx-auto max-w-3xl px-4 py-6 sm:px-8 sm:py-10">
        <div className="overflow-hidden rounded-3xl border border-stone-200 bg-white shadow-xl shadow-slate-200/40">
          <IntakeChat />
        </div>
        <p className="mx-auto mt-5 max-w-xl text-center text-xs leading-5 text-slate-500">
          Your responses are used only to identify relevant services and build your plan.
        </p>
      </main>
    </div>
  );
}
