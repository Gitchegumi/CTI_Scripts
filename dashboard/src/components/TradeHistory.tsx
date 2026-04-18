"use client";

import { useState, useMemo } from "react";
import { ClosedTrade } from "@/types";

function isJPY(symbol: string): boolean {
  return symbol.includes("JPY");
}

function formatPrice(price: number, symbol: string): string {
  const decimals = isJPY(symbol) ? 3 : 5;
  return price.toFixed(decimals);
}

function formatDuration(openTime: string, closeTime: string): string {
  try {
    const start = new Date(openTime);
    const end = new Date(closeTime);
    const diffMs = end.getTime() - start.getTime();
    if (diffMs < 0) return "—";
    const totalSeconds = Math.floor(diffMs / 1000);
    if (totalSeconds < 60) return `${totalSeconds}s`;
    const minutes = Math.floor(totalSeconds / 60);
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
  } catch {
    return "—";
  }
}

function formatPL(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}$${value.toFixed(2)}`;
}

function PLCell({ value }: { value: number }) {
  const color = value >= 0 ? "text-green-400" : "text-red-400";
  return <span className={color}>{formatPL(value)}</span>;
}

function SideCell({ side }: { side: "BUY" | "SELL" }) {
  const color = side === "BUY" ? "text-green-400" : "text-red-400";
  return <span className={color}>{side}</span>;
}

interface TradeHistoryProps {
  trades: ClosedTrade[];
}

type FilterSide = "all" | "BUY" | "SELL";
type SortKey = "close_time" | "pnl" | "symbol";

export default function TradeHistory({ trades }: TradeHistoryProps) {
  const [showAll, setShowAll] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [filterSide, setFilterSide] = useState<FilterSide>("all");
  const [sortBy, setSortBy] = useState<SortKey>("close_time");

  const filtered = useMemo(() => {
    let result = trades;
    if (filterSide !== "all") {
      result = result.filter((t) => t.side === filterSide);
    }
    return result.sort((a, b) => {
      switch (sortBy) {
        case "pnl": return b.pnl - a.pnl;
        case "symbol": return a.symbol.localeCompare(b.symbol);
        default: return b.close_time.localeCompare(a.close_time);
      }
    });
  }, [trades, filterSide, sortBy]);

  const displayed = showAll ? filtered : filtered.slice(0, 20);
  const hasMore = filtered.length > 20;
  const wins = trades.filter((t) => t.pnl >= 0).length;
  const losses = trades.filter((t) => t.pnl < 0).length;
  const totalPnl = trades.reduce((sum, t) => sum + t.pnl, 0);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
      <div className="px-4 py-2 border-b border-slate-800">
        <div className="flex items-center justify-between">
          <button
            onClick={() => setCollapsed((v) => !v)}
            className="flex items-center gap-1.5 text-sm font-medium text-slate-300 hover:text-white transition-colors"
          >
            <span className={`transition-transform duration-200 ${collapsed ? "" : "rotate-90"}`}>▶</span>
            <span>📜 Trade History</span>
            <span className="text-xs text-slate-500">({trades.length})</span>
          </button>
          {trades.length > 0 && (
            <span className={`text-xs font-mono ${totalPnl >= 0 ? "text-green-400" : "text-red-400"}`}>
              {formatPL(totalPnl)} · {wins}W/{losses}L
            </span>
          )}
        </div>
      </div>

      <div
        className="overflow-hidden transition-all duration-300 ease-in-out"
        style={{ maxHeight: collapsed ? "0" : "2000px" }}
      >
        {trades.length === 0 ? (
          <div className="px-4 py-4 text-sm text-slate-500 text-center">No trade history</div>
        ) : (
          <>
            {/* Filters */}
            <div className="px-3 py-2 border-b border-slate-800 flex items-center gap-3 flex-wrap">
              <div className="flex items-center gap-1">
                <span className="text-xs text-slate-500">Side:</span>
                {(["all", "BUY", "SELL"] as FilterSide[]).map((f) => (
                  <button
                    key={f}
                    onClick={() => setFilterSide(f)}
                    className={`px-2 py-0.5 text-xs rounded transition-colors ${
                      filterSide === f
                        ? f === "BUY" ? "bg-green-900 text-green-300" : f === "SELL" ? "bg-red-900 text-red-300" : "bg-slate-700 text-slate-200"
                        : "bg-slate-800 text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    {f === "all" ? "All" : f}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-1">
                <span className="text-xs text-slate-500">Sort:</span>
                {([
                  ["close_time", "Recent"],
                  ["pnl", "P/L"],
                  ["symbol", "Symbol"],
                ] as [SortKey, string][]).map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => setSortBy(key)}
                    className={`px-2 py-0.5 text-xs rounded transition-colors ${
                      sortBy === key ? "bg-slate-700 text-slate-200" : "bg-slate-800 text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {/* Table */}
            <div className="overflow-x-auto max-h-80 overflow-y-auto">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-slate-900">
                  <tr className="text-slate-500 border-b border-slate-800">
                    <th className="px-3 py-1.5 text-left font-medium">Symbol</th>
                    <th className="px-3 py-1.5 text-left font-medium">Side</th>
                    <th className="px-3 py-1.5 text-right font-medium">Volume</th>
                    <th className="px-3 py-1.5 text-right font-medium">Open→Close</th>
                    <th className="px-3 py-1.5 text-right font-medium">P/L</th>
                    <th className="px-3 py-1.5 text-right font-medium">Duration</th>
                  </tr>
                </thead>
                <tbody>
                  {displayed.map((trade) => (
                    <tr key={trade.id} className="border-b border-slate-800 last:border-0 hover:bg-slate-800/50">
                      <td className="px-3 py-1.5 font-medium text-slate-200">{trade.symbol}</td>
                      <td className="px-3 py-1.5"><SideCell side={trade.side} /></td>
                      <td className="px-3 py-1.5 text-right text-slate-300">{trade.volume.toLocaleString()}</td>
                      <td className="px-3 py-1.5 text-right text-slate-300">
                        {formatPrice(trade.open_price, trade.symbol)}→{formatPrice(trade.close_price, trade.symbol)}
                      </td>
                      <td className="px-3 py-1.5 text-right"><PLCell value={trade.pnl} /></td>
                      <td className="px-3 py-1.5 text-right text-slate-400">{formatDuration(trade.open_time, trade.close_time)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {hasMore && (
              <div className="px-4 py-2 border-t border-slate-800 text-center">
                <button
                  onClick={() => setShowAll((v) => !v)}
                  className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
                >
                  {showAll ? "Show less" : `Show all (${filtered.length})`}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}