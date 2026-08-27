import { afterEach, expect, test, vi } from "vitest";

import type { NewBabyProfile } from "@/types/api";

import { ApiError, confirmIntake } from "./api";

afterEach(() => vi.restoreAllMocks());

test("creates baby cases with baby workflow context and no BESCOM data", async () => {
  const profile: NewBabyProfile = {
    baby: { name: "Anaya Rao", dob: "2026-08-20", gender: "female" },
    parents: ["Asha Rao", "Vikram Rao"],
    birth_place: "Bengaluru General Hospital",
    location: { city: "Bengaluru", state: "Karnataka" },
  };
  const fetchMock = vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(Response.json({ profile }))
    .mockResolvedValueOnce(Response.json({ case_id: "case-1" }));

  await expect(confirmIntake("conversation-1", "new_baby")).resolves.toEqual({
    case_id: "case-1",
  });

  const [url, init] = fetchMock.mock.calls[1];
  const payload = JSON.parse(String(init?.body));
  expect(String(url)).toBe("/api/cases");
  expect(payload.life_event.context).toMatchObject({ category_id: "new_baby", ...profile });
  expect(payload.life_event.context).not.toHaveProperty("assets");
  expect(payload).not.toHaveProperty("household_profile");
});

test("rejects a profile returned for the wrong intake category", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(Response.json({
    profile: {
      spouse1: "Asha Rao",
      spouse2: "Vikram Rao",
      marriage_date: "2026-08-20",
      marriage_place: "Bengaluru",
      location: { city: "Bengaluru", state: "Karnataka" },
    },
  }));

  await expect(confirmIntake("conversation-1", "new_baby")).rejects.toEqual(
    new ApiError("Intake profile does not match category: new_baby"),
  );
  expect(fetchMock).toHaveBeenCalledTimes(1);
});
