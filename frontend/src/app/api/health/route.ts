import { NextResponse } from "next/server";

export async function GET() {
  const apiUrl = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  try {
    const response = await fetch(`${apiUrl}/health`, { cache: "no-store" });
    return NextResponse.json(
      { status: response.ok ? "ok" : "unavailable" },
      { status: response.ok ? 200 : 503 },
    );
  } catch {
    return NextResponse.json({ status: "unavailable" }, { status: 503 });
  }
}
