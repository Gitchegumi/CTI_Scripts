"use client";

import { useMemo, useState, useEffect } from "react";
import { SignalEntry, ActiveSignal } from "@/types";

const DISPLAY_WINDOW_MS = 60 * 60 * 1000; // 60 minutes

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
  const d = price >= 10 ? 3 : 5;
  return price.toLocaleString("en-US", {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
}

function fmtTs(ts: string): { et: string; ct: string } {
  try {
    const date = new Date(ts);
    const opts: Intl.DateTimeFormatOptions = {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    };
    return {
      et: date.toLocaleString("en-US", { ...opts, timeZone: "America/New_York" }),
      ct: date.toLocaleString("en-US", { ...opts, timeZone: "America/Chicago" }),
    };
  } catch {
    return { et: ts, ct: ts };
  }
}

function groupSignals(signals: SignalEntry[], now: number): ActiveSignal[] {
  const cutoff = now - DISPLAY_WINDOW_MS;
  const recent = signals.filter(s => new Date(s.timestamp).getTime() >= cutoff);

  // Group by symbol+direction — each direction gets its own card.
  // Conflicting signals for the same symbol (BUY and SELL) both show.
  const byKey = new Map<string, ActiveSignal>();
  for (const s of recent) {
    const key = `${s.symbol}:${s.direction}`;
    const existing = byKey.get(key);
    if (!existing) {
      byKey.set(key, { latest: s, count: 1 });
    } else {
      existing.count++;
      if (new Date(s.timestamp) > new Date(existing.latest.timestamp)) {
        existing.latest = s;
      }
    }
  }

  // Sort by most recent firing first
  return Array.from(byKey.values()).sort(
    (a, b) => new Date(b.latest.timestamp).getTime() - new Date(a.latest.timestamp).getTime()
  );
}

export default function SignalsSection({ signals }: SignalsSectionProps) {
  // Re-evaluate the 60-min window every minute so cards expire without a data change
  const [tick, setTick] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setTick(Date.now()), 60_000);
    return () => clearInterval(id);
  }, []);

  const active = useMemo(() => groupSignals(signals, tick), [signals, tick]);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
      <div className="px-4 py-2 border-b border-slate-800 flex items-center justify-between">
        <span className="text-sm font-medium text-slate-300">⚡ Active Signals</span>
        <span className="text-xs text-slate-500">last 60 min</span>
      </div>

      {active.length === 0 ? (
        <div className="px-4 py-4 text-sm text-slate-500 text-center">No signals in the last 60 minutes</div>
      ) : (
        <div className="p-3 grid gap-2 grid-cols-1 xs:grid-cols-2">
          {active.map(({ latest: sig, count }) => {
            const key = `${sig.symbol}:${sig.direction}`;
            const dirColor = sig.direction === "BUY" ? "text-green-400" : "text-red-400";
            const dirBg = sig.direction === "BUY" ? "bg-green-900/30 border-green-700" : "bg-red-900/30 border-red-700";
            return (
              <div
                key={key}
                className={`bg-slate-950 border rounded-lg p-3 space-y-2 ${dirBg}`}
              >
                {/* Header: symbol + count badge on one line, direction on its own line */}
                <div>
                  <div className="flex items-center gap-1.5">
                    <span className="font-bold text-white">{sig.symbol}</span>
                    {count > 1 && (
                      <span className="text-xs px-1.5 py-0.5 rounded bg-slate-700 text-slate-300">
                        ×{count}
                      </span>
                    )}
                  </div>
                  <span className={`text-xs font-bold uppercase ${dirColor}`}>
                    {sig.direction}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                  <div className="text-slate-400">Strategy</div>
                  <div className="text-white text-right">{sig.strategy ?? "CTI-v1"}</div>
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
                  <div className="text-white text-right">
                    {sig.rr !== null ? sig.rr.toFixed(1) : "—"}
                  </div>
                </div>
                <div className="text-xs text-slate-500 border-t border-slate-700 pt-1.5 mt-1 space-y-0.5">
                  {(() => { const t = fmtTs(sig.timestamp); return (<><div>{t.et} ET</div><div>{t.ct} CT</div></>); })()}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
