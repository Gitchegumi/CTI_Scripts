"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { readApiError } from "@/lib/api";
import { PageSubNav } from "@/components/PageSubNav";
import { isBullishDirection, directionColorClasses } from "@/lib/direction";
import { statsUseLabel, reachedTargetLabel } from "@/lib/journalLabels";

// ── Types ─────────────────────────────────────────────────────────────────────

interface JournalEntry {
  signal_id: string;
  symbol: string;
  direction: "BUY" | "SELL" | "UPTREND" | "DOWNTREND" | "LONG" | "SHORT" | string;
  strategy: string;
  confidence: number;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  lot_size: number;
  atr: number;
  rr: number | null;
  signal_timestamp: string;
  status?: "pending" | "open_simulated" | "closed" | "ambiguous" | "invalidated" | "expired" | string;
  outcome?: "tp" | "sl" | "ambiguous" | "expired" | "manually_closed" | "invalidated_by_prime" | "invalidated_by_system" | "none" | string;
  outcome_source?: string | null;
  exit_time?: string | null;
  exit_price?: number | null;
  outcome_checked_at?: string | null;
  ambiguous_reason?: string | null;
  manually_overridden?: boolean;
  manual_override_reason?: string | null;
  grade: TradeGrade | "MANUAL_CLOSE" | "EXPIRED";
  trade_grade?: TradeGrade;
  setup_group_id?: string;
  is_duplicate_setup?: boolean;
  entry_valid_at_signal?: boolean | null;
  entry_miss_distance?: { absolute?: number | null; atr_normalized?: number | null };
  signal_age_bars?: number;
  late_signal?: boolean;
  usable_for_strategy_stats?: boolean;
  stats_exclusion_reason?: string | null;
  prime_active?: boolean;
  prime_suppressed_signal_count?: number;
  prime_suppressed_last_at?: string | null;
  prime_closed_reason?: string | null;
  prime_closed_at?: string | null;
  prime_close_ambiguous?: boolean;
  prime_suppressed_same_direction_count?: number;
  prime_suppressed_opposite_direction_count?: number;
  lifecycle_role?: string | null;
  trade_id?: string | null;
  management_accepted?: boolean | null;
  management_reason?: string | null;
  management_rejection_reason?: string | null;
  old_stop_loss?: number | null;
  new_stop_loss?: number | null;
  old_take_profit?: number | null;
  new_take_profit?: number | null;
  current_stop_loss?: number | null;
  current_take_profit?: number | null;
  managed_exit_reason?: string | null;
  managed_result_category?: string | null;
  captured_r?: number | null;
  grade_timestamp: string | null;
  notes: string;
  discord_msg_id: string | null;
}

interface TradeGroup {
  groupId: string;           // signal_id of first entry — stable key
  symbol: string;
  direction: "BUY" | "SELL" | "UPTREND" | "DOWNTREND" | "LONG" | "SHORT" | string;
  strategy: string;
  entries: JournalEntry[];   // oldest → newest
  avgConfidence: number;
  grade: TradeGrade | "MANUAL_CLOSE" | "EXPIRED";
  firstTs: string;
  lastTs: string;
  rr: number | null;         // from the first entry
}

type TradeGrade = "PENDING" | "TP_HIT" | "SL_HIT" | "BE" | "MISSED_ENTRY" | "LATE_SIGNAL" | "DUPLICATE" | "INVALID";
type GradeFilter = "ALL" | TradeGrade | "MANUAL_CLOSE" | "EXPIRED";

function displayGrade(entry: JournalEntry): TradeGroup["grade"] {
  return entry.trade_grade ?? entry.grade ?? "PENDING";
}

function normalizedTradeGrade(grade: JournalEntry["grade"]): TradeGrade {
  if (grade === "MANUAL_CLOSE") return "BE";
  if (grade === "EXPIRED") return "MISSED_ENTRY";
  return grade;
}

