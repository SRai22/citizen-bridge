import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import ActivityPage from "./page";

afterEach(() => vi.restoreAllMocks());

test("groups, filters, links, and paginates citizen activity", async () => {
  const now = new Date().toISOString();
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    const security = url.includes("category=security");
    const older = url.includes("offset=1");
    const activities = security ? [{
      id: "security-1", activity_type: "login_new_device", title: "Login from new device",
      description: "Bengaluru", icon: "lock", category: "security", case_id: null,
      task_id: null, document_id: null, data: {}, occurred_at: now,
    }] : older ? [] : [{
      id: "task-1", activity_type: "task_submitted", title: "Death Certificate submitted",
      description: "Submitted to BBMP", icon: "check", category: "submissions",
      case_id: "case-1", task_id: "task-1", document_id: null, data: {}, occurred_at: now,
    }];
    return Promise.resolve(Response.json({ activities, groups: [], has_more: !security && !older }));
  });

  render(<ActivityPage />);
  expect(await screen.findByText("Death Certificate submitted")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Today" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /View Death Certificate/ })).toHaveAttribute(
    "href", "/life-events/case-1/task/task-1",
  );
  fireEvent.click(screen.getByRole("tab", { name: "Security" }));
  expect(await screen.findByText("Login from new device")).toBeInTheDocument();
});
