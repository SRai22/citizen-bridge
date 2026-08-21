import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { citizenCase, taskDetail } from "@/test/fixtures";
import type {
  ApprovalRequest,
  ExternalApplication,
  RejectionInterpretation,
  TaskDetail,
} from "@/types/api";

import TaskDetailPage from "./page";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "case-12345678", taskId: "task-pension" }),
  useRouter: () => ({ push }),
}));

afterEach(() => {
  push.mockReset();
  vi.restoreAllMocks();
});

const approval: ApprovalRequest = {
  id: "approval-1",
  created_at: "2026-08-15T12:00:00Z",
  updated_at: "2026-08-15T12:00:00Z",
  task_id: "task-pension",
  action_description: "Submit death registration",
  status: "pending",
  context: {
    summary: "Review and submit the death registration to BBMP.",
    input_data: {},
  },
  requested_at: "2026-08-15T12:00:00Z",
  resolved_at: null,
};

const approvedApplication: ExternalApplication = {
  id: "application-1",
  created_at: "2026-08-15T12:00:00Z",
  updated_at: "2026-08-15T12:00:00Z",
  task_id: "task-pension",
  adapter_type: "death_certificate",
  external_reference_id: "BBMP/D/2026/ABC12345",
  status: "approved",
  request_payload: {},
  response_payload: { message: "Certificate issued", data: {} },
  submitted_at: "2026-08-15T12:00:00Z",
  responded_at: "2026-08-15T12:00:01Z",
};

const readyDeathTask: TaskDetail = {
  ...taskDetail,
  status: "ready",
  workflow_id: "death_certificate",
  task_type: "death_registration",
  title: "Register Death and Obtain Certificate",
  dependencies: [],
  input_data: {},
  required_documents: [],
};

const interpretation: RejectionInterpretation = {
  cause: "missing_legal_heir_certificate",
  explanation:
    "BESCOM requires a Legal Heir Certificate before the electricity account can be transferred.",
  confidence: 0.99,
  remediation: {
    action: "add_task",
    workflow_id: "legal_heir_certificate",
    dependency_target: "bescom_transfer",
  },
};

