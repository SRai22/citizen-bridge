import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { IntakeChat } from "./intake-chat";

const { router } = vi.hoisted(() => ({ router: { push: vi.fn() } }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));

afterEach(() => {
  router.push.mockReset();
  vi.restoreAllMocks();
});

test("asks for a newborn's birth date with a calendar", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    Response.json({
      conversation_id: "conversation-1",
      status: "in_progress",
      message: "Congratulations! When was the baby born?",
      profile: null,
    }),
  );

  render(<IntakeChat categoryId="new_baby" />);

  const dateInput = await screen.findByLabelText("Baby's date of birth");
  const today = new Date();
  const localToday = new Date(today.getTime() - today.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 10);
  expect(dateInput).toHaveAttribute("type", "date");
  expect(dateInput).toHaveAttribute("max", localToday);
});
