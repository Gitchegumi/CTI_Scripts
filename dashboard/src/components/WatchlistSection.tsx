"use client";

import { useState } from "react";
import { WatchlistData, SymbolState } from "@/types";

interface WatchlistSectionProps {
  data: WatchlistData;
  loopState: SymbolState[];
}

const trendColors: Record<string, string> = {
  Uptrend: "text-green-400",
  Downtrend: "text-red-400",
  flat: "text-slate-500",
  closed: "text-slate-600",
  rollover: "text-yellow-500",
};

const trendArrows: Record<string, string> = {
  Uptrend: "▲",
  Downtrend: "▼",
  flat: "◆",
  closed: "✕",
  rollover: "⟳",
};

function formatPrice(price: number | undefined): string {
  if (price === undefined || price === 0) return "—";
  if (price >= 100) return price.toFixed(2);
  if (price >= 10) return price.toFixed(3);
  if (price >= 1) return price.toFixed(5);
  return price.toFixed(6);
}

export default function WatchlistSection({ data, loopState }: WatchlistSectionProps) {
  const [showBelow, setShowBelow] = useState(false);

  // Build a lookup from loopState for quick access
  const stateMap = new Map<string, SymbolState>();
  for (const s of loopState) {
    stateMap.set(s.symbol, s);
  }

  const tier1Items = data.ranked.filter((r) => r[2] === "Tier 1");
  const tier2Items = data.ranked.filter((r) => r[2] === "Tier 2");
  const belowItems = data.ranked.filter((r) => r[2] === "Below Threshold");

  function tableHeaders() {
    return (
      <tr className="border-b border-slate-800 text-slate-500 text-xs uppercase">
        <th className="text-left py-2 px-3 font-medium">Symbol</th>
        <th className="text-right py-2 px-3 font-medium">Score</th>
        <th className="text-right py-2 px-3 font-medium">Bid</th>
        <th className="text-right py-2 px-3 font-medium">Ask</th>
        <th className="text-center py-2 px-3 font-medium">State</th>
        <th className="text-right py-2 px-3 font-medium">LR 15m</th>
        <th className="text-right py-2 px-3 font-medium">LR 5m</th>
      </tr>
    );
  }

  function renderRow([sym, score]: [string, number, string]) {
    const state = stateMap.get(sym);
    const trend = state?.trend ?? "flat";
    const color = trendColors[trend] ?? "text-slate-500";
    const arrow = trendArrows[trend] ?? "◆";

    // Color score based on tier
    let scoreColor = "text-slate-400";
    if (score >= 70) scoreColor = "text-green-400";
    else if (score >= 50) scoreColor = "text-yellow-400";
    else if (score >= 30) scoreColor = "text-orange-400";

    return (
      <tr key={sym} className="border-b border-slate-800 last:border-0 hover:bg-slate-800/50">
        <td className="py-2 px-3 font-medium text-white">{sym}</td>
        <td className={`py-2 px-3 text-right font-mono text-xs ${scoreColor}`}>
          {score.toFixed(3)}
        </td>
        <td className="py-2 px-3 text-right font-mono text-xs text-slate-300">
          {formatPrice(state?.bid)}
        </td>
        <td className="py-2 px-3 text-right font-mono text-xs text-slate-300">
          {formatPrice(state?.ask)}
        </td>
        <td className={`py-2 px-3 text-center text-sm font-medium ${color}`}>
          {arrow} {trend === "flat" ? "Flat" : trend === "closed" ? "Closed" : trend === "rollover" ? "Rollover" : trend}
        </td>
        <td className={`py-2 px-3 text-right font-mono text-xs ${(state?.lr_15 ?? 0) > 0 ? "text-green-400" : (state?.lr_15 ?? 0) < 0 ? "text-red-400" : "text-slate-500"}`}>
          {state ? (state.lr_15 > 0 ? "+" : "") + state.lr_15.toFixed(4) + "%" : "—"}
        </td>
        <td className={`py-2 px-3 text-right font-mono text-xs ${(state?.lr_5 ?? 0) > 0 ? "text-green-400" : (state?.lr_5 ?? 0) < 0 ? "text-red-400" : "text-slate-500"}`}>
          {state ? (state.lr_5 > 0 ? "+" : "") + state.lr_5.toFixed(4) + "%" : "—"}
        </td>
      </tr>
    );
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
      <div className="px-4 py-2 border-b border-slate-800 flex items-center justify-between">
        <span className="text-sm font-medium text-slate-300">📊 Watchlist</span>
        <span className="text-xs text-slate-500">{data.ranked.length} symbols</span>
      </div>

      <div className="space-y-0">
        {/* Tier 1 */}
        {tier1Items.length > 0 && (
          <div>
            <div className="text-xs text-green-400 font-medium px-3 pt-2 pb-1">Tier 1</div>
            <table className="w-full text-sm">
              <thead>{tableHeaders()}</thead>
              <tbody>
                {tier1Items.map((r) => renderRow(r))}
              </tbody>
            </table>
          </div>
        )}

        {/* Tier 2 */}
        {tier2Items.length > 0 && (
          <div>
            <div className="text-xs text-yellow-400 font-medium px-3 pt-2 pb-1">Tier 2</div>
            <table className="w-full text-sm">
              <thead>{tableHeaders()}</thead>
              <tbody>
                {tier2Items.map((r) => renderRow(r))}
              </tbody>
            </table>
          </div>
        )}

        {/* Below Threshold — collapsible */}
        <div>
          <button
            onClick={() => setShowBelow(!showBelow)}
            className="flex items-center gap-2 text-xs text-slate-400 hover:text-slate-200 transition-colors w-full px-3 pt-1 pb-1"
          >
            <span className={`transition-transform ${showBelow ? "rotate-90" : ""}`}>▶</span>
            <span>Below Threshold ({belowItems.length})</span>
          </button>
          {showBelow && (
            <table className="w-full text-sm">
              <thead>{tableHeaders()}</thead>
              <tbody>
                {belowItems.map((r) => renderRow(r))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}