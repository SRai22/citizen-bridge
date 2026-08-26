import { NextRequest } from "next/server";

import { proxyBackendRequest } from "../_proxy";

export async function GET(request: NextRequest) {
  return proxyBackendRequest(request, "/api/cases");
}

export async function POST(request: NextRequest) {
  return proxyBackendRequest(request, "/api/cases");
}
