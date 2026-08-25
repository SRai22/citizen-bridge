import { NextRequest } from "next/server";

import { proxyBackendRequest } from "../../_proxy";

interface RouteContext {
  params: Promise<{ path: string[] }>;
}

export async function GET(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return proxyBackendRequest(request, `/api/docs/${path.map(encodeURIComponent).join("/")}`);
}

export async function POST(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return proxyBackendRequest(request, `/api/docs/${path.map(encodeURIComponent).join("/")}`);
}
