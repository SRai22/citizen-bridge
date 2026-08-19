import { NextRequest, NextResponse } from "next/server";

export async function proxyBackendRequest(request: NextRequest, backendPath: string) {
  const apiUrl = process.env.API_URL ?? "http://localhost:8000";
  const requestBody = request.method === "GET" ? undefined : await request.text();
  const contentType = request.headers.get("content-type");
  const headers = new Headers({ Accept: "application/json" });
  if (contentType) headers.set("Content-Type", contentType);

  try {
    const response = await fetch(`${apiUrl}${backendPath}${request.nextUrl.search}`, {
      method: request.method,
      headers,
      body: requestBody || undefined,
      cache: "no-store",
    });
    const payload = await response.text();
    return new NextResponse(payload, {
      status: response.status,
      headers: { "Content-Type": response.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return NextResponse.json(
      { detail: "The Citizen Bridge service is currently unreachable." },
      { status: 503 },
    );
  }
}
