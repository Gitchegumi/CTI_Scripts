"use client";

import { useState, useEffect, useMemo } from "react";
import Link from "next/link";

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

// ── Formatting helpers ────────────────────────────────────────────────────────

function fmtPrice(p: number): string {
  const d = p >= 10 ? 3 : 5;
  return p.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
}

function fmtDateGroup(ts: string): string {
  try {
    return new Date(ts).toLocaleDateString("en-US", {
      weekday: "long",
      month: "long",
      day: "numeric",
      year: "numeric",
      timeZone: "America/Chicago",
    });
  } catch {
    return ts.slice(0, 10);
  }
}

function fmtTime(ts: string): { et: string; ct: string } {
  try {
    const d = new Date(ts);
    const opts: Intl.DateTimeFormatOptions = { hour: "2-digit", minute: "2-digit", hour12: false };
    return {
      et: d.toLocaleString("en-US", { ...opts, timeZone: "America/New_York" }) + " ET",
      ct: d.toLocaleString("en-US", { ...opts, timeZone: "America/Chicago" }) + " CT",
    };
  } catch {
    return { et: ts, ct: ts };
  }
}

function dateGroupKey(ts: string): string {
  try {
    return new Date(ts).toLocaleDateString("en-US", {
      year: "numeric", month: "2-digit", day: "2-digit",
      timeZone: "America/Chicago",
    });
  } catch {
    return ts.slice(0, 10);
  }
}

// ── Grade badge ───────────────────────────────────────────────────────────────

const GRADE_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  TP_HIT:       { bg: "bg-green-900/40 border-green-700",  text: "text-green-400",  label: "✅ TP Hit" },
  SL_HIT:       { bg: "bg-red-900/40 border-red-700",      text: "text-red-400",    label: "❌ SL Hit" },
  MANUAL_CLOSE: { bg: "bg-yellow-900/40 border-yellow-700",text: "text-yellow-400", label: "⚠️ Manual" },
  EXPIRED:      { bg: "bg-slate-800 border-slate-700",     text: "text-slate-500",  label: "⏭ Expired" },
  PENDING:      { bg: "bg-slate-800 border-slate-700",     text: "text-slate-400",  label: "⏳ Pending" },
};

function GradeBadge({ grade }: { grade: string }) {
  const s = GRADE_STYLES[grade] ?? GRADE_STYLES.PENDING;
  return (
    <span className={`text-xs px-2 py-0.5 rounded border font-medium ${s.bg} ${s.text}`}>
      {s.label}
    </span>
  );
}

// ── Stats bar ─────────────────────────────────────────────────────────────────

