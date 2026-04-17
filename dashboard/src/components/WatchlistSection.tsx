"use client";

import { useState } from "react";
import { WatchlistData, SymbolState } from "@/types";

interface WatchlistSectionProps {
  data: WatchlistData;
  loopState: SymbolState[];
}

const tierColors: Record<string, string> = {
  "Tier 1": "bg-green-600 text-green-100",
  "Tier 2": "bg-yellow-600 text-yellow-100",
  "Below Threshold": "bg-slate-700 text-slate-300",
};

const trendColors: Record<string, string> = {
  "Uptrend": "text-green-400",
  "Downtrend": "text-red-400",
  "flat": "text-slate-500",
};

const trendArrows: Record<string, string> = {
  "Uptrend": "▲",
  "Downtrend": "▼",
  "flat": "◆",
};

function TrendBadge({ trend, lr15, lr5 }: { trend: string; lr15: number; lr5: number }) {
  const color = trendColors[trend] || "text-slate-500";
  const arrow = trendArrows[trend] || "◆";
  return (
    <div className={`flex items-center gap-1.5 ${color}`}>
      <span className="text-sm">{arrow}</span>
      <span className="text-xs font-mono">
        15m: <span className={lr15 > 0 ? "text-green-400" : lr15 < 0 ? "text-red-400" : "text-slate-400"}>
          {lr15 > 0 ? "+" : ""}{lr15.toFixed(2)}%
        </span>
      </span>
      <span className="text-xs font-mono">
        5m: <span className={lr5 > 0 ? "text-green-400" : lr5 < 0 ? "text-red-400" : "text-slate-400"}>
          {lr5 > 0 ? "+" : ""}{lr5.toFixed(2)}%
        </span>
      </span>
    </div>
  );
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
              <thead>
                <tr className="border-b border-slate-800 text-slate-500 text-xs uppercase">
                  <th className="text-left py-2 px-3 font-medium">Symbol</th>
                  <th className="text-right py-2 px-3 font-medium">Score</th>
                  <th className="text-right py-2 px-3 font-medium">Trend</th>
                  <th className="text-right py-2 px-3 font-medium">LR 15m</th>
                  <th className="text-right py-2 px-3 font-medium">LR 5m</th>
                </tr>
              </thead>
              <tbody>
                {tier1Items.map(([sym, score, tier]) => {
                  const state = stateMap.get(sym);
                  return (
                    <tr key={sym} className="border-b border-slate-800 last:border-0 hover:bg-slate-800/50">
                      <td className="py-2 px-3 font-medium text-white">{sym}</td>
                      <td className="py-2 px-3 text-right text-slate-300">{score.toFixed(3)}</td>
                      <td className="py-2 px-3 text-right">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${tierColors[tier]}`}>
                          {tier}
                        </span>
                      </td>
                      <td className={`py-2 px-3 text-right font-mono text-xs ${(state?.lr_15 ?? 0) > 0 ? "text-green-400" : (state?.lr_15 ?? 0) < 0 ? "text-red-400" : "text-slate-500"}`}>
                        {state ? (state.lr_15 > 0 ? "+" : "") + state.lr_15.toFixed(2) + "%" : "—"}
                      </td>
                      <td className={`py-2 px-3 text-right font-mono text-xs ${(state?.lr_5 ?? 0) > 0 ? "text-green-400" : (state?.lr_5 ?? 0) < 0 ? "text-red-400" : "text-slate-500"}`}>
                        {state ? (state.lr_5 > 0 ? "+" : "") + state.lr_5.toFixed(2) + "%" : "—"}
                      </td>
                    </tr>
                  );
                })}
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
              <thead>
                <tr className="border-b border-slate-800 text-slate-500 text-xs uppercase">
                  <th className="text-left py-2 px-3 font-medium">Symbol</th>
                  <th className="text-right py-2 px-3 font-medium">Score</th>
                  <th className="text-right py-2 px-3 font-medium">Trend</th>
                  <th className="text-right py-2 px-3 font-medium">LR 15m</th>
                  <th className="text-right py-2 px-3 font-medium">LR 5m</th>
                </tr>
              </thead>
              <tbody>
                {tier2Items.map(([sym, score, tier]) => {
                  const state = stateMap.get(sym);
                  return (
                    <tr key={sym} className="border-b border-slate-800 last:border-0 hover:bg-slate-800/50">
                      <td className="py-2 px-3 font-medium text-white">{sym}</td>
                      <td className="py-2 px-3 text-right text-slate-300">{score.toFixed(3)}</td>
                      <td className="py-2 px-3 text-right">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${tierColors[tier]}`}>
                          {tier}
                        </span>
                      </td>
                      <td className={`py-2 px-3 text-right font-mono text-xs ${(state?.lr_15 ?? 0) > 0 ? "text-green-400" : (state?.lr_15 ?? 0) < 0 ? "text-red-400" : "text-slate-500"}`}>
                        {state ? (state.lr_15 > 0 ? "+" : "") + state.lr_15.toFixed(2) + "%" : "—"}
                      </td>
                      <td className={`py-2 px-3 text-right font-mono text-xs ${(state?.lr_5 ?? 0) > 0 ? "text-green-400" : (state?.lr_5 ?? 0) < 0 ? "text-red-400" : "text-slate-500"}`}>
                        {state ? (state.lr_5 > 0 ? "+" : "") + state.lr_5.toFixed(2) + "%" : "—"}
                      </td>
                    </tr>
                  );
                })}
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
                  <th className="text-right py-2 px-3 font-medium">Tier</th>
                </tr>
              </thead>
              <tbody>
                {belowItems.map(([sym, score, tier]) => (
                  <tr key={sym} className="border-b border-slate-800 last:border-0 hover:bg-slate-800/50">
                    <td className="py-2 px-3 font-medium text-slate-400">{sym}</td>
                    <td className="py-2 px-3 text-right text-slate-500">{score.toFixed(3)}</td>
                    <td className="py-2 px-3 text-right">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${tierColors[tier]}`}>
                        {tier}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}