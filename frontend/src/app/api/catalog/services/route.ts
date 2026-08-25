import { NextRequest } from "next/server";

import { proxyBackendRequest } from "../../_proxy";

export function GET(request: NextRequest) {
  return proxyBackendRequest(request, "/api/catalog/services");
}
