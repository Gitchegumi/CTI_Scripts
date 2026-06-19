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
import type { LifecycleCardSpec } from "./LifecycleDrilldown";

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

/**
 * Maps a second-row card to its lifecycle drill-down spec, or null if not
 * drillable. These cards are journal-derived (not evaluated opportunities), so
 * they open a LifecycleDrilldown via the lifecycle-events endpoint.
 */
function cardLifecycleSpec(label: string): LifecycleCardSpec | null {
  switch (label) {
    case "Prime suppressed":
      return {
        metric: "prime_suppressed",
        title: "Prime-Suppressed Signals",
        description: "Prime entries that suppressed lower-priority signals, most recent first.",
      };
    case "Pullback entries":
      return {
        metric: "pullback_entries",
        title: "Pullback Entries",
        description: "Pullback entry signals opened in this range, most recent first.",
      };
    case "Continuation events":
      return {
        metric: "continuation_events",
        title: "Continuation Management Events",
        description: "Continuation management/warning events observed, most recent first.",
      };
    case "Rejected mgmt":
      return {
        metric: "continuation_rejected",
        title: "Rejected Management Events",
        description: "Continuation management events that were not accepted, most recent first.",
      };
    case "SL moves":
      return {
        metric: "sl_moves",
        title: "Stop-Loss Adjustments",
        description: "Entries with stop-loss tightenings or break-even moves, most recent first.",
      };
    case "TP extension":
      return {
        metric: "tp_extension",
        title: "Take-Profit Extensions",
        description: "Entries with take-profit extensions, most recent first.",
      };
    case "Avg R captured":
      return {
        metric: "avg_r_captured",
        title: "Captured R",
        description: "Managed records with a captured-R value, most recent first.",
      };
    default:
      return null;
  }
}

export function ExecutiveSummary({
  summary,
  onMetricClick,
  onLifecycleClick,
}: {
  summary: StrategyMetricsSummary | null;
  onMetricClick?: (spec: CardClickSpec) => void;
  onLifecycleClick?: (spec: LifecycleCardSpec) => void;
}) {
  const delta = summary?.managed_vs_original_result_delta;

  function makeOnClick(label: string) {
    const spec = cardClickSpec(label);
    if (!spec || !onMetricClick) return undefined;
    return () => onMetricClick(spec);
  }

  function makeLifecycleOnClick(label: string) {
    const spec = cardLifecycleSpec(label);
    if (!spec || !onLifecycleClick) return undefined;
    return () => onLifecycleClick(spec);
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
        {/* Stat-eligible has no underlying record set to drill into — leave it
            non-clickable. The second-row lifecycle cards below are journal-backed
            and open a LifecycleDrilldown. */}
        <StatCard
          label="Stat-eligible"
          value={summary?.trade_opportunity_count}
          sub={summary ? `${summary.stats_excluded_count} excluded` : undefined}
        />
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
        <StatCard
          label="Prime suppressed"
          value={summary?.total_prime_suppressed_signals}
          onClick={makeLifecycleOnClick("Prime suppressed")}
        />
        <StatCard
          label="Pullback entries"
          value={summary?.pullback_entries_opened}
          onClick={makeLifecycleOnClick("Pullback entries")}
        />
        <StatCard
          label="Continuation events"
          value={summary?.continuation_management_events_observed}
          sub={summary ? `${summary.continuation_management_events_accepted} accepted` : undefined}
          onClick={makeLifecycleOnClick("Continuation events")}
        />
        <StatCard
          label="Rejected mgmt"
          value={summary?.continuation_management_events_rejected}
          onClick={makeLifecycleOnClick("Rejected mgmt")}
        />
        <StatCard
          label="SL moves"
          value={summary?.sl_tighten_count}
          sub={summary ? `${summary.break_even_move_count} break-even` : undefined}
          onClick={makeLifecycleOnClick("SL moves")}
        />
        <StatCard
          label="TP extension"
          value={summary?.tp_extension_count}
          onClick={makeLifecycleOnClick("TP extension")}
        />
        <StatCard
          label="Avg R captured"
          value={summary?.average_r_captured ?? null}
          sub={delta ? `+${delta.improved ?? 0} / -${delta.worsened ?? 0} managed` : undefined}
          onClick={makeLifecycleOnClick("Avg R captured")}
        />
      </div>
    </section>
  );
}