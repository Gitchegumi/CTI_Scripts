"use client";

/**
 * Executive summary stat cards (spec 022 US3).
 *
 * Every card is bound to an actual field on the report summary — there are no
 * hardcoded values (FR-007). A genuine `0` renders as `0`; a `null`/absent
 * metric renders as an explicit "Unavailable" treatment that is visually
 * distinct from zero (FR-008/FR-009), via the metrics-availability helper.
 */
import { HelpCircle } from "lucide-react";
import { Card } from "@/components/ui/card";
import { metricDisplay, type MetricValue } from "@/lib/metrics-availability";
import type { StrategyMetricsSummary } from "@/types";

function StatCard({ label, value, sub }: { label: string; value: MetricValue; sub?: string }) {
  const display = metricDisplay(value);
  return (
    <Card className="gap-1 p-3" data-available={display.available}>
      <div className="text-xs text-muted-foreground">{label}</div>
      {display.available ? (
        <div className="text-xl font-semibold tabular-nums text-foreground">{display.text}</div>
      ) : (
        <div className="flex items-center gap-1 text-xl font-semibold text-muted-foreground/70">
          <HelpCircle className="size-4" aria-hidden="true" />
          <span className="text-sm font-normal">Unavailable</span>
        </div>
      )}
      {sub && <div className="text-xs text-muted-foreground/80">{sub}</div>}
    </Card>
  );
}

export function ExecutiveSummary({ summary }: { summary: StrategyMetricsSummary | null }) {
  const delta = summary?.managed_vs_original_result_delta;
  return (
    <section aria-label="Executive summary" className="space-y-3">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
        <StatCard label="Evaluated" value={summary?.total_evaluated} />
        <StatCard label="Emitted" value={summary?.emitted_count} />
        <StatCard label="Rejected" value={summary?.rejected_count} />
        <StatCard label="Skipped" value={summary?.skipped_count} />
        <StatCard label="Indeterminate" value={summary?.indeterminate_count} />
        <StatCard label="Near miss" value={summary?.near_miss_count} />
        <StatCard
          label="Stat-eligible"
          value={summary?.trade_opportunity_count}
          sub={summary ? `${summary.stats_excluded_count} excluded` : undefined}
        />
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
        <StatCard label="Prime suppressed" value={summary?.total_prime_suppressed_signals} />
        <StatCard label="Pullback entries" value={summary?.pullback_entries_opened} />
        <StatCard
          label="Continuation events"
          value={summary?.continuation_management_events_observed}
          sub={summary ? `${summary.continuation_management_events_accepted} accepted` : undefined}
        />
        <StatCard label="Rejected mgmt" value={summary?.continuation_management_events_rejected} />
        <StatCard
          label="SL moves"
          value={summary?.sl_tighten_count}
          sub={summary ? `${summary.break_even_move_count} break-even` : undefined}
        />
        <StatCard label="TP extensions" value={summary?.tp_extension_count} />
        <StatCard
          label="Avg R captured"
          value={summary?.average_r_captured ?? null}
          sub={delta ? `+${delta.improved ?? 0} / -${delta.worsened ?? 0} managed` : undefined}
        />
      </div>
    </section>
  );
}
