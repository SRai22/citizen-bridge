import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { citizenCase, makeTask } from "@/test/fixtures";

import CaseOverviewPage from "./page";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "case-12345678" }),
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

afterEach(() => vi.restoreAllMocks());

test("renders case metadata, task statuses, dependencies, and detail links", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(citizenCase), {
      headers: { "Content-Type": "application/json" },
    }),
  );

  render(<CaseOverviewPage />);

  expect(screen.getByRole("status")).toHaveTextContent("Loading your case");
  expect(await screen.findByRole("heading", { name: "Parent Death case" })).toBeInTheDocument();
  expect(screen.getByText("15 Aug 2026", { exact: false })).toBeInTheDocument();
  expect(screen.getByText("Completed")).toBeInTheDocument();
  expect(screen.getByText("Waiting")).toBeInTheDocument();
  expect(screen.getByText("Prerequisite complete: Obtain Death Certificate")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Apply for Family Pension/ })).toHaveAttribute(
    "href",
    "/case/case-12345678/task/task-pension",
  );
  expect(fetchMock).toHaveBeenCalledOnce();
  const [requestUrl, requestInit] = fetchMock.mock.calls[0]!;

  expect(new URL(String(requestUrl), "http://test").pathname).toBe(
    "/api/cases/case-12345678",
  );
  expect(requestInit).toEqual(
    expect.objectContaining({
      headers: expect.objectContaining({ Accept: "application/json" }),
      signal: expect.any(AbortSignal),
    }),
  );
});

test("shows a retryable error when the backend is unavailable", async () => {
  vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Network error"));

  render(<CaseOverviewPage />);

  expect(await screen.findByRole("heading", { name: "We couldn't load this page" })).toBeInTheDocument();
  expect(screen.getByText(/currently unreachable/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
});

test("shows a replanned task and names the prerequisite blocking the failed task", async () => {
  const legalHeirTask = makeTask({
    id: "task-legal-heir",
    title: "Obtain Legal Heir Certificate",
    workflow_id: "legal_heir_certificate",
    status: "ready",
  });
  const blockedBescomTask = makeTask({
    id: "task-bescom",
    title: "Transfer BESCOM Electricity Account",
    workflow_id: "bescom_transfer",
    status: "blocked",
    dependencies: [
      {
        id: "dependency-remediation",
        created_at: citizenCase.created_at,
        updated_at: citizenCase.updated_at,
        task_id: "task-bescom",
        depends_on_task_id: legalHeirTask.id,
        dependency_type: "completion",
      },
    ],
  });
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    Response.json({ ...citizenCase, tasks: [legalHeirTask, blockedBescomTask] }),
  );

  render(<CaseOverviewPage />);

  expect((await screen.findByText("Obtain Legal Heir Certificate")).closest("a")).toHaveAttribute(
    "href",
    "/case/case-12345678/task/task-legal-heir",
  );
  expect(screen.getByRole("link", { name: /Transfer BESCOM Electricity Account/ })).toHaveTextContent(
    "Blocked by: Obtain Legal Heir Certificate",
  );
  expect(screen.getByText("Ready")).toBeInTheDocument();
  expect(screen.getByText("Blocked")).toBeInTheDocument();
});
