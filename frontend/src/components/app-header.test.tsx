import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { AppHeader } from "./app-header";

const { push, refresh } = vi.hoisted(() => ({ push: vi.fn(), refresh: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => ({ push, refresh }) }));

afterEach(() => {
  vi.restoreAllMocks();
  push.mockReset();
  refresh.mockReset();
});

test("seeds a fresh demo and navigates to the case", async () => {
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(Response.json({ status: "ok" }))
    .mockResolvedValueOnce(
      Response.json({ case_id: "case-123", state: "initial", tasks: 4 }),
    );

  render(<AppHeader />);
  fireEvent.click(screen.getByRole("button", { name: "Fresh start" }));

  await waitFor(() => expect(push).toHaveBeenCalledWith("/case/case-123"));
});

test("shows the backend error when reset fails", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
    Response.json(
      { detail: { message: "Demo reset is unavailable." } },
      { status: 503 },
    ),
  );

  render(<AppHeader />);
  fireEvent.click(screen.getByRole("button", { name: "Reset" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Demo reset is unavailable.");
  expect(push).not.toHaveBeenCalled();
});
