import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { PhoneAuth } from "./phone-auth";

const { replace, router } = vi.hoisted(() => ({ replace: vi.fn(), router: { replace: vi.fn() } }));
router.replace = replace;
vi.mock("next/navigation", () => ({ useRouter: () => router }));

afterEach(() => { replace.mockReset(); vi.restoreAllMocks(); });

test("registers a new user with phone and OTP", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(Response.json({ sent: true, demo_code: "123456" })).mockResolvedValueOnce(Response.json({ user_id: "user-1", is_new_user: true }));
  render(<PhoneAuth intent="register" />);
  fireEvent.change(screen.getByLabelText("Mobile number"), { target: { value: "9876543210" } });
  fireEvent.click(screen.getByRole("button", { name: "Send OTP" }));
  expect(await screen.findByRole("status")).toHaveTextContent("123456");
  fireEvent.change(screen.getByLabelText("One-time password"), { target: { value: "123456" } });
  fireEvent.click(screen.getByRole("button", { name: "Register" }));
  await vi.waitFor(() => expect(replace).toHaveBeenCalledWith("/onboarding"));
  expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/auth/phone/request", expect.objectContaining({ method: "POST" }));
});

test("logs a returning complete user into services", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(Response.json({ sent: true, demo_code: "123456" })).mockResolvedValueOnce(Response.json({ user_id: "user-1", is_new_user: false })).mockResolvedValueOnce(Response.json({ user_id: "user-1", username: "asha", name: "Asha", date_of_birth: "1992-01-01", city: "Bengaluru" }));
  render(<PhoneAuth intent="login" />);
  fireEvent.change(screen.getByLabelText("Mobile number"), { target: { value: "9876543210" } });
  fireEvent.click(screen.getByRole("button", { name: "Send OTP" }));
  await screen.findByRole("status");
  fireEvent.change(screen.getByLabelText("One-time password"), { target: { value: "123456" } });
  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  await vi.waitFor(() => expect(replace).toHaveBeenCalledWith("/services"));
});
