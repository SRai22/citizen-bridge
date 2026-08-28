import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import type { NewBabyProfile } from "@/types/api";

import { ProfileSummary } from "./profile-summary";

test("renders a baby profile without bereavement assets", () => {
  const profile: NewBabyProfile = {
    baby: { name: "Anaya Rao", dob: "2026-08-20", gender: "female" },
    parents: ["Asha Rao", "Vikram Rao"],
    birth_place: "Bengaluru General Hospital",
    location: { city: "Bengaluru", state: "Karnataka" },
  };

  render(
    <ProfileSummary
      busy={false}
      categoryId="new_baby"
      error={null}
      onClarify={vi.fn()}
      onConfirm={vi.fn()}
      profile={profile}
    />,
  );

  expect(screen.getByText("Anaya Rao")).toBeInTheDocument();
  expect(screen.getByText("Asha Rao and Vikram Rao")).toBeInTheDocument();
  expect(screen.getByText("Bengaluru General Hospital")).toBeInTheDocument();
  expect(screen.getByText("New Baby workflow")).toBeInTheDocument();
  expect(screen.queryByText("BESCOM connection")).not.toBeInTheDocument();
});
