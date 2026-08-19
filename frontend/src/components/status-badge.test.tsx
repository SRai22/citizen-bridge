import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { StatusBadge } from "./status-badge";

test("gives completion and failure states distinct accessible labels and symbols", () => {
  const { rerender } = render(<StatusBadge status="completed" />);
  expect(screen.getByText("Completed")).toHaveTextContent("Completed");
  expect(screen.getByText("✓")).toBeInTheDocument();

  rerender(<StatusBadge status="failed" />);
  expect(screen.getByText("Failed")).toHaveTextContent("Failed");
  expect(screen.getByText("×")).toBeInTheDocument();
});
