import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import Home from "./page";

afterEach(() => vi.restoreAllMocks());

test("renders the Citizen Bridge placeholder and backend status", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ status: "ok" }), {
      headers: { "Content-Type": "application/json" },
    }),
  );

  render(<Home />);

  expect(screen.getByRole("heading", { name: "Citizen Bridge" })).toBeInTheDocument();
  expect(await screen.findByText("API status: ok")).toBeInTheDocument();
});
