import { NextRequest, NextResponse } from "next/server";

const COOKIE = "tg_journal_auth";

export async function GET(req: NextRequest) {
  const token = req.cookies.get(COOKIE)?.value;
  const expected = process.env.JOURNAL_TOKEN;

  if (!expected) {
    return NextResponse.json({ error: "Auth not configured" }, { status: 500 });
  }

  const authed = !!token && token === expected;
  return NextResponse.json({ authed });
}
