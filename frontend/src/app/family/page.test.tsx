import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import FamilyPage from "./page";

afterEach(() => vi.restoreAllMocks());

test("shows contextual family details and adds a member", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url = String(input);
    if (url.endsWith("/api/auth/me/family") && init?.method === "POST") {
      return Promise.resolve(Response.json({
        id: "member-2", name: "Arun Rao", relationship: "sibling", date_of_birth: null,
        phone: null, is_deceased: false, death_date: null, source: "manual",
        created_at: "2026-08-25T00:00:00Z", updated_at: "2026-08-25T00:00:00Z",
      }, { status: 201 }));
    }
    if (url.endsWith("/api/auth/me/family")) {
      return Promise.resolve(Response.json([{
        id: "member-1", name: "Kamala Devi", relationship: "mother",
        date_of_birth: "1960-02-03", phone: null, is_deceased: false, death_date: null,
        source: "intake", created_at: "2026-08-20T00:00:00Z", updated_at: "2026-08-20T00:00:00Z",
      }]));
    }
    if (url.endsWith("/api/cases")) return Promise.resolve(Response.json({ cases: [] }));
    return Promise.reject(new Error(`Unexpected request: ${url}`));
  });

  render(<FamilyPage />);
  expect(await screen.findByRole("heading", { name: "Kamala Devi" })).toBeInTheDocument();
  expect(screen.getByText("Pending identity and certificate verification")).toBeInTheDocument();
  expect(screen.getByText("No active cases")).toBeInTheDocument();
  fireEvent.click(screen.getByText("+ Add a family member"));
  fireEvent.change(screen.getAllByLabelText("Name").at(-1)!, { target: { value: "Arun Rao" } });
  fireEvent.change(screen.getAllByLabelText("Relationship").at(-1)!, { target: { value: "sibling" } });
  fireEvent.click(screen.getByRole("button", { name: "Add family member" }));
  expect(await screen.findByRole("heading", { name: "Arun Rao" })).toBeInTheDocument();
});
