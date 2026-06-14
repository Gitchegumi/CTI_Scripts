import { NextRequest, NextResponse } from "next/server";

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "content-length",
  "host",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

export function apiBase(): string {
  return (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8199").replace(/\/$/, "");
}

function proxyHeaders(req: NextRequest): Headers {
  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });
  return headers;
}

export async function proxyApi(req: NextRequest, backendPath: string) {
  const source = new URL(req.url);
  const upstream = `${apiBase()}${backendPath}${source.search}`;
  try {
    const method = req.method.toUpperCase();
    const hasBody = !["GET", "HEAD"].includes(method);
    const res = await fetch(upstream, {
      method,
      headers: proxyHeaders(req),
      body: hasBody ? await req.text() : undefined,
      cache: "no-store",
    });
    const body = await res.arrayBuffer();
    const headers = new Headers(res.headers);
    headers.delete("content-encoding");
    headers.delete("content-length");
    return new NextResponse(body, { status: res.status, headers });
  } catch (error) {
    return NextResponse.json(
      {
        error: "Could not reach API server",
        upstream,
        detail: error instanceof Error ? error.message : String(error),
      },
      { status: 502 }
    );
  }
}
