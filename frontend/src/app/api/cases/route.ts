import { NextRequest } from "next/server";

import { proxyBackendRequest } from "../_proxy";

export async function POST(request: NextRequest) {
  return proxyBackendRequest(request, "/api/cases");
}
