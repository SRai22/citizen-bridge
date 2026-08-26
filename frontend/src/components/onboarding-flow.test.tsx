import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { OnboardingFlow } from "./onboarding-flow";

const { replace, router } = vi.hoisted(() => ({ replace: vi.fn(), router: { replace: vi.fn() } }));
router.replace = replace;
vi.mock("next/navigation", () => ({ useRouter: () => router }));

afterEach(() => { replace.mockReset(); vi.restoreAllMocks(); });

test("completes profile details after phone authentication", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith("/api/auth/session")) return Response.json({ user_id: "user-1", username: "phone_9876543210", phone: "+919876543210", name: null, date_of_birth: null, city: null });
    if (url.endsWith("/api/auth/me") && init?.method === "PATCH") return Response.json({ user_id: "user-1", username: "phone_9876543210", name: "Asha Rao", date_of_birth: "1992-04-03", city: "Bengaluru" });
    throw new Error(`Unexpected request: ${url}`);
  });

  render(<OnboardingFlow />);
  expect(await screen.findByRole("heading", { name: "Tell us the basics" })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Asha Rao" } });
  fireEvent.change(screen.getByLabelText("Date of birth"), { target: { value: "1992-04-03" } });
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));
  expect(await screen.findByRole("heading", { name: "Link Aadhaar for faster matching" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Skip for now" }));
  expect(replace).toHaveBeenCalledWith("/services");
});

test("redirects unauthenticated visitors home and complete profiles to services", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(Response.json({ detail: "Missing bearer token" }, { status: 401 }));
  const { unmount } = render(<OnboardingFlow />);
  await vi.waitFor(() => expect(replace).toHaveBeenCalledWith("/"));
  unmount();

  replace.mockReset();
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(Response.json({ user_id: "user-1", username: "asha", name: "Asha Rao", date_of_birth: "1992-04-03", city: "Bengaluru" }));
  render(<OnboardingFlow />);
  await vi.waitFor(() => expect(replace).toHaveBeenCalledWith("/services"));
});
