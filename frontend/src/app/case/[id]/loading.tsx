import { LoadingState } from "@/components/page-state";

export default function CaseLoading() {
  return (
    <div className="mx-auto max-w-5xl py-2 sm:py-3">
      <LoadingState label="Loading your case…" />
    </div>
  );
}
