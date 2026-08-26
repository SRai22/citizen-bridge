import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import ApplicationsPage from "./page";

afterEach(() => vi.restoreAllMocks());

test("aggregates applications across cases and filters actionable work", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    if (url.endsWith("/api/cases")) return Promise.resolve(Response.json({ cases: [{ case_id: "case-1" }] }));
    if (url.endsWith("/api/catalog/services")) return Promise.resolve(Response.json({ services: [{ workflow_id: "pension", authority: "Treasury" }] }));
    if (url.endsWith("/api/cases/case-1")) return Promise.resolve(Response.json({
      case_id: "case-1", title: "Mother's Pension", status: "active", life_event_type: "pension",
      my_role: "coordinator", my_permissions: ["view", "submit"], limitations: [], subject: null,
      progress: { completed: 0, total: 2 }, created_at: "2026-08-20T00:00:00Z", updated_at: "2026-08-25T00:00:00Z",
      tasks_by_group: {
        ready: [{ task_id: "task-ready", case_id: "case-1", workflow_id: "pension", task_type: "form", title: "Pension application", description: null, status: "ready", completed_at: null, blocked_reason: null, blocked_by_task_ids: [] }],
        waiting: [{ task_id: "task-wait", case_id: "case-1", workflow_id: "pension", task_type: "review", title: "Pension review", description: null, status: "submitted", completed_at: null, blocked_reason: null, blocked_by_task_ids: [], wait_state: null }],
        blocked: [], completed: [],
      },
    }));
    return Promise.reject(new Error(`Unexpected request: ${url}`));
  });

  render(<ApplicationsPage />);
  expect(await screen.findByRole("heading", { name: "Pension application" })).toBeInTheDocument();
  expect(screen.getAllByText(/Treasury · From: Mother's Pension/).length).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole("tab", { name: "Pending" }));
  expect(screen.getByRole("heading", { name: "Pension review" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Pension application" })).not.toBeInTheDocument();
});
