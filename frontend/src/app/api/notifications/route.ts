import { NextRequest } from "next/server";

import { proxyBackendRequest } from "../_proxy";

export async function GET(request: NextRequest) {
  return proxyBackendRequest(request, "/api/notifications");
}

export async function POST(request: NextRequest) {
  return proxyBackendRequest(request, "/api/notifications/read-all");
}
