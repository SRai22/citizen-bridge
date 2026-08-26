import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import BenefitsPage from "./page";

const { push, router } = vi.hoisted(() => {
  const stablePush = vi.fn();
  return { push: stablePush, router: { push: stablePush } };
});
vi.mock("next/navigation", () => ({ useRouter: () => router }));

afterEach(() => {
  push.mockReset();
  vi.restoreAllMocks();
});

test("shows active benefits, readiness evidence, and starts an application", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url = String(input);
    if (url.endsWith("/api/cases/benefits/active")) {
      return Promise.resolve(Response.json({ benefits: [] }));
    }
    if (url.endsWith("/api/cases/benefits/eligible")) {
      return Promise.resolve(Response.json({
        benefits: [{
          id: "widow_pension",
          name: "Widow Pension",
          description: "Monthly financial assistance.",
          authority: "Karnataka",
          amount: "₹1,000 per month",
          source: "Matched from your saved profile and document wallet",
          eligibility: {
            status: "eligible",
            missing_profile_fields: [],
            rule_results: [{
              field: "annual_income",
              operator: "lt",
              expected: 200000,
              actual: 120000,
              status: "satisfied",
              source: { type: "document_extracted", verified: true },
            }],
          },
          readiness: {
            percentage: 100,
            profile: { complete: 1, total: 1, missing: [] },
            documents: { available: ["aadhaar"], total: 1, missing: [] },
          },
        }],
      }));
    }
    if (url.endsWith("/api/cases/benefits/widow_pension/apply") && init?.method === "POST") {
      return Promise.resolve(Response.json({ case: { case_id: "case-benefit-1" } }, { status: 201 }));
    }
    return Promise.reject(new Error(`Unexpected request: ${url}`));
  });

  render(<BenefitsPage />);

  expect(await screen.findByRole("heading", { name: "Widow Pension" })).toBeInTheDocument();
  expect(screen.getByRole("progressbar", { name: "Widow Pension readiness" })).toHaveAttribute("aria-valuenow", "100");
  fireEvent.click(screen.getByText("Why this match and what is missing"));
  expect(screen.getByText(/document extracted \(verified\)/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Apply now" }));
  await vi.waitFor(() => expect(push).toHaveBeenCalledWith("/case/case-benefit-1"));
});
