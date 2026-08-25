import { NextRequest } from "next/server";

import { proxyBackendRequest } from "../../_proxy";

interface RouteContext {
  params: Promise<{ path: string[] }>;
}

function authPath(path: string[]) {
  return `/api/auth/${path[0] === "session" ? "me" : path.map(encodeURIComponent).join("/")}`;
}

export async function GET(request: NextRequest, context: RouteContext) {
  return proxyBackendRequest(request, authPath((await context.params).path));
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxyBackendRequest(request, authPath((await context.params).path));
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return proxyBackendRequest(request, authPath((await context.params).path));
}
