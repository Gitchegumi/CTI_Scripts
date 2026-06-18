"use client";

/**
 * Executive summary stat cards (spec 022 US3, issue #144).
 *
 * Every card is bound to an actual field on the report summary — there are no
 * hardcoded values (FR-007). A genuine `0` renders as `0`; a `null`/absent
 * metric renders as an explicit "Unavailable" treatment that is visually
 * distinct from zero (FR-008/FR-009), via the metrics-availability helper.
 *
 * Issue #144: cards with a non-null, non-zero value and a clear API filter
 * mapping are clickable — clicking opens a MetricDrilldown showing the
 * underlying records.
 */
import { HelpCircle } from "lucide-react";
import { Card } from "@/components/ui/card";
import { metricDisplay, type MetricValue } from "@/lib/metrics-availability";
import type { StrategyMetricsSummary } from "@/types";
import type { MetricExtraParams } from "./MetricDrilldown";

interface StatCardProps {
  label: string;
  value: MetricValue;
  sub?: string;
  /** When provided and value is available + non-zero, the card is clickable. */
  onClick?: () => void;
}

function StatCard({ label, value, sub, onClick }: StatCardProps) {
  const display = metricDisplay(value);
  const clickable = onClick != null && display.available && !display.isZero;
  return (
    <Card
      data-available={display.available}
      {...(clickable
        ? {
            role: "button",
            tabIndex: 0,
            onClick,
            onKeyDown: (e: React.KeyboardEvent) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onClick!();
              }
            },
            className:
              "gap-1 p-3 cursor-pointer hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors",
          }
        : {
            className: "gap-1 p-3 transition-colors",
          })}
    >
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

export interface CardClickSpec {
  title: string;
  description: string;
  extraParams: MetricExtraParams;
}

/** Maps a card label to its drill-down spec, or null if not drillable. */
function cardClickSpec(label: string): CardClickSpec | null {
  switch (label) {
    case "Evaluated":
      return {
        title: "All Evaluated Opportunities",
        description: "Every evaluated opportunity in the selected range, most recent first.",
        extraParams: {},
      };
    case "Emitted":
      return {
        title: "Emitted Opportunities",
        description: "Opportunities with final decision = emitted, most recent first.",
        extraParams: { decision: "emitted" },
      };
    case "Rejected":
      return {
        title: "Rejected Opportunities",
        description: "Opportunities with final decision = rejected, most recent first.",
        extraParams: { decision: "rejected" },
      };
    case "Skipped":
      return {
        title: "Skipped Opportunities",
        description: "Opportunities with final decision = skipped, most recent first.",
        extraParams: { decision: "skipped" },
      };
    case "Indeterminate":
      return {
        title: "Indeterminate Opportunities",
        description: "Opportunities with final decision = indeterminate, most recent first.",
        extraParams: { decision: "indeterminate" },
      };
    case "Near miss":
      return {
        title: "Near-Miss Opportunities",
        description: "Opportunities that nearly passed — most recent first.",
        extraParams: { near_miss: true },
      };
    default:
      return null;
  }
}

export function ExecutiveSummary({
  summary,
  onMetricClick,
}: {
  summary: StrategyMetricsSummary | null;
  onMetricClick?: (spec: CardClickSpec) => void;
}) {
  const delta = summary?.managed_vs_original_result_delta;

  function makeOnClick(label: string) {
    const spec = cardClickSpec(label);
    if (!spec || !onMetricClick) return undefined;
    return () => onMetricClick(spec);
  }

  return (
    <section aria-label="Executive summary" className="space-y-3">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
        <StatCard label="Evaluated" value={summary?.total_evaluated} onClick={makeOnClick("Evaluated")} />
        <StatCard label="Emitted" value={summary?.emitted_count} onClick={makeOnClick("Emitted")} />
        <StatCard label="Rejected" value={summary?.rejected_count} onClick={makeOnClick("Rejected")} />
        <StatCard label="Skipped" value={summary?.skipped_count} onClick={makeOnClick("Skipped")} />
        <StatCard label="Indeterminate" value={summary?.indeterminate_count} onClick={makeOnClick("Indeterminate")} />
        <StatCard label="Near miss" value={summary?.near_miss_count} onClick={makeOnClick("Near miss")} />
        {/* Stat-eligible, Prime suppressed, Pullback entries, Continuation events
            have no direct API filter — leave non-clickable per issue #144. */}
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
        <StatCard label="TP extension" value={summary?.tp_extension_count} />
        <StatCard
          label="Avg R captured"
          value={summary?.average_r_captured ?? null}
          sub={delta ? `+${delta.improved ?? 0} / -${delta.worsened ?? 0} managed` : undefined}
        />
      </div>
    </section>
  );
}