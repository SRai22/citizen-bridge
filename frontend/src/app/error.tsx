"use client";

import { AppHeader } from "@/components/app-header";
import { ErrorState } from "@/components/page-state";

export default function AppError({ retry }: { retry: () => void }) {
  return (
    <div className="min-h-screen">
      <AppHeader />
      <main className="mx-auto max-w-5xl px-5 py-8 sm:px-8 sm:py-12">
        <ErrorState message="Something unexpected went wrong." onRetry={retry} />
      </main>
    </div>
  );
}
