import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { citizenCase, deathCertificate } from "@/test/fixtures";

import { DocumentsPanel } from "./documents-panel";

test("shows document metadata, producer, consumers, and count", () => {
  render(
    <DocumentsPanel
      citizenCase={{ ...citizenCase, documents: [deathCertificate] }}
      requirementsByTask={{
        "task-pension": [
          {
            type: "death_certificate",
            owner: "deceased",
            description: null,
            status: "satisfied",
          },
        ],
      }}
    />,
  );

  expect(screen.getByLabelText("1 document")).toHaveTextContent("1");
  expect(screen.getByRole("heading", { name: "Death Certificate" })).toBeInTheDocument();
  expect(screen.getByText("Owner: Arun Rao")).toBeInTheDocument();
  expect(screen.getByText(/BBMP South Zone/)).toBeInTheDocument();
  expect(screen.getByText(/15 Aug 2026/)).toBeInTheDocument();
  expect(screen.getByText("Obtain Death Certificate")).toHaveAttribute(
    "href",
    "/case/case-12345678/task/task-death",
  );
  expect(screen.getByText("Apply for Family Pension")).toHaveAttribute(
    "href",
    "/case/case-12345678/task/task-pension",
  );
});
