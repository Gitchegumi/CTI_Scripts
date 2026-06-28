"use client";

import { useState, useEffect } from "react";
import { WatchlistData, LoopState } from "@/types";
import { ApiStatus } from "@/lib/api";

interface HeaderProps {
  data: WatchlistData | null;
  lastUpdated: Date | null;
  isRefreshing: boolean;
  loopState: LoopState | null;
  apiStatus: ApiStatus | null;
}

function formatTime(date: Date, tz: string): string {
  return date.toLocaleString("en-US", {
    timeZone: tz,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

export default function Header({ data, lastUpdated, isRefreshing, loopState, apiStatus }: HeaderProps) {
  // Prefer live config from API, fall back to loopState, then watchlist
  const mode: string = apiStatus?.mode ?? loopState?.mode ?? data?.account?.cti_program ?? "—";
  const provider = loopState?.provider ?? "—";

  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    const first = window.setTimeout(() => setNow(new Date()), 0);
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => {
      window.clearTimeout(first);
      clearInterval(id);
    };
  }, []);

  const modeColors: Record<string, string> = {
    alert_only: "bg-blue-600 text-blue-100",
    demo: "bg-yellow-600 text-yellow-100",
    live: "bg-red-600 text-red-100",
  };

  return (
    <header className="flex items-center justify-between px-4 py-3 border-b border-slate-700 bg-slate-900">
      <div className="flex items-center gap-3">
        <img
          src="/tradegumi-logo.svg"
          alt="TradeGumi"
          className="h-16 w-16 rounded"
        />
        <span className={`px-2 py-0.5 text-xs font-medium rounded ${modeColors[mode] ?? "bg-slate-600 text-slate-200"}`}>
          {mode}
        </span>
        <span className="px-2 py-0.5 text-xs font-medium rounded bg-slate-700 text-slate-300">
          {provider}
        </span>
      </div>
      <div className="flex items-center gap-3 text-xs text-slate-400">
        <span className="font-mono" suppressHydrationWarning>
          {now ? (
            <>
              <span>{formatTime(now, "America/New_York")} ET</span>
              <span className="hidden sm:inline"> ({formatTime(now, "America/Chicago")} CT)</span>
            </>
          ) : ""}
        </span>
        <span
          className={`flex items-center gap-1 ${
            isRefreshing ? "text-yellow-400" : "text-green-400"
          }`}
        >
          <span
            className={`w-2 h-2 rounded-full ${
              isRefreshing ? "bg-yellow-400 animate-pulse" : "bg-green-400"
            }`}
          />
          {isRefreshing ? "refreshing" : "live"}
        </span>
        {lastUpdated && (
          <span className="hidden md:inline text-slate-600">
            updated {lastUpdated.toLocaleTimeString()}
          </span>
        )}
      </div>
    </header>
  );
}