function StatsBar({ entries }: { entries: JournalEntry[] }) {
  const graded = entries.filter(e => e.grade !== "PENDING" && e.grade !== "EXPIRED");
  const tp = graded.filter(e => e.grade === "TP_HIT").length;
  const sl = graded.filter(e => e.grade === "SL_HIT").length;
  const manual = graded.filter(e => e.grade === "MANUAL_CLOSE").length;
  const winRate = graded.length > 0 ? Math.round((tp / graded.length) * 100) : null;

  const avgRR = (() => {
    const valid = graded.filter(e => e.rr !== null && e.rr !== undefined);
    if (!valid.length) return null;
    return (valid.reduce((s, e) => s + (e.rr ?? 0), 0) / valid.length).toFixed(1);
  })();

  const avgConf = (() => {
    if (!graded.length) return null;
    return Math.round(graded.reduce((s, e) => s + e.confidence, 0) / graded.length * 100);
  })();

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
      {[
        { label: "Win Rate", value: winRate !== null ? `${winRate}%` : "—", sub: `${tp}W / ${sl}L / ${manual}M` },
        { label: "Graded Signals", value: graded.length, sub: `${entries.length} total` },
        { label: "Avg R:R", value: avgRR ?? "—", sub: "graded only" },
        { label: "Avg Confidence", value: avgConf !== null ? `${avgConf}%` : "—", sub: "graded only" },
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

// ── Signal card ───────────────────────────────────────────────────────────────

const GRADE_BUTTONS: { grade: JournalEntry["grade"]; label: string; style: string }[] = [
  { grade: "TP_HIT",       label: "✅ TP",      style: "border-green-700 text-green-400 hover:bg-green-900/30" },
  { grade: "SL_HIT",       label: "❌ SL",      style: "border-red-700 text-red-400 hover:bg-red-900/30" },
  { grade: "MANUAL_CLOSE", label: "⚠️ Manual",  style: "border-yellow-700 text-yellow-400 hover:bg-yellow-900/30" },
  { grade: "EXPIRED",      label: "⏭ Expired",  style: "border-slate-600 text-slate-500 hover:bg-slate-800" },
];

function SignalCard({
  entry,
  onGrade,
}: {
  entry: JournalEntry;
  onGrade: (signalId: string, grade: JournalEntry["grade"]) => Promise<void>;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const dirColor = entry.direction === "BUY" ? "text-green-400" : "text-red-400";
  const dirBg = entry.direction === "BUY" ? "border-green-800" : "border-red-800";
  const t = fmtTime(entry.signal_timestamp);

  async function handleGrade(grade: JournalEntry["grade"]) {
    setBusy(grade);
    try {
      await onGrade(entry.signal_id, grade);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className={`bg-slate-950 border rounded-lg p-3 space-y-2 ${dirBg}`}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <span className="font-bold text-white">{entry.symbol}</span>
          <span className={`ml-2 text-xs font-bold uppercase ${dirColor}`}>{entry.direction}</span>
        </div>
        <GradeBadge grade={entry.grade} />
      </div>

      <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
        <div className="text-slate-400">Strategy</div>
        <div className="text-white text-right">{entry.strategy ?? "CTI-v1"}</div>
        <div className="text-slate-400">Confidence</div>
        <div className="text-white text-right">{Math.round(entry.confidence * 100)}%</div>
        <div className="text-slate-400">Entry</div>
        <div className="text-white text-right">{fmtPrice(entry.entry_price)}</div>
        <div className="text-slate-400">SL / TP</div>
        <div className="text-white text-right">
          <span className="text-red-400">{fmtPrice(entry.stop_loss)}</span>
          {" / "}
          <span className="text-green-400">{fmtPrice(entry.take_profit)}</span>
        </div>
        <div className="text-slate-400">R:R</div>
        <div className="text-white text-right">{entry.rr !== null ? entry.rr?.toFixed(1) : "—"}</div>
        <div className="text-slate-400">Lot</div>
        <div className="text-white text-right">{entry.lot_size}</div>
      </div>

      {/* Grade buttons — always shown so any grade can be changed */}
      <div className="grid grid-cols-2 gap-1 border-t border-slate-800 pt-2">
        {GRADE_BUTTONS.map(({ grade, label, style }) => (
          <button
            key={grade}
            onClick={() => handleGrade(grade)}
            disabled={!!busy}
            className={`text-xs px-2 py-1 rounded border transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${style} ${
              entry.grade === grade ? "opacity-100 font-bold ring-1 ring-current" : "opacity-50"
            }`}
          >
            {busy === grade ? "…" : label}
          </button>
        ))}
      </div>

      <div className="text-xs text-slate-500 border-t border-slate-800 pt-1.5 space-y-0.5">
        <div>{t.et}</div>
        <div>{t.ct}</div>
      </div>

      {entry.notes && (
        <div className="text-xs text-slate-400 italic border-t border-slate-800 pt-1.5">
          {entry.notes}
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
        const count = value === "ALL" ? Object.values(counts).reduce((s, n) => s + n, 0) : (counts[value] ?? 0);
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
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<GradeFilter>("ALL");

  async function handleGrade(signalId: string, grade: JournalEntry["grade"]) {
    // Optimistic update
    setEntries(prev =>
      prev.map(e => e.signal_id === signalId ? { ...e, grade } : e)
    );
    const res = await fetch("/api/journal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ signal_id: signalId, grade }),
    });
    if (!res.ok) {
      // Revert on failure by reloading
      const fresh = await fetch(`/api/journal?_=${Date.now()}`, { cache: "no-store" });
      if (fresh.ok) setEntries(await fresh.json());
    }
  }

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

  const filtered = useMemo(
    () => (filter === "ALL" ? entries : entries.filter(e => e.grade === filter)),
    [entries, filter]
  );

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const e of entries) c[e.grade] = (c[e.grade] ?? 0) + 1;
    return c;
  }, [entries]);

  // Group by CT day
  const groups = useMemo(() => {
    const map = new Map<string, { label: string; entries: JournalEntry[] }>();
    for (const e of filtered) {
      const key = dateGroupKey(e.signal_timestamp);
      if (!map.has(key)) {
        map.set(key, { label: fmtDateGroup(e.signal_timestamp), entries: [] });
      }
      map.get(key)!.entries.push(e);
    }
    return Array.from(map.entries()).sort((a, b) => b[0].localeCompare(a[0]));
  }, [filtered]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Header */}
      <div className="border-b border-slate-800 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/" className="text-slate-500 hover:text-slate-300 text-sm transition-colors">
            ← Dashboard
          </Link>
          <span className="text-slate-700">|</span>
          <span className="text-white font-semibold text-sm">Signal Journal</span>
        </div>
        <span className="text-xs text-slate-600">{entries.length} signals total (never purged)</span>
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
            <StatsBar entries={entries} />
            <FilterBar active={filter} onChange={setFilter} counts={counts} />

            {groups.length === 0 ? (
              <div className="text-slate-500 text-sm text-center py-20">
                {entries.length === 0 ? "No signals recorded yet." : "No signals match this filter."}
              </div>
            ) : (
              <div className="space-y-6">
                {groups.map(([key, { label, entries: dayEntries }]) => (
                  <section key={key}>
                    <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
                      {label}
                    </h2>
                    <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
                      {dayEntries.map(e => (
                        <SignalCard key={e.signal_id} entry={e} onGrade={handleGrade} />
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
