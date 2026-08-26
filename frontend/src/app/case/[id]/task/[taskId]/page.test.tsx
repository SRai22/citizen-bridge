import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { citizenCase, deathCertificate, makeTask, taskDetail } from "@/test/fixtures";
import type {
  ApprovalRequest,
  ExternalApplication,
  RejectionInterpretation,
  TaskDetail,
} from "@/types/api";

import TaskDetailPage from "./page";

const { push, replace, router } = vi.hoisted(() => {
  const stablePush = vi.fn();
  const stableReplace = vi.fn();
  return { push: stablePush, replace: stableReplace, router: { push: stablePush, replace: stableReplace } };
});

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "case-12345678", taskId: "task-pension" }),
  useRouter: () => router,
}));

afterEach(() => {
  push.mockReset();
  replace.mockReset();
  vi.restoreAllMocks();
});

const approval: ApprovalRequest = {
  id: "approval-1",
  created_at: "2026-08-15T12:00:00Z",
  updated_at: "2026-08-15T12:00:00Z",
  task_id: "task-pension",
  action_description: "Submit death registration to BBMP",
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
    if (url.endsWith("/requirements")) {
      return Response.json(
        taskDetail.required_documents.map((document) => ({ ...document, status: "satisfied" })),
      );
    }
    const payload = url.endsWith("/tasks/task-pension") ? taskDetail : citizenCase;
    return Response.json(
      url.endsWith("/tasks/task-pension")
        ? payload
        : { ...citizenCase, documents: [deathCertificate] },
    );
  });

  render(<TaskDetailPage />);

  expect(screen.getByRole("status")).toHaveTextContent("Loading task details");
  expect(
    await screen.findByRole("heading", { name: "Apply for Family Pension" }),
  ).toBeInTheDocument();
  expect(screen.getByText(taskDetail.description!)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Available documents" })).toBeInTheDocument();
  expect(screen.getByText("Required: Death Certificate")).toBeInTheDocument();
  expect(screen.getByText("Available")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Dependencies" })).toBeInTheDocument();
  expect(screen.getByText("Obtain Death Certificate")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Back to case" })).toHaveAttribute(
    "href",
    "/life-events/case-12345678",
  );
  expect(fetchMock).toHaveBeenCalledTimes(3);
});

test("prepares a submission and navigates to the full-page review", async () => {
  let currentTask = readyDeathTask;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (url.endsWith("/requirements")) return Response.json([]);
    if (method === "PATCH") return Response.json(currentTask);
    if (url.endsWith("/prepare")) {
      currentTask = { ...currentTask, status: "awaiting_approval", approval_requests: [approval] };
      return Response.json(approval);
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

  await waitFor(() => expect(push).toHaveBeenCalledWith(
    "/life-events/case-12345678/task/task-pension/review?approval=approval-1",
  ));
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
    if (url.endsWith("/requirements")) return Response.json([]);
    if (url.endsWith("/interpret-rejection")) return Response.json(interpretation);
    if (url.endsWith("/accept-remediation")) return Response.json(citizenCase);
    return Response.json(url.endsWith("/tasks/task-pension") ? failedTask : citizenCase);
  });

  render(<TaskDetailPage />);

  expect(await screen.findByText("Submission needs attention")).toBeInTheDocument();
  expect(screen.getByText("A Legal Heir Certificate is required.")).toBeInTheDocument();
  expect(await screen.findByRole("heading", { name: "What happened" })).toBeInTheDocument();
  expect(await screen.findByText(interpretation.explanation)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "What you can do" })).toBeInTheDocument();
  expect(screen.getByText(/Obtain Legal Heir Certificate/)).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Add this to my plan" }));

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
    if (url.endsWith("/requirements")) return Response.json([]);
    if (url.endsWith("/interpret-rejection")) return Response.json(interpretation);
    return Response.json(url.endsWith("/tasks/task-pension") ? failedTask : citizenCase);
  });

  render(<TaskDetailPage />);
  await screen.findByRole("heading", { name: "What you can do" });
  fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));

  expect(screen.queryByRole("heading", { name: "What happened" })).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "What you can do" })).not.toBeInTheDocument();
  expect(screen.getByText("A Legal Heir Certificate is required.")).toBeInTheDocument();
  expect(
    fetchMock.mock.calls.some(([input]) => String(input).endsWith("/accept-remediation")),
  ).toBe(false);
  expect(push).not.toHaveBeenCalled();
});

test("shows a completion receipt with reference and produced document", async () => {
  const completedTask: TaskDetail = {
    ...readyDeathTask,
    status: "completed",
    completed_at: "2026-08-25T12:00:00Z",
    external_applications: [approvedApplication],
    produced_documents: [deathCertificate],
  };
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/requirements")) return Response.json([]);
    return Response.json(url.endsWith("/tasks/task-pension") ? completedTask : citizenCase);
  });

  render(<TaskDetailPage />);

  expect(await screen.findByText(`${completedTask.title} — Done`)).toBeInTheDocument();
  expect(screen.getByText(`Reference: ${approvedApplication.external_reference_id}`)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Document produced: Death Certificate →" })).toHaveAttribute("href", `/documents/${deathCertificate.id}`);
  expect(screen.getByRole("link", { name: "View receipt" })).toHaveAttribute("href", "#receipt");
});

test("shows remediation documents as missing and names their producer task", async () => {
  let legalCertificateAvailable = false;
  const legalHeirTask = makeTask({
    id: "task-legal-heir",
    title: "Obtain Legal Heir Certificate",
    workflow_id: "legal_heir_certificate",
    status: "ready",
  });
  const bescomTask: TaskDetail = {
    ...taskDetail,
    id: "task-pension",
    title: "Transfer BESCOM Electricity Account",
    workflow_id: "bescom_transfer",
    dependencies: [
      {
        id: "dependency-legal-heir",
        created_at: taskDetail.created_at,
        updated_at: taskDetail.updated_at,
        task_id: "task-pension",
        depends_on_task_id: legalHeirTask.id,
        dependency_type: "completion",
      },
    ],
  };
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/requirements")) {
      return Response.json([
        { ...taskDetail.required_documents[0], status: "satisfied" },
      ]);
    }
    return Response.json(
      url.endsWith("/tasks/task-pension")
        ? bescomTask
        : {
            ...citizenCase,
            tasks: [citizenCase.tasks[0], legalHeirTask, bescomTask],
            documents: [
              deathCertificate,
              ...(legalCertificateAvailable
                ? [
                    {
                      ...deathCertificate,
                      id: "document-legal-heir",
                      produced_by_task_id: legalHeirTask.id,
                      document_type: "legal_heir_certificate",
                      issuer: "Karnataka Revenue Department",
                    },
                  ]
                : []),
            ],
          },
    );
  });

  const { unmount } = render(<TaskDetailPage />);

  expect(await screen.findByText("Required: Death Certificate")).toBeInTheDocument();
  expect(screen.getByText("Required: Legal Heir Certificate")).toBeInTheDocument();
  expect(screen.getByText("Not yet obtained")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Obtain Legal Heir Certificate" })).toHaveAttribute(
    "href",
    "/life-events/case-12345678/task/task-legal-heir",
  );

  unmount();
  legalCertificateAvailable = true;
  render(<TaskDetailPage />);
  const legalRequirement = await screen.findByText("Required: Legal Heir Certificate");
  expect(within(legalRequirement.closest("li")!).getByText("Available")).toBeInTheDocument();
  expect(screen.queryByText("Not yet obtained")).not.toBeInTheDocument();
});
