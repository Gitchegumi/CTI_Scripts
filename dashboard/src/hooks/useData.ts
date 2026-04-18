"use client";

import { useState, useEffect, useCallback } from "react";
import { WatchlistData, SignalEntry, LoopState } from "@/types";

interface UseWatchlistReturn {
  data: WatchlistData | null;
  lastUpdated: Date | null;
  error: string | null;
  isRefreshing: boolean;
  refresh: () => void;
}

export function useWatchlist(pollIntervalMs = 60000): UseWatchlistReturn {
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

interface UseSignalsReturn {
  signals: SignalEntry[];
  error: string | null;
}

export function useSignals(): UseSignalsReturn {
  const [signals, setSignals] = useState<SignalEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchSignals = async () => {
      try {
        const res = await fetch(`/data/signals.json?_=${Date.now()}`, {
          cache: "no-store",
        });
        if (!res.ok) {
          if (res.status === 404) {
            setSignals([]);
            return;
          }
          throw new Error(`HTTP ${res.status}`);
        }
        const json = await res.json();
        setSignals(Array.isArray(json) ? json : []);
        setError(null);
      } catch {
        setSignals([]);
      }
    };

    fetchSignals();
    const id = setInterval(fetchSignals, 60000);
    return () => clearInterval(id);
  }, []);

  return { signals, error };
}

interface UseLoopStateReturn {
  loopState: LoopState | null;
  error: string | null;
}

export function useLoopState(): UseLoopStateReturn {
  const [loopState, setLoopState] = useState<LoopState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchState = async () => {
      try {
        const res = await fetch(`/data/loop_state.json?_=${Date.now()}`, {
          cache: "no-store",
        });
        if (!res.ok) {
          if (res.status === 404) {
            setLoopState(null);
            return;
          }
          throw new Error(`HTTP ${res.status}`);
        }
        const json = await res.json();
        setLoopState(json);
        setError(null);
      } catch {
        setLoopState(null);
      }
    };

    fetchState();
    const id = setInterval(fetchState, 2000); // Poll every 2s for live price updates
    return () => clearInterval(id);
  }, []);

  return { loopState, error };
}