import { NextRequest, NextResponse } from "next/server";

interface RouteContext {
  params: Promise<{ path: string[] }>;
}

export async function GET(request: NextRequest, context: RouteContext) {
  const apiUrl = process.env.API_URL ?? "http://localhost:8000";
  const { path } = await context.params;
  const backendPath = path.map(encodeURIComponent).join("/");

  try {
    const response = await fetch(
      `${apiUrl}/api/cases/${backendPath}${request.nextUrl.search}`,
      { cache: "no-store", headers: { Accept: "application/json" } },
    );
    const payload: unknown = await response.json();
    return NextResponse.json(payload, { status: response.status });
  } catch {
    return NextResponse.json(
      { detail: "The Citizen Bridge service is currently unreachable." },
      { status: 503 },
    );
  }
}
