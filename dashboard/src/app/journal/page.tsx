"use client";

import { useState, useEffect, useMemo } from "react";
import Link from "next/link";

// ── Types ─────────────────────────────────────────────────────────────────────

interface JournalEntry {
  signal_id: string;
  symbol: string;
  direction: "BUY" | "SELL";
  strategy: string;
  confidence: number;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  lot_size: number;
  atr: number;
  rr: number | null;
  signal_timestamp: string;
  grade: "PENDING" | "TP_HIT" | "SL_HIT" | "MANUAL_CLOSE" | "EXPIRED";
  grade_timestamp: string | null;
  notes: string;
  discord_msg_id: string | null;
}

interface TradeGroup {
  groupId: string;           // signal_id of first entry — stable key
  symbol: string;
  direction: "BUY" | "SELL";
  strategy: string;
  entries: JournalEntry[];   // oldest → newest
  avgConfidence: number;
  grade: JournalEntry["grade"];
  firstTs: string;
  lastTs: string;
  rr: number | null;         // from the first entry
}

// ── Grouping logic ────────────────────────────────────────────────────────────

function isSameTrade(prev: JournalEntry, curr: JournalEntry): boolean {
  const e = curr.entry_price;
  if (prev.direction === "BUY") {
    // Still between the SL and TP of the previous signal → same trade
    return e > prev.stop_loss && e < prev.take_profit;
  } else {
    // SELL: SL is above entry, TP is below entry
    return e < prev.stop_loss && e > prev.take_profit;
  }
}

function groupIntoTrades(entries: JournalEntry[]): TradeGroup[] {
  // Process oldest → newest so each new entry can be compared to its predecessor
  const sorted = [...entries].sort(
    (a, b) => new Date(a.signal_timestamp).getTime() - new Date(b.signal_timestamp).getTime()
  );

  const groups: TradeGroup[] = [];

  for (const entry of sorted) {
    // Find the most recent open group for this symbol+direction
    const lastGroup = [...groups].reverse().find(
      g => g.symbol === entry.symbol && g.direction === entry.direction
    );

    if (lastGroup) {
      const lastEntry = lastGroup.entries[lastGroup.entries.length - 1];
      if (isSameTrade(lastEntry, entry)) {
        lastGroup.entries.push(entry);
        lastGroup.lastTs = entry.signal_timestamp;
        lastGroup.avgConfidence =
          lastGroup.entries.reduce((s, e) => s + e.confidence, 0) / lastGroup.entries.length;
        // Grade: most recent non-PENDING wins; otherwise keep what we have
        if (entry.grade !== "PENDING") lastGroup.grade = entry.grade;
        continue;
      }
    }

    groups.push({
      groupId: entry.signal_id,
      symbol: entry.symbol,
      direction: entry.direction,
      strategy: entry.strategy ?? "CTI-v1",
      entries: [entry],
      avgConfidence: entry.confidence,
      grade: entry.grade,
      firstTs: entry.signal_timestamp,
      lastTs: entry.signal_timestamp,
      rr: entry.rr,
    });
  }

  return groups.reverse(); // newest first for display
}

// ── Formatting helpers ────────────────────────────────────────────────────────

function fmtPrice(p: number): string {
  const d = p >= 10 ? 3 : 5;
  return p.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
}

function fmtDateGroup(ts: string): string {
  try {
    return new Date(ts).toLocaleDateString("en-US", {
      weekday: "long", month: "long", day: "numeric", year: "numeric",
      timeZone: "America/Chicago",
    });
  } catch { return ts.slice(0, 10); }
}

function fmtTime(ts: string): string {
  try {
    const d = new Date(ts);
    const et = d.toLocaleString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "America/New_York" });
    const ct = d.toLocaleString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "America/Chicago" });
    return `${et} ET / ${ct} CT`;
  } catch { return ts; }
}

function dateGroupKey(ts: string): string {
  try {
    return new Date(ts).toLocaleDateString("en-US", {
      year: "numeric", month: "2-digit", day: "2-digit",
      timeZone: "America/Chicago",
    });
  } catch { return ts.slice(0, 10); }
}

// ── Grade badge ───────────────────────────────────────────────────────────────

const GRADE_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  TP_HIT:       { bg: "bg-green-900/40 border-green-700",   text: "text-green-400",  label: "✅ TP Hit" },
  SL_HIT:       { bg: "bg-red-900/40 border-red-700",       text: "text-red-400",    label: "❌ SL Hit" },
  MANUAL_CLOSE: { bg: "bg-yellow-900/40 border-yellow-700", text: "text-yellow-400", label: "⚠️ Manual" },
  EXPIRED:      { bg: "bg-slate-800 border-slate-700",      text: "text-slate-500",  label: "⏭ Expired" },
  PENDING:      { bg: "bg-slate-800 border-slate-700",      text: "text-slate-400",  label: "⏳ Pending" },
};

