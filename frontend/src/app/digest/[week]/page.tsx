import { DigestView } from "@/components/digest-view";

interface PageProps {
  params: Promise<{ week: string }>;
}

export default async function HistoricalDigestPage({ params }: PageProps) {
  const { week } = await params;
  return <DigestView week={week} />;
}
