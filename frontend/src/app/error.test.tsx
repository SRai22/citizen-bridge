import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import AppError from "./error";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

test("renders an unexpected-error fallback and retries the route", () => {
  const retry = vi.fn();

  render(<AppError retry={retry} />);
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));

  expect(screen.getByText("Something unexpected went wrong.")).toBeInTheDocument();
  expect(retry).toHaveBeenCalledOnce();
});
