const BASE_URL = "";

export interface ApiStatus {
  mode: "alert_only" | "demo" | "live";
  program: "challenge" | "instant";
  phase: 1 | 2 | 3;
  daily_loss_pct: number;
  max_dd_pct: number;
  running: boolean;
  loop_count: number;
  last_signal_time: string | null;
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  // Include auth cookie for protected endpoints
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (typeof document !== "undefined") {
    const token = document.cookie
      .split(";")
      .map((c) => c.trim())
      .find((c) => c.startsWith("tg_journal_auth="));
    if (token) headers["X-Auth-Token"] = token.split("=")[1];
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    headers,
    ...options,
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json() as Promise<T>;
}

export async function getConfig(): Promise<ApiStatus> {
  return apiFetch<ApiStatus>("/api/status");
}

export async function setMode(mode: ApiStatus["mode"]): Promise<void> {
  await apiFetch("/api/config/mode", {
    method: "POST",
    body: JSON.stringify({ mode }),
  });
}

export async function setProgram(program: ApiStatus["program"]): Promise<void> {
  await apiFetch("/api/config/program", {
    method: "POST",
    body: JSON.stringify({ program }),
  });
}

export async function setPhase(phase: ApiStatus["phase"]): Promise<void> {
  await apiFetch("/api/config/phase", {
    method: "POST",
    body: JSON.stringify({ phase }),
  });
}

export async function triggerRescan(): Promise<void> {
  await apiFetch("/api/action/rescan", { method: "POST" });
}

export interface OpenPosition {
  id: string;
  symbol: string;
  side: "BUY" | "SELL";
  volume: number;
  open_price: number;
  current_price: number;
  stop_loss: number | null;
  take_profit: number | null;
  unrealized_pl: number;
  net_profit: number;
}

export interface ClosedTrade {
  id: string;
  symbol: string;
  side: "BUY" | "SELL";
  volume: number;
  open_price: number;
  close_price: number;
  open_time: string;
  close_time: string;
  realized_pl: number;
  financing: number;
  pnl: number;
}

export async function getPositions(): Promise<OpenPosition[]> {
  return apiFetch<OpenPosition[]>("/api/positions");
}

export async function getTradeHistory(count = 50): Promise<ClosedTrade[]> {
  return apiFetch<ClosedTrade[]>(`/api/trades?count=${count}`);
}