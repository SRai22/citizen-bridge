import { afterEach, expect, test, vi } from "vitest";

import type { NewBabyProfile } from "@/types/api";

import { confirmIntake } from "./api";

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
