import { NextRequest } from "next/server";

import { proxyBackendRequest } from "../../_proxy";

interface RouteContext {
  params: Promise<{ path: string[] }>;
}

export async function GET(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const backendPath = path.map(encodeURIComponent).join("/");
  return proxyBackendRequest(request, `/api/cases/${backendPath}`);
}

export async function POST(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const backendPath = path.map(encodeURIComponent).join("/");
  return proxyBackendRequest(request, `/api/cases/${backendPath}`);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const backendPath = path.map(encodeURIComponent).join("/");
  return proxyBackendRequest(request, `/api/cases/${backendPath}`);
}
