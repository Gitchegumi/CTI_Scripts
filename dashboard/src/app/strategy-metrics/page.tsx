"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { exportStrategyMetrics } from "@/lib/api";
import { useStrategyMetricsComparison, useStrategyMetricsSummary } from "@/hooks/useData";
import type { StrategyBlockerSummary, StrategyMetricOpportunity, StrategyMetricsSummary } from "@/types";

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

function Stat({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="border border-slate-800 bg-slate-950 px-3 py-2 rounded">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-xl font-semibold text-white">{value}</div>
      {sub && <div className="text-xs text-slate-600">{sub}</div>}
    </div>
  );
}

function Warnings({ summary }: { summary: StrategyMetricsSummary | null }) {
  if (!summary?.data_quality_warnings.length) return null;
  return (
    <div className="border border-yellow-800 bg-yellow-950/20 text-yellow-300 rounded p-3 text-sm">
      {summary.data_quality_warnings.map((w) => <div key={w}>{w}</div>)}
    </div>
  );
}

function Blockers({ blockers }: { blockers: StrategyBlockerSummary[] }) {
  if (!blockers.length) {
    return <div className="text-sm text-slate-500 py-6">No blockers ranked for this range.</div>;
  }
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      {blockers.slice(0, 3).map((b) => (
        <div key={b.criterion_name} className="border border-slate-800 bg-slate-950 rounded p-3">
          <div className="text-white font-medium">{b.criterion_name}</div>
          <div className="text-xs text-slate-500 mt-1">{b.blocked_count} blocked</div>
          <div className="text-sm text-slate-300 mt-2">Score {b.combined_score.toFixed(2)}</div>
          <div className="text-xs text-slate-600 mt-1">
            F {pct(b.frequency_component)} / M {pct(b.margin_component)} / Q {pct(b.quality_component)}
          </div>
        </div>
      ))}
    </div>
  );
}

