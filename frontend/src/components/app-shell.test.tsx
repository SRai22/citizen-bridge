import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { AppShell, navigation } from "./app-shell";

let pathname = "/documents";
vi.mock("next/navigation", () => ({ usePathname: () => pathname }));

test("provides all seven sections, active state, collapse, and mobile drawer", () => {
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
