import { NextRequest } from "next/server";
import { afterEach, expect, test, vi } from "vitest";

import { proxyBackendRequest } from "./_proxy";

afterEach(() => vi.restoreAllMocks());

test("stores registration tokens in HTTP-only cookies without returning them to the client", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
    Response.json({
      user_id: "user-1",
      access_token: "access-1",
      refresh_token: "refresh-1",
    }),
  );
  const request = new NextRequest("http://localhost/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: "asha" }),
  });

  const response = await proxyBackendRequest(request, "/api/auth/register");

  expect(await response.json()).toEqual({ user_id: "user-1" });
  expect(response.headers.get("set-cookie")).toContain("access_token=access-1");
  expect(response.headers.get("set-cookie")).toContain("HttpOnly");
});

test("rotates an expired access token and retries the original request", async () => {
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(Response.json({ detail: "expired" }, { status: 401 }))
    .mockResolvedValueOnce(
      Response.json({ access_token: "access-2", refresh_token: "refresh-2" }),
    )
    .mockResolvedValueOnce(
      Response.json({ user_id: "user-1", username: "asha", name: "Asha Rao" }),
    );
  const request = new NextRequest("http://localhost/api/auth/session", {
    headers: { Cookie: "access_token=expired; refresh_token=refresh-1" },
  });

  const response = await proxyBackendRequest(request, "/api/auth/me");

  expect(response.status).toBe(200);
  expect(fetchMock).toHaveBeenCalledTimes(3);
  expect(new Headers(fetchMock.mock.calls[2]?.[1]?.headers).get("Authorization")).toBe(
    "Bearer access-2",
  );
  expect(response.headers.get("set-cookie")).toContain("refresh_token=refresh-2");
});
