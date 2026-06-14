import { NextRequest, NextResponse } from "next/server";
import {
  AUTHENTIK_FORWARD_HEADERS,
  authentikHeadersTrusted,
  trustedAuthentikUsername,
} from "@/lib/authentik";

const COOKIE = "tg_journal_auth";
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8199";

/*
 * Authentik integration
 * =====================
 * When deployed behind an Authentik outpost, forwarded identity headers
 * replace the legacy JOURNAL_TOKEN cookie auth.  The proxy reads these headers
 * only when AUTHENTIK_TRUST_PROXY_HEADERS=true (see src/lib/authentik.ts);
 * otherwise the legacy cookie check is used.
 */

export function isAuthed(req: NextRequest): boolean {
  // Authentik path — only when header trust is explicitly enabled
  if (trustedAuthentikUsername(req)) {
    return true;
  }

  // Legacy fallback — JOURNAL_TOKEN cookie
  const token = req.cookies.get(COOKIE)?.value;
  const expected = process.env.JOURNAL_TOKEN;
  return !!expected && token === expected;
}

function getApiHeaders(req: NextRequest): Record<string, string> {
  const headers: Record<string, string> = {};
  // Forward Authentik identity headers to the backend only when trusted, so a
  // client cannot smuggle forged identity headers through the proxy.
  if (authentikHeadersTrusted()) {
    for (const h of AUTHENTIK_FORWARD_HEADERS) {
      const v = req.headers.get(h);
      if (v) {
        headers[h] = v;
      }
    }
  }
  // Legacy X-API-Key fallback
  const token = req.cookies.get(COOKIE)?.value;
  if (token) {
    headers["X-API-Key"] = token;
  }
  return headers;
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
