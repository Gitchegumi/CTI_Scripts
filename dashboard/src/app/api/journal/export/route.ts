import { NextRequest, NextResponse } from "next/server";

const COOKIE = "tg_journal_auth";
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8199";

function isAuthed(req: NextRequest): boolean {
  const token = req.cookies.get(COOKIE)?.value;
  const expected = process.env.JOURNAL_TOKEN;
  return !!expected && token === expected;
}

function getApiHeaders(req: NextRequest): Record<string, string> {
  const token = req.cookies.get(COOKIE)?.value;
  return token ? { "X-API-Key": token } : {};
}

const EXPORT_QUERY_PARAMS = [
  "grade",
  "start",
  "end",
  "symbol",
  "status",
  "final_decision",
  "strategy",
  "mode",
  "graded_state",
];

function buildExportQuery(req: NextRequest): string {
  const params = new URLSearchParams();
  for (const name of EXPORT_QUERY_PARAMS) {
    const value = req.nextUrl.searchParams.get(name);
    if (value) params.set(name, value);
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export async function GET(req: NextRequest) {
  if (!isAuthed(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  try {
    const qs = buildExportQuery(req);
    const res = await fetch(`${API_BASE}/api/journal/export${qs}`, {
      cache: "no-store",
      headers: getApiHeaders(req),
    });
    const body = await res.arrayBuffer();
    const headers = new Headers();
    headers.set("Content-Type", res.headers.get("Content-Type") ?? "text/csv; charset=utf-8");
    const disposition = res.headers.get("Content-Disposition");
    if (disposition) headers.set("Content-Disposition", disposition);
    return new NextResponse(body, {
      status: res.status,
      headers,
    });
  } catch {
    return NextResponse.json({ error: "Could not reach API server" }, { status: 502 });
  }
}
