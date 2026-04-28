import { NextRequest, NextResponse } from "next/server";

const COOKIE = "tg_journal_auth";
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8199";

function isAuthed(req: NextRequest): boolean {
  const token = req.cookies.get(COOKIE)?.value;
  const expected = process.env.JOURNAL_TOKEN;
  return !!expected && token === expected;
}

function getApiHeaders(req: NextRequest): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = req.cookies.get(COOKIE)?.value;
  if (token) {
    headers["X-API-Key"] = token;
  }
  return headers;
}

// GET /api/manual-trades — list manual trades with optional filters
export async function GET(req: NextRequest) {
  if (!isAuthed(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    // Forward query params to the backend
    const { searchParams } = new URL(req.url);
    const qs = searchParams.toString();
    const url = `${API_BASE}/api/trades/manual${qs ? "?" + qs : ""}`;

    const res = await fetch(url, {
      cache: "no-store",
      headers: getApiHeaders(req),
    });
    if (!res.ok) {
      return NextResponse.json(
        { error: `Upstream error ${res.status}` },
        { status: res.status }
      );
    }
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json(
      { error: "Could not reach API server" },
      { status: 502 }
    );
  }
}

// POST /api/manual-trades — create a new manual trade
export async function POST(req: NextRequest) {
  if (!isAuthed(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const body = await req.json();
    const res = await fetch(`${API_BASE}/api/trades/manual`, {
      method: "POST",
      headers: getApiHeaders(req),
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { error: "Could not reach API server" },
      { status: 502 }
    );
  }
}

// PUT /api/manual-trades/:id — update a manual trade
export async function PUT(req: NextRequest) {
  if (!isAuthed(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    // Extract ID from path: /api/manual-trades/123
    const id = req.nextUrl.pathname.split("/").pop();
    if (!id || id === "manual-trades") {
      return NextResponse.json({ error: "Trade ID required" }, { status: 400 });
    }

    const body = await req.json();
    const res = await fetch(`${API_BASE}/api/trades/manual/${id}`, {
      method: "PUT",
      headers: getApiHeaders(req),
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { error: "Could not reach API server" },
      { status: 502 }
    );
  }
}

// DELETE /api/manual-trades/:id — delete a manual trade
export async function DELETE(req: NextRequest) {
  if (!isAuthed(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const id = req.nextUrl.pathname.split("/").pop();
    if (!id || id === "manual-trades") {
      return NextResponse.json({ error: "Trade ID required" }, { status: 400 });
    }

    const res = await fetch(`${API_BASE}/api/trades/manual/${id}`, {
      method: "DELETE",
      headers: getApiHeaders(req),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { error: "Could not reach API server" },
      { status: 502 }
    );
  }
}
