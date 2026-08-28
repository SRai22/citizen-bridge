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

test("mocks the hospital birth-record upload and acknowledges it", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    if (String(input).endsWith("/message")) {
      expect(JSON.parse(String(init?.body)).message).toContain("hospital-record.pdf");
      return Response.json({
        conversation_id: "conversation-1",
        status: "in_progress",
        message: "Thank you for uploading the certificate from the hospital. What is the other parent's name?",
        profile: null,
      });
    }
    return Response.json({
      conversation_id: "conversation-1",
      status: "in_progress",
      message: "Please upload the hospital birth report or discharge summary so we can prepare the civil birth registration.",
      profile: null,
    });
  });

  render(<IntakeChat categoryId="new_baby" />);
  const upload = await screen.findByLabelText("Upload hospital birth record");
  fireEvent.change(upload, { target: { files: [new File(["record"], "hospital-record.pdf", { type: "application/pdf" })] } });

  expect(await screen.findByText("Uploaded hospital-record.pdf")).toBeInTheDocument();
  expect(await screen.findByText(/Thank you for uploading the certificate from the hospital/)).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

test("offers saved family members and asks for the death date with a calendar", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url === "/api/auth/me/family") return Response.json([
      {
        id: "family-1", name: "Arun Rao", relationship: "father", date_of_birth: null,
        phone: null, is_deceased: false, death_date: null, source: "manual",
        created_at: "2026-08-20T00:00:00Z", updated_at: "2026-08-20T00:00:00Z",
      },
      {
        id: "family-2", name: "Meera Rao", relationship: "mother", date_of_birth: null,
        phone: null, is_deceased: false, death_date: null, source: "manual",
        created_at: "2026-08-20T00:00:00Z", updated_at: "2026-08-20T00:00:00Z",
      },
    ]);
    if (url.endsWith("/message")) {
      const sent = JSON.parse(String(init?.body)).message;
      expect(sent).toContain("Arun Rao");
      expect(sent).toContain("Meera Rao (mother)");
      expect(sent).toContain("do not ask for them again");
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
  expect(screen.getByText("Arun Rao, my father, passed away.")).toBeInTheDocument();
  expect(screen.queryByText(/Meera Rao \(mother\)/)).not.toBeInTheDocument();
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
});

test("renders server-provided pension replies while keeping text input", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({
    conversation_id: "conversation-1", status: "in_progress",
    message: "What was their occupation and pension status?", input_type: "text",
    suggested_replies: ["Retired with government pension", "Not sure"], profile: null,
  }));

  render(<IntakeChat categoryId="bereavement" />);

  expect(await screen.findByRole("button", { name: "Retired with government pension" })).toBeInTheDocument();
  expect(screen.getByLabelText("Your message")).toHaveAttribute("type", "text");
});
