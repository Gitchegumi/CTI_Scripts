"use client";

import { WatchlistData, LoopState } from "@/types";

interface HeaderProps {
  data: WatchlistData | null;
  lastUpdated: Date | null;
  isRefreshing: boolean;
  loopState: LoopState | null;
}

function formatET(date: Date): { et: string; ct: string } {
  const et = date.toLocaleString("en-US", {
    timeZone: "America/New_York",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
  const ct = date.toLocaleString("en-US", {
    timeZone: "America/Chicago",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return { et, ct };
}

export default function Header({ data, lastUpdated, isRefreshing, loopState }: HeaderProps) {
  const mode = loopState?.mode ?? data?.account?.cti_program ?? "—";
  const provider = loopState?.provider ?? "—";

  return (
    <header className="flex items-center justify-between px-4 py-3 border-b border-slate-700 bg-slate-900">
      <div className="flex items-center gap-3">
        <span className="text-lg font-bold text-white tracking-wide">TradeGumi</span>
        <span className="px-2 py-0.5 text-xs font-medium rounded bg-blue-600 text-blue-100">
          {mode}
        </span>
        <span className="px-2 py-0.5 text-xs font-medium rounded bg-slate-700 text-slate-300">
          {provider}
        </span>
      </div>
      <div className="flex items-center gap-3 text-xs text-slate-400">
        {lastUpdated && (
          <span>
            {formatET(lastUpdated).et} ET ({formatET(lastUpdated).ct} CT)
          </span>
        )}
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
      </div>
    </header>
  );
}