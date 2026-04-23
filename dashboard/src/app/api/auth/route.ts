import { NextRequest, NextResponse } from "next/server";

const COOKIE = "tg_journal_auth";

function getClientInfo(req: NextRequest) {
  const ua = req.headers.get("user-agent") || "unknown";
  const ip = req.headers.get("x-forwarded-for") || "unknown";
  return { ua, ip };
}

async function sendSecurityAlert(token: string, ip: string, ua: string) {
  const webhook = process.env.DISCORD_WEBHOOK_URL;
  if (!webhook) return;

  const masked = token.length > 4 ? "•••" + token.slice(-4) : "•••";
  const payload = {
    content: "🔐 **TradeGumi Journal Login**",
    embeds: [
      {
        title: "Settings Accessed",
        description: `Journal/Settings page accessed with token **${masked}**`,
        color: 0x5865F2,
        fields: [
          { name: "IP", value: ip, inline: true },
          { name: "User-Agent", value: ua.slice(0, 100), inline: false },
          { name: "Time", value: new Date().toISOString(), inline: true },
        ],
      },
    ],
  };

  try {
    await fetch(webhook, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    // Fail silently — don't block login if webhook fails
  }
}

export async function POST(req: NextRequest) {
  const { token } = await req.json();
  const expected = process.env.JOURNAL_TOKEN;

  if (!expected) {
    return NextResponse.json({ error: "Journal auth not configured (JOURNAL_TOKEN missing)" }, { status: 500 });
  }

  if (!token || token !== expected) {
    return NextResponse.json({ error: "Invalid token" }, { status: 401 });
  }

  const { ip, ua } = getClientInfo(req);
  await sendSecurityAlert(token, ip, ua);

  const res = NextResponse.json({ ok: true });
  res.cookies.set(COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    // Session cookie — expires when browser closes
  });
  return res;
}
