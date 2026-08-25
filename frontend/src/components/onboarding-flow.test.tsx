import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { OnboardingFlow } from "./onboarding-flow";

const { replace, router } = vi.hoisted(() => {
  const stableReplace = vi.fn();
  return { replace: stableReplace, router: { replace: stableReplace } };
});
vi.mock("next/navigation", () => ({ useRouter: () => router }));

afterEach(() => {
  localStorage.clear();
  replace.mockReset();
  vi.restoreAllMocks();
});

test("verifies the mock OTP, creates a profile, and allows Aadhaar to be skipped", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url = String(input);
    if (url.endsWith("/api/auth/session")) {
      return Promise.resolve(
        Response.json({ detail: "Missing bearer token" }, { status: 401 }),
      );
    }
    if (url.endsWith("/api/auth/register")) {
      return Promise.resolve(Response.json({ user_id: "user-1" }, { status: 201 }));
    }
    if (url.endsWith("/api/auth/me") && init?.method === "PATCH") {
      return Promise.resolve(
        Response.json({
          user_id: "user-1",
          username: "phone_9876543210",
          name: "Asha Rao",
          date_of_birth: "1992-04-03",
          city: "Bengaluru",
        }),
      );
    }
    return Promise.reject(new Error(`Unexpected request: ${url}`));
  });

  render(<OnboardingFlow />);
  fireEvent.click(await screen.findByRole("button", { name: "Get Started" }));
  fireEvent.change(screen.getByLabelText("Mobile number"), {
    target: { value: "98765 43210" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Send OTP" }));
  fireEvent.change(screen.getByLabelText("One-time password"), {
    target: { value: "000000" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Verify and continue" }));
  expect(screen.getByRole("alert")).toHaveTextContent("Invalid OTP. Try again.");

  fireEvent.change(screen.getByLabelText("One-time password"), {
    target: { value: "123456" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Verify and continue" }));
  expect(
    await screen.findByRole("heading", { name: "Tell us the basics" }),
  ).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Asha Rao" } });
  fireEvent.change(screen.getByLabelText("Date of birth"), {
    target: { value: "1992-04-03" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));

  expect(
    await screen.findByRole("heading", { name: "Link Aadhaar for faster matching" }),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Skip for now" }));
  expect(replace).toHaveBeenCalledWith("/");
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/auth/register",
    expect.objectContaining({
      body: expect.stringContaining('"phone":"+919876543210"'),
      method: "POST",
    }),
  );
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/auth/me",
    expect.objectContaining({
      body: JSON.stringify({
        name: "Asha Rao",
        date_of_birth: "1992-04-03",
        city: "Bengaluru",
        state: "Karnataka",
      }),
    }),
  );
});

test("resumes the last onboarding step and returning users skip it", async () => {
  localStorage.setItem(
    "citizen-bridge:onboarding",
    JSON.stringify({ step: 1, phone: "9876543210", verified: false }),
  );
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    Response.json({ detail: "Missing bearer token" }, { status: 401 }),
  );
  const { unmount } = render(<OnboardingFlow />);
  expect(await screen.findByRole("heading", { name: "Verify your phone" })).toBeInTheDocument();
  expect(screen.getByLabelText("Mobile number")).toHaveValue("9876543210");
  unmount();

  vi.restoreAllMocks();
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    Response.json({
      user_id: "user-1",
      username: "asha",
      name: "Asha Rao",
      date_of_birth: "1992-04-03",
      city: "Bengaluru",
    }),
  );
  render(<OnboardingFlow />);
  await vi.waitFor(() => expect(replace).toHaveBeenCalledWith("/"));
});
