import { NextRequest, NextResponse } from "next/server";

export async function proxyBackendRequest(
  request: NextRequest,
  backendPath: string,
  body?: string,
) {
  const apiUrl = process.env.API_URL ?? "http://localhost:8000";
  const requestBody = body ?? (request.method === "GET" ? undefined : await request.text());
  const contentType = request.headers.get("content-type");
  const accessToken = request.cookies.get("access_token")?.value;
  const refreshToken = request.cookies.get("refresh_token")?.value;
  const correlationId = request.headers.get("x-correlation-id");

  try {
    let response = await backendFetch(
      `${apiUrl}${backendPath}${request.nextUrl.search}`,
      request.method,
      requestBody,
      contentType,
      correlationId,
      accessToken,
    );
    let rotatedTokens: Tokens | null = null;
    if (response.status === 401 && refreshToken && canRefresh(backendPath)) {
      const refreshed = await fetch(`${apiUrl}/api/auth/refresh`, {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
        cache: "no-store",
      });
      if (refreshed.ok) {
        rotatedTokens = (await refreshed.json()) as Tokens;
        response = await backendFetch(
          `${apiUrl}${backendPath}${request.nextUrl.search}`,
          request.method,
          requestBody,
          contentType,
          correlationId,
          rotatedTokens.access_token,
        );
      }
    }

    let payload = await response.text();
    if (response.ok && isSessionStart(backendPath)) {
      rotatedTokens = JSON.parse(payload) as Tokens;
      payload = JSON.stringify({ user_id: rotatedTokens.user_id });
    }
    const result = backendResponse(response, payload);
    if (rotatedTokens) setTokenCookies(result, request, rotatedTokens);
    if (backendPath === "/api/auth/logout") {
      result.cookies.delete("access_token");
      result.cookies.delete("refresh_token");
    }
    return result;
  } catch {
    return NextResponse.json(
      { detail: "The Citizen Bridge service is currently unreachable." },
      { status: 503 },
    );
  }
}

interface Tokens {
  user_id?: string;
  access_token: string;
  refresh_token: string;
}

function backendFetch(
  url: string,
  method: string,
  body: string | undefined,
  contentType: string | null,
  correlationId: string | null,
  token?: string,
) {
  const headers = new Headers({ Accept: "application/json" });
  if (contentType || body) headers.set("Content-Type", contentType ?? "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (correlationId) headers.set("X-Correlation-ID", correlationId);
  return fetch(url, { method, headers, body: body || undefined, cache: "no-store" });
}

function backendResponse(response: Response, payload: string) {
  return new NextResponse(payload, {
    status: response.status,
    headers: {
      "Content-Type": response.headers.get("content-type") ?? "application/json",
      ...(response.headers.get("x-correlation-id")
        ? { "X-Correlation-ID": response.headers.get("x-correlation-id")! }
        : {}),
    },
  });
}

function canRefresh(path: string) {
  return !["/api/auth/login", "/api/auth/register", "/api/auth/refresh", "/api/auth/logout"].includes(path);
}

function isSessionStart(path: string) {
  return path === "/api/auth/login" || path === "/api/auth/register";
}

function setTokenCookies(result: NextResponse, request: NextRequest, tokens: Tokens) {
  result.cookies.set("access_token", tokens.access_token, cookieOptions(request, 15 * 60));
  result.cookies.set(
    "refresh_token",
    tokens.refresh_token,
    cookieOptions(request, 7 * 24 * 60 * 60),
  );
}

function cookieOptions(request: NextRequest, maxAge: number) {
  return {
    httpOnly: true,
    maxAge,
    path: "/",
    sameSite: "lax" as const,
    secure: request.nextUrl.protocol === "https:",
  };
}
