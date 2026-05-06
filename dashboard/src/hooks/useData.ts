"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { WatchlistData, SignalEntry, LoopState, TradeCorrelation } from "@/types";
import type { StrategyMetricOpportunity, StrategyMetricsComparison, StrategyMetricsSummary } from "@/types";
import { ApiStatus, OpenPosition, ClosedTrade } from "@/lib/api";

// ── Weekend / Market-Closed Detection ────────────────────────────────────────
// Derive market state from loop_state. When all symbols are "closed",
// throttle all polling to 60s. When any market is open, use fast intervals.

function useMarketOpen(loopState: LoopState | null): boolean {
  return useMemo(() => {
    if (!loopState?.symbols?.length) return true; // default to open until we know
    return loopState.symbols.some((s) => s.state !== "closed");
  }, [loopState]);
}

const FAST_MS = 2000;   // loop_state & positions when market open
const SLOW_MS = 60000;  // everything when market closed (weekend)

// ── Watchlist ────────────────────────────────────────────────────────────────

interface UseWatchlistReturn {
  data: WatchlistData | null;
  lastUpdated: Date | null;
  error: string | null;
  isRefreshing: boolean;
  refresh: () => void;
}

export function useWatchlist(marketOpen: boolean): UseWatchlistReturn {
  const pollIntervalMs = marketOpen ? 5000 : SLOW_MS;
  const [data, setData] = useState<WatchlistData | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const res = await fetch(`/data/watchlist.json?_=${Date.now()}`, {
        cache: "no-store",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: WatchlistData = await res.json();
      setData(json);
      setLastUpdated(new Date());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load watchlist");
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const first = window.setTimeout(() => { void fetchData(); }, 0);
    const id = setInterval(fetchData, pollIntervalMs);
    return () => { window.clearTimeout(first); clearInterval(id); };
  }, [fetchData, pollIntervalMs]);

  return { data, lastUpdated, error, isRefreshing, refresh: fetchData };
}

// ── Signals ──────────────────────────────────────────────────────────────────

interface UseSignalsReturn {
  signals: SignalEntry[];
  error: string | null;
}

export function useSignals(marketOpen: boolean): UseSignalsReturn {
  const pollIntervalMs = marketOpen ? 30000 : SLOW_MS;
  const [signals, setSignals] = useState<SignalEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchSignals = async () => {
      try {
        const res = await fetch(`/data/signals.json?_=${Date.now()}`, {
          cache: "no-store",
        });
        if (!res.ok) {
          if (res.status === 404) { setSignals([]); return; }
          throw new Error(`HTTP ${res.status}`);
        }
        const json = await res.json();
        setSignals(Array.isArray(json) ? json : []);
        setError(null);
      } catch { setSignals([]); }
    };

    fetchSignals();
    const id = setInterval(fetchSignals, pollIntervalMs);
    return () => clearInterval(id);
  }, [pollIntervalMs]);

  return { signals, error };
}

// ── Loop State ───────────────────────────────────────────────────────────────

interface UseLoopStateReturn {
  loopState: LoopState | null;
  error: string | null;
}

export function useLoopState(marketOpen: boolean): UseLoopStateReturn {
  const pollIntervalMs = marketOpen ? FAST_MS : SLOW_MS;
  const [loopState, setLoopState] = useState<LoopState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchState = async () => {
      try {
        const res = await fetch(`/data/loop_state.json?_=${Date.now()}`, {
          cache: "no-store",
        });
        if (!res.ok) {
          if (res.status === 404) { setLoopState(null); return; }
          throw new Error(`HTTP ${res.status}`);
        }
        const json = await res.json();
        setLoopState(json);
        setError(null);
      } catch { setLoopState(null); }
    };

    fetchState();
    const id = setInterval(fetchState, pollIntervalMs);
    return () => clearInterval(id);
  }, [pollIntervalMs]);

  return { loopState, error };
}

// ── API Status ───────────────────────────────────────────────────────────────

interface UseApiStatusReturn {
  status: ApiStatus | null;
  error: string | null;
}

export function useApiStatus(pollIntervalMs = 5000): UseApiStatusReturn {
  const [status, setStatus] = useState<ApiStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchStatus = async () => {
      try {
        const { getConfig } = await import("@/lib/api");
        const data = await getConfig();
        if (!cancelled) setStatus(data);
      } catch {
        if (!cancelled) setError(null);
      }
    };

    fetchStatus();
    const id = setInterval(fetchStatus, pollIntervalMs);
    return () => { cancelled = true; clearInterval(id); };
  }, [pollIntervalMs]);

  return { status, error };
}

