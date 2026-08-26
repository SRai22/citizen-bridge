import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { AppShell, navigation } from "./app-shell";

let pathname = "/documents";
const { back, refresh, replace, router } = vi.hoisted(() => ({
  back: vi.fn(),
  refresh: vi.fn(),
  replace: vi.fn(),
  router: { back: vi.fn(), refresh: vi.fn(), replace: vi.fn() },
}));
router.back = back;
router.refresh = refresh;
router.replace = replace;
vi.mock("next/navigation", () => ({ usePathname: () => pathname, useRouter: () => router }));

afterEach(() => {
  back.mockReset();
  refresh.mockReset();
  replace.mockReset();
  vi.restoreAllMocks();
});

test("provides navigation, back action, collapse, and mobile drawer", () => {
  render(
    <AppShell>
      <p>Page content</p>
    </AppShell>,
  );

  for (const item of navigation) {
    expect(screen.getAllByRole("link", { name: item.label }).length).toBeGreaterThan(0);
  }
  expect(screen.getAllByRole("link", { name: "My Documents" })[0]).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(screen.getByText("Page content")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Go back" }));
  expect(back).toHaveBeenCalledOnce();

  fireEvent.click(screen.getByRole("button", { name: "Collapse sidebar" }));
  expect(screen.getByRole("button", { name: "Expand sidebar" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Open navigation" }));
  expect(screen.getByRole("button", { name: "Open navigation" })).toHaveAttribute(
    "aria-expanded",
    "true",
  );
  fireEvent.click(screen.getAllByRole("link", { name: "My Benefits" }).at(-1)!);
  expect(screen.getByRole("button", { name: "Open navigation" })).toHaveAttribute(
    "aria-expanded",
    "false",
  );
});

test("logs out locally and returns to onboarding when auth is unavailable", async () => {
  vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Network error"));
  render(<AppShell><p>Page content</p></AppShell>);

  fireEvent.click(screen.getAllByRole("button", { name: "Log out" })[0]);

  await waitFor(() => expect(replace).toHaveBeenCalledWith("/"));
  expect(refresh).toHaveBeenCalledOnce();
});

test("keeps onboarding outside the authenticated shell", () => {
  pathname = "/onboarding";
  render(
    <AppShell>
      <p>Onboarding content</p>
    </AppShell>,
  );

  expect(screen.getByText("Onboarding content")).toBeInTheDocument();
  expect(screen.queryByRole("navigation", { name: "Primary navigation" })).not.toBeInTheDocument();
  pathname = "/documents";
});