test("fetches and renders full task details", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const payload = url.endsWith("/tasks/task-pension") ? taskDetail : citizenCase;
    return new Response(JSON.stringify(payload), {
      headers: { "Content-Type": "application/json" },
    });
  });

  render(<TaskDetailPage />);

  expect(screen.getByRole("status")).toHaveTextContent("Loading task details");
  expect(
    await screen.findByRole("heading", { name: "Apply for Family Pension" }),
  ).toBeInTheDocument();
  expect(screen.getByText(taskDetail.description!)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Required documents" })).toBeInTheDocument();
  expect(screen.getByText("Death Certificate")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Dependencies" })).toBeInTheDocument();
  expect(screen.getByText("Obtain Death Certificate")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Back to case" })).toHaveAttribute(
    "href",
    "/case/case-12345678",
  );
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

test("prepares, confirms, and refreshes a completed submission", async () => {
  let currentTask = readyDeathTask;
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (method === "PATCH") return Response.json(currentTask);
    if (url.endsWith("/prepare")) {
      currentTask = { ...currentTask, status: "awaiting_approval", approval_requests: [approval] };
      return Response.json(approval);
    }
    if (url.endsWith("/approve")) {
      currentTask = {
        ...currentTask,
        status: "completed",
        completed_at: "2026-08-15T12:00:01Z",
        approval_requests: [{ ...approval, status: "approved" }],
        external_applications: [approvedApplication],
        produced_documents: [
          {
            id: "document-1",
            created_at: "2026-08-15T12:00:01Z",
            updated_at: "2026-08-15T12:00:01Z",
            case_id: citizenCase.id,
            produced_by_task_id: currentTask.id,
            document_type: "death_certificate",
            owner_name: "Arun Rao",
            issuer: "BBMP",
            issued_at: "2026-08-15T12:00:01Z",
            verification_status: "verified",
            extracted_fields: {},
            metadata: {},
          },
        ],
      };
      return Response.json(approvedApplication);
    }
    if (url.endsWith("/tasks/task-pension")) return Response.json(currentTask);
    return Response.json({ ...citizenCase, tasks: [currentTask] });
  });

  render(<TaskDetailPage />);
  await screen.findByRole("heading", { name: readyDeathTask.title });

  fireEvent.change(screen.getByLabelText("Full name of deceased"), {
    target: { value: "Arun Rao" },
  });
  fireEvent.change(screen.getByLabelText("Date of death"), {
    target: { value: "2026-08-10" },
  });
  fireEvent.change(screen.getByLabelText("Place of death"), {
    target: { value: "Bengaluru" },
  });
  fireEvent.change(screen.getByLabelText("Cause of death"), {
    target: { value: "Natural causes" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Prepare submission" }));

  const dialog = await screen.findByRole("dialog", { name: "Confirm this submission" });
  expect(dialog).toHaveTextContent("Review and submit the death registration to BBMP.");
  expect(dialog).toHaveTextContent("Arun Rao");
  expect(dialog).toHaveTextContent("Bengaluru");

  fireEvent.click(screen.getByRole("button", { name: "Approve & submit" }));

  expect(await screen.findByText("Task completed")).toBeInTheDocument();
  const documentsSection = screen.getByRole("heading", { name: "Documents" }).parentElement;
  expect(documentsSection).not.toBeNull();
  expect(within(documentsSection!).getByText("Death Certificate")).toBeInTheDocument();
  expect(screen.getByText("Submission approved and completed successfully.")).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(
    fetchMock.mock.calls.some(
      ([input, init]) => String(input).endsWith("/approve") && init?.method === "POST",
    ),
  ).toBe(true);
});

test("cancel rejects the approval and returns the task to ready", async () => {
  let currentTask = readyDeathTask;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (method === "PATCH") return Response.json(currentTask);
    if (url.endsWith("/prepare")) {
      currentTask = { ...currentTask, status: "awaiting_approval", approval_requests: [approval] };
      return Response.json(approval);
    }
    if (url.endsWith("/reject")) {
      currentTask = { ...currentTask, status: "ready", approval_requests: [] };
      return Response.json({ ...approval, status: "rejected" });
    }
    if (url.endsWith("/tasks/task-pension")) return Response.json(currentTask);
    return Response.json({ ...citizenCase, tasks: [currentTask] });
  });

  render(<TaskDetailPage />);
  await screen.findByRole("heading", { name: readyDeathTask.title });
  for (const [label, value] of [
    ["Full name of deceased", "Arun Rao"],
    ["Date of death", "2026-08-10"],
    ["Place of death", "Bengaluru"],
    ["Cause of death", "Natural causes"],
  ]) {
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  }
  fireEvent.click(screen.getByRole("button", { name: "Prepare submission" }));
  await screen.findByRole("dialog");
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(screen.getByText(/Submission cancelled/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Prepare submission" })).toBeEnabled();
});

test("explains a rejection and accepts the proposed remediation", async () => {
  const failedTask: TaskDetail = {
    ...readyDeathTask,
    status: "failed",
    external_applications: [
      {
        ...approvedApplication,
        status: "rejected",
        response_payload: { message: "A Legal Heir Certificate is required.", data: {} },
      },
    ],
  };
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/interpret-rejection")) return Response.json(interpretation);
    if (url.endsWith("/accept-remediation")) return Response.json(citizenCase);
    return Response.json(url.endsWith("/tasks/task-pension") ? failedTask : citizenCase);
  });

  render(<TaskDetailPage />);

  expect(await screen.findByText("Submission needs attention")).toBeInTheDocument();
  expect(screen.getByText("A Legal Heir Certificate is required.")).toBeInTheDocument();
  expect(await screen.findByRole("heading", { name: "System Analysis" })).toBeInTheDocument();
  expect(await screen.findByText(interpretation.explanation)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Proposed Action" })).toBeInTheDocument();
  expect(screen.getByText(/Obtain Legal Heir Certificate/)).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Accept Recommendation" }));

  await waitFor(() => expect(push).toHaveBeenCalledWith("/case/case-12345678"));
  const acceptance = fetchMock.mock.calls.find(([input]) =>
    String(input).endsWith("/accept-remediation"),
  );
  expect(acceptance?.[1]).toEqual(
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify(interpretation.remediation),
    }),
  );
});

test("dismisses the recommendation without changing the failed task", async () => {
  const failedTask: TaskDetail = {
    ...readyDeathTask,
    status: "failed",
    external_applications: [
      {
        ...approvedApplication,
        status: "rejected",
        response_payload: { message: "A Legal Heir Certificate is required.", data: {} },
      },
    ],
  };
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/interpret-rejection")) return Response.json(interpretation);
    return Response.json(url.endsWith("/tasks/task-pension") ? failedTask : citizenCase);
  });

  render(<TaskDetailPage />);
  await screen.findByRole("heading", { name: "Proposed Action" });
  fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));

  expect(screen.queryByRole("heading", { name: "System Analysis" })).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Proposed Action" })).not.toBeInTheDocument();
  expect(screen.getByText("A Legal Heir Certificate is required.")).toBeInTheDocument();
  expect(
    fetchMock.mock.calls.some(([input]) => String(input).endsWith("/accept-remediation")),
  ).toBe(false);
  expect(push).not.toHaveBeenCalled();
});
