import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { taskDetail } from "@/test/fixtures";
import type { ApprovalRequest, ExternalApplication } from "@/types/api";

import { ApprovalReview } from "./approval-review";

const { push, router } = vi.hoisted(() => {
  const stablePush = vi.fn();
  return { push: stablePush, router: { push: stablePush } };
});
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const approval: ApprovalRequest = {
  id: "approval-1",
  created_at: "2026-08-15T12:00:00Z",
  updated_at: "2026-08-15T12:00:00Z",
  task_id: taskDetail.id,
  action_description: "Submit family pension application to Karnataka Treasury Department",
  status: "pending",
  context: { input_data: { spouse_name: "Meera Rao", ppo_number: "PPO-123", bank_account_number: "1234" } },
  requested_at: "2026-08-15T12:00:00Z",
  resolved_at: null,
};

const application: ExternalApplication = {
  id: "application-1",
  created_at: "2026-08-15T12:00:00Z",
  updated_at: "2026-08-15T12:00:01Z",
  task_id: taskDetail.id,
  adapter_type: "family_pension",
  external_reference_id: "TREASURY/PENSION/2026/1234",
  status: "approved",
  request_payload: {},
  response_payload: { message: "Approved automatically for the Citizen Bridge demo." },
  submitted_at: "2026-08-15T12:00:01Z",
  responded_at: "2026-08-15T12:00:02Z",
};

afterEach(() => {
  push.mockReset();
  vi.restoreAllMocks();
});

test("shows submission before the demo approval and offers the next step", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/requirements")) {
      return Response.json([{ ...taskDetail.required_documents[0], status: "satisfied" }]);
    }
    if (url.endsWith("/approve")) return Response.json(application);
    return Response.json({ ...taskDetail, approval_requests: [approval] });
  });

  render(<ApprovalReview approvalId={approval.id} caseId="case-123" taskId={taskDetail.id} />);

  expect(await screen.findByRole("heading", { name: "You’re about to submit:" })).toBeInTheDocument();
  expect(screen.getByText("To: Karnataka Treasury Department")).toBeInTheDocument();
  expect(screen.getByText("Meera Rao")).toBeInTheDocument();
  expect(screen.getByText(/source: your verified documents/)).toBeInTheDocument();
  expect(screen.getByText(/cannot be undone/)).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Confirm & Submit →" }));

  expect(await screen.findByRole("heading", { name: "Sent for approval" })).toBeInTheDocument();
  expect(screen.getByText(/automatically reviewing/)).toBeInTheDocument();
  expect(screen.getByText(application.external_reference_id!)).toBeInTheDocument();
  expect(
    await screen.findByRole("heading", { name: "Approved" }, { timeout: 2000 }),
  ).toBeInTheDocument();
  expect(screen.getByText(/For demo purposes/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Next →" })).toHaveAttribute(
    "href",
    "/life-events/case-123",
  );
});

test("cancels the pending approval and returns to the task", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/requirements")) return Response.json([]);
    if (url.endsWith("/reject")) return Response.json({ ...approval, status: "rejected" });
    return Response.json({ ...taskDetail, approval_requests: [approval] });
  });

  render(<ApprovalReview approvalId={approval.id} caseId="case-123" taskId={taskDetail.id} />);
  fireEvent.click(await screen.findByRole("button", { name: "Cancel" }));
  await waitFor(() => expect(push).toHaveBeenCalledWith(`/life-events/case-123/task/${taskDetail.id}`));
});
