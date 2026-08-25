import { NextRequest } from "next/server";

import { proxyBackendRequest } from "../../_proxy";

interface RouteContext {
  params: Promise<{ path: string[] }>;
}

export async function POST(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  if (path.length === 1 && path[0] === "start") {
    return proxyBackendRequest(request, "/api/ai/intake/start");
  }

  const [conversationId, action] = path;
  return proxyBackendRequest(
    request,
    `/api/ai/intake/${encodeURIComponent(conversationId)}/${encodeURIComponent(action)}`,
  );
}
