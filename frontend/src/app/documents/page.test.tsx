import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import DocumentsPage from "./page";

afterEach(() => vi.restoreAllMocks());

test("uploads a local file and shows the DigiLocker future scope", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    if (String(input) === "/api/docs/upload-file") {
      const body = init?.body as FormData;
      expect(body.get("source")).toBe("local");
      expect((body.get("file") as File).name).toBe("aadhaar.pdf");
      return Response.json({ id: "document-1" }, { status: 201 });
    }
    return Response.json({ documents_by_category: {} });
  });

  render(<DocumentsPage />);

  expect(await screen.findByText(/Get verified documents directly from the DigiLocker API/i)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText(/From this device/i), {
    target: { files: [new File(["document"], "aadhaar.pdf", { type: "application/pdf" })] },
  });
  fireEvent.change(screen.getByLabelText("Document name"), { target: { value: "Aadhaar" } });
  fireEvent.change(screen.getByLabelText("Document type"), { target: { value: "aadhaar" } });
  fireEvent.click(screen.getByRole("button", { name: "Upload document" }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    "/api/docs/upload-file",
    expect.objectContaining({ method: "POST" }),
  ));
});

test("explains when Google Drive credentials are not configured", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({ documents_by_category: {} }));
  render(<DocumentsPage />);

  fireEvent.click(await screen.findByRole("button", { name: "Choose from Google Drive" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Google Drive needs CLIENT_ID, API_KEY, and APP_ID configuration.");
});
