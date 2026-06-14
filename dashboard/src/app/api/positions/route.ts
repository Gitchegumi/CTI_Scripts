import { NextRequest } from "next/server";
import { proxyApi } from "@/app/api/_proxy";

export async function GET(req: NextRequest) {
  return proxyApi(req, "/api/positions");
}
