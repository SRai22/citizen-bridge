import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import ProfilePage from "./page";

test("loads and updates the profile", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => Response.json({
    user_id: "user-1",
    username: "asha",
    name: init?.method === "PATCH" ? "Asha Rai" : "Asha Rao",
    date_of_birth: "1992-04-03",
    city: "Bengaluru",
    state: "Karnataka",
    phone: "+919876543210",
  }));

  render(<ProfilePage />);

  expect(await screen.findByLabelText("Full name")).toHaveValue("Asha Rao");
  fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Asha Rai" } });
  fireEvent.click(screen.getByRole("button", { name: "Save profile" }));

  expect(await screen.findByRole("status")).toHaveTextContent("Profile saved");
  expect(fetchMock).toHaveBeenLastCalledWith("/api/auth/me", expect.objectContaining({ method: "PATCH" }));
  await waitFor(() => expect(screen.getByLabelText("Full name")).toHaveValue("Asha Rai"));
  expect(screen.getByRole("link", { name: "← Back to My Services" })).toHaveAttribute("href", "/services");
});
