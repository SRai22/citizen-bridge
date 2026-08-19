import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import type { IntakeHouseholdProfile, IntakeResponse } from "@/types/api";

import Home from "./page";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const profile: IntakeHouseholdProfile = {
  deceased: {
    name: "Arun Rao",
    relationship: "father",
    occupation: "retired Karnataka state government employee",
    pension_status: "active",
  },
  surviving_members: [
    {
      name: "Meera Rao",
      relationship: "spouse",
      occupation: "homemaker",
      pension_status: "none",
    },
  ],
  location: { city: "Bengaluru", state: "Karnataka" },
  assets: { bescom: true, ration_card: true, property: false },
};

const started: IntakeResponse = {
  session_id: "session-123",
  status: "in_progress",
  message: "I’m sorry you’re going through this. What happened?",
  profile: null,
};

afterEach(() => {
  vi.restoreAllMocks();
  push.mockReset();
});

test("starts the intake and shows messages with a pending indicator", async () => {
  let resolveMessage: ((response: Response) => void) | undefined;
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(jsonResponse(started))
    .mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          resolveMessage = resolve;
        }),
    );

  render(<Home />);

  expect(screen.getByRole("status")).toHaveTextContent("Starting a private conversation");
  expect(await screen.findByText(started.message)).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Your message"), {
    target: { value: "My father passed away" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));

  expect(screen.getByText("My father passed away")).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("Thinking");

  resolveMessage?.(
    jsonResponse({
      ...started,
      message: "Which city and state did he live in?",
    }),
  );
  expect(await screen.findByText("Which city and state did he live in?")).toBeInTheDocument();
  expect(screen.queryByText("Thinking…")).not.toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(2);
  expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/intake/session-123/message");
  expect(fetchMock.mock.calls[1]?.[1]).toEqual(
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ message: "My father passed away" }),
    }),
  );
});

test("reviews, clarifies, confirms, and navigates to the created case", async () => {
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(jsonResponse(started))
    .mockResolvedValueOnce(
      jsonResponse({
        ...started,
        status: "complete",
        message: "I have enough information to prepare your plan.",
        profile,
      }),
    )
    .mockResolvedValueOnce(
      jsonResponse({
        ...started,
        status: "complete",
        message: "Thanks, I updated that detail.",
        profile: { ...profile, deceased: { ...profile.deceased, name: "Anil Rao" } },
      }),
    )
    .mockResolvedValueOnce(jsonResponse({ case_id: "case-456" }));

  render(<Home />);
  await screen.findByText(started.message);
  sendMessage("My father passed away");

  expect(
    await screen.findByRole("heading", { name: "Here's what I understood" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Arun Rao")).toBeInTheDocument();
  expect(screen.getByText("Bengaluru, Karnataka")).toBeInTheDocument();
  expect(screen.getByText("✓ BESCOM connection")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Something's wrong, let me clarify" }));
  expect(screen.getByRole("heading", { name: "Tell us what your family needs" })).toBeInTheDocument();
  expect(screen.getByText("My father passed away")).toBeInTheDocument();
  expect(screen.getByText("I have enough information to prepare your plan.")).toBeInTheDocument();

  sendMessage("His name was Anil Rao");
  expect(await screen.findByText("Anil Rao")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Looks correct, create my plan" }));

  await waitFor(() => expect(push).toHaveBeenCalledWith("/case/case-456"));
});

test("shows an inline error and preserves the answer when a message fails", async () => {
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(jsonResponse(started))
    .mockRejectedValueOnce(new TypeError("Network error"));

  render(<Home />);
  await screen.findByText(started.message);
  sendMessage("My father passed away");

  expect(await screen.findByRole("alert")).toHaveTextContent("currently unreachable");
  expect(screen.getByLabelText("Your message")).toHaveValue("My father passed away");
});

function sendMessage(message: string) {
  fireEvent.change(screen.getByLabelText("Your message"), { target: { value: message } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
  });
}
