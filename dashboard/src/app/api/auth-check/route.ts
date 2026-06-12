import { NextRequest, NextResponse } from "next/server";

const COOKIE = "tg_journal_auth";

function isAuthed(req: NextRequest): boolean {
  // Authentik path
  if (req.headers.get("x-authentik-username")) {
    return true;
  }
  // Legacy fallback
  const token = req.cookies.get(COOKIE)?.value;
  const expected = process.env.JOURNAL_TOKEN;
  return !!expected && token === expected;
}

export async function GET(req: NextRequest) {
  const authed = isAuthed(req);
  const username = req.headers.get("x-authentik-username") || null;
  return NextResponse.json({ authed, username });
}
