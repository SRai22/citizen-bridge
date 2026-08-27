import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

test("offers saved family members and asks for the death date with a calendar", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url === "/api/auth/me/family") return Response.json([{
      id: "family-1", name: "Arun Rao", relationship: "father", date_of_birth: null,
      phone: null, is_deceased: false, death_date: null, source: "manual",
      created_at: "2026-08-20T00:00:00Z", updated_at: "2026-08-20T00:00:00Z",
    }]);
    if (url.endsWith("/message")) {
      expect(JSON.parse(String(init?.body)).message).toContain("Arun Rao");
      return Response.json({
        conversation_id: "conversation-1", status: "in_progress",
        message: "Thank you for telling me.", input_type: "date", profile: null,
      });
    }
    return Response.json({
      conversation_id: "conversation-1", status: "in_progress",
      message: "I'm sorry for your loss. Who passed away?", profile: null,
    });
  });

  render(<IntakeChat categoryId="bereavement" />);
  fireEvent.click(await screen.findByRole("button", { name: "Arun Rao, father" }));

  const dateInput = await screen.findByLabelText("Date of death");
  expect(dateInput).toHaveAttribute("type", "date");
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
});
