import { NextRequest } from "next/server";

/*
 * Authentik forwarded-header trust
 * ================================
 * When the dashboard sits behind an Authentik outpost / reverse proxy, the
 * proxy injects identity headers (x-authentik-*) after it authenticates the
 * request.  Trusting those headers is ONLY safe when the proxy is guaranteed
 * to strip any client-supplied x-authentik-* headers first — otherwise a
 * caller could forge `x-authentik-username` and bypass auth entirely.
 *
 * Because that guarantee depends on deployment topology, header trust is
 * OFF by default and must be explicitly enabled with:
 *
 *   AUTHENTIK_TRUST_PROXY_HEADERS=true
 *
 * Only set this when the app is unreachable except through the Authentik
 * proxy and the proxy strips inbound x-authentik-* headers.
 */

export const AUTHENTIK_FORWARD_HEADERS = [
  "x-authentik-username",
  "x-authentik-email",
  "x-authentik-groups",
  "x-authentik-uid",
  "x-authentik-name",
] as const;

export function authentikHeadersTrusted(): boolean {
  return process.env.AUTHENTIK_TRUST_PROXY_HEADERS === "true";
}

/**
 * Return the forwarded Authentik username, but only when header trust is
 * explicitly enabled.  Returns null otherwise so callers fall back to the
 * legacy JOURNAL_TOKEN cookie check.
 */
export function trustedAuthentikUsername(req: NextRequest): string | null {
  if (!authentikHeadersTrusted()) {
    return null;
  }
  return req.headers.get("x-authentik-username") || null;
}