// ── Open Positions ───────────────────────────────────────────────────────────

interface UsePositionsReturn {
  positions: OpenPosition[];
  error: string | null;
}

export function usePositions(marketOpen: boolean): UsePositionsReturn {
  const pollIntervalMs = marketOpen ? FAST_MS : SLOW_MS;
  const [positions, setPositions] = useState<OpenPosition[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchPositions = async () => {
      try {
        const { getPositions } = await import("@/lib/api");
        const data = await getPositions();
        if (!cancelled) setPositions(data);
      } catch {
        if (!cancelled) setPositions([]);
      }
    };

    fetchPositions();
    const id = setInterval(fetchPositions, pollIntervalMs);
    return () => { cancelled = true; clearInterval(id); };
  }, [pollIntervalMs]);

  return { positions, error };
}

// ── Trade History ────────────────────────────────────────────────────────────

interface UseTradeHistoryReturn {
  trades: ClosedTrade[];
  error: string | null;
}

export function useTradeHistory(count = 50, marketOpen: boolean = true, modeKey = ""): UseTradeHistoryReturn {
  const pollIntervalMs = marketOpen ? 30000 : SLOW_MS;
  const [trades, setTrades] = useState<ClosedTrade[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchTrades = async () => {
      try {
        const { getTradeHistory } = await import("@/lib/api");
        const data = await getTradeHistory(count);
        if (!cancelled) {
          setTrades(data);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) {
          setTrades([]);
          setError(e instanceof Error ? e.message : "Failed to load trade history");
        }
      }
    };

    fetchTrades();
    const id = setInterval(fetchTrades, pollIntervalMs);
    return () => { cancelled = true; clearInterval(id); };
  }, [count, pollIntervalMs, modeKey]);

  return { trades, error };
}

// ── Trade Correlations ───────────────────────────────────────────────────────

export function useTradeCorrelations(): TradeCorrelation[] {
  const [correlations, setCorrelations] = useState<TradeCorrelation[]>([]);

  useEffect(() => {
    const fetch_ = async () => {
      try {
        const res = await fetch(`/api/trade-correlations?_=${Date.now()}`, { cache: "no-store" });
        if (!res.ok) { setCorrelations([]); return; }
        const json = await res.json();
        setCorrelations(Array.isArray(json) ? json : []);
      } catch { setCorrelations([]); }
    };
    fetch_();
    // Correlations only change when trades are placed — poll every 30s
    const id = setInterval(fetch_, 30_000);
    return () => clearInterval(id);
  }, []);

  return correlations;
}

export function useStrategyMetricsSummary(params: {
  start: string;
  end: string;
  symbol?: string;
}) {
  const [summary, setSummary] = useState<StrategyMetricsSummary | null>(null);
  const [opportunities, setOpportunities] = useState<StrategyMetricOpportunity[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!params.start || !params.end) return;
    setLoading(true);
    try {
      const { getStrategyMetricOpportunities, getStrategyMetricsSummary } = await import("@/lib/api");
      const [summaryData, opportunityData] = await Promise.all([
        getStrategyMetricsSummary(params),
        getStrategyMetricOpportunities({ ...params, limit: 200 }),
      ]);
      setSummary(summaryData);
      setOpportunities(opportunityData);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load strategy metrics");
      setSummary(null);
      setOpportunities([]);
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => {
    const id = window.setTimeout(() => { void refresh(); }, 0);
    return () => window.clearTimeout(id);
  }, [refresh]);

  return { summary, opportunities, error, loading, refresh };
}

export function useStrategyMetricsComparison(params: {
  base_start: string;
  base_end: string;
  compare_start: string;
  compare_end: string;
  symbol?: string;
}, enabled = true) {
  const [comparison, setComparison] = useState<StrategyMetricsComparison | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!enabled) {
      setComparison(null);
      setError(null);
      setLoading(false);
      return;
    }
    if (!params.base_start || !params.base_end || !params.compare_start || !params.compare_end) return;
    setLoading(true);
    try {
      const { getStrategyMetricsComparison } = await import("@/lib/api");
      setComparison(await getStrategyMetricsComparison(params));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to compare strategy metrics");
      setComparison(null);
    } finally {
      setLoading(false);
    }
  }, [enabled, params]);

  useEffect(() => {
    const id = window.setTimeout(() => { void refresh(); }, 0);
    return () => window.clearTimeout(id);
  }, [refresh]);

  return { comparison, error, loading, refresh };
}

// ── Export market hook ──────────────────────────────────────────────────────

export { useMarketOpen };
