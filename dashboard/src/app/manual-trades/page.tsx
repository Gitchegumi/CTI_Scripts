"use client";

import { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { ManualTrade, ManualTradeSummary } from "@/types";

// ── Formatting helpers ────────────────────────────────────────────────────────

function fmtPrice(p: number, symbol?: string): string {
  if (!p && p !== 0) return "—";
  const decimals = symbol?.includes("JPY") ? 3 : 5;
  return p.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("en-US", {
      timeZone: "America/Chicago",
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  } catch {
    return iso;
  }
}

function fmtPL(v: number): string {
  const prefix = v >= 0 ? "+" : "";
  return `${prefix}$${Math.abs(v).toFixed(2)}`;
}

function fmtPct(v: number): string {
  const prefix = v >= 0 ? "+" : "";
  return `${prefix}${v.toFixed(2)}%`;
}

// ── Direction badge ───────────────────────────────────────────────────────────

function DirectionBadge({ direction }: { direction: string }) {
  const isLong = direction === "long";
  return (
    <span
      className={`text-xs font-bold uppercase px-2 py-0.5 rounded ${
        isLong
          ? "bg-green-900/40 text-green-400 border border-green-700"
          : "bg-red-900/40 text-red-400 border border-red-700"
      }`}
    >
      {direction}
    </span>
  );
}

// ── Status badge ──────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`text-xs px-2 py-0.5 rounded border ${
        status === "closed"
          ? "bg-slate-700 text-slate-300 border-slate-600"
          : "bg-blue-900/30 text-blue-400 border-blue-700"
      }`}
    >
      {status}
    </span>
  );
}

// ── P/L cell ─────────────────────────────────────────────────────────────────

function PLCell({ value, percent }: { value: number; percent?: number }) {
  const isWin = value >= 0;
  return (
    <div className="text-right">
      <span className={isWin ? "text-green-400" : "text-red-400"}>
        {fmtPL(value)}
      </span>
      {percent !== undefined && (
        <div className={`text-xs ${isWin ? "text-green-500" : "text-red-500"}`}>
          {fmtPct(percent)}
        </div>
      )}
    </div>
  );
}

// ── Stats cards ─────────────────────────────────────────────────────────────

function StatsCards({ stats }: { stats: ManualTradeSummary | null }) {
  if (!stats) return null;

  const cards = [
    { label: "Total Trades", value: stats.total_trades, sub: `${stats.open_trades} open` },
    { label: "Win Rate", value: `${stats.win_rate}%`, sub: `${stats.wins}W / ${stats.losses}L` },
    { label: "Total P&L", value: fmtPL(stats.total_pnl), sub: "all closed trades" },
    { label: "Avg P&L", value: fmtPL(stats.avg_pnl), sub: fmtPct(stats.avg_pnl_percent) },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
      {cards.map(({ label, value, sub }) => (
        <div key={label} className="bg-slate-900 border border-slate-800 rounded-lg px-4 py-3">
          <div className="text-slate-500 text-xs">{label}</div>
          <div className="text-white text-xl font-semibold mt-0.5">{value}</div>
          <div className="text-slate-600 text-xs mt-0.5">{sub}</div>
        </div>
      ))}
    </div>
  );
}

// ── Trade form modal ──────────────────────────────────────────────────────────

interface TradeFormData {
  symbol: string;
  direction: "long" | "short";
  entry_price: string;
  exit_price: string;
  entry_time: string;
  exit_time: string;
  notes: string;
}

const EMPTY_FORM: TradeFormData = {
  symbol: "",
  direction: "long",
  entry_price: "",
  exit_price: "",
  entry_time: "",
  exit_time: "",
  notes: "",
};

function TradeFormModal({
  trade,
  onSave,
  onClose,
}: {
  trade?: ManualTrade;
  onSave: (data: Partial<TradeFormData>) => void;
  onClose: () => void;
}) {
  const [form, setForm] = useState<TradeFormData>(() => {
    if (!trade) return EMPTY_FORM;
    return {
      symbol: trade.symbol,
      direction: trade.direction,
      entry_price: trade.entry_price.toString(),
      exit_price: trade.exit_price?.toString() ?? "",
      entry_time: trade.entry_time.slice(0, 16), // datetime-local format
      exit_time: trade.exit_time?.slice(0, 16) ?? "",
      notes: trade.notes,
    };
  });

  const isEdit = !!trade;

  function updateField(field: keyof TradeFormData, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const payload: Partial<TradeFormData> = {};

    if (form.symbol.trim()) payload.symbol = form.symbol.trim().toUpperCase();
    if (form.direction) payload.direction = form.direction;
    if (form.entry_price) payload.entry_price = form.entry_price;
    if (form.exit_price) payload.exit_price = form.exit_price;
    if (form.entry_time) payload.entry_time = new Date(form.entry_time).toISOString();
    if (form.exit_time) payload.exit_time = new Date(form.exit_time).toISOString();
    if (form.notes) payload.notes = form.notes;

    onSave(payload);
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 px-4">
      <div className="bg-slate-900 border border-slate-700 rounded-lg w-full max-w-md max-h-[90vh] overflow-y-auto">
        <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
          <h3 className="text-white font-semibold text-sm">
            {isEdit ? "Edit Trade" : "Add Trade"}
          </h3>
          <button
            onClick={onClose}
            className="text-slate-500 hover:text-slate-300 text-lg leading-none"
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-4 py-4 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Symbol</label>
              <input
                type="text"
                value={form.symbol}
                onChange={(e) => updateField("symbol", e.target.value)}
                placeholder="EURUSD"
                required
                className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500 placeholder-slate-600"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Direction</label>
              <select
                value={form.direction}
                onChange={(e) => updateField("direction", e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500"
              >
                <option value="long">Long</option>
                <option value="short">Short</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Entry Price</label>
              <input
                type="number"
                step="0.00001"
                value={form.entry_price}
                onChange={(e) => updateField("entry_price", e.target.value)}
                required
                className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Exit Price</label>
              <input
                type="number"
                step="0.00001"
                value={form.exit_price}
                onChange={(e) => updateField("exit_price", e.target.value)}
                placeholder="Optional"
                className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500 placeholder-slate-600"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Entry Time</label>
              <input
                type="datetime-local"
                value={form.entry_time}
                onChange={(e) => updateField("entry_time", e.target.value)}
                required
                className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500 [color-scheme:dark]"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Exit Time</label>
              <input
                type="datetime-local"
                value={form.exit_time}
                onChange={(e) => updateField("exit_time", e.target.value)}
                placeholder="Optional"
                className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500 placeholder-slate-600 [color-scheme:dark]"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs text-slate-500 mb-1">Notes</label>
            <textarea
              value={form.notes}
              onChange={(e) => updateField("notes", e.target.value)}
              rows={3}
              placeholder="Optional notes about this trade..."
              className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500 placeholder-slate-600 resize-none"
            />
          </div>

          <div className="flex gap-2 pt-2">
            <button
              type="submit"
              className="flex-1 bg-blue-700 hover:bg-blue-600 text-white text-sm rounded py-2 transition-colors"
            >
              {isEdit ? "Save Changes" : "Add Trade"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm rounded py-2 transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Delete confirmation ───────────────────────────────────────────────────────

function DeleteConfirmModal({
  trade,
  onConfirm,
  onClose,
}: {
  trade: ManualTrade;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 px-4">
      <div className="bg-slate-900 border border-slate-700 rounded-lg w-full max-w-sm px-4 py-4">
        <h3 className="text-white font-semibold text-sm mb-2">Delete Trade?</h3>
        <p className="text-slate-400 text-sm mb-4">
          {trade.symbol} {trade.direction} @ {fmtPrice(trade.entry_price, trade.symbol)}
        </p>
        <div className="flex gap-2">
          <button
            onClick={onConfirm}
            className="flex-1 bg-red-700 hover:bg-red-600 text-white text-sm rounded py-2 transition-colors"
          >
            Delete
          </button>
          <button
            onClick={onClose}
            className="px-4 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm rounded py-2 transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main page ───────────────────────────────────────────────────────────────

export default function ManualTradesPage() {
  const [trades, setTrades] = useState<ManualTrade[]>([]);
  const [stats, setStats] = useState<ManualTradeSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingTrade, setEditingTrade] = useState<ManualTrade | undefined>(undefined);
  const [deletingTrade, setDeletingTrade] = useState<ManualTrade | null>(null);
  const [filterSymbol, setFilterSymbol] = useState("");
  const [filterStatus, setFilterStatus] = useState<"all" | "open" | "closed">("all");

  // Load trades
  async function loadTrades() {
    try {
      const res = await fetch(`/api/manual-trades?_=${Date.now()}`, { cache: "no-store" });
      if (!res.ok) {
        if (res.status === 401) {
          setError("Unauthorized — please log in");
          return;
        }
        throw new Error(`HTTP ${res.status}`);
      }
      const data = await res.json();
      setTrades(Array.isArray(data) ? data : []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load trades");
    }
  }

  // Load stats
  async function loadStats() {
    try {
      const res = await fetch(`/api/manual-trades/stats?_=${Date.now()}`, { cache: "no-store" });
      if (res.ok) {
        setStats(await res.json());
      }
    } catch {
      // Non-critical
    }
  }

  // Initial load
  useEffect(() => {
    async function init() {
      setLoading(true);
      await Promise.all([loadTrades(), loadStats()]);
      setLoading(false);
    }
    init();
  }, []);

  // Refresh interval
  useEffect(() => {
    const id = setInterval(() => {
      loadTrades();
      loadStats();
    }, 30_000);
    return () => clearInterval(id);
  }, []);

  // Create trade
  async function createTrade(data: Partial<TradeFormData>) {
    try {
      const res = await fetch("/api/manual-trades", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await loadTrades();
      await loadStats();
      setShowForm(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create trade");
    }
  }

  // Update trade
  async function updateTrade(id: number, data: Partial<TradeFormData>) {
    try {
      const res = await fetch(`/api/manual-trades/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await loadTrades();
      await loadStats();
      setEditingTrade(undefined);
      setShowForm(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update trade");
    }
  }

  // Delete trade
  async function deleteTrade(id: number) {
    try {
      const res = await fetch(`/api/manual-trades/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await loadTrades();
      await loadStats();
      setDeletingTrade(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete trade");
    }
  }

  // Filtered trades
  const filteredTrades = useMemo(() => {
    return trades.filter((t) => {
      if (filterSymbol && !t.symbol.toLowerCase().includes(filterSymbol.toLowerCase())) return false;
      if (filterStatus !== "all" && t.status !== filterStatus) return false;
      return true;
    });
  }, [trades, filterSymbol, filterStatus]);

  // Unique symbols for filter
  const symbols = useMemo(
    () => Array.from(new Set(trades.map((t) => t.symbol))).sort(),
    [trades]
  );

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Header */}
      <div className="border-b border-slate-800 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/" className="text-slate-500 hover:text-slate-300 text-sm transition-colors">
            ← Dashboard
          </Link>
          <span className="text-slate-700">|</span>
          <span className="text-white font-semibold text-sm">Manual Trade History</span>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/journal"
            className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
          >
            Journal →
          </Link>
          <button
            onClick={() => {
              setEditingTrade(undefined);
              setShowForm(true);
            }}
            className="bg-blue-700 hover:bg-blue-600 text-white text-xs px-3 py-1.5 rounded transition-colors"
          >
            + Add Trade
          </button>
        </div>
      </div>

      <main className="px-4 py-6 max-w-6xl mx-auto">
        {loading && (
          <div className="text-slate-500 text-sm text-center py-20">Loading trades…</div>
        )}

        {error && (
          <div className="bg-red-900/20 border border-red-800 rounded-lg p-4 text-red-400 text-sm mb-6">
            {error}
          </div>
        )}

        {!loading && !error && (
          <>
            <StatsCards stats={stats} />

            {/* Filters */}
            <div className="flex flex-wrap gap-3 mb-4">
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500">Symbol:</span>
                <input
                  type="text"
                  value={filterSymbol}
                  onChange={(e) => setFilterSymbol(e.target.value)}
                  placeholder="Filter..."
                  className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-blue-500 placeholder-slate-600 w-24"
                />
                {symbols.length > 0 && (
                  <select
                    value={filterSymbol}
                    onChange={(e) => setFilterSymbol(e.target.value)}
                    className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-blue-500"
                  >
                    <option value="">All symbols</option>
                    {symbols.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <div className="flex items-center gap-1">
                <span className="text-xs text-slate-500">Status:</span>
                {(["all", "open", "closed"] as const).map((s) => (
                  <button
                    key={s}
                    onClick={() => setFilterStatus(s)}
                    className={`text-xs px-2 py-0.5 rounded transition-colors ${
                      filterStatus === s
                        ? "bg-slate-600 text-white"
                        : "bg-slate-800 text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    {s === "all" ? "All" : s}
                  </button>
                ))}
              </div>

              <div className="ml-auto text-xs text-slate-500">
                {filteredTrades.length} of {trades.length} trades
              </div>
            </div>

            {/* Table */}
            {filteredTrades.length === 0 ? (
              <div className="text-slate-500 text-sm text-center py-20">
                {trades.length === 0
                  ? "No trades recorded yet. Click \"+ Add Trade\" to log your first manual trade."
                  : "No trades match the current filters."}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-slate-500 border-b border-slate-800">
                      <th className="px-3 py-2 text-left font-medium">Symbol</th>
                      <th className="px-3 py-2 text-left font-medium">Dir</th>
                      <th className="px-3 py-2 text-right font-medium">Entry</th>
                      <th className="px-3 py-2 text-right font-medium">Exit</th>
                      <th className="px-3 py-2 text-right font-medium">P&L</th>
                      <th className="px-3 py-2 text-left font-medium">Status</th>
                      <th className="px-3 py-2 text-left font-medium">Entry Time</th>
                      <th className="px-3 py-2 text-left font-medium">Notes</th>
                      <th className="px-3 py-2 text-right font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredTrades.map((trade) => (
                      <tr
                        key={trade.id}
                        className="border-b border-slate-800/60 hover:bg-slate-800/30 transition-colors"
                      >
                        <td className="px-3 py-2 font-medium text-white">{trade.symbol}</td>
                        <td className="px-3 py-2">
                          <DirectionBadge direction={trade.direction} />
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-slate-300">
                          {fmtPrice(trade.entry_price, trade.symbol)}
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-slate-300">
                          {trade.exit_price ? fmtPrice(trade.exit_price, trade.symbol) : "—"}
                        </td>
                        <td className="px-3 py-2">
                          <PLCell
                            value={trade.pnl}
                            percent={trade.status === "closed" ? trade.pnl_percent : undefined}
                          />
                        </td>
                        <td className="px-3 py-2">
                          <StatusBadge status={trade.status} />
                        </td>
                        <td className="px-3 py-2 text-slate-400">{fmtDate(trade.entry_time)}</td>
                        <td className="px-3 py-2 text-slate-400 max-w-[200px] truncate">
                          {trade.notes || "—"}
                        </td>
                        <td className="px-3 py-2 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <button
                              onClick={() => {
                                setEditingTrade(trade);
                                setShowForm(true);
                              }}
                              className="text-slate-500 hover:text-blue-400 transition-colors px-1"
                              title="Edit"
                            >
                              ✎
                            </button>
                            <button
                              onClick={() => setDeletingTrade(trade)}
                              className="text-slate-500 hover:text-red-400 transition-colors px-1"
                              title="Delete"
                            >
                              🗑
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </main>

      {/* Modals */}
      {showForm && (
        <TradeFormModal
          trade={editingTrade}
          onSave={(data) => {
            if (editingTrade) {
              updateTrade(editingTrade.id, data);
            } else {
              createTrade(data);
            }
          }}
          onClose={() => {
            setShowForm(false);
            setEditingTrade(undefined);
          }}
        />
      )}

      {deletingTrade && (
        <DeleteConfirmModal
          trade={deletingTrade}
          onConfirm={() => deleteTrade(deletingTrade.id)}
          onClose={() => setDeletingTrade(null)}
        />
      )}
    </div>
  );
}
