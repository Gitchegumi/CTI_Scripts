import { NextRequest } from "next/server";
import { proxyMetrics } from "../../_auth";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ criterionName: string }> }
) {
  const { criterionName } = await params;
  const proxyPath = `/api/strategy-metrics/criteria/${encodeURIComponent(criterionName)}`;
  return proxyMetrics(req, proxyPath);
}