function GradeBadge({ grade }: { grade: string }) {
  const s = GRADE_STYLES[grade] ?? GRADE_STYLES.PENDING;
  return (
    <span className={`text-xs px-2 py-0.5 rounded border font-medium ${s.bg} ${s.text}`}>
      {s.label}
    </span>
  );
}

// ── Stats bar — counts per trade group, not per raw entry ────────────────────

function StatsBar({ groups }: { groups: TradeGroup[] }) {
  const graded = groups.filter(g => g.grade !== "PENDING" && g.grade !== "EXPIRED");
  const tp = graded.filter(g => g.grade === "TP_HIT").length;
  const sl = graded.filter(g => g.grade === "SL_HIT").length;
  const manual = graded.filter(g => g.grade === "MANUAL_CLOSE").length;
  const winRate = graded.length > 0 ? Math.round((tp / graded.length) * 100) : null;

  const avgRR = (() => {
    const valid = graded.filter(g => g.rr != null);
    if (!valid.length) return null;
    return (valid.reduce((s, g) => s + (g.rr ?? 0), 0) / valid.length).toFixed(1);
  })();

  const avgConf = graded.length > 0
    ? Math.round(graded.reduce((s, g) => s + g.avgConfidence, 0) / graded.length * 100)
    : null;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
      {[
        { label: "Win Rate",        value: winRate !== null ? `${winRate}%` : "—", sub: `${tp}W / ${sl}L / ${manual}M` },
        { label: "Graded Trades",   value: graded.length,                          sub: `${groups.length} total` },
        { label: "Avg R:R",         value: avgRR ?? "—",                           sub: "graded only" },
        { label: "Avg Confidence",  value: avgConf !== null ? `${avgConf}%` : "—", sub: "graded only" },
      ].map(({ label, value, sub }) => (
        <div key={label} className="bg-slate-900 border border-slate-800 rounded-lg px-4 py-3">
          <div className="text-slate-500 text-xs">{label}</div>
          <div className="text-white text-xl font-semibold mt-0.5">{value}</div>
          <div className="text-slate-600 text-xs mt-0.5">{sub}</div>
        </div>
      ))}
    </div>
  );
}

// ── Grade buttons ─────────────────────────────────────────────────────────────

const GRADE_BUTTONS: { grade: JournalEntry["grade"]; label: string; style: string }[] = [
  { grade: "TP_HIT",       label: "✅ TP",     style: "border-green-700 text-green-400 hover:bg-green-900/30" },
  { grade: "SL_HIT",       label: "❌ SL",     style: "border-red-700 text-red-400 hover:bg-red-900/30" },
  { grade: "MANUAL_CLOSE", label: "⚠️ Manual", style: "border-yellow-700 text-yellow-400 hover:bg-yellow-900/30" },
  { grade: "EXPIRED",      label: "⏭ Expired", style: "border-slate-600 text-slate-500 hover:bg-slate-800" },
];

// ── Trade group card ──────────────────────────────────────────────────────────