function suppressedPrimeLabel(entry: JournalEntry): string | null {
  const total = entry.prime_suppressed_signal_count ?? 0;
  if (total <= 0) return null;
  const opposite = entry.prime_suppressed_opposite_direction_count ?? 0;
  if (opposite > 0) return `${total} total, ${opposite} opposite direction`;
  return String(total);
}

function titleCaseToken(value?: string | null): string {
  if (!value) return "None";
  return value
    .split("_")
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function outcomeLabel(entry: JournalEntry): string | null {
  const status = entry.status ? statsUseLabel(entry.status) : null;
  const outcome = entry.outcome && entry.outcome !== "none" ? statsUseLabel(entry.outcome) : null;
  if (!status && !outcome) return null;
  return outcome ? `${status ?? "Open"} / ${outcome}` : status;
}

function sourceLabel(source?: string | null): string | null {
  if (!source) return null;
  if (source === "live_price_observation_1s") return "Auto 1s";
  if (source === "live_price_observation_1s_mid") return "Auto 1s mid";
  if (source === "oanda_pricing_stream") return "Stream";
  if (source === "historical_candle") return "Candle";
  if (source === "manual") return "Manual";
  if (source === "system_prime_filter") return "Prime filter";
  return statsUseLabel(source);
}

// ── Grouping logic ────────────────────────────────────────────────────────────

function isSameTrade(prev: JournalEntry, curr: JournalEntry): boolean {
  const e = curr.entry_price;
  if (isBullishDirection(prev.direction)) {
    // Still between the SL and TP of the previous signal → same trade
    return e > prev.stop_loss && e < prev.take_profit;
  } else {
    // SELL / DOWNTREND: SL is above entry, TP is below entry
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
    const explicitGroup = entry.setup_group_id
      ? groups.find(g => g.groupId === entry.setup_group_id)
      : undefined;
    if (explicitGroup) {
      explicitGroup.entries.push(entry);
      explicitGroup.lastTs = entry.signal_timestamp;
      explicitGroup.avgConfidence =
        explicitGroup.entries.reduce((s, e) => s + e.confidence, 0) / explicitGroup.entries.length;
      if (displayGrade(entry) !== "PENDING") explicitGroup.grade = displayGrade(entry);
      continue;
    }

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
        if (displayGrade(entry) !== "PENDING") lastGroup.grade = displayGrade(entry);
        continue;
      }
    }

    groups.push({
      groupId: entry.setup_group_id ?? entry.signal_id,
      symbol: entry.symbol,
      direction: entry.direction,
      strategy: entry.strategy ?? "CTI-v1",
      entries: [entry],
      avgConfidence: entry.confidence,
      grade: displayGrade(entry),
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

function toExportTimestamp(value: string): string | null {
  if (!value) return null;
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) throw new Error("Choose a valid export date/time range.");
  return timestamp.toISOString();
}

function filenameFromDisposition(disposition: string | null): string | null {
  if (!disposition) return null;
  const utf8 = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8?.[1]) return decodeURIComponent(utf8[1].replace(/"/g, ""));
  const quoted = disposition.match(/filename="([^"]+)"/i);
  if (quoted?.[1]) return quoted[1];
  const plain = disposition.match(/filename=([^;]+)/i);
  return plain?.[1]?.trim().replace(/^"|"$/g, "") ?? null;
}

function fallbackExportFilename(filter: GradeFilter, start: string, end: string): string {
  if (start && end) return `signal-journal-${start.slice(0, 10)}-to-${end.slice(0, 10)}.csv`;
  if (start || end) return "signal-journal-selected-range.csv";
  return `signal-journal-${filter.toLowerCase()}-${new Date().toISOString().slice(0, 10)}.csv`;
}

// ── Grade badge ───────────────────────────────────────────────────────────────

const GRADE_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  BE:           { bg: "bg-blue-900/40 border-blue-700",     text: "text-blue-300",   label: "BE" },
  MISSED_ENTRY: { bg: "bg-orange-900/40 border-orange-700", text: "text-orange-300", label: "Missed" },
  LATE_SIGNAL:  { bg: "bg-orange-900/40 border-orange-700", text: "text-orange-300", label: "Late" },
  DUPLICATE:    { bg: "bg-slate-800 border-slate-600",      text: "text-slate-300",  label: "Duplicate" },
  INVALID:      { bg: "bg-zinc-900 border-zinc-600",        text: "text-zinc-300",   label: "Invalid" },
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
  const graded = groups.filter(g => !["PENDING", "EXPIRED", "DUPLICATE", "MISSED_ENTRY", "LATE_SIGNAL", "INVALID"].includes(g.grade));
  const tp = graded.filter(g => g.grade === "TP_HIT").length;
  const sl = graded.filter(g => g.grade === "SL_HIT").length;
  const manual = graded.filter(g => g.grade === "MANUAL_CLOSE" || g.grade === "BE").length;
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
        <div key={label} className="bg-card border border-border rounded-lg px-4 py-3">
          <div className="text-muted-foreground text-xs">{label}</div>
          <div className="text-foreground text-xl font-semibold mt-0.5">{value}</div>
          <div className="text-muted-foreground/70 text-xs mt-0.5">{sub}</div>
        </div>
      ))}
    </div>
  );
}

