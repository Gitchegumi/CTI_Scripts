import { NextRequest } from "next/server";
import { proxyApi } from "@/app/api/_proxy";

type RouteContext = { params: Promise<{ path: string[] }> };

export async function POST(req: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return proxyApi(req, `/api/config/${path.join("/")}`);
}

export async function OPTIONS(req: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return proxyApi(req, `/api/config/${path.join("/")}`);
}
