import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ServicesHome } from "@/components/services-home";

const { replace, router } = vi.hoisted(() => {
  const stableReplace = vi.fn();
  return { replace: stableReplace, router: { replace: stableReplace } };
});

vi.mock("next/navigation", () => ({ useRouter: () => router }));

afterEach(() => {
  vi.restoreAllMocks();
  replace.mockReset();
});

test("loads the signed-in user's service categories and starts intake", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    if (url.endsWith("/api/auth/session")) {
      return Promise.resolve(
        Response.json({
          user_id: "user-1",
          username: "asha",
          name: "Asha Rao",
          date_of_birth: "1992-04-03",
          city: "Bengaluru",
        }),
      );
    }
    if (url.endsWith("/api/catalog/categories")) {
      return Promise.resolve(Response.json({
        categories: [
          { id: "bereavement", title: "Someone Passed Away", description: "Build a plan." },
        ],
      }));
    }
    if (url.endsWith("/api/intake/start")) {
      return Promise.resolve(Response.json({
        session_id: "intake-1",
        status: "in_progress",
        message: "What happened?",
        profile: null,
      }));
    }
    return Promise.reject(new Error(`Unexpected request: ${url}`));
  });

  render(<ServicesHome />);

  expect(screen.getByRole("status")).toHaveTextContent("Loading your services");
  expect(await screen.findByRole("heading", { name: "Welcome, Asha Rao" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Someone Passed Away/ }));
  expect(await screen.findByText("What happened?")).toBeInTheDocument();
});

test("sends a new user to onboarding", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    return Promise.resolve(
      url.endsWith("/api/auth/session")
        ? Response.json({ detail: "Missing bearer token" }, { status: 401 })
        : Response.json({ categories: [] }),
    );
  });

  render(<ServicesHome />);

  await vi.waitFor(() => expect(replace).toHaveBeenCalledWith("/onboarding"));
});
