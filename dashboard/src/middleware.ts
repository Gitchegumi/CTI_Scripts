import { NextRequest, NextResponse } from "next/server";

const COOKIE = "tg_journal_auth";

/*
 * Authentik integration
 * =====================
 * When the dashboard is deployed behind an Authentik outpost, Authentik
 * injects forwarded headers after successful authentication.  The app trusts
 * these headers and skips the legacy JOURNAL_TOKEN cookie check.
 *
 * Required Authentik proxy-provider header mappings (default):
 *   X-authentik-username
 *   X-authentik-email
 *   X-authentik-groups
 *   X-authentik-uid
 *   X-authentik-name
 */

export function isAuthed(req: NextRequest): boolean {
  // 1. Authentik path — check forwarded headers from the outpost
  const authentikUser = req.headers.get("x-authentik-username");
  if (authentikUser) {
    return true;
  }

  // 2. Legacy fallback — JOURNAL_TOKEN cookie (local dev / self-hosted)
  const expected = process.env.JOURNAL_TOKEN;
  if (!expected) {
    return true; // No auth required if not configured
  }
  const token = req.cookies.get(COOKIE)?.value;
  return token === expected;
}

export function middleware(req: NextRequest) {
  // Login page is always accessible (Authentik redirects here if needed)
  if (req.nextUrl.pathname.startsWith("/journal/login")) {
    return NextResponse.next();
  }

  if (!isAuthed(req)) {
    const url = req.nextUrl.clone();
    url.pathname = "/journal/login";
    url.searchParams.set("from", req.nextUrl.pathname);
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/journal/:path*", "/manual-trades", "/manual-trades/:path*"],
};