function CriteriaTable({ summary }: { summary: StrategyMetricsSummary | null }) {
  const rows = summary?.criterion_summaries ?? [];
  if (!rows.length) return <div className="text-sm text-slate-500 py-6">No criterion diagnostics in this range.</div>;
  return (
    <div className="overflow-x-auto border border-slate-800 rounded">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-900 text-slate-400">
          <tr>
            {["Criterion", "Pass", "Fail", "Near-miss", "Avg miss", "Incomplete"].map((h) => (
              <th key={h} className="text-left px-3 py-2 font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.criterion_name} className="border-t border-slate-800">
              <td className="px-3 py-2 text-white">{r.criterion_name}</td>
              <td className="px-3 py-2 text-green-300">{r.pass_count} ({pct(r.pass_rate)})</td>
              <td className="px-3 py-2 text-red-300">{r.fail_count} ({pct(r.fail_rate)})</td>
              <td className="px-3 py-2 text-blue-300">{r.near_miss_contribution}</td>
              <td className="px-3 py-2 text-slate-300">{r.average_failure_margin ?? "-"}</td>
              <td className="px-3 py-2 text-yellow-300">{r.incomplete_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OpportunityRow({ opportunity }: { opportunity: StrategyMetricOpportunity }) {
  const failed = opportunity.criteria.filter((c) => c.passed === false);
  return (
    <details className="border border-slate-800 bg-slate-950 rounded">
      <summary className="cursor-pointer px-3 py-2 grid grid-cols-2 md:grid-cols-6 gap-2 text-sm">
        <span className="text-white">{opportunity.symbol}</span>
        <span className="text-slate-300">{opportunity.final_decision}</span>
        <span className="text-slate-400">{opportunity.decision_reason}</span>
        <span className={opportunity.near_miss ? "text-blue-300" : "text-slate-500"}>
          {opportunity.near_miss ? "near-miss" : `${opportunity.failed_criteria_count} failed`}
        </span>
        <span className="text-slate-500">{opportunity.threshold_version}</span>
        <span className="text-slate-500">{new Date(opportunity.evaluated_at).toLocaleString()}</span>
      </summary>
      <div className="border-t border-slate-800 px-3 py-2 text-xs">
        {(failed.length ? failed : opportunity.criteria).map((c) => (
          <div key={`${opportunity.id}-${c.criterion_name}`} className="grid grid-cols-2 md:grid-cols-5 gap-2 py-1">
            <span className="text-white">{c.criterion_name}</span>
            <span className={c.passed ? "text-green-300" : "text-red-300"}>{String(c.passed)}</span>
            <span className="text-slate-400">value {JSON.stringify(c.measured_value)}</span>
            <span className="text-slate-400">threshold {JSON.stringify(c.threshold_value)}</span>
            <span className="text-slate-500">margin {c.margin ?? "-"}</span>
          </div>
        ))}
      </div>
    </details>
  );
}

export default function StrategyMetricsPage() {
  const [start, setStart] = useState(defaultStart(7));
  const [end, setEnd] = useState(isoDate(new Date()));
  const [symbol, setSymbol] = useState("");
  const [compare, setCompare] = useState(false);
  const [baseStart, setBaseStart] = useState(defaultStart(14));
  const [baseEnd, setBaseEnd] = useState(defaultStart(7));
  const summaryParams = useMemo(() => ({ start, end, symbol: symbol || undefined }), [start, end, symbol]);
  const { summary, opportunities, error, loading, refresh } = useStrategyMetricsSummary(summaryParams);
  const comparisonParams = useMemo(() => ({
    base_start: baseStart,
    base_end: baseEnd,
    compare_start: start,
    compare_end: end,
    symbol: symbol || undefined,
  }), [baseStart, baseEnd, start, end, symbol]);
  const { comparison } = useStrategyMetricsComparison(comparisonParams, compare);

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
      <div className="border-b border-slate-800 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/" className="text-slate-500 hover:text-slate-300 text-sm">Dashboard</Link>
          <span className="text-white font-semibold text-sm">Strategy Metrics</span>
        </div>
        <button onClick={refresh} className="text-xs border border-slate-700 rounded px-3 py-1 text-slate-300 hover:border-slate-500">
          {loading ? "Refreshing" : "Refresh"}
        </button>
      </div>

      <main className="max-w-7xl mx-auto px-4 py-5 space-y-5">
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3 text-sm">
          <label className="space-y-1">
            <span className="text-slate-500">Start</span>
            <input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
          </label>
          <label className="space-y-1">
            <span className="text-slate-500">End</span>
            <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
          </label>
          <label className="space-y-1">
            <span className="text-slate-500">Symbol</span>
            <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} placeholder="All" className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
          </label>
          <label className="space-y-1">
            <span className="text-slate-500">Baseline start</span>
            <input type="date" value={baseStart} onChange={(e) => setBaseStart(e.target.value)} className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
          </label>
          <label className="space-y-1">
            <span className="text-slate-500">Baseline end</span>
            <input type="date" value={baseEnd} onChange={(e) => setBaseEnd(e.target.value)} className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
          </label>
          <div className="flex items-end gap-2">
            <button onClick={() => setCompare(!compare)} className="border border-slate-700 rounded px-3 py-1 text-slate-300 hover:border-slate-500">
              {compare ? "Summary" : "Compare"}
            </button>
            <button onClick={handleExport} className="border border-slate-700 rounded px-3 py-1 text-slate-300 hover:border-slate-500">
              Export
            </button>
          </div>
        </div>

        {error && <div className="border border-red-800 bg-red-950/20 text-red-300 rounded p-3 text-sm">{error}</div>}
        <Warnings summary={summary} />

        {compare && comparison ? (
          <section className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Stat label="Evaluated delta" value={comparison.deltas.total_evaluated} />
              <Stat label="Signal delta" value={comparison.deltas.emitted_count} />
              <Stat label="Near-miss delta" value={comparison.deltas.near_miss_count} />
              <Stat label="Top blocker" value={comparison.deltas.comparison_top_blocker ?? "-"} sub={comparison.deltas.top_blocker_changed ? "changed" : "unchanged"} />
            </div>
            <Blockers blockers={comparison.comparison.top_blockers} />
          </section>
        ) : (
          <section className="space-y-5">
            <div className="grid grid-cols-2 md:grid-cols-7 gap-3">
              <Stat label="Evaluated" value={summary?.total_evaluated ?? 0} />
              <Stat label="Emitted" value={summary?.emitted_count ?? 0} />
              <Stat label="Tradable" value={summary?.trade_opportunity_count ?? 0} sub={`${summary?.stats_excluded_count ?? 0} excluded`} />
              <Stat label="Rejected" value={summary?.rejected_count ?? 0} />
              <Stat label="Skipped" value={summary?.skipped_count ?? 0} />
              <Stat label="Near-miss" value={summary?.near_miss_count ?? 0} />
              <Stat label="Indeterminate" value={summary?.indeterminate_count ?? 0} />
            </div>
            <Blockers blockers={summary?.top_blockers ?? []} />
            <CriteriaTable summary={summary} />
            <div className="space-y-2">
              <h2 className="text-sm font-semibold text-slate-300">Evaluated Opportunities</h2>
              {opportunities.length ? opportunities.map((o) => <OpportunityRow key={o.id} opportunity={o} />) : (
                <div className="text-sm text-slate-500 py-8 border border-slate-800 rounded text-center">
                  No evaluated opportunities for this range.
                </div>
              )}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
