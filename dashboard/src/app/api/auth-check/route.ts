import { NextRequest, NextResponse } from "next/server";
import { trustedAuthentikUsername } from "@/lib/authentik";

const COOKIE = "tg_journal_auth";

function isAuthed(req: NextRequest): boolean {
  // Authentik path — only when header trust is explicitly enabled
  if (trustedAuthentikUsername(req)) {
    return true;
  }
  // Legacy fallback
  const token = req.cookies.get(COOKIE)?.value;
  const expected = process.env.JOURNAL_TOKEN;
  return !!expected && token === expected;
}

export async function GET(req: NextRequest) {
  const authed = isAuthed(req);
  const username = trustedAuthentikUsername(req);
  return NextResponse.json({ authed, username });
}
