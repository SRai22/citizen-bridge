import { afterEach, expect, test, vi } from "vitest";

import type { FamilyMember, IntakeHouseholdProfile, NewBabyProfile } from "@/types/api";

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

test("marks a selected family member deceased instead of creating a duplicate", async () => {
  const profile: IntakeHouseholdProfile = {
    deceased: { name: "Arun Rao", relationship: "father", occupation: "retired", pension_status: "active" },
    death_date: "2026-08-20",
    surviving_members: [],
    location: { city: "Bengaluru", state: "Karnataka" },
    assets: { bescom: true, ration_card: true, property: false },
  };
  const father: FamilyMember = {
    id: "family-1", name: "Arun Rao", relationship: "father", date_of_birth: null,
    phone: null, is_deceased: false, death_date: null, source: "manual",
    created_at: "2026-08-20T00:00:00Z", updated_at: "2026-08-20T00:00:00Z",
  };
  const fetchMock = vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(Response.json({ profile }))
    .mockResolvedValueOnce(Response.json({ ...father, is_deceased: true, death_date: profile.death_date }))
    .mockResolvedValueOnce(Response.json({ case_id: "case-1" }));

  await confirmIntake("conversation-1", "bereavement", father);

  expect(fetchMock.mock.calls[1][0]).toBe("/api/auth/me/family/family-1");
  expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual({
    is_deceased: true,
    death_date: "2026-08-20",
  });
  expect(fetchMock.mock.calls.some(([url, init]) =>
    url === "/api/auth/me/family" && init?.method === "POST"
  )).toBe(false);
});