function TradeGroupCard({
  group,
  expanded,
  onToggle,
  onGrade,
}: {
  group: TradeGroup;
  expanded: boolean;
  onToggle: () => void;
  onGrade: (group: TradeGroup, grade: JournalEntry["grade"], masterSignalId: string) => Promise<void>;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  // Default master = most recent trigger
  const [masterSignalId, setMasterSignalId] = useState<string>(
    group.entries[group.entries.length - 1].signal_id
  );
  const dirColor = group.direction === "BUY" ? "text-green-400" : "text-red-400";
  const dirBg   = group.direction === "BUY" ? "border-green-800" : "border-red-800";
  const first   = group.entries[0];
  const multi   = group.entries.length > 1;

  async function handleGrade(grade: JournalEntry["grade"]) {
    setBusy(grade);
    try { await onGrade(group, grade, masterSignalId); }
    finally { setBusy(null); }
  }

  return (
    <div className={`bg-slate-950 border rounded-lg overflow-hidden ${dirBg}`}>
      {/* ── Header row — click to expand ── */}
      <button
        onClick={onToggle}
        className="w-full text-left px-3 pt-3 pb-2 flex items-start justify-between gap-2 hover:bg-slate-900/50 transition-colors"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-bold text-white">{group.symbol}</span>
            <span className={`text-xs font-bold uppercase ${dirColor}`}>{group.direction}</span>
            {multi && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-slate-700 text-slate-300">
                ×{group.entries.length} triggers
              </span>
            )}
          </div>
          <div className="text-xs text-slate-500 mt-0.5">{group.strategy ?? "CTI-v1"}</div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <GradeBadge grade={group.grade} />
          <span className="text-slate-500 text-xs">{expanded ? "▲" : "▼"}</span>
        </div>
      </button>

      {/* ── Summary data ── */}
      <div className="px-3 pb-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
        <div className="text-slate-400">Avg Confidence</div>
        <div className="text-white text-right">{Math.round(group.avgConfidence * 100)}%</div>
        <div className="text-slate-400">Entry</div>
        <div className="text-white text-right">{fmtPrice(first.entry_price)}</div>
        <div className="text-slate-400">SL / TP</div>
        <div className="text-white text-right">
          <span className="text-red-400">{fmtPrice(first.stop_loss)}</span>
          {" / "}
          <span className="text-green-400">{fmtPrice(first.take_profit)}</span>
        </div>
        <div className="text-slate-400">R:R</div>
        <div className="text-white text-right">{group.rr != null ? group.rr.toFixed(1) : "—"}</div>
      </div>

      {/* ── Grade buttons ── */}
      <div className="px-3 pb-3 grid grid-cols-2 gap-1 border-t border-slate-800 pt-2">
        {GRADE_BUTTONS.map(({ grade, label, style }) => (
          <button
            key={grade}
            onClick={() => handleGrade(grade)}
            disabled={!!busy}
            className={`text-xs px-2 py-1 rounded border transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${style} ${
              group.grade === grade ? "opacity-100 font-bold ring-1 ring-current" : "opacity-50"
            }`}
          >
            {busy === grade ? "…" : label}
          </button>
        ))}
      </div>

      {/* ── Timestamp ── */}
      <div className="px-3 pb-2 text-xs text-slate-500 border-t border-slate-800 pt-1.5">
        {multi
          ? <>{fmtTime(group.firstTs)} <span className="text-slate-600">→ {fmtTime(group.lastTs)}</span></>
          : fmtTime(group.firstTs)
        }
      </div>

      {/* ── Drill-down: individual triggers ── */}
      {expanded && (
        <div className="border-t border-slate-800 bg-slate-900/50">
          <div className="px-3 py-2 text-xs text-slate-500 font-semibold uppercase tracking-wider">
            Individual Triggers
            {multi && <span className="ml-1 font-normal normal-case text-slate-600">— select master to grade</span>}
          </div>
          {group.entries.map((e, i) => {
            const isMaster = e.signal_id === masterSignalId;
            return (
              <div
                key={e.signal_id}
                className={`px-3 py-2 border-t border-slate-800/60 grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs transition-colors ${
                  isMaster ? "bg-slate-800/40" : ""
                }`}
              >
                <div className="col-span-2 flex items-center justify-between mb-0.5">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name={`master-${group.groupId}`}
                      checked={isMaster}
                      onChange={() => setMasterSignalId(e.signal_id)}
                      className="accent-blue-500"
                    />
                    <span className={isMaster ? "text-slate-200" : "text-slate-400"}>
                      #{i + 1} — {fmtTime(e.signal_timestamp)}
                    </span>
                    {isMaster && <span className="text-blue-400 text-[10px] font-semibold uppercase">master</span>}
                  </label>
                  <GradeBadge grade={e.grade} />
                </div>
                <div className="text-slate-500">Confidence</div>
                <div className="text-white text-right">{Math.round(e.confidence * 100)}%</div>
                <div className="text-slate-500">Entry</div>
                <div className="text-white text-right">{fmtPrice(e.entry_price)}</div>
                <div className="text-slate-500">SL / TP</div>
                <div className="text-white text-right">
                  <span className="text-red-400">{fmtPrice(e.stop_loss)}</span>
                  {" / "}
                  <span className="text-green-400">{fmtPrice(e.take_profit)}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Filter bar ────────────────────────────────────────────────────────────────

type GradeFilter = "ALL" | "PENDING" | "TP_HIT" | "SL_HIT" | "MANUAL_CLOSE" | "EXPIRED";

function FilterBar({
  active,
  onChange,
  counts,
}: {
  active: GradeFilter;
  onChange: (f: GradeFilter) => void;
  counts: Record<string, number>;
}) {
  const filters: { value: GradeFilter; label: string }[] = [
    { value: "ALL",          label: "All" },
    { value: "PENDING",      label: "Pending" },
    { value: "TP_HIT",       label: "TP Hit" },
    { value: "SL_HIT",       label: "SL Hit" },
    { value: "MANUAL_CLOSE", label: "Manual" },
    { value: "EXPIRED",      label: "Expired" },
  ];

  return (
    <div className="flex flex-wrap gap-2 mb-4">
      {filters.map(({ value, label }) => {
        const count = value === "ALL"
          ? Object.values(counts).reduce((s, n) => s + n, 0)
          : (counts[value] ?? 0);
        const isActive = active === value;
        return (
          <button
            key={value}
            onClick={() => onChange(value)}
            className={`text-xs px-3 py-1 rounded-full border transition-colors ${
              isActive
                ? "bg-slate-600 border-slate-500 text-white"
                : "bg-slate-900 border-slate-700 text-slate-400 hover:border-slate-500"
            }`}
          >
            {label} <span className="opacity-60">({count})</span>
          </button>
        );
      })}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function JournalPage() {
  const [entries, setEntries]   = useState<JournalEntry[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const [filter, setFilter]     = useState<GradeFilter>("ALL");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

    // ── Grade only the master signal in a group ──────────────────────────────
  async function handleGradeGroup(group: TradeGroup, grade: JournalEntry["grade"], masterSignalId: string) {
    // Optimistic: update only the master entry
    setEntries(prev => prev.map(e => e.signal_id === masterSignalId ? { ...e, grade } : e));
    const res = await fetch("/api/journal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ signal_id: masterSignalId, grade }),
    });
    if (!res.ok) {
      // Revert on failure
      const fresh = await fetch(`/api/journal?_=${Date.now()}`, { cache: "no-store" });
      if (fresh.ok) setEntries(await fresh.json());
    }
  }

  function toggleExpand(groupId: string) {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(groupId) ? next.delete(groupId) : next.add(groupId);
      return next;
    });
  }

  // ── Data loading ─────────────────────────────────────────────────────────
  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`/api/journal?_=${Date.now()}`, { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setEntries(Array.isArray(data) ? data : []);
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load journal");
      } finally {
        setLoading(false);
      }
    };
    load();
    const id = setInterval(load, 60_000);
    return () => clearInterval(id);
  }, []);

  // ── Compute trade groups from raw entries ────────────────────────────────
  const allGroups = useMemo(() => groupIntoTrades(entries), [entries]);

  const filteredGroups = useMemo(
    () => filter === "ALL" ? allGroups : allGroups.filter(g => g.grade === filter),
    [allGroups, filter]
  );

  const gradeCounts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const g of allGroups) c[g.grade] = (c[g.grade] ?? 0) + 1;
    return c;
  }, [allGroups]);

  // ── Group by CT day using the first signal's timestamp ───────────────────
  const dayGroups = useMemo(() => {
    const map = new Map<string, { label: string; groups: TradeGroup[] }>();
    for (const g of filteredGroups) {
      const key = dateGroupKey(g.firstTs);
      if (!map.has(key)) map.set(key, { label: fmtDateGroup(g.firstTs), groups: [] });
      map.get(key)!.groups.push(g);
    }
    return Array.from(map.entries()).sort((a, b) => b[0].localeCompare(a[0]));
  }, [filteredGroups]);

  const totalSignals = entries.length;
  const totalTrades  = allGroups.length;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="border-b border-slate-800 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/" className="text-slate-500 hover:text-slate-300 text-sm transition-colors">
            ← Dashboard
          </Link>
          <span className="text-slate-700">|</span>
          <span className="text-white font-semibold text-sm">Signal Journal</span>
        </div>
        <span className="text-xs text-slate-600">
          {totalTrades} trades · {totalSignals} triggers (never purged)
        </span>
      </div>

      <main className="px-4 py-6 max-w-5xl mx-auto">
        {loading && (
          <div className="text-slate-500 text-sm text-center py-20">Loading journal…</div>
        )}
        {error && (
          <div className="bg-red-900/20 border border-red-800 rounded-lg p-4 text-red-400 text-sm mb-6">
            {error}
          </div>
        )}
        {!loading && !error && (
          <>
            <StatsBar groups={allGroups} />
            <FilterBar active={filter} onChange={setFilter} counts={gradeCounts} />

            {dayGroups.length === 0 ? (
              <div className="text-slate-500 text-sm text-center py-20">
                {entries.length === 0 ? "No signals recorded yet." : "No trades match this filter."}
              </div>
            ) : (
              <div className="space-y-6">
                {dayGroups.map(([key, { label, groups }]) => (
                  <section key={key}>
                    <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
                      {label}
                    </h2>
                    <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
                      {groups.map(g => (
                        <TradeGroupCard
                          key={g.groupId}
                          group={g}
                          expanded={expanded.has(g.groupId)}
                          onToggle={() => toggleExpand(g.groupId)}
                          onGrade={handleGradeGroup}
                        />
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
