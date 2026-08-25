"use client";

import { ErrorState } from "@/components/page-state";

export default function AppError({ retry }: { retry: () => void }) {
  return (
    <div className="mx-auto max-w-5xl py-2 sm:py-3">
      <ErrorState message="Something unexpected went wrong." onRetry={retry} />
    </div>
  );
}