// ── Grade buttons ─────────────────────────────────────────────────────────────

const GRADE_BUTTONS: { grade: JournalEntry["grade"]; label: string; style: string }[] = [
  { grade: "BE",           label: "BE",        style: "border-blue-700 text-blue-300 hover:bg-blue-900/30" },
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
  onNotes,
  onReset,
  onInvalidate,
}: {
  group: TradeGroup;
  expanded: boolean;
  onToggle: () => void;
  onGrade: (group: TradeGroup, grade: JournalEntry["grade"], masterSignalId: string) => Promise<void>;
  onNotes: (group: TradeGroup, notes: string, masterSignalId: string) => Promise<void>;
  onReset: (group: TradeGroup, masterSignalId: string) => Promise<void>;
  onInvalidate: (group: TradeGroup, masterSignalId: string) => Promise<void>;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [noteBusy] = useState(false);
  const [noteText, setNoteText] = useState(
    group.entries.find(e => e.notes)?.notes ?? ""
  );
  // Default master = most recent trigger
  const [masterSignalId, setMasterSignalId] = useState<string>(
    group.entries[group.entries.length - 1].signal_id
  );
  const { text: dirColor, border: dirBg } = directionColorClasses(group.direction);
  const first   = group.entries[0];
  const multi   = group.entries.length > 1;

  async function handleGrade(grade: JournalEntry["grade"]) {
    setBusy(grade);
    try { await onGrade(group, grade, masterSignalId); }
    finally { setBusy(null); }
  }

  async function handleReset() {
    setBusy("PENDING");
    try { await onReset(group, masterSignalId); }
    finally { setBusy(null); }
  }

  async function handleInvalidate() {
    setBusy("INVALID");
    try { await onInvalidate(group, masterSignalId); }
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
          <div className="text-xs text-muted-foreground mt-0.5">{group.strategy ?? "CTI-v1"}</div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <GradeBadge grade={group.grade} />
          <span className="text-muted-foreground text-xs">{expanded ? "▲" : "▼"}</span>
        </div>
      </button>

      {/* ── Summary data ── */}
      {(() => {
        const master = group.entries.find(e => e.signal_id === masterSignalId) ?? first;
        return (
          <div className="px-3 pb-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs [overflow-wrap:anywhere]">
            <div className="text-muted-foreground">Avg Confidence</div>
            <div className="text-white text-right">{Math.round(group.avgConfidence * 100)}%</div>
            <div className="text-muted-foreground">Entry</div>
            <div className="text-white text-right">{fmtPrice(master.entry_price)}</div>
            <div className="text-muted-foreground">SL / TP</div>
            <div className="text-white text-right">
              <span className="text-red-400">{fmtPrice(master.stop_loss)}</span>
              {" / "}
              <span className="text-green-400">{fmtPrice(master.take_profit)}</span>
            </div>
            <div className="text-muted-foreground">R:R</div>
            <div className="text-white text-right">{master.rr != null ? master.rr.toFixed(1) : "N/A"}</div>
            {master.lifecycle_role && master.lifecycle_role !== "legacy_signal" && (
              <>
                <div className="text-muted-foreground">Lifecycle</div>
                <div className="text-cyan-200 text-right">{statsUseLabel(master.lifecycle_role)}</div>
              </>
            )}
            {(master.current_stop_loss != null || master.current_take_profit != null) && (
              <>
                <div className="text-muted-foreground">Managed SL / TP</div>
                <div className="text-white text-right">
                  <span className="text-red-300">{master.current_stop_loss != null ? fmtPrice(master.current_stop_loss) : "N/A"}</span>
                  {" / "}
                  <span className="text-green-300">{master.current_take_profit != null ? fmtPrice(master.current_take_profit) : "N/A"}</span>
                </div>
              </>
            )}
            {master.lifecycle_role === "management" && (
              <>
                <div className="text-muted-foreground">Management</div>
                <div className={master.management_accepted ? "text-green-300 text-right" : "text-orange-300 text-right break-words whitespace-normal"}>
                  {master.management_accepted ? "Accepted" : statsUseLabel(master.management_rejection_reason || master.management_reason || "Rejected")}
                </div>
              </>
            )}
            {(master.old_stop_loss != null || master.new_stop_loss != null || master.old_take_profit != null || master.new_take_profit != null) && (
              <>
                <div className="text-muted-foreground">SL/TP Change</div>
                <div className="text-white text-right">
                  {master.old_stop_loss != null ? fmtPrice(master.old_stop_loss) : "N/A"} {"->"} {master.new_stop_loss != null ? fmtPrice(master.new_stop_loss) : "N/A"}
                  {" | "}
                  {master.old_take_profit != null ? fmtPrice(master.old_take_profit) : "N/A"} {"->"} {master.new_take_profit != null ? fmtPrice(master.new_take_profit) : "N/A"}
                </div>
              </>
            )}
            <div className="text-muted-foreground">Entry Valid</div>
            <div className="text-white text-right">
              {master.entry_valid_at_signal == null ? "Unknown" : master.entry_valid_at_signal ? "Yes" : "No"}
            </div>
            <div className="text-muted-foreground">Stats Use</div>
            <div className={`${master.usable_for_strategy_stats ? "text-green-300" : "text-orange-300"} text-right break-words whitespace-normal`}>
              {master.usable_for_strategy_stats ? "Included" : statsUseLabel(master.stats_exclusion_reason ?? "Excluded")}
            </div>
            {suppressedPrimeLabel(master) && (
              <>
                <div className="text-muted-foreground">Suppressed by this prime</div>
                <div className="text-cyan-200 text-right">{suppressedPrimeLabel(master)}</div>
              </>
            )}
            {outcomeLabel(master) && (
              <>
                <div className="text-muted-foreground">Outcome</div>
                <div className={master.status === "ambiguous" ? "text-amber-300 text-right" : "text-white text-right"}>
                  {outcomeLabel(master)}
                </div>
              </>
            )}
            {reachedTargetLabel(master) && (
              <>
                <div className="text-muted-foreground">Reached Target</div>
                <div className="text-white text-right">
                  {reachedTargetLabel(master)}
                </div>
              </>
            )}
            {master.managed_result_category && (
              <>
                <div className="text-muted-foreground">Managed Result</div>
                <div className="text-white text-right break-words whitespace-normal">
                  {statsUseLabel(master.managed_result_category)}
                  {master.captured_r != null ? ` (${master.captured_r.toFixed(2)}R)` : ""}
                </div>
              </>
            )}
            {sourceLabel(master.outcome_source) && (
              <>
                <div className="text-muted-foreground">Source</div>
                <div className="text-slate-200 text-right">{sourceLabel(master.outcome_source)}</div>
              </>
            )}
            {master.exit_time && (
              <>
                <div className="text-muted-foreground">Exit</div>
                <div className="text-white text-right">
                  {master.exit_price != null ? fmtPrice(master.exit_price) : "N/A"} <span className="text-muted-foreground">{fmtTime(master.exit_time)}</span>
                </div>
              </>
            )}
            {master.manually_overridden && (
              <>
                <div className="text-muted-foreground">Manual Override</div>
                <div className="text-blue-200 text-right">{master.manual_override_reason || "Yes"}</div>
              </>
            )}
            {master.ambiguous_reason && (
              <>
                <div className="text-muted-foreground">Ambiguous</div>
                <div className="text-amber-300 text-right">{statsUseLabel(master.ambiguous_reason)}</div>
              </>
            )}
          </div>
        );
      })()}

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
        {group.grade !== "PENDING" && (
          <button
            onClick={handleReset}
            disabled={!!busy}
            className="col-span-2 text-xs px-2 py-1 rounded border border-blue-700 text-blue-300 hover:bg-blue-900/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {busy === "PENDING" ? "..." : "Reset to Pending"}
          </button>
        )}
        {group.grade !== "INVALID" && (
          <button
            onClick={handleInvalidate}
            disabled={!!busy}
            className="col-span-2 text-xs px-2 py-1 rounded border border-zinc-600 text-zinc-300 hover:bg-zinc-900/40 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {busy === "INVALID" ? "..." : "Mark Invalid"}
          </button>
        )}
      </div>

      {/* ── Notes ── */}
      <div className="px-3 pb-2 border-t border-slate-800 pt-1.5">
        <div className="text-xs text-muted-foreground mb-1">Notes</div>
        <div className="flex items-start gap-2">
          <textarea
            className="flex-1 bg-card border border-border rounded px-2 py-1 text-xs text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:border-ring resize-none"
            rows={2}
            placeholder="Add notes..."
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            onBlur={() => {
              const existing = group.entries.find(e => e.notes)?.notes ?? "";
              if (noteText !== existing) {
                onNotes(group, noteText, masterSignalId);
              }
            }}
            disabled={noteBusy}
          />
          {noteBusy && (
            <span className="text-muted-foreground text-[10px]">…</span>
          )}
        </div>
      </div>

      {/* ── Timestamp ── */}
      <div className="px-3 pb-2 text-xs text-muted-foreground border-t border-border pt-1.5">
        {multi
          ? <>{fmtTime(group.firstTs)} <span className="text-muted-foreground/70">→ {fmtTime(group.lastTs)}</span></>
          : fmtTime(group.firstTs)
        }
      </div>

      {/* ── Drill-down: individual triggers ── */}
      {expanded && (
        <div className="border-t border-slate-800 bg-slate-900/50">
          <div className="px-3 py-2 text-xs text-muted-foreground font-semibold uppercase tracking-wider">
            Individual Triggers
            {multi && <span className="ml-1 font-normal normal-case text-muted-foreground/70">— select master to grade</span>}
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
                    <span className={isMaster ? "text-foreground" : "text-muted-foreground"}>
                      #{i + 1} — {fmtTime(e.signal_timestamp)}
                    </span>
                    {isMaster && <span className="text-blue-400 text-[10px] font-semibold uppercase">master</span>}
                  </label>
                  <GradeBadge grade={displayGrade(e)} />
                </div>
                <div className="text-muted-foreground">Confidence</div>
                <div className="text-white text-right">{Math.round(e.confidence * 100)}%</div>
                <div className="text-muted-foreground">Entry</div>
                <div className="text-white text-right">{fmtPrice(e.entry_price)}</div>
                <div className="text-muted-foreground">SL / TP</div>
                <div className="text-white text-right">
                  <span className="text-red-400">{fmtPrice(e.stop_loss)}</span>
                  {" / "}
                  <span className="text-green-400">{fmtPrice(e.take_profit)}</span>
                </div>
                {outcomeLabel(e) && (
                  <>
                    <div className="text-muted-foreground">Outcome</div>
                    <div className={e.status === "ambiguous" ? "text-amber-300 text-right" : "text-white text-right"}>
                      {outcomeLabel(e)}
                    </div>
                  </>
                )}
                {e.exit_price != null && (
                  <>
                    <div className="text-muted-foreground">Exit</div>
                    <div className="text-white text-right">{fmtPrice(e.exit_price)}</div>
                  </>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Filter bar ────────────────────────────────────────────────────────────────

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
    { value: "BE",           label: "BE" },
    { value: "DUPLICATE",    label: "Duplicate" },
    { value: "MISSED_ENTRY", label: "Missed" },
    { value: "LATE_SIGNAL",  label: "Late" },
    { value: "INVALID",      label: "Invalid" },
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
                ? "bg-secondary border-input text-foreground"
                : "bg-card border-border text-muted-foreground hover:border-input hover:text-foreground"
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
  const [exportMessage, setExportMessage] = useState<{ tone: "info" | "error"; text: string } | null>(null);
  const [filter, setFilter]     = useState<GradeFilter>("ALL");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [exporting, setExporting] = useState(false);
  const [purging, setPurging] = useState(false);
  const [exportStart, setExportStart] = useState("");
  const [exportEnd, setExportEnd] = useState("");

  const loadJournal = useCallback(async () => {
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
  }, []);

    // ── Notes update ─────────────────────────────────────────────────────────
  async function handleNotesGroup(group: TradeGroup, notes: string, masterSignalId: string) {
    // Optimistic: update the master entry locally
    setEntries(prev => prev.map(e => e.signal_id === masterSignalId ? { ...e, notes } : e));
    const res = await fetch("/api/journal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ signal_id: masterSignalId, notes }),
    });
    if (!res.ok) {
      // Revert on failure
      const fresh = await fetch(`/api/journal?_=${Date.now()}`, { cache: "no-store" });
      if (fresh.ok) setEntries(await fresh.json());
    }
  }
  async function handleGradeGroup(group: TradeGroup, grade: JournalEntry["grade"], masterSignalId: string) {
    // Optimistic: update only the master entry
    setEntries(prev => prev.map(e => e.signal_id === masterSignalId ? { ...e, grade, trade_grade: normalizedTradeGrade(grade) } : e));
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

  async function handleInvalidateGroup(group: TradeGroup, masterSignalId: string) {
    setEntries(prev => prev.map(e => e.signal_id === masterSignalId ? {
      ...e,
      grade: "INVALID",
      trade_grade: "INVALID",
      usable_for_strategy_stats: false,
      stats_exclusion_reason: "manual_invalidated",
    } : e));
    const res = await fetch("/api/journal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ signal_id: masterSignalId, invalidate: true }),
    });
    if (!res.ok) {
      await loadJournal();
    }
  }

  async function handleResetGroup(group: TradeGroup, masterSignalId: string) {
    setEntries(prev => prev.map(e => e.signal_id === masterSignalId ? { ...e, grade: "PENDING", trade_grade: "PENDING", grade_timestamp: null } : e));
    const res = await fetch("/api/journal/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ signal_id: masterSignalId }),
    });
    if (!res.ok) {
      await loadJournal();
    }
  }

  function toggleExpand(groupId: string) {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(groupId)) next.delete(groupId);
      else next.add(groupId);
      return next;
    });
  }

  // ── Data loading ─────────────────────────────────────────────────────────
  useEffect(() => {
    const first = window.setTimeout(() => { void loadJournal(); }, 0);
    const id = setInterval(loadJournal, 60_000);
    return () => {
      window.clearTimeout(first);
      clearInterval(id);
    };
  }, [loadJournal]);

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

  async function exportJournal() {
    setExporting(true);
    setExportMessage(null);
    try {
      if (exportStart && exportEnd && new Date(exportStart) > new Date(exportEnd)) {
        throw new Error("Export start must be before export end.");
      }
      const params = new URLSearchParams();
      if (filter !== "ALL") params.set("grade", filter);
      const start = toExportTimestamp(exportStart);
      const end = toExportTimestamp(exportEnd);
      if (start) params.set("start", start);
      if (end) params.set("end", end);
      const qs = params.toString() ? `?${params.toString()}` : "";
      const res = await fetch(`/api/journal/export${qs}`, { cache: "no-store" });
      if (!res.ok) throw new Error(await readApiError(res));
      const blob = await res.blob();
      if (blob.size === 0) throw new Error("No Signal Journal records match the selected export range.");
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filenameFromDisposition(res.headers.get("Content-Disposition"))
        ?? fallbackExportFilename(filter, exportStart, exportEnd);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
      setExportMessage({ tone: "info", text: `Downloaded ${link.download}.` });
    } catch (e) {
      setExportMessage({ tone: "error", text: e instanceof Error ? e.message : "Failed to export journal" });
    } finally {
      setExporting(false);
    }
  }

  async function purgeJournal() {
    const scope = filter === "ALL" ? "all signal journal entries" : `${filter.toLowerCase()} signal journal entries`;
    if (!window.confirm(`Purge ${scope}? This cannot be undone.`)) return;
    setPurging(true);
    try {
      const qs = filter === "ALL" ? "" : `?grade=${encodeURIComponent(filter)}`;
      const res = await fetch(`/api/journal${qs}`, { method: "DELETE" });
      if (!res.ok) throw new Error(await readApiError(res));
      await loadJournal();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to purge journal");
    } finally {
      setPurging(false);
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <PageSubNav
        currentPage="/journal"
        actions={
          <>
            <span className="text-xs text-muted-foreground/70">
              {totalTrades} trades · {totalSignals} triggers
            </span>
            <label className="flex items-center gap-1 text-xs text-muted-foreground">
              <span>Start</span>
              <input
                type="datetime-local"
                value={exportStart}
                onChange={(event) => setExportStart(event.target.value)}
                className="w-40 rounded border border-border bg-card px-2 py-1 text-xs text-foreground focus:border-ring focus:outline-none [color-scheme:dark]"
              />
            </label>
            <label className="flex items-center gap-1 text-xs text-muted-foreground">
              <span>End</span>
              <input
                type="datetime-local"
                value={exportEnd}
                onChange={(event) => setExportEnd(event.target.value)}
                className="w-40 rounded border border-border bg-card px-2 py-1 text-xs text-foreground focus:border-ring focus:outline-none [color-scheme:dark]"
              />
            </label>
            <button
              onClick={exportJournal}
              disabled={exporting}
              className="text-xs px-3 py-1 rounded bg-secondary hover:bg-secondary/80 disabled:opacity-50 text-secondary-foreground transition-colors"
            >
              {exporting ? "Exporting..." : "Export CSV"}
            </button>
            <button
              onClick={purgeJournal}
              disabled={purging || entries.length === 0}
              className="text-xs px-3 py-1 rounded bg-destructive/60 hover:bg-destructive/80 disabled:opacity-50 text-destructive-foreground transition-colors"
            >
              {purging ? "Purging..." : "Purge"}
            </button>
          </>
        }
      />

      <main className="px-4 py-6 max-w-5xl mx-auto">
        {loading && (
          <div className="text-muted-foreground text-sm text-center py-20">Loading journal…</div>
        )}
        {error && (
          <div className="bg-red-900/20 border border-red-800 rounded-lg p-4 text-red-400 text-sm mb-6">
            {error}
          </div>
        )}
        {exportMessage && (
          <div className={`border rounded-lg p-4 text-sm mb-6 ${
            exportMessage.tone === "error"
              ? "bg-amber-900/20 border-amber-800 text-amber-300"
              : "bg-blue-900/20 border-blue-800 text-blue-300"
          }`}>
            {exportMessage.text}
          </div>
        )}
        {!loading && !error && (
          <>
            <StatsBar groups={allGroups} />
            <FilterBar active={filter} onChange={setFilter} counts={gradeCounts} />

            {dayGroups.length === 0 ? (
              <div className="text-muted-foreground text-sm text-center py-20">
                {entries.length === 0 ? "No signals recorded yet." : "No trades match this filter."}
              </div>
            ) : (
              <div className="space-y-6">
                {dayGroups.map(([key, { label, groups }]) => (
                  <section key={key}>
                    <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
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
                          onNotes={handleNotesGroup}
                          onReset={handleResetGroup}
                          onInvalidate={handleInvalidateGroup}
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
