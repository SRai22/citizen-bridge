import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { citizenCase } from "@/test/fixtures";

import CaseOverviewPage from "./page";

vi.mock("next/navigation", () => ({ useParams: () => ({ id: "case-12345678" }) }));

afterEach(() => vi.restoreAllMocks());

test("renders case metadata, task statuses, dependencies, and detail links", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(citizenCase), {
      headers: { "Content-Type": "application/json" },
    }),
  );

  render(<CaseOverviewPage />);

  expect(screen.getByRole("status")).toHaveTextContent("Loading your case");
  expect(await screen.findByRole("heading", { name: "Parent Death case" })).toBeInTheDocument();
  expect(screen.getByText("15 Aug 2026", { exact: false })).toBeInTheDocument();
  expect(screen.getByText("Completed")).toBeInTheDocument();
  expect(screen.getByText("Waiting")).toBeInTheDocument();
  expect(screen.getByText("Prerequisite complete: Obtain Death Certificate")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Apply for Family Pension/ })).toHaveAttribute(
    "href",
    "/case/case-12345678/task/task-pension",
  );
  expect(fetchMock).toHaveBeenCalledOnce();
  const [requestUrl, requestInit] = fetchMock.mock.calls[0]!;

  expect(new URL(String(requestUrl), "http://test").pathname).toBe(
    "/api/cases/case-12345678",
  );
  expect(requestInit).toEqual(
    expect.objectContaining({
      headers: expect.objectContaining({ Accept: "application/json" }),
      signal: expect.any(AbortSignal),
    }),
  );
});

test("shows a retryable error when the backend is unavailable", async () => {
  vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Network error"));

  render(<CaseOverviewPage />);

  expect(await screen.findByRole("heading", { name: "We couldn't load this page" })).toBeInTheDocument();
  expect(screen.getByText(/currently unreachable/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
});
