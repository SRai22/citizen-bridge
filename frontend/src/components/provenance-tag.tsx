import type { DocProvenanceType } from "@/types/api";

export function ProvenanceTag({
  type,
  source,
}: {
  type: DocProvenanceType;
  source: string | null;
}) {
  return (
    <span className="inline-block text-xs text-slate-400" title={provenanceLabel(type, source)}>
      📍 {provenanceLabel(type, source)}
    </span>
  );
}

export function provenanceLabel(type: DocProvenanceType, source: string | null): string {
  if (source) return source;
  switch (type) {
    case "digilocker":
      return "From DigiLocker (government verified)";
    case "auto_fetched":
      return "Auto-fetched";
    case "user_uploaded":
      return "Uploaded by you";
    case "platform_issued":
      return "Issued via Citizen Bridge";
  }
}
