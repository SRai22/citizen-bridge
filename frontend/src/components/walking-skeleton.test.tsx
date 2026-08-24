import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { WalkingSkeleton } from "./walking-skeleton";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

afterEach(() => vi.restoreAllMocks());

test("registers, signs in, browses and starts intake", async () => {
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(Response.json({ detail: "Missing bearer token" }, { status: 401 }))
    .mockResolvedValueOnce(Response.json({ user_id: "user-1" }, { status: 201 }))
    .mockResolvedValueOnce(Response.json({ user_id: "user-1" }))
    .mockResolvedValueOnce(
      Response.json({
        categories: [
          {
            id: "father_death",
            title: "Someone Passed Away",
            description: "Build a clear plan.",
          },
        ],
      }),
    )
    .mockResolvedValueOnce(
      Response.json({
        session_id: "session-1",
        status: "in_progress",
        message: "What happened?",
        profile: null,
      }),
    );

  render(<WalkingSkeleton />);
  expect(await screen.findByRole("heading", { name: "Create your account" })).toBeInTheDocument();
  change("Full name", "Integration User");
  change("Username", "integration-user");
  change("Date of birth", "1990-01-01");
  change("Password", "integration-password");
  fireEvent.click(screen.getByRole("button", { name: "Create account" }));

  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("Account created");
  change("Password", "integration-password");
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

  const category = await screen.findByRole("button", { name: /Someone Passed Away/ });
  fireEvent.click(category);
  expect(await screen.findByText("What happened?")).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(5);
});

function change(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}
