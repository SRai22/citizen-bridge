import { NextRequest, NextResponse } from "next/server";

export async function proxyBackendRequest(
  request: NextRequest,
  backendPath: string,
  body?: string,
) {
  const apiUrl = process.env.API_URL ?? "http://localhost:8000";
  const requestBody = body ?? (request.method === "GET" ? undefined : await request.text());
  const contentType = request.headers.get("content-type");
  const headers = new Headers({ Accept: "application/json" });
  if (contentType || body) headers.set("Content-Type", contentType ?? "application/json");
  const token = request.cookies.get("access_token")?.value;
  const correlationId = request.headers.get("x-correlation-id");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (correlationId) headers.set("X-Correlation-ID", correlationId);

  try {
    const response = await fetch(`${apiUrl}${backendPath}${request.nextUrl.search}`, {
      method: request.method,
      headers,
      body: requestBody || undefined,
      cache: "no-store",
    });
    const payload = await response.text();
    const result = new NextResponse(payload, {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("content-type") ?? "application/json",
        ...(response.headers.get("x-correlation-id")
          ? { "X-Correlation-ID": response.headers.get("x-correlation-id")! }
          : {}),
      },
    });
    if (response.ok && backendPath === "/api/auth/login") {
      const tokens = JSON.parse(payload) as { access_token: string; refresh_token: string };
      result.cookies.set("access_token", tokens.access_token, cookieOptions(request, 15 * 60));
      result.cookies.set(
        "refresh_token",
        tokens.refresh_token,
        cookieOptions(request, 7 * 24 * 60 * 60),
      );
    } else if (backendPath === "/api/auth/logout") {
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

function cookieOptions(request: NextRequest, maxAge: number) {
  return { httpOnly: true, maxAge, sameSite: "lax" as const, secure: request.nextUrl.protocol === "https:" };
}
