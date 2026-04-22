import { NextRequest, NextResponse } from "next/server";

const COOKIE = "tg_journal_auth";

export async function GET(req: NextRequest) {
  const token = req.cookies.get(COOKIE)?.value;
  const expected = process.env.JOURNAL_TOKEN;

  if (!expected || token !== expected) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8199";
  try {
    const res = await fetch(`${apiBase}/api/data/journal`, { cache: "no-store" });
    if (!res.ok) {
      return NextResponse.json({ error: `Upstream error ${res.status}` }, { status: res.status });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json({ error: "Could not reach API server" }, { status: 502 });
  }
}
