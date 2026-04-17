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
};

const trendArrows: Record<string, string> = {
  Uptrend: "▲",
  Downtrend: "▼",
  flat: "◆",
  closed: "✕",
};

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

  const tableHeaders = (
    <tr className="border-b border-slate-800 text-slate-500 text-xs uppercase">
      <th className="text-left py-2 px-3 font-medium">Symbol</th>
      <th className="text-right py-2 px-3 font-medium">Score</th>
      <th className="text-center py-2 px-3 font-medium">State</th>
      <th className="text-right py-2 px-3 font-medium">LR 15m</th>
      <th className="text-right py-2 px-3 font-medium">LR 5m</th>
    </tr>
  );

  function renderRow([sym, score]: [string, number, string]) {
    const state = stateMap.get(sym);
    const trend = state?.trend ?? "flat";
    const color = trendColors[trend] ?? "text-slate-500";
    const arrow = trendArrows[trend] ?? "◆";

    return (
      <tr key={sym} className="border-b border-slate-800 last:border-0 hover:bg-slate-800/50">
        <td className="py-2 px-3 font-medium text-white">{sym}</td>
        <td className="py-2 px-3 text-right text-slate-300">{score.toFixed(3)}</td>
        <td className={`py-2 px-3 text-center text-sm font-medium ${color}`}>
          {arrow} {trend === "flat" ? "Flat" : trend === "closed" ? "Closed" : trend}
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
    <div className="space-y-2 h-full">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide">
          Watchlist
        </h2>
        <span className="text-xs text-slate-500">{data.ranked.length} symbols</span>
      </div>

      {/* Tier 1 */}
      {tier1Items.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs text-green-400 font-medium px-1">Tier 1</div>
          <div className="bg-slate-900 border border-green-900 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>{tableHeaders}</thead>
              <tbody>
                {tier1Items.map((r) => renderRow(r))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tier 2 */}
      {tier2Items.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs text-yellow-400 font-medium px-1">Tier 2</div>
          <div className="bg-slate-900 border border-yellow-900 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>{tableHeaders}</thead>
              <tbody>
                {tier2Items.map((r) => renderRow(r))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Below Threshold — collapsible */}
      <div className="space-y-1">
        <button
          onClick={() => setShowBelow(!showBelow)}
          className="flex items-center gap-2 text-xs text-slate-400 hover:text-slate-200 transition-colors w-full px-1"
        >
          <span className={`transition-transform ${showBelow ? "rotate-90" : ""}`}>▶</span>
          <span>Below Threshold ({belowItems.length})</span>
        </button>
        {showBelow && (
          <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-slate-500 text-xs uppercase">
                  <th className="text-left py-2 px-3 font-medium">Symbol</th>
                  <th className="text-right py-2 px-3 font-medium">Score</th>
                  <th className="text-center py-2 px-3 font-medium">State</th>
                  <th className="text-right py-2 px-3 font-medium">LR 15m</th>
                  <th className="text-right py-2 px-3 font-medium">LR 5m</th>
                </tr>
              </thead>
              <tbody>
                {belowItems.map(([sym, score]) => {
                  const state = stateMap.get(sym);
                  const trend = state?.trend ?? "flat";
                  const color = trendColors[trend] ?? "text-slate-500";
                  const arrow = trendArrows[trend] ?? "◆";
                  return (
                    <tr key={sym} className="border-b border-slate-800 last:border-0 hover:bg-slate-800/50">
                      <td className="py-2 px-3 font-medium text-slate-400">{sym}</td>
                      <td className="py-2 px-3 text-right text-slate-500">{score.toFixed(3)}</td>
                      <td className={`py-2 px-3 text-center text-xs font-medium ${color}`}>
                        {arrow} {trend === "flat" ? "Flat" : trend === "closed" ? "Closed" : trend}
                      </td>
                      <td className={`py-2 px-3 text-right font-mono text-xs ${(state?.lr_15 ?? 0) > 0 ? "text-green-400" : (state?.lr_15 ?? 0) < 0 ? "text-red-400" : "text-slate-500"}`}>
                        {state ? (state.lr_15 > 0 ? "+" : "") + state.lr_15.toFixed(4) + "%" : "—"}
                      </td>
                      <td className={`py-2 px-3 text-right font-mono text-xs ${(state?.lr_5 ?? 0) > 0 ? "text-green-400" : (state?.lr_5 ?? 0) < 0 ? "text-red-400" : "text-slate-500"}`}>
                        {state ? (state.lr_5 > 0 ? "+" : "") + state.lr_5.toFixed(4) + "%" : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}