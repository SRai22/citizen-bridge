import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { CoordinatorBanner } from "./coordinator-banner";

test("explains coordinator context and limitations", () => {
  render(<CoordinatorBanner citizenCase={{
    case_id: "case-1", title: "Pension", status: "active", life_event_type: "pension",
    my_role: "coordinator", my_permissions: ["view", "submit"],
    limitations: ["Cannot approve legal declarations"],
    subject: { person_id: "person-1", name: "Kamala Devi", relationship: "mother" },
    progress: { completed: 0, total: 1 }, created_at: "2026-08-20", updated_at: "2026-08-20",
    tasks_by_group: { ready: [], waiting: [], blocked: [], completed: [] },
  }} />);
  expect(screen.getByText(/Acting for: Kamala Devi/)).toBeInTheDocument();
  expect(screen.getByText(/Cannot approve legal declarations/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Switch to my services" })).toHaveAttribute("href", "/");
});
