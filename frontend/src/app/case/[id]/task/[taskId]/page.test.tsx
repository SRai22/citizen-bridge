import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { citizenCase, taskDetail } from "@/test/fixtures";

import TaskDetailPage from "./page";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "case-12345678", taskId: "task-pension" }),
}));

afterEach(() => vi.restoreAllMocks());

test("fetches and renders full task details", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const payload = url.endsWith("/tasks/task-pension") ? taskDetail : citizenCase;
    return new Response(JSON.stringify(payload), {
      headers: { "Content-Type": "application/json" },
    });
  });

  render(<TaskDetailPage />);

  expect(screen.getByRole("status")).toHaveTextContent("Loading task details");
  expect(
    await screen.findByRole("heading", { name: "Apply for Family Pension" }),
  ).toBeInTheDocument();
  expect(screen.getByText(taskDetail.description!)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Required documents" })).toBeInTheDocument();
  expect(screen.getByText("Death Certificate")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Dependencies" })).toBeInTheDocument();
  expect(screen.getByText("Obtain Death Certificate")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Back to case" })).toHaveAttribute(
    "href",
    "/case/case-12345678",
  );
  expect(fetchMock).toHaveBeenCalledTimes(2);
});
