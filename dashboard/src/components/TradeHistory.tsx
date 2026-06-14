"use client";

import { useState, useMemo, Fragment } from "react";
import { ClosedTrade, TradeCorrelation } from "@/types";

// ── Formatting helpers ────────────────────────────────────────────────────────

function fmtPrice(price: number, symbol: string): string {
  const decimals = symbol.includes("JPY") ? 3 : 5;
  return price.toFixed(decimals);
}

function fmtDateTime(iso: string, opts: { dateOnly?: boolean; timeOnly?: boolean } = {}): string {
  try {
    const d = new Date(iso);
    if (opts.timeOnly) {
      return d.toLocaleString("en-US", {
        timeZone: "America/New_York",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      });
    }
    if (opts.dateOnly) {
      return d.toLocaleDateString("en-US", {
        timeZone: "America/New_York",
        weekday: "short",
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    }
    return d.toLocaleString("en-US", {
      timeZone: "America/New_York",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  } catch {
    return iso;
  }
}

function closeDateKey(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      timeZone: "America/New_York",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
  } catch {
    return iso.slice(0, 10);
  }
}

function fmtDuration(openTime: string, closeTime: string): string {
  try {
    const ms = new Date(closeTime).getTime() - new Date(openTime).getTime();
    if (ms < 0) return "—";
    const s = Math.floor(ms / 1000);
    if (s < 60) return `${s}s`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m}m`;
    const h = Math.floor(m / 60);
    return m % 60 > 0 ? `${h}h ${m % 60}m` : `${h}h`;
  } catch { return "—"; }
}

function fmtPL(v: number): string {
  return `${v >= 0 ? "+" : ""}$${Math.abs(v).toFixed(2)}`;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function PLCell({ value }: { value: number }) {
  return (
    <span className={value >= 0 ? "text-green-400" : "text-red-400"}>
      {fmtPL(value)}
    </span>
  );
}

function SideCell({ side }: { side: "BUY" | "SELL" }) {
  return (
    <span className={side === "BUY" ? "text-green-400" : "text-red-400"}>
      {side}
    </span>
  );
}

function ConfCell({ confidence }: { confidence: number | undefined }) {
  if (confidence === undefined) return <span className="text-slate-600">—</span>;
  const pct = Math.round(confidence * 100);
  const color = pct >= 80 ? "text-green-400" : pct >= 65 ? "text-yellow-400" : "text-slate-400";
  return <span className={color}>{pct}%</span>;
}

// ── Date group header ─────────────────────────────────────────────────────────

function DateGroupHeader({ dateLabel, trades }: { dateLabel: string; trades: ClosedTrade[] }) {
  const dayPnl = trades.reduce((s, t) => s + t.pnl, 0);
  const wins = trades.filter(t => t.pnl >= 0).length;
  return (
    <tr className="bg-slate-800/60">
      <td colSpan={9} className="px-3 py-1.5 text-xs font-semibold text-slate-400">
        <span className="text-slate-300">{dateLabel}</span>
        <span className="ml-3 font-mono">
          <PLCell value={dayPnl} />
        </span>
        <span className="ml-2 text-slate-500">{wins}W / {trades.length - wins}L</span>
      </td>
    </tr>
  );
}

// ── Types ─────────────────────────────────────────────────────────────────────

type FilterSide = "all" | "BUY" | "SELL";
type SortKey = "close_time" | "pnl" | "symbol";

interface TradeHistoryProps {
  trades: ClosedTrade[];
  correlations: TradeCorrelation[];
  error?: string | null;
}

// ── Main component ────────────────────────────────────────────────────────────

export default function TradeHistory({ trades, correlations, error = null }: TradeHistoryProps) {
  const [showAll, setShowAll] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [filterSide, setFilterSide] = useState<FilterSide>("all");
  const [sortBy, setSortBy] = useState<SortKey>("close_time");

  // Build trade_id → confidence lookup from correlations
  const confidenceMap = useMemo(() => {
    const m = new Map<string, number>();
    for (const c of correlations) {
      m.set(c.trade_id, c.confidence);
    }
    return m;
  }, [correlations]);

  const filtered = useMemo(() => {
    const result = filterSide !== "all" ? trades.filter(t => t.side === filterSide) : [...trades];
    return result.sort((a, b) => {
      switch (sortBy) {
        case "pnl":    return b.pnl - a.pnl;
        case "symbol": return a.symbol.localeCompare(b.symbol);
        default:       return b.close_time.localeCompare(a.close_time);
      }
    });
  }, [trades, filterSide, sortBy]);

  const displayed = showAll ? filtered : filtered.slice(0, 20);

  // Group displayed trades by close date (ET), preserving sort order
  const dateGroups = useMemo(() => {
    const groups: { key: string; label: string; trades: ClosedTrade[] }[] = [];
    for (const trade of displayed) {
      const key = closeDateKey(trade.close_time);
      const existing = groups.find(g => g.key === key);
      if (existing) {
        existing.trades.push(trade);
      } else {
        groups.push({
          key,
          label: fmtDateTime(trade.close_time, { dateOnly: true }),
          trades: [trade],
        });
      }
    }
    return groups;
  }, [displayed]);

  const hasMore = filtered.length > 20;
  const wins    = trades.filter(t => t.pnl >= 0).length;
  const losses  = trades.filter(t => t.pnl < 0).length;
  const totalPnl = trades.reduce((s, t) => s + t.pnl, 0);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-2 border-b border-slate-800">
        <div className="flex items-center justify-between">
          <button
            onClick={() => setCollapsed(v => !v)}
            className="flex items-center gap-1.5 text-sm font-medium text-slate-300 hover:text-white transition-colors"
          >
            <span className={`transition-transform duration-200 ${collapsed ? "" : "rotate-90"}`}>▶</span>
            <span>📜 Trade History</span>
            <span className="text-xs text-slate-500">({trades.length})</span>
          </button>
          {trades.length > 0 && (
            <span className={`text-xs font-mono ${totalPnl >= 0 ? "text-green-400" : "text-red-400"}`}>
              {fmtPL(totalPnl)} · {wins}W/{losses}L
            </span>
          )}
        </div>
      </div>

      <div
        className="overflow-hidden transition-all duration-300 ease-in-out"
        style={{ maxHeight: collapsed ? "0" : "2000px" }}
      >
        {trades.length === 0 ? (
          <div className="px-4 py-4 text-sm text-center">
            {error ? (
              /\b401\b|unauthorized/i.test(error) ? (
                // Trade history is intentionally gated (see specs/019); show a
                // clean locked state on the public dashboard instead of a raw
                // 401 error.
                <a href="/journal/login" className="text-slate-500 hover:text-blue-400 transition-colors">
                  🔒 Log in to view trade history
                </a>
              ) : (
                <span className="text-red-400">Trade history unavailable: {error}</span>
              )
            ) : (
              <span className="text-slate-500">No trade history</span>
            )}
          </div>
        ) : (
          <>
            {/* Filters */}
            <div className="px-3 py-2 border-b border-slate-800 flex items-center gap-3 flex-wrap">
              <div className="flex items-center gap-1">
                <span className="text-xs text-slate-500">Side:</span>
                {(["all", "BUY", "SELL"] as FilterSide[]).map(f => (
                  <button
                    key={f}
                    onClick={() => setFilterSide(f)}
                    className={`px-2 py-0.5 text-xs rounded transition-colors ${
                      filterSide === f
                        ? f === "BUY" ? "bg-green-900 text-green-300"
                          : f === "SELL" ? "bg-red-900 text-red-300"
                          : "bg-slate-700 text-slate-200"
                        : "bg-slate-800 text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    {f === "all" ? "All" : f}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-1">
                <span className="text-xs text-slate-500">Sort:</span>
                {([["close_time", "Recent"], ["pnl", "P/L"], ["symbol", "Symbol"]] as [SortKey, string][]).map(([key, label]) => (
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

            {/* Table — scrollable on small screens */}
            <div className="overflow-x-auto max-h-96 overflow-y-auto">
              <table className="w-full text-xs min-w-[560px]">
                <thead className="sticky top-0 bg-slate-900 z-10">
                  <tr className="text-slate-500 border-b border-slate-800">
                    <th className="px-3 py-1.5 text-left font-medium">Symbol</th>
                    <th className="px-3 py-1.5 text-left font-medium">Side</th>
                    <th className="px-3 py-1.5 text-right font-medium hidden md:table-cell">Vol</th>
                    <th className="px-3 py-1.5 text-right font-medium">Conf</th>
                    <th className="px-3 py-1.5 text-right font-medium">Entry</th>
                    <th className="px-3 py-1.5 text-right font-medium">Exit</th>
                    <th className="px-3 py-1.5 text-right font-medium hidden sm:table-cell">Price ↕</th>
                    <th className="px-3 py-1.5 text-right font-medium">P/L</th>
                    <th className="px-3 py-1.5 text-right font-medium hidden md:table-cell">Dur</th>
                  </tr>
                </thead>
                <tbody>
                  {dateGroups.map(({ key, label, trades: groupTrades }) => (
                    <Fragment key={key}>
                      <DateGroupHeader dateLabel={label} trades={groupTrades} />
                      {groupTrades.map(trade => {
                        const openDate  = closeDateKey(trade.open_time);
                        const closeDate = key;
                        const openTs = openDate !== closeDate
                          ? fmtDateTime(trade.open_time)          // different day — show date+time
                          : fmtDateTime(trade.open_time, { timeOnly: true }); // same day — time only
                        const closeTs = fmtDateTime(trade.close_time, { timeOnly: true });
                        const conf = confidenceMap.get(trade.id);

                        return (
                          <tr key={trade.id} className="border-b border-slate-800/60 last:border-0 hover:bg-slate-800/40">
                            <td className="px-3 py-1.5 font-medium text-slate-200">{trade.symbol}</td>
                            <td className="px-3 py-1.5"><SideCell side={trade.side} /></td>
                            <td className="px-3 py-1.5 text-right text-slate-300 hidden md:table-cell">
                              {trade.volume.toLocaleString()}
                            </td>
                            <td className="px-3 py-1.5 text-right font-mono">
                              <ConfCell confidence={conf} />
                            </td>
                            <td className="px-3 py-1.5 text-right font-mono text-slate-400">{openTs}</td>
                            <td className="px-3 py-1.5 text-right font-mono text-slate-400">{closeTs}</td>
                            <td className="px-3 py-1.5 text-right font-mono text-slate-300 hidden sm:table-cell">
                              {fmtPrice(trade.open_price, trade.symbol)}→{fmtPrice(trade.close_price, trade.symbol)}
                            </td>
                            <td className="px-3 py-1.5 text-right font-mono">
                              <PLCell value={trade.pnl} />
                            </td>
                            <td className="px-3 py-1.5 text-right text-slate-500 hidden md:table-cell">
                              {fmtDuration(trade.open_time, trade.close_time)}
                            </td>
                          </tr>
                        );
                      })}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>

            {hasMore && (
              <div className="px-4 py-2 border-t border-slate-800 text-center">
                <button
                  onClick={() => setShowAll(v => !v)}
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
