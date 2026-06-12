import type {
  AgentExport,
  CriterionDetail,
  StrategyCriteriaList,
  StrategyMetricOpportunity,
  StrategyMetricsComparison,
  StrategyMetricsSummary,
  TradePermissions,
} from "@/types";


const BASE_URL = "";

export interface ApiStatus {
  mode: "alert_only" | "demo" | "live";
  challenge_type: "1-step" | "2-step" | "instant";
  phase: 1 | 2 | 3;
  daily_loss_pct: number;
  max_dd_pct: number;
  running: boolean;
  loop_count: number;
  last_signal_time: string | null;
  tiers: number[];
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

export async function readApiError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.error === "string" && data.error.trim()) return data.error;
  } catch {
    // Fall through to status text below.
  }
  return res.statusText || `HTTP ${res.status}`;
}

export function modeDisplayLabel(mode: ApiStatus["mode"] | string | null | undefined): string {
  if (mode === "alert_only") return "Developing";
  if (mode === "demo") return "Demo";
  if (mode === "live") return "Live";
  return "Developing";
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

export async function setChallengeType(challenge_type: ApiStatus["challenge_type"]): Promise<void> {
  await apiFetch("/api/config/challenge_type", {
    method: "POST",
    body: JSON.stringify({ challenge_type }),
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
  source?: string;
  source_trade_id?: string;
  bot_mode?: ApiStatus["mode"];
  notes?: string;
  tags?: string[];
  has_overrides?: boolean;
  permissions?: TradePermissions;
}

export async function getPositions(): Promise<OpenPosition[]> {
  return apiFetch<OpenPosition[]>("/api/positions");
}

export async function getTradeHistory(count = 50): Promise<ClosedTrade[]> {
  return apiFetch<ClosedTrade[]>(`/api/trades/history?count=${count}`);
}

export async function getUnifiedTradeHistory(count = 50): Promise<ClosedTrade[]> {
  return getTradeHistory(count);
}

function query(params: Record<string, string | number | boolean | undefined | null>): string {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") qs.set(key, String(value));
  });
  return qs.toString();
}

export async function getStrategyMetricsSummary(params: {
  start: string;
  end: string;
  symbol?: string;
  strategy?: string;
  signal_type?: string;
  decision?: string;
  first_blocker?: string;
}): Promise<StrategyMetricsSummary> {
  return apiFetch<StrategyMetricsSummary>(`/api/strategy-metrics/summary?${query(params)}`);
}

export async function getStrategyMetricOpportunities(params: {
  start: string;
  end: string;
  symbol?: string;
  decision?: string;
  strategy?: string;
  signal_type?: string;
  first_blocker?: string;
  near_miss?: boolean;
  limit?: number;
  offset?: number;
}): Promise<StrategyMetricOpportunity[]> {
  return apiFetch<StrategyMetricOpportunity[]>(`/api/strategy-metrics/opportunities?${query(params)}`);
}

export async function getStrategyMetricsComparison(params: {
  base_start: string;
  base_end: string;
  compare_start: string;
  compare_end: string;
  symbol?: string;
}): Promise<StrategyMetricsComparison> {
  return apiFetch<StrategyMetricsComparison>(`/api/strategy-metrics/compare?${query(params)}`);
}

export async function getCriteriaList(params: {
  start: string;
  end: string;
  symbol?: string;
  strategy?: string;
  signal_type?: string;
  decision?: string;
  first_blocker?: string;
}): Promise<StrategyCriteriaList> {
  return apiFetch<StrategyCriteriaList>(`/api/strategy-metrics/criteria?${query(params)}`);
}

export async function getCriterionDetail(
  criterionName: string,
  params: {
    start: string;
    end: string;
    symbol?: string;
    decision?: string;
    near_miss?: boolean;
    first_blocker?: string;
    limit?: number;
    offset?: number;
  }
): Promise<CriterionDetail> {
  const { limit = 50, offset = 0, ...rest } = params;
  const q = query({ ...rest, limit, offset });
  return apiFetch<CriterionDetail>(
    `/api/strategy-metrics/criteria/${encodeURIComponent(criterionName)}?${q}`
  );
}

export async function exportStrategyMetrics(params: {
  start: string;
  end: string;
  symbol?: string;
  strategy?: string;
  signal_type?: string;
  decision?: string;
  first_blocker?: string;
  include_opportunities?: boolean;
}): Promise<unknown> {
  return apiFetch<unknown>(`/api/strategy-metrics/export?${query(params)}`);
}

export async function exportManualTrades(params: {
  symbol?: string;
  status?: string;
  tag?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
} = {}): Promise<AgentExport> {
  return apiFetch<AgentExport>(`/api/manual-trades/export?${query(params)}`);
}

export interface PurgeResult {
  ok: boolean;
  results?: Record<string, boolean>;
  error?: string;
}

export async function purgeData(targets?: string[]): Promise<PurgeResult> {
  return apiFetch<PurgeResult>("/api/purge", {
    method: "POST",
    body: JSON.stringify(targets ? { targets } : {}),
  });
}
