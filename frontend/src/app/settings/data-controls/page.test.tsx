import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import DataControlsPage from "./page";

afterEach(() => vi.restoreAllMocks());

test("revokes shares, withdraws applications, and starts deletion cooling-off", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url = String(input);
    if (url.endsWith("/api/docs/shares") && !init?.method) return Promise.resolve(Response.json({ active_shares: [{ share_id: "share-1", document_id: "doc-1", document_title: "Aadhaar", shared_with: "Treasury", purpose: "Pension", shared_at: "2026-08-20T00:00:00Z", case_id: null, task_id: null }] }));
    if (url.endsWith("/api/cases/withdrawable")) return Promise.resolve(Response.json({ withdrawable: [{ task_id: "task-1", case_id: "case-1", title: "Pension application", authority: "Treasury", submitted_at: "2026-08-20T00:00:00Z", can_withdraw: true, withdrawal_note: "" }] }));
    if (url.endsWith("/api/auth/me/delete/status")) return Promise.resolve(Response.json({ status: "none" }));
    if (url.endsWith("/api/docs/shares/share-1/revoke")) return Promise.resolve(Response.json({ revoked: true, note: "Copies cannot be recalled." }));
    if (url.endsWith("/api/cases/case-1/tasks/task-1/withdraw")) return Promise.resolve(Response.json({ withdrawn: true, note: "Withdrawal sent." }));
    if (url.endsWith("/api/auth/me/delete")) return Promise.resolve(Response.json({ status: "cooling_off", cooling_off_until: "2026-09-02T00:00:00Z" }));
    return Promise.reject(new Error(`Unexpected request: ${url}`));
  });

  render(<DataControlsPage />);
  fireEvent.click(await screen.findByRole("button", { name: "Revoke" }));
  expect(await screen.findByText("Copies cannot be recalled.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Withdraw" }));
  expect(await screen.findByText("Withdrawal sent.")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Re-enter password"), { target: { value: "correct-horse" } });
  fireEvent.change(screen.getByLabelText("Type DELETE MY ACCOUNT"), { target: { value: "DELETE MY ACCOUNT" } });
  fireEvent.click(screen.getByRole("button", { name: "Start 7-day cooling-off" }));
  expect(await screen.findByRole("button", { name: "Cancel deletion" })).toBeInTheDocument();
});
