import { NextRequest, NextResponse } from "next/server";

const COOKIE = "tg_journal_auth";
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8199";

function isAuthed(req: NextRequest): boolean {
  const token = req.cookies.get(COOKIE)?.value;
  const expected = process.env.JOURNAL_TOKEN;
  return !!expected && token === expected;
}

function getApiHeaders(req: NextRequest): Record<string, string> {
  const headers: Record<string, string> = {};
  const token = req.cookies.get(COOKIE)?.value;
  if (token) headers["X-API-Key"] = token;
  return headers;
}

export async function GET(req: NextRequest) {
  if (!isAuthed(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const qs = req.nextUrl.searchParams.toString();
    const res = await fetch(`${API_BASE}/api/trades/manual/export${qs ? `?${qs}` : ""}`, {
      cache: "no-store",
      headers: getApiHeaders(req),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { error: "Could not reach API server" },
      { status: 502 }
    );
  }
}
