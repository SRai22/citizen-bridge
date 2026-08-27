import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ServicesHome } from "@/components/services-home";
import Home from "./page";

const { push, replace, router } = vi.hoisted(() => {
  const stablePush = vi.fn();
  const stableReplace = vi.fn();
  return {
    push: stablePush,
    replace: stableReplace,
    router: { push: stablePush, replace: stableReplace },
  };
});

vi.mock("next/navigation", () => ({ useRouter: () => router }));

afterEach(() => {
  vi.restoreAllMocks();
  push.mockReset();
  replace.mockReset();
});

test("offers public login and registration before onboarding", () => {
  render(<Home />);
  expect(screen.getByRole("heading", { name: /One place for services/ })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Log in" })).toHaveAttribute("href", "/login");
  expect(screen.getByRole("link", { name: "Register" })).toHaveAttribute("href", "/register");
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
          {
            id: "bereavement",
            title: "Someone Passed Away",
            subtitle: "Death certificate, pension, utilities",
            icon: "dove",
            description: "Build a plan.",
            service_count: 3,
          },
        ],
      }));
    }
    if (url.endsWith("/api/catalog/services")) {
      return Promise.resolve(Response.json({ services: [] }));
    }
    if (url.endsWith("/api/cases")) {
      return Promise.resolve(Response.json({ cases: [] }));
    }
    if (url.endsWith("/api/intake/start")) {
      return Promise.resolve(Response.json({
        conversation_id: "intake-1",
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
  expect(screen.getByRole("heading", { name: "Someone Passed Away" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Start conversation/ }));
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

  await vi.waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
});

test("routes future workflows to the demo availability page", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    if (url.endsWith("/api/auth/session")) {
      return Promise.resolve(Response.json({
        user_id: "user-1",
        username: "asha",
        name: "Asha Rao",
        date_of_birth: "1992-04-03",
        city: "Bengaluru",
      }));
    }
    if (url.endsWith("/api/catalog/categories")) {
      return Promise.resolve(Response.json({ categories: [{
        id: "address_change",
        title: "Moving to a New Address",
        subtitle: "Utilities and records",
        icon: "home",
        description: "Update records.",
        service_count: 4,
      }] }));
    }
    if (url.endsWith("/api/catalog/services")) {
      return Promise.resolve(Response.json({ services: [] }));
    }
    if (url.endsWith("/api/cases")) {
      return Promise.resolve(Response.json({ cases: [] }));
    }
    return Promise.reject(new Error(`Unexpected request: ${url}`));
  });

  render(<ServicesHome />);
  fireEvent.click(await screen.findByRole("button", { name: /Moving to a New Address/ }));
  fireEvent.click(screen.getByRole("button", { name: "View demo availability →" }));

  expect(push).toHaveBeenCalledWith("/services/coming-soon/address_change");
});
