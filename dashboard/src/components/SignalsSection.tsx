"use client";

import { SignalEntry } from "@/types";

interface SignalsSectionProps {
  signals: SignalEntry[];
}

function fmt(n: number, d = 2): string {
  return n.toLocaleString("en-US", {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
}

function fmtPrice(price: number): string {
  // Match Oanda quoting conventions by price magnitude:
  //   >= 10  → JPY crosses (NZDJPY ~93, USDJPY ~159) → 3 decimal places
  //   >= 1   → Major pairs (EURUSD ~1.09, GBPUSD ~1.27) → 5 decimal places
  const d = price >= 10 ? 3 : 5;
  return price.toLocaleString("en-US", {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
}

function fmtTs(ts: string): string {
  try {
    const d = new Date(ts);
    return d.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: "America/New_York",
    });
  } catch {
    return ts;
  }
}

export default function SignalsSection({ signals }: SignalsSectionProps) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
      <div className="px-4 py-2 border-b border-slate-800">
        <span className="text-sm font-medium text-slate-300">⚡ Active Signals</span>
      </div>

      {signals.length === 0 ? (
        <div className="px-4 py-4 text-sm text-slate-500 text-center">No active signals</div>
      ) : (
        <div className="p-3 grid gap-2 grid-cols-2">
          {signals.map((sig, i) => {
            const dirColor = sig.direction === "BUY" ? "text-green-400" : "text-red-400";
            const dirBg = sig.direction === "BUY" ? "bg-green-900/30 border-green-700" : "bg-red-900/30 border-red-700";
            return (
              <div
                key={i}
                className={`bg-slate-950 border rounded-lg p-3 space-y-2 ${dirBg}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="font-bold text-white">{sig.symbol}</span>
                    {(sig.update_count ?? 1) > 1 && (
                      <span className="text-xs px-1.5 py-0.5 rounded bg-slate-700 text-slate-300">
                        ×{sig.update_count}
                      </span>
                    )}
                  </div>
                  <span className={`text-xs font-bold uppercase ${dirColor}`}>
                    {sig.direction}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                  <div className="text-slate-400">Confidence</div>
                  <div className="text-white text-right">{Math.round(sig.confidence * 100)}%</div>
                  <div className="text-slate-400">Entry</div>
                  <div className="text-white text-right">{fmtPrice(sig.entry_price)}</div>
                  <div className="text-slate-400">Stop Loss</div>
                  <div className="text-red-400 text-right">{fmtPrice(sig.stop_loss)}</div>
                  <div className="text-slate-400">Take Profit</div>
                  <div className="text-green-400 text-right">{fmtPrice(sig.take_profit)}</div>
                  <div className="text-slate-400">Lot Size</div>
                  <div className="text-white text-right">{sig.lot_size}</div>
                  <div className="text-slate-400">ATR</div>
                  <div className="text-white text-right">{fmt(sig.atr)}</div>
                  <div className="text-slate-400">R:R</div>
                  <div className="text-white text-right">{sig.rr.toFixed(1)}</div>
                </div>
                <div className="text-xs text-slate-500 border-t border-slate-700 pt-1.5 mt-1">
                  {fmtTs(sig.timestamp)} ET
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}