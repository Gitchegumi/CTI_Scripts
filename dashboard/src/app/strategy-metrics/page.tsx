"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { exportStrategyMetrics, getCriteriaList, getCriterionDetail } from "@/lib/api";
import { useStrategyMetricsComparison, useStrategyMetricsSummary } from "@/hooks/useData";
import type {
  CriterionDetail,
  StrategyBlockerSummary,
  StrategyCriteriaList,
  StrategyMetricOpportunity,
  StrategyMetricsSummary,
} from "@/types";

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function defaultStart(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return isoDate(d);
}

function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

// ── Utility UI primitives ────────────────────────────────────────────────────

function LoadingBar({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 py-4 text-sm text-slate-400">
      <div className="h-1 w-24 animate-pulse rounded-full bg-slate-800" />
      <span>{label}…</span>
    </div>
  );
}

function SectionHeader({ id, title, badge }: { id?: string; title: string; badge?: string | number }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <h2 id={id} className="text-sm font-semibold text-slate-200 uppercase tracking-wider">{title}</h2>
      {badge !== undefined && (
        <span className="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full">{badge}</span>
      )}
    </div>
  );
}

function StatCard({ label, value, sub, accent }: {
  label: string; value: string | number; sub?: string; accent?: "green" | "red" | "blue" | "yellow" | "purple";
}) {
  const colors: Record<string, string> = {
    green: "border-green-900 bg-green-950/30 text-green-300",
    red: "border-red-900 bg-red-950/30 text-red-300",
    blue: "border-blue-900 bg-blue-950/30 text-blue-300",
    yellow: "border-yellow-900 bg-yellow-950/30 text-yellow-300",
    purple: "border-purple-900 bg-purple-950/30 text-purple-300",
  };
  const cls = accent ? colors[accent] : "border-slate-800 bg-slate-950 text-white";
  return (
    <div className={`border px-3 py-2 rounded ${cls}`}>
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-xl font-semibold">{value}</div>
      {sub && <div className="text-xs text-slate-600 mt-0.5">{sub}</div>}
    </div>
  );
}

// ── Pipeline funnel ─────────────────────────────────────────────────────────

function PipelineFunnel({ funnel }: { funnel: Record<string, number> }) {
  if (!funnel || Object.keys(funnel).length === 0) return null;
  const stages = [
    { key: "total_evaluated", label: "Evaluated" },
    { key: "trend_candidate_found", label: "Trend found" },
    { key: "signal_data_complete", label: "Data complete" },
    { key: "candle_close_gate_passed", label: "Candle gate" },
    { key: "signal_rules_evaluated", label: "Rules eval'd" },
    { key: "signal_emitted", label: "Emitted", accent: "green" },
    { key: "signal_rejected", label: "Rejected", accent: "red" },
  ];
  const max = funnel["total_evaluated"] || 1;
  return (
    <div className="space-y-1">
      {stages.map(({ key, label, accent }) => {
        const count = funnel[key] ?? 0;
        const pct2 = Math.round((count / max) * 100);
        const colorCls = accent === "green" ? "bg-green-700" : accent === "red" ? "bg-red-700" : "bg-slate-700";
        return (
          <div key={key} className="flex items-center gap-2 text-xs">
            <span className="w-24 text-slate-400 text-right">{label}</span>
            <div className="flex-1 h-4 bg-slate-900 rounded overflow-hidden">
              <div className={`h-full ${colorCls} rounded transition-all duration-300`} style={{ width: `${pct2}%` }} />
            </div>
            <span className="w-12 text-slate-500">{count.toLocaleString()}</span>
            <span className="w-10 text-slate-600 text-right">{pct2}%</span>
          </div>
        );
      })}
    </div>
  );
}

// ── Signal outcome breakdown ─────────────────────────────────────────────────

function SignalOutcomeBreakdown({ summary }: { summary: StrategyMetricsSummary | null }) {
  if (!summary) return null;
  const { emitted_count, rejected_count, skipped_count, indeterminate_count, near_miss_count } = summary;
  const total = emitted_count + rejected_count + skipped_count + indeterminate_count || 1;
  const items = [
    { label: "Emitted", count: emitted_count, cls: "bg-green-700" },
    { label: "Rejected", count: rejected_count, cls: "bg-red-700" },
    { label: "Skipped", count: skipped_count, cls: "bg-yellow-700" },
    { label: "Indeterminate", count: indeterminate_count, cls: "bg-slate-700" },
    { label: "Near-miss", count: near_miss_count, cls: "bg-blue-700" },
  ];
  return (
    <div className="space-y-1">
      {items.map(({ label, count, cls }) => {
        const pct2 = Math.round((count / total) * 100);
        return (
          <div key={label} className="flex items-center gap-2 text-xs">
            <span className="w-24 text-slate-400 text-right">{label}</span>
            <div className="flex-1 h-4 bg-slate-900 rounded overflow-hidden">
              <div className={`h-full ${cls} rounded`} style={{ width: `${pct2}%` }} />
            </div>
            <span className="w-12 text-slate-500">{count.toLocaleString()}</span>
            <span className="w-10 text-slate-600 text-right">{pct2}%</span>
          </div>
        );
      })}
    </div>
  );
}

