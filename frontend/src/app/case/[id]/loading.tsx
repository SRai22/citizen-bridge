import { AppHeader } from "@/components/app-header";
import { LoadingState } from "@/components/page-state";

export default function CaseLoading() {
  return (
    <div className="min-h-screen">
      <AppHeader />
      <main className="mx-auto max-w-5xl px-5 py-8 sm:px-8 sm:py-12">
        <LoadingState label="Loading your case…" />
      </main>
    </div>
  );
}
