import { NextRequest } from "next/server";
import { proxyMetrics } from "../_auth";

export async function GET(req: NextRequest) {
  return proxyMetrics(req, "/api/strategy-metrics/compare");
}
