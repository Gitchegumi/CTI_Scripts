"use client";

/**
 * Strategy Metrics dashboard (spec 022).
 *
 * Composes the redesigned page in the required hierarchy (FR-018): report
 * controls → executive summary → failure diagnosis → criterion drilldown →
 * opportunity explorer. Reports run only on Apply (US1), the last successful
 * report stays visible during loads/errors (FR-005), and any criterion can be
 * drilled into (US2).
 */
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { useStrategyMetricsReport, type ReportFilters } from "@/hooks/useData";
import { Skeleton } from "@/components/ui/skeleton";
import { ReportControls } from "@/components/strategy-metrics/ReportControls";
import { ExecutiveSummary } from "@/components/strategy-metrics/ExecutiveSummary";
import { FailureDiagnosis } from "@/components/strategy-metrics/FailureDiagnosis";
import { CriterionDrilldown } from "@/components/strategy-metrics/CriterionDrilldown";
import { OpportunityExplorer } from "@/components/strategy-metrics/OpportunityExplorer";
import type { StrategyMetricsSummary } from "@/types";

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function defaultFilters(): ReportFilters {
  const start = new Date();
  start.setDate(start.getDate() - 7);
  return { start: isoDate(start), end: isoDate(new Date()) };
}

function Warnings({ summary }: { summary: StrategyMetricsSummary | null }) {
  if (!summary?.data_quality_warnings.length) return null;
  return (
    <div className="rounded-lg border border-chart-3/40 bg-chart-3/10 p-3 text-sm text-chart-3" role="status">
      {summary.data_quality_warnings.map((w) => <div key={w}>{w}</div>)}
    </div>
  );
}

export default function StrategyMetricsPage() {
  const [appliedFilters, setAppliedFilters] = useState<ReportFilters>(defaultFilters);
  const [selectedCriterion, setSelectedCriterion] = useState<string | null>(null);
  const { summary, opportunities, status, error, loading, loadingMore, run, loadMore } =
    useStrategyMetricsReport();

  // Initial report on mount only; subsequent loads happen on explicit Apply (US1).
  const didInit = useRef(false);
  useEffect(() => {
    if (didInit.current) return;
    didInit.current = true;
    void run(appliedFilters);
  }, [run, appliedFilters]);

  function handleApply(filters: ReportFilters) {
    setAppliedFilters(filters);
    void run(filters);
  }

  async function handleExport() {
    const { exportStrategyMetrics } = await import("@/lib/api");
    const data = await exportStrategyMetrics({ ...appliedFilters, include_opportunities: true });
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `strategy-metrics-${appliedFilters.start}-to-${appliedFilters.end}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const firstLoad = loading && !summary;

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-3">
          <Link href="/" className="text-sm text-muted-foreground hover:text-foreground">Dashboard</Link>
          <span className="text-sm font-semibold text-foreground">Strategy Metrics</span>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-5 px-4 py-5">
        <ReportControls
          appliedFilters={appliedFilters}
          loading={loading}
          onApply={handleApply}
          onExport={handleExport}
        />

        {status === "error" && error && (
          <div role="alert" className="flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            <AlertTriangle className="size-4" />
            {error} — showing the last successful report.
          </div>
        )}

        <Warnings summary={summary} />

        {firstLoad ? (
          <LoadingSkeleton />
        ) : (
          <>
            <ExecutiveSummary summary={summary} />
            <FailureDiagnosis summary={summary} onSelectCriterion={setSelectedCriterion} />
            <OpportunityExplorer
              opportunities={opportunities}
              totalEvaluated={summary?.total_evaluated ?? opportunities.length}
              loadingMore={loadingMore}
              onLoadMore={loadMore}
            />
          </>
        )}

        <CriterionDrilldown
          criterionName={selectedCriterion}
          appliedFilters={appliedFilters}
          summary={summary}
          onClose={() => setSelectedCriterion(null)}
        />
      </main>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-5" aria-busy="true" aria-label="Loading report">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
        {Array.from({ length: 7 }).map((_, i) => <Skeleton key={i} className="h-16 rounded-lg" />)}
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-48 rounded-lg" />)}
      </div>
      <Skeleton className="h-64 rounded-lg" />
    </div>
  );
}
