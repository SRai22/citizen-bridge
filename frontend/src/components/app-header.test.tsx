import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { AppHeader } from "./app-header";

test("links the brand home and identifies the current milestone", () => {
  render(<AppHeader />);

  expect(screen.getByRole("link", { name: /Citizen Bridge/ })).toHaveAttribute("href", "/");
  expect(screen.getByText("Phase 0")).toBeInTheDocument();
});
