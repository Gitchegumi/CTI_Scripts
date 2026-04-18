"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { WatchlistData, SignalEntry, LoopState } from "@/types";
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
  const pollIntervalMs = marketOpen ? 30000 : SLOW_MS;
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
    fetchData();
    const id = setInterval(fetchData, pollIntervalMs);
    return () => clearInterval(id);
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

export function useTradeHistory(count = 50, marketOpen: boolean = true): UseTradeHistoryReturn {
  const pollIntervalMs = marketOpen ? 30000 : SLOW_MS;
  const [trades, setTrades] = useState<ClosedTrade[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchTrades = async () => {
      try {
        const { getTradeHistory } = await import("@/lib/api");
        const data = await getTradeHistory(count);
        if (!cancelled) setTrades(data);
      } catch {
        if (!cancelled) setTrades([]);
      }
    };

    fetchTrades();
    const id = setInterval(fetchTrades, pollIntervalMs);
    return () => { cancelled = true; clearInterval(id); };
  }, [count, pollIntervalMs]);

  return { trades, error };
}

// ── Export market hook ──────────────────────────────────────────────────────

export { useMarketOpen };