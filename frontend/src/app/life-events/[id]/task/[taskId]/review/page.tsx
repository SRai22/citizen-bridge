import { ApprovalReview } from "@/components/approval-review";

export default async function ApprovalReviewPage({ params, searchParams }: {
  params: Promise<{ id: string; taskId: string }>;
  searchParams: Promise<{ approval?: string }>;
}) {
  const [{ id, taskId }, { approval }] = await Promise.all([params, searchParams]);
  return <ApprovalReview approvalId={approval} caseId={id} taskId={taskId} />;
}
