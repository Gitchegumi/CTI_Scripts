"use client";

import { OpenPosition } from "@/types";

function isJPY(symbol: string): boolean {
  return symbol.includes("JPY");
}

function formatPrice(price: number, symbol: string): string {
  if (price === 0) return "—";
  const decimals = isJPY(symbol) ? 3 : 5;
  return price.toFixed(decimals);
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

interface OpenTradesProps {
  positions: OpenPosition[];
}

export default function OpenTrades({ positions }: OpenTradesProps) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
      <div className="px-4 py-2 border-b border-slate-800 text-sm font-medium text-slate-300">
        📊 Open Trades
      </div>
      {positions.length === 0 ? (
        <div className="px-4 py-4 text-sm text-slate-500 text-center">No open positions</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-slate-500 border-b border-slate-800">
                <th className="px-3 py-1.5 text-left font-medium">Symbol</th>
                <th className="px-3 py-1.5 text-left font-medium">Side</th>
                <th className="px-3 py-1.5 text-right font-medium">Volume</th>
                <th className="px-3 py-1.5 text-right font-medium">Open</th>
                <th className="px-3 py-1.5 text-right font-medium">Current</th>
                <th className="px-3 py-1.5 text-right font-medium">SL</th>
                <th className="px-3 py-1.5 text-right font-medium">TP</th>
                <th className="px-3 py-1.5 text-right font-medium">Unreal. P/L</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((pos) => (
                <tr key={pos.id} className="border-b border-slate-800 last:border-0 hover:bg-slate-800/50">
                  <td className="px-3 py-1.5 font-medium text-slate-200">{pos.symbol}</td>
                  <td className="px-3 py-1.5"><SideCell side={pos.side} /></td>
                  <td className="px-3 py-1.5 text-right text-slate-300">{pos.volume.toLocaleString()}</td>
                  <td className="px-3 py-1.5 text-right text-slate-300">{formatPrice(pos.open_price, pos.symbol)}</td>
                  <td className="px-3 py-1.5 text-right text-slate-300">{formatPrice(pos.current_price, pos.symbol)}</td>
                  <td className="px-3 py-1.5 text-right text-slate-400">{pos.stop_loss ? formatPrice(pos.stop_loss, pos.symbol) : "—"}</td>
                  <td className="px-3 py-1.5 text-right text-slate-400">{pos.take_profit ? formatPrice(pos.take_profit, pos.symbol) : "—"}</td>
                  <td className="px-3 py-1.5 text-right"><PLCell value={pos.unrealized_pl} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
