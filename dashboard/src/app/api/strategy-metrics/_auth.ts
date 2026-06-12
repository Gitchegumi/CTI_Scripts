import { NextRequest, NextResponse } from "next/server";

const COOKIE = "tg_journal_auth";
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8199";

function getApiHeaders(req: NextRequest): Record<string, string> {
  const token = req.cookies.get(COOKIE)?.value;
  return token ? { "X-API-Key": token } : {};
}

export function isAuthed(req: NextRequest): boolean {
  const token = req.cookies.get(COOKIE)?.value;
  const expected = process.env.JOURNAL_TOKEN;
  return !!expected && token === expected;
}

export async function proxyMetrics(req: NextRequest, backendPath: string) {
  if (!isAuthed(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const url = new URL(req.url);
  const upstream = `${API_BASE}${backendPath}${url.search}`;
  try {
    const res = await fetch(upstream, {
      cache: "no-store",
      headers: getApiHeaders(req),
    });
    const contentType = res.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      const data = await res.json();
      return NextResponse.json(data, { status: res.status });
    }
    const text = await res.text();
    return NextResponse.json(
      { error: text || `Upstream returned ${res.status}` },
      { status: res.status }
    );
  } catch {
    return NextResponse.json({ error: "Could not reach API server" }, { status: 502 });
  }
}
