import { NextRequest, NextResponse } from "next/server";
import { trustedAuthentikUsername } from "@/lib/authentik";

const COOKIE = "tg_journal_auth";

/*
 * Authentik integration
 * =====================
 * When the dashboard is deployed behind an Authentik outpost, Authentik
 * injects forwarded headers after successful authentication.  Those headers
 * are trusted ONLY when AUTHENTIK_TRUST_PROXY_HEADERS=true and the proxy is
 * known to strip client-supplied x-authentik-* headers (see src/lib/authentik.ts).
 *
 * Authentik proxy-provider header mappings used when enabled:
 *   X-authentik-username
 *   X-authentik-email
 *   X-authentik-groups
 *   X-authentik-uid
 *   X-authentik-name
 */

export function isAuthed(req: NextRequest): boolean {
  // 1. Authentik path — only when header trust is explicitly enabled
  if (trustedAuthentikUsername(req)) {
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
