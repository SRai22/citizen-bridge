import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import type { CaseOverview } from "@/types/api";

import CaseOverviewPage from "./page";

vi.mock("next/navigation", () => ({ useParams: () => ({ id: "case-12345678" }) }));

const citizenCase: CaseOverview = {
  case_id: "case-12345678",
  title: "Father Death — Administrative Formalities",
  status: "active",
  life_event_type: "father_death",
  my_role: "owner",
  my_permissions: ["view", "submit", "approve", "manage"],
  limitations: [],
  subject: null,
  progress: { completed: 0, total: 2 },
  created_at: "2026-08-24T12:00:00Z",
  updated_at: "2026-08-24T12:00:00Z",
  tasks_by_group: {
    ready: [
      {
        task_id: "task-ready",
        case_id: "case-12345678",
        workflow_id: "death_certificate",
        task_type: "death_registration",
        title: "Obtain Death Certificate",
        description: "Register the death.",
        status: "ready",
        completed_at: null,
        blocked_reason: null,
        blocked_by_task_ids: [],
      },
    ],
    waiting: [],
    blocked: [
      {
        task_id: "task-blocked",
        case_id: "case-12345678",
        workflow_id: "family_pension",
        task_type: "family_pension_application",
        title: "Apply for Family Pension",
        description: "Transfer the pension.",
        status: "pending",
        completed_at: null,
        blocked_reason: "Waiting for prerequisite tasks",
        blocked_by_task_ids: ["task-ready"],
      },
    ],
    completed: [],
  },
};

afterEach(() => vi.restoreAllMocks());

test("renders ownership, progress and grouped tasks", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json(citizenCase));

  render(<CaseOverviewPage />);

  expect(screen.getByRole("status")).toHaveTextContent("Loading your case");
  expect(await screen.findByRole("heading", { name: citizenCase.title })).toBeInTheDocument();
  expect(screen.getByText("0 of 2 completed", { exact: false })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "What to do next" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Blocked" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Start this →" })).toHaveAttribute(
    "href",
    "/life-events/case-12345678/task/task-ready",
  );
  expect(screen.getByText("Needs: Obtain Death Certificate")).toBeInTheDocument();
  expect(screen.getByText("Waiting for prerequisite tasks")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "View dependency graph →" })).toBeInTheDocument();
});

test("shows a retryable error when the gateway is unavailable", async () => {
  vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Network error"));

  render(<CaseOverviewPage />);

  expect(await screen.findByRole("heading", { name: "We couldn't load this page" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
});