// ── Near-miss reasons ────────────────────────────────────────────────────────

function NearMissReasons({ counts }: { counts: Record<string, number> }) {
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  if (!entries.length) return <div className="text-xs text-slate-600">None</div>;
  return (
    <div className="space-y-1">
      {entries.slice(0, 8).map(([reason, count]) => (
        <div key={reason} className="flex items-center justify-between text-xs">
          <span className="text-slate-400 truncate max-w-[200px]" title={reason}>{reason}</span>
          <span className="text-blue-400 ml-2">{count}</span>
        </div>
      ))}
    </div>
  );
}

// ── Top blockers ─────────────────────────────────────────────────────────────

function TopBlockers({ blockers }: { blockers: StrategyBlockerSummary[] }) {
  if (!blockers.length) return <div className="text-sm text-slate-500">No blockers for this range.</div>;
  const max = blockers[0]?.combined_score || 1;
  return (
    <div className="space-y-2">
      {blockers.slice(0, 6).map((b) => {
        const barPct = Math.round((b.combined_score / max) * 100);
        return (
          <div key={b.criterion_name} className="border border-slate-800 bg-slate-950 rounded p-2">
            <div className="flex items-center justify-between mb-1">
              <span className="text-white text-xs font-medium truncate max-w-[180px]" title={b.criterion_name}>
                {b.criterion_name}
              </span>
              <span className="text-slate-400 text-xs ml-2">{b.blocked_count} blocked</span>
            </div>
            <div className="h-1.5 bg-slate-900 rounded overflow-hidden">
              <div
                className="h-full bg-red-600 rounded"
                style={{ width: `${barPct}%` }}
              />
            </div>
            <div className="flex gap-3 mt-1 text-xs text-slate-600">
              <span>F: {pct(b.frequency_component)}</span>
              <span>M: {pct(b.margin_component)}</span>
              <span>Q: {pct(b.quality_component)}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Criterion table ──────────────────────────────────────────────────────────

interface CriteriaTableProps {
  criteria: StrategyCriteriaList | null;
  onSelect: (name: string) => void;
  selected: string | null;
}

function CriteriaTable({ criteria, onSelect, selected }: CriteriaTableProps) {
  const rows = criteria?.criteria ?? [];
  if (!rows.length) return <div className="text-sm text-slate-500 py-4">No criteria for this range.</div>;
  return (
    <div className="border border-slate-800 rounded overflow-hidden">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-900 text-slate-400">
          <tr>
            {["Criterion", "Pass", "Fail", "P/F rate", "Near-miss", "Avg miss", "Incomplete"].map((h) => (
              <th key={h} className="text-left px-3 py-2 font-medium text-xs">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.criterion_name}
              onClick={() => onSelect(r.criterion_name === selected ? "" : r.criterion_name)}
              className={`border-t border-slate-800 cursor-pointer transition-colors ${r.criterion_name === selected ? "bg-slate-800" : "hover:bg-slate-900"}`}
            >
              <td className="px-3 py-2 text-white text-xs max-w-[160px] truncate" title={r.criterion_name}>
                {r.criterion_name}
              </td>
              <td className="px-3 py-2 text-green-300">{r.pass_count.toLocaleString()}</td>
              <td className="px-3 py-2 text-red-300">{r.fail_count.toLocaleString()}</td>
              <td className="px-3 py-2 text-slate-300">{pct(r.pass_rate)}</td>
              <td className="px-3 py-2 text-blue-300">{r.near_miss_contribution}</td>
              <td className="px-3 py-2 text-slate-300">{r.average_failure_margin != null ? r.average_failure_margin.toFixed(3) : "—"}</td>
              <td className="px-3 py-2 text-yellow-300">{r.incomplete_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Criterion drilldown panel ────────────────────────────────────────────────

interface CriterionDrilldownProps {
  detail: CriterionDetail | null;
  loading: boolean;
  onClose: () => void;
  filterSymbol: string;
  filterDecision: string;
  filterNearMiss: string;
  onFilterChange: (key: string, value: string) => void;
  filters: { symbol: string; decision: string; near_miss: string };
}

function CriterionDrilldown({
  detail,
  loading,
  onClose,
  filterSymbol,
  filterDecision,
  filterNearMiss,
  onFilterChange,
  filters,
}: CriterionDrilldownProps) {
  if (!detail && !loading) return null;
  return (
    <div className="border border-blue-900 bg-blue-950/20 rounded p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-blue-300">
          Criterion Drilldown{detail ? `: ${detail.criterion_name}` : ""}
        </h3>
        <button
          onClick={onClose}
          className="text-xs text-slate-500 hover:text-slate-300 border border-slate-700 rounded px-2 py-1"
        >
          Close
        </button>
      </div>

      {loading ? (
        <LoadingBar label="Loading criterion details" />
      ) : detail ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard label="Layer" value={detail.layer} />
            <StatCard label="Pass rate" value={pct(detail.pass_rate)} accent="green" />
            <StatCard label="Fail rate" value={pct(detail.fail_rate)} accent="red" />
            <StatCard label="Near-miss contrib." value={detail.near_miss_contribution} accent="blue" />
            <StatCard label="Evaluated" value={detail.evaluated_count.toLocaleString()} />
            <StatCard label="Passed" value={detail.pass_count.toLocaleString()} accent="green" />
            <StatCard label="Failed" value={detail.fail_count.toLocaleString()} accent="red" />
            <StatCard
              label="Avg failure margin"
              value={detail.average_failure_margin != null ? detail.average_failure_margin.toFixed(4) : "—"}
              sub={detail.average_normalized_margin != null ? `norm: ${detail.average_normalized_margin.toFixed(4)}` : undefined}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1">
              <SectionHeader title="Drilldown Filters" />
              <div className="flex gap-2 flex-wrap">
                <select
                  value={filters.symbol}
                  onChange={(e) => onFilterChange("symbol", e.target.value)}
                  className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-slate-300"
                >
                  <option value="">All symbols</option>
                </select>
                <select
                  value={filters.decision}
                  onChange={(e) => onFilterChange("decision", e.target.value)}
                  className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-slate-300"
                >
                  <option value="">All decisions</option>
                  <option value="rejected">Rejected</option>
                  <option value="emitted">Emitted</option>
                </select>
                <select
                  value={filters.near_miss}
                  onChange={(e) => onFilterChange("near_miss", e.target.value)}
                  className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-slate-300"
                >
                  <option value="">All</option>
                  <option value="true">Near-miss only</option>
                  <option value="false">Non near-miss only</option>
                </select>
              </div>
            </div>
            <div className="text-xs text-slate-500 flex items-center">
              Showing {detail.opportunities.length} of {detail.total_matching.toLocaleString()} matching
            </div>
          </div>

          {detail.opportunities.length === 0 ? (
            <div className="text-sm text-slate-500 py-4 text-center">No matching opportunities.</div>
          ) : (
            <div className="space-y-2">
              {detail.opportunities.map((opp) => (
                <OpportunityDetailRow key={opp.id} opportunity={opp} highlightCriterion={detail.criterion_name} />
              ))}
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}

// ── Single opportunity row (in drilldown) ────────────────────────────────────

function OpportunityDetailRow({ opportunity, highlightCriterion }: {
  opportunity: StrategyMetricOpportunity;
  highlightCriterion?: string;
}) {
  const criterion = opportunity.criteria.find((c) => c.criterion_name === highlightCriterion);
  const failed = opportunity.criteria.filter((c) => c.passed === false);

  return (
    <details className="border border-slate-800 bg-slate-950 rounded">
      <summary className="cursor-pointer px-3 py-2 text-xs grid grid-cols-2 md:grid-cols-5 gap-2">
        <span className="text-white font-medium">{opportunity.symbol}</span>
        <span className={opportunity.final_decision === "emitted" ? "text-green-300" : "text-red-300"}>
          {opportunity.final_decision}
        </span>
        <span className="text-slate-400">{opportunity.near_miss ? "near-miss" : `${failed.length} failed`}</span>
        <span className="text-slate-500">{new Date(opportunity.evaluated_at).toLocaleString()}</span>
        <span className="text-slate-600">{opportunity.failed_criteria_count} fail / {opportunity.criteria.length} total</span>
      </summary>
      <div className="border-t border-slate-800 px-3 py-2 space-y-2">
        {criterion && (
          <div className="bg-slate-900 rounded p-2 space-y-1">
            <div className="text-xs font-semibold text-blue-300 mb-1">Highlighted criterion</div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-1 text-xs">
              <span className="text-slate-400">Measured</span>
              <span className="text-white col-span-3">{JSON.stringify(criterion.measured_value)}</span>
              <span className="text-slate-400">Threshold</span>
              <span className="text-white col-span-3">{JSON.stringify(criterion.threshold_value)} ({criterion.threshold_operator})</span>
              <span className="text-slate-400">Result</span>
              <span className={criterion.passed ? "text-green-300" : criterion.passed === false ? "text-red-300" : "text-yellow-300"}>
                {String(criterion.passed)}
              </span>
              <span className="text-slate-400">Margin</span>
              <span className="text-slate-300">{criterion.margin != null ? criterion.margin.toFixed(4) : "—"}</span>
              {criterion.reason && (
                <>
                  <span className="text-slate-400">Reason</span>
                  <span className="text-yellow-300 col-span-3">{criterion.reason}</span>
                </>
              )}
              {Object.keys(criterion.context || {}).length > 0 && (
                <>
                  <span className="text-slate-400">Context</span>
                  <span className="text-slate-500 col-span-3 text-[10px]">{JSON.stringify(criterion.context)}</span>
                </>
              )}
            </div>
          </div>
        )}
        <div>
          <div className="text-xs text-slate-500 mb-1">All criteria ({opportunity.criteria.length})</div>
          <div className="grid gap-0.5 text-[10px]">
            {opportunity.criteria.map((c) => (
              <div
                key={`${opportunity.id}-${c.criterion_name}`}
                className={`grid grid-cols-4 gap-1 px-1 py-0.5 rounded ${c.criterion_name === highlightCriterion ? "bg-blue-900/30" : ""}`}
              >
                <span className="text-slate-400 truncate" title={c.criterion_name}>{c.criterion_name.split(":").pop()}</span>
                <span className={c.passed ? "text-green-300" : c.passed === false ? "text-red-300" : "text-yellow-300"}>
                  {String(c.passed ?? "null")}
                </span>
                <span className="text-slate-500">val {JSON.stringify(c.measured_value)}</span>
                <span className="text-slate-600">mrg {c.margin != null ? c.margin.toFixed(3) : "—"}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </details>
  );
}

// ── Opportunity explorer ─────────────────────────────────────────────────────

interface OpportunityExplorerProps {
  opportunities: StrategyMetricOpportunity[];
  totalEvaluated: number;
  loadingMore: boolean;
  onLoadMore: () => void;
  loading: boolean;
  searchSymbol: string;
  onSearchChange: (v: string) => void;
  searchDecision: string;
  onDecisionChange: (v: string) => void;
  searchNearMiss: string;
  onNearMissChange: (v: string) => void;
}

function OpportunityExplorer({
  opportunities,
  totalEvaluated,
  loadingMore,
  onLoadMore,
  loading,
  searchSymbol,
  onSearchChange,
  searchDecision,
  onDecisionChange,
  searchNearMiss,
  onNearMissChange,
}: OpportunityExplorerProps) {
  const filtered = opportunities.filter((o) => {
    if (searchSymbol && !o.symbol.toLowerCase().includes(searchSymbol.toLowerCase())) return false;
    if (searchDecision && o.final_decision !== searchDecision) return false;
    if (searchNearMiss === "true" && !o.near_miss) return false;
    if (searchNearMiss === "false" && o.near_miss) return false;
    return true;
  });

  return (
    <div className="space-y-3">
      <div className="flex gap-2 flex-wrap items-center">
        <input
          value={searchSymbol}
          onChange={(e) => onSearchChange(e.target.value.toUpperCase())}
          placeholder="Filter by symbol…"
          className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-slate-300 w-32"
        />
        <select
          value={searchDecision}
          onChange={(e) => onDecisionChange(e.target.value)}
          className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-slate-300"
        >
          <option value="">All decisions</option>
          <option value="emitted">Emitted</option>
          <option value="rejected">Rejected</option>
          <option value="skipped">Skipped</option>
          <option value="indeterminate">Indeterminate</option>
        </select>
        <select
          value={searchNearMiss}
          onChange={(e) => onNearMissChange(e.target.value)}
          className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-slate-300"
        >
          <option value="">All</option>
          <option value="true">Near-miss only</option>
          <option value="false">Non near-miss only</option>
        </select>
        <span className="text-xs text-slate-600 ml-auto">
          {filtered.length} of {totalEvaluated.toLocaleString()} shown
        </span>
      </div>

      {loading ? (
        <LoadingBar label="Loading opportunities" />
      ) : filtered.length === 0 ? (
        <div className="text-sm text-slate-500 py-8 border border-slate-800 rounded text-center">
          No matching opportunities.
        </div>
      ) : (
        <>
          {filtered.map((o) => (
            <OpportunityDetailRow key={o.id} opportunity={o} />
          ))}
          {filtered.length < totalEvaluated && (
            <button
              onClick={onLoadMore}
              disabled={loadingMore}
              className="w-full border border-slate-700 rounded px-3 py-2 text-sm text-slate-300 hover:border-slate-500 disabled:opacity-50"
            >
              {loadingMore ? "Loading…" : `Load more (${filtered.length}/${totalEvaluated.toLocaleString()})`}
            </button>
          )}
        </>
      )}
    </div>
  );
}

// ── Managed lifecycle stats ──────────────────────────────────────────────────

function ManagedLifecycleStats({ summary }: { summary: StrategyMetricsSummary | null }) {
  if (!summary) return null;
  const { managed_vs_original_result_delta, continuation_management_events_observed,
    continuation_management_events_accepted, continuation_management_events_rejected,
    tp_extension_count, sl_tighten_count, break_even_move_count } = summary;
  const delta = managed_vs_original_result_delta;
  if (!continuation_management_events_observed && !tp_extension_count && !sl_tighten_count) return null;
  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
      <StatCard label="Continuation observed" value={continuation_management_events_observed} />
      <StatCard label="Continuation accepted" value={continuation_management_events_accepted}
        sub={`${continuation_management_events_rejected} rejected`} accent="green" />
      <StatCard label="SL moves" value={sl_tighten_count} sub={`${break_even_move_count} break-even`} />
      <StatCard label="TP extensions" value={tp_extension_count} />
      <StatCard label="Result delta" value={`+${delta?.improved ?? 0} / -${delta?.worsened ?? 0}`}
        sub={`avg R ${summary.average_r_captured ?? "—"}`} />
    </div>
  );
}

// ── Utility hook ────────────────────────────────────────────────────────────

function usePrevious<T>(value: T): T | undefined {
  const ref = useRef<T | undefined>(undefined);
  useEffect(() => { ref.current = value; }, [value]);
  return ref.current;
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function StrategyMetricsPage() {
  const [start, setStart] = useState(defaultStart(7));
  const [end, setEnd] = useState(isoDate(new Date()));
  const [symbol, setSymbol] = useState("");
  const [strategy, setStrategy] = useState("");
  const [signalType, setSignalType] = useState("");
  const [decision, setDecision] = useState("");
  const [firstBlocker, setFirstBlocker] = useState("");

  const [compare, setCompare] = useState(false);
  const [baseStart, setBaseStart] = useState(defaultStart(14));
  const [baseEnd, setBaseEnd] = useState(defaultStart(7));

  const [appliedFilters, setAppliedFilters] = useState({
    start: defaultStart(7),
    end: isoDate(new Date()),
    symbol: "",
    strategy: "",
    signalType: "",
    decision: "",
    firstBlocker: "",
  });

  const [applyDisabled, setApplyDisabled] = useState(false);

  // Criterion drilldown state
  const [selectedCriterion, setSelectedCriterion] = useState<string | null>(null);
  const [criterionDetail, setCriterionDetail] = useState<CriterionDetail | null>(null);
  const [criteriaList, setCriteriaList] = useState<StrategyCriteriaList | null>(null);
  const [loadingCriterionDetail, setLoadingCriterionDetail] = useState(false);
  const [drilldownFilters, setDrilldownFilters] = useState({ symbol: "", decision: "", near_miss: "" });

  // Opportunity explorer filters
  const [oppSearchSymbol, setOppSearchSymbol] = useState("");
  const [oppSearchDecision, setOppSearchDecision] = useState("");
  const [oppSearchNearMiss, setOppSearchNearMiss] = useState("");

  const summaryParams = useMemo(
    () => ({
      start: appliedFilters.start,
      end: appliedFilters.end,
      symbol: appliedFilters.symbol || undefined,
    }),
    [appliedFilters]
  );

  const { summary, opportunities, error, loading, loadingMore, loadMore, refresh } =
    useStrategyMetricsSummary(summaryParams);

  const comparisonParams = useMemo(
    () => ({
      base_start: baseStart,
      base_end: baseEnd,
      compare_start: appliedFilters.start,
      compare_end: appliedFilters.end,
      symbol: appliedFilters.symbol || undefined,
    }),
    [baseStart, baseEnd, appliedFilters]
  );

  const { comparison } = useStrategyMetricsComparison(comparisonParams, compare);


  const handleApply = useCallback(() => {
    if (applyDisabled) return;
    setApplyDisabled(true);
    setSelectedCriterion(null);
    setCriterionDetail(null);
    setCriteriaList(null);
    setOppSearchSymbol("");
    setOppSearchDecision("");
    setOppSearchNearMiss("");
    setAppliedFilters({ start, end, symbol, strategy, signalType, decision, firstBlocker });
    setTimeout(() => setApplyDisabled(false), 600);
  }, [applyDisabled, start, end, symbol, strategy, signalType, decision, firstBlocker]);

  // Fetch criteria list when filters change
  const fetchCriteriaList = useCallback(async () => {
    if (!appliedFilters.start || !appliedFilters.end) return;
    try {
      const data = await getCriteriaList({
        start: appliedFilters.start,
        end: appliedFilters.end,
        symbol: appliedFilters.symbol || undefined,
        strategy: appliedFilters.strategy || undefined,
        signal_type: appliedFilters.signalType || undefined,
        decision: appliedFilters.decision || undefined,
        first_blocker: appliedFilters.firstBlocker || undefined,
      });
      setCriteriaList(data);
    } catch { /* silently ignore criteria list errors */ }
  }, [appliedFilters]);

  // Trigger data fetch when filters version increments (i.e. Apply was clicked)
  const triggerRefresh = useCallback(async () => {
    await refresh();
    void fetchCriteriaList();
    if (compare) void comparison.refresh();
  }, [refresh, fetchCriteriaList, compare, comparison]);

  // Watch appliedFilters to trigger refresh after apply
  const prevAppliedFilters = usePrevious(appliedFilters);
  useEffect(() => {
    if (
      prevAppliedFilters &&
      (appliedFilters.start !== prevAppliedFilters.start ||
        appliedFilters.end !== prevAppliedFilters.end ||
        appliedFilters.symbol !== prevAppliedFilters.symbol ||
        appliedFilters.strategy !== prevAppliedFilters.strategy ||
        appliedFilters.signalType !== prevAppliedFilters.signalType ||
        appliedFilters.decision !== prevAppliedFilters.decision ||
        appliedFilters.firstBlocker !== prevAppliedFilters.firstBlocker)
    ) {
      void triggerRefresh();
    }
  }, [appliedFilters, prevAppliedFilters, triggerRefresh]);

  // Also trigger on initial mount
  useEffect(() => {
    void triggerRefresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Trigger comparison refresh when compare mode or compare params change
  useEffect(() => {
    if (compare) void comparison.refresh();
  }, [compare, comparisonParams, comparison]);



  const handleCriterionSelect = useCallback(
    async (name: string) => {
      setSelectedCriterion(name);
      if (!name) { setCriterionDetail(null); return; }
      setLoadingCriterionDetail(true);
      try {
        const data = await getCriterionDetail(
          name,
          {
            start: appliedFilters.start,
            end: appliedFilters.end,
            symbol: drilldownFilters.symbol || undefined,
            decision: drilldownFilters.decision || undefined,
            near_miss: drilldownFilters.near_miss === "true" ? true : drilldownFilters.near_miss === "false" ? false : undefined,
            first_blocker: appliedFilters.firstBlocker || undefined,
          }
        );
        setCriterionDetail(data);
      } catch { setCriterionDetail(null); }
      finally { setLoadingCriterionDetail(false); }
    },
    [appliedFilters, drilldownFilters]
  );

  const handleDrilldownFilterChange = useCallback(
    (key: string, value: string) => {
      setDrilldownFilters((prev) => ({ ...prev, [key]: value }));
      const newFilters = { ...drilldownFilters, [key]: value };
      if (!selectedCriterion) return;
      setLoadingCriterionDetail(true);
      void getCriterionDetail(selectedCriterion, {
        start: appliedFilters.start,
        end: appliedFilters.end,
        symbol: newFilters.symbol || undefined,
        decision: newFilters.decision || undefined,
        near_miss: newFilters.near_miss === "true" ? true : newFilters.near_miss === "false" ? false : undefined,
        first_blocker: appliedFilters.firstBlocker || undefined,
      })
        .then(setCriterionDetail)
        .catch(() => setCriterionDetail(null))
        .finally(() => setLoadingCriterionDetail(false));
    },
    [selectedCriterion, appliedFilters, drilldownFilters]
  );

  async function handleExport() {
    const data = await exportStrategyMetrics({ ...summaryParams, include_opportunities: true });
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `strategy-metrics-${start}-to-${end}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* ── Header ── */}
      <div className="border-b border-slate-800 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/" className="text-slate-500 hover:text-slate-300 text-sm">Dashboard</Link>
          <span className="text-white font-semibold text-sm">Strategy Metrics</span>
        </div>
        <button
          onClick={() => { void triggerRefresh(); }}
          disabled={loading}
          className="text-xs border border-slate-700 rounded px-3 py-1 text-slate-300 hover:border-slate-500 disabled:opacity-50"
        >
          {loading ? "Refreshing" : "Refresh"}
        </button>
      </div>

      <main className="max-w-7xl mx-auto px-4 py-5 space-y-6">

        {/* ── Section 1: Report Controls ── */}
        <section className="space-y-3">
          <SectionHeader title="Report Controls" />
          <div className="grid grid-cols-2 md:grid-cols-7 gap-3 text-sm">
            <label className="space-y-1">
              <span className="text-slate-500 text-xs">Start</span>
              <input
                type="date"
                value={start}
                onChange={(e) => setStart(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs"
              />
            </label>
            <label className="space-y-1">
              <span className="text-slate-500 text-xs">End</span>
              <input
                type="date"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs"
              />
            </label>
            <label className="space-y-1">
              <span className="text-slate-500 text-xs">Symbol</span>
              <input
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                placeholder="All"
                className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs"
              />
            </label>
            <label className="space-y-1">
              <span className="text-slate-500 text-xs">Strategy</span>
              <input
                value={strategy}
                onChange={(e) => setStrategy(e.target.value)}
                placeholder="All"
                className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs"
              />
            </label>
            <label className="space-y-1">
              <span className="text-slate-500 text-xs">Signal type</span>
              <input
                value={signalType}
                onChange={(e) => setSignalType(e.target.value)}
                placeholder="All"
                className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs"
              />
            </label>
            <label className="space-y-1">
              <span className="text-slate-500 text-xs">Decision</span>
              <select
                value={decision}
                onChange={(e) => setDecision(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs"
              >
                <option value="">All</option>
                <option value="emitted">Emitted</option>
                <option value="rejected">Rejected</option>
                <option value="skipped">Skipped</option>
                <option value="indeterminate">Indeterminate</option>
              </select>
            </label>
            <label className="space-y-1">
              <span className="text-slate-500 text-xs">First blocker</span>
              <input
                value={firstBlocker}
                onChange={(e) => setFirstBlocker(e.target.value)}
                placeholder="All"
                className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs"
              />
            </label>
          </div>
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={handleApply}
              disabled={applyDisabled || loading}
              className="border border-blue-700 bg-blue-900/40 hover:bg-blue-800/40 rounded px-4 py-1.5 text-sm text-blue-300 hover:text-blue-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? "Loading…" : "Apply Filters / Run Report"}
            </button>
            <button
              onClick={() => setCompare(!compare)}
              className="border border-slate-700 rounded px-3 py-1 text-slate-300 hover:border-slate-500 text-xs"
            >
              {compare ? "Summary view" : "Compare periods"}
            </button>
            <button
              onClick={handleExport}
              disabled={loading}
              className="border border-slate-700 rounded px-3 py-1 text-slate-300 hover:border-slate-500 text-xs disabled:opacity-50"
            >
              Export JSON
            </button>
          </div>
        </section>

        {/* Compare mode */}
        {compare && comparison ? (
          <section className="space-y-4">
            <SectionHeader title="Period Comparison" />
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <StatCard label="Evaluated delta" value={comparison.deltas.total_evaluated > 0 ? `+${comparison.deltas.total_evaluated}` : comparison.deltas.total_evaluated} />
              <StatCard label="Emitted delta" value={comparison.deltas.emitted_count > 0 ? `+${comparison.deltas.emitted_count}` : comparison.deltas.emitted_count} accent="green" />
              <StatCard label="Near-miss delta" value={comparison.deltas.near_miss_count > 0 ? `+${comparison.deltas.near_miss_count}` : comparison.deltas.near_miss_count} accent="blue" />
              <StatCard
                label="Top blocker"
                value={comparison.deltas.comparison_top_blocker ?? "—"}
                sub={comparison.deltas.top_blocker_changed ? "⚠ changed" : "unchanged"}
                accent={comparison.deltas.top_blocker_changed ? "yellow" : undefined}
              />
            </div>
            <SectionHeader title="Top Blockers — Comparison period" />
            <TopBlockers blockers={comparison.comparison.top_blockers} />
          </section>
        ) : (
          <>
            {error && (
              <div className="border border-red-800 bg-red-950/20 text-red-300 rounded p-3 text-sm">{error}</div>
            )}

            {/* ── Section 2: Executive Summary ── */}
            <section className="space-y-3">
              <SectionHeader title="Executive Summary" badge={summary?.total_evaluated?.toLocaleString()} />
              {loading && !summary ? (
                <LoadingBar label="Loading summary" />
              ) : (
                <>
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                    <StatCard label="Evaluated" value={summary?.total_evaluated ?? 0} />
                    <StatCard label="Emitted" value={summary?.emitted_count ?? 0} accent="green" />
                    <StatCard label="Rejected" value={summary?.rejected_count ?? 0} accent="red" />
                    <StatCard label="Skipped" value={summary?.skipped_count ?? 0} accent="yellow" />
                    <StatCard label="Indeterminate" value={summary?.indeterminate_count ?? 0} />
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
                    <StatCard
                      label="Tradable"
                      value={summary?.trade_opportunity_count ?? 0}
                      sub={`${summary?.stats_excluded_count ?? 0} excluded`}
                      accent="green"
                    />
                    <StatCard label="Near-miss" value={summary?.near_miss_count ?? 0} accent="blue" />
                    <StatCard label="Prime suppressed" value={summary?.total_prime_suppressed_signals ?? 0} accent="purple" />
                    <StatCard label="Inferred TP close" value={summary?.inferred_tp_close_count ?? 0} accent="green" />
                    <StatCard label="Inferred SL close" value={summary?.inferred_sl_close_count ?? 0} accent="red" />
                    <StatCard label="Strategy-stat eligible" value={summary?.trade_opportunity_count ?? 0} />
                  </div>
                  <ManagedLifecycleStats summary={summary} />
                  {summary?.data_quality_warnings?.length ? (
                    <div className="border border-yellow-800 bg-yellow-950/20 text-yellow-300 rounded p-3 text-xs space-y-1">
                      <div className="font-semibold text-yellow-400 mb-1">Data quality warnings</div>
                      {summary.data_quality_warnings.map((w) => <div key={w}>{w}</div>)}
                    </div>
                  ) : null}
                </>
              )}
            </section>

            {/* ── Section 3: Failure Diagnosis ── */}
            {summary && (
              <section className="space-y-4">
                <SectionHeader title="Failure Diagnosis" />

                {/* Pipeline funnel + signal outcomes */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="border border-slate-800 rounded p-3 space-y-2">
                    <SectionHeader title="Pipeline Funnel" />
                    <PipelineFunnel funnel={summary.pipeline_funnel ?? {}} />
                  </div>
                  <div className="border border-slate-800 rounded p-3 space-y-2">
                    <SectionHeader title="Signal Outcome Breakdown" />
                    <SignalOutcomeBreakdown summary={summary} />
                  </div>
                </div>

                {/* Top blockers + near-miss reasons */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="border border-slate-800 rounded p-3 space-y-2">
                    <SectionHeader title="Top Blockers by Impact" badge={summary.top_blockers?.length} />
                    <TopBlockers blockers={summary.top_blockers ?? []} />
                  </div>
                  <div className="border border-slate-800 rounded p-3 space-y-2">
                    <SectionHeader title="Near-Miss Reasons" />
                    <NearMissReasons counts={summary.near_miss_reason_counts ?? {}} />
                  </div>
                </div>
              </section>
            )}

            {/* ── Section 4: Criterion Drilldown ── */}
            <section className="space-y-3">
              <SectionHeader
                title="Criterion Pass/Fail"
                badge={criteriaList?.criteria?.length ?? summary?.criterion_summaries?.length}
              />
              {loading && !criteriaList && !summary ? (
                <LoadingBar label="Loading criteria" />
              ) : (
                <>
                  {/* Fall back to summary-based criteria if criteria list not loaded */}
                  {criteriaList ? (
                    <CriteriaTable
                      criteria={criteriaList}
                      onSelect={handleCriterionSelect}
                      selected={selectedCriterion}
                    />
                  ) : summary?.criterion_summaries?.length ? (
                    <CriteriaTable
                      criteria={{ start: appliedFilters.start, end: appliedFilters.end, criteria: summary.criterion_summaries }}
                      onSelect={handleCriterionSelect}
                      selected={selectedCriterion}
                    />
                  ) : null}

                  {/* Drilldown panel */}
                  <CriterionDrilldown
                    detail={criterionDetail}
                    loading={loadingCriterionDetail}
                    onClose={() => { setSelectedCriterion(null); setCriterionDetail(null); }}
                    filterSymbol={drilldownFilters.symbol}
                    filterDecision={drilldownFilters.decision}
                    filterNearMiss={drilldownFilters.near_miss}
                    onFilterChange={handleDrilldownFilterChange}
                    filters={drilldownFilters}
                  />
                </>
              )}
            </section>

            {/* ── Section 5: Opportunity Explorer ── */}
            <section className="space-y-3">
              <SectionHeader title="Opportunity Explorer" badge={summary?.total_evaluated?.toLocaleString()} />
              {loading && !summary ? (
                <LoadingBar label="Loading opportunities" />
              ) : (
                <OpportunityExplorer
                  opportunities={opportunities}
                  totalEvaluated={summary?.total_evaluated ?? 0}
                  loadingMore={loadingMore}
                  onLoadMore={loadMore}
                  loading={loading}
                  searchSymbol={oppSearchSymbol}
                  onSearchChange={setOppSearchSymbol}
                  searchDecision={oppSearchDecision}
                  onDecisionChange={setOppSearchDecision}
                  searchNearMiss={oppSearchNearMiss}
                  onNearMissChange={setOppSearchNearMiss}
                />
              )}
            </section>
          </>
        )}
      </main>
    </div>
  );
}