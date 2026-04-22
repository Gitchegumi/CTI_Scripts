import { NextRequest, NextResponse } from "next/server";

const COOKIE = "tg_journal_auth";

export async function POST(req: NextRequest) {
  const { token } = await req.json();
  const expected = process.env.JOURNAL_TOKEN;

  if (!expected) {
    return NextResponse.json({ error: "Journal auth not configured (JOURNAL_TOKEN missing)" }, { status: 500 });
  }

  if (!token || token !== expected) {
    return NextResponse.json({ error: "Invalid token" }, { status: 401 });
  }

  const res = NextResponse.json({ ok: true });
  res.cookies.set(COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    // Session cookie — expires when browser closes
  });
  return res;
}
