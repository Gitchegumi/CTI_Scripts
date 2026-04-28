import { NextRequest, NextResponse } from "next/server";

const COOKIE = "tg_journal_auth";

export function middleware(req: NextRequest) {
  // Login page is always accessible
  if (req.nextUrl.pathname.startsWith("/journal/login")) {
    return NextResponse.next();
  }

  const token = req.cookies.get(COOKIE)?.value;
  const expected = process.env.JOURNAL_TOKEN;

  if (!expected || token !== expected) {
    const url = req.nextUrl.clone();
    url.pathname = "/journal/login";
    url.searchParams.set("from", req.nextUrl.pathname);
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/journal/:path*", "/manual-trades/:path*"],
};
