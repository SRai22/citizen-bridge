import { afterEach, expect, test, vi } from "vitest";

import type { FamilyMember, IntakeHouseholdProfile, MarriageProfile, NewBabyProfile } from "@/types/api";

import { ApiError, confirmIntake } from "./api";

afterEach(() => vi.restoreAllMocks());

test("creates baby cases with baby workflow context and no BESCOM data", async () => {
  const profile: NewBabyProfile = {
    baby: { name: "Anaya Rao", dob: "2026-08-20", gender: "female" },
    parents: ["Asha Rao", "Vikram Rao"],
    birth_place: "Bengaluru General Hospital",
    location: { city: "Bengaluru", state: "Karnataka" },
    hospital_record_uploaded: true,
  };
  const fetchMock = vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(Response.json({ profile }))
    .mockResolvedValueOnce(Response.json({
      id: "family-baby", name: "Anaya Rao", relationship: "child",
      date_of_birth: profile.baby.dob, phone: null, is_deceased: false, death_date: null,
      source: "intake", created_at: "2026-08-20T00:00:00Z", updated_at: "2026-08-20T00:00:00Z",
    }, { status: 201 }))
    .mockResolvedValueOnce(Response.json({
      id: "family-parent", name: "Vikram Rao", relationship: "spouse",
      date_of_birth: null, phone: null, is_deceased: false, death_date: null,
      source: "intake", created_at: "2026-08-20T00:00:00Z", updated_at: "2026-08-20T00:00:00Z",
    }, { status: 201 }))
    .mockResolvedValueOnce(Response.json({ case_id: "case-1" }));

  await expect(confirmIntake("conversation-1", "new_baby")).resolves.toEqual({
    case_id: "case-1",
  });

  expect(fetchMock.mock.calls.slice(1, 3).map(([url]) => url)).toEqual([
    "/api/auth/me/family",
    "/api/auth/me/family",
  ]);
  expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toMatchObject({
    name: "Anaya Rao", relationship: "child", date_of_birth: "2026-08-20", source: "intake",
  });
  expect(JSON.parse(String(fetchMock.mock.calls[2][1]?.body))).toMatchObject({
    name: "Vikram Rao", relationship: "spouse", source: "intake",
  });
  const [url, init] = fetchMock.mock.calls[3];
  const payload = JSON.parse(String(init?.body));
  expect(String(url)).toBe("/api/cases");
  expect(payload.life_event.context).toMatchObject({ category_id: "new_baby", ...profile });
  expect(payload.life_event.context).not.toHaveProperty("assets");
  expect(payload.household_profile.people).toHaveLength(2);
  expect(payload.household_profile.people[0]).toMatchObject({ id: "family-baby", relationship: "child" });
  expect(payload.subject_person_index).toBe(0);
});

test("adds the named partner as a pending spouse before creating a marriage case", async () => {
  const profile: MarriageProfile = {
    spouse1: "Asha Rao",
    spouse2: "Vikram Rao",
    marriage_date: "2026-08-20",
    marriage_place: "Bengaluru",
    location: { city: "Bengaluru", state: "Karnataka" },
    change_address: true,
    change_name: false,
    add_to_ration_card: true,
  };
  const fetchMock = vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(Response.json({ profile }))
    .mockResolvedValueOnce(Response.json({
      id: "family-spouse", name: "Vikram Rao", relationship: "spouse",
      date_of_birth: null, phone: null, is_deceased: false, death_date: null,
      source: "intake", created_at: "2026-08-20T00:00:00Z", updated_at: "2026-08-20T00:00:00Z",
    }, { status: 201 }))
    .mockResolvedValueOnce(Response.json({ case_id: "case-2" }));

  await confirmIntake("conversation-2", "marriage");

  expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toMatchObject({
    name: "Vikram Rao", relationship: "spouse", source: "intake",
  });
  const payload = JSON.parse(String(fetchMock.mock.calls[2][1]?.body));
  expect(payload.household_profile.people[0]).toMatchObject({
    id: "family-spouse", name: "Vikram Rao", relationship: "spouse",
  });
  expect(payload.subject_relationship).toBe("spouse");
});

test("rejects a profile returned for the wrong intake category", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(Response.json({
    profile: {
      spouse1: "Asha Rao",
      spouse2: "Vikram Rao",
      marriage_date: "2026-08-20",
      marriage_place: "Bengaluru",
      location: { city: "Bengaluru", state: "Karnataka" },
      change_address: false,
      change_name: false,
      add_to_ration_card: false,
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
