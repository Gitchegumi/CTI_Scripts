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
    const res = await fetch(`${API_BASE}/api/data/journal`, { cache: "no-store" });
    if (!res.ok) {
      return NextResponse.json({ error: `Upstream error ${res.status}` }, { status: res.status });
    }
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ error: "Could not reach API server" }, { status: 502 });
  }
}

export async function POST(req: NextRequest) {
  if (!isAuthed(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  try {
    const body = await req.json();
    // Route to the correct backend endpoint based on payload
    const endpoint = body.invalidate === true
      ? "/api/journal/invalidate"
      : body.grade != null
        ? "/api/journal/grade"
        : "/api/journal/notes";
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "Could not reach API server" }, { status: 502 });
  }
}

export async function DELETE(req: NextRequest) {
  if (!isAuthed(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  try {
    const grade = req.nextUrl.searchParams.get("grade");
    const qs = grade ? `?grade=${encodeURIComponent(grade)}` : "";
    const res = await fetch(`${API_BASE}/api/journal${qs}`, {
      method: "DELETE",
      headers: getApiHeaders(req),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "Could not reach API server" }, { status: 502 });
  }
}
