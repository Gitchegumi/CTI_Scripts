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

export async function GET(req: NextRequest) {
  if (!isAuthed(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  try {
    const grade = req.nextUrl.searchParams.get("grade");
    const qs = grade ? `?grade=${encodeURIComponent(grade)}` : "";
    const res = await fetch(`${API_BASE}/api/journal/export${qs}`, {
      cache: "no-store",
      headers: getApiHeaders(req),
    });
    const body = await res.text();
    return new NextResponse(body, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("Content-Type") ?? "text/csv; charset=utf-8" },
    });
  } catch {
    return NextResponse.json({ error: "Could not reach API server" }, { status: 502 });
  }
}
