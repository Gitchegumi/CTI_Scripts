"use client";

/**
 * Pipeline funnel (evaluated → candidate → rules evaluated → emitted/rejected)
 * rendered as ordered, proportional stepped bars (spec 022 FR-019). SSR-safe,
 * labelled, and degrades to an empty-state when no stages are present.
 *
 * Row layout matches BarList: label renders inside the bar, value is
 * right-aligned to the right of the bar (issue #151).
 *
 * Issue #144: stages with a clear API filter mapping are clickable — clicking
 * calls `onSelectStage` with the stage key.
 */
import { cn } from "@/lib/utils";

const STAGE_LABELS: Record<string, string> = {
  total_evaluated: "Evaluated",
  candidate: "Candidate",
  candidates: "Candidate",
  signal_rules_evaluated: "Rules evaluated",
  rules_evaluated: "Rules evaluated",
  emitted: "Emitted",
  emitted_count: "Emitted",
  signal_emitted: "Emitted",
  rejected: "Rejected",
  rejected_count: "Rejected",
  signal_rejected: "Rejected",
};

const STAGE_ORDER = [
  "total_evaluated",
  "candidate",
  "candidates",
  "signal_rules_evaluated",
  "rules_evaluated",
  "emitted",
  "emitted_count",
  "signal_emitted",
  "rejected",
  "rejected_count",
  "signal_rejected",
];

/** Stages that have a clear API filter mapping for drill-down. */
const CLICKABLE_STAGES: Record<string, string> = {
  total_evaluated: "evaluated",
  emitted: "emitted",
  emitted_count: "emitted",
  signal_emitted: "emitted",
  rejected: "rejected",
  rejected_count: "rejected",
  signal_rejected: "rejected",
};

export function PipelineFunnel({
  funnel,
  onSelectStage,
}: {
  funnel: Record<string, number> | undefined;
  onSelectStage?: (stageKey: string) => void;
}) {
  const entries = Object.entries(funnel ?? {}).filter(([, v]) => typeof v === "number");
  if (!entries.length) {
    return <div className="py-6 text-sm text-muted-foreground">No pipeline data for this range.</div>;
  }
  // Order known stages first (pipeline order), then any extras as-seen.
  entries.sort((a, b) => {
    const ai = STAGE_ORDER.indexOf(a[0]);
    const bi = STAGE_ORDER.indexOf(b[0]);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });
  const max = Math.max(...entries.map(([, v]) => v), 1);
  return (
    <ol className="space-y-1.5">
      {entries.map(([key, value]) => {
        const pct = Math.round((value / max) * 100);
        const isReject = key.startsWith("rejected");
        const clickable = onSelectStage != null && key in CLICKABLE_STAGES && value > 0;
        const RowTag = clickable ? "button" : "div";
        return (
          <li key={key}>
            <RowTag
              {...(clickable ? { onClick: () => onSelectStage!(key), type: "button" as const } : {})}
              className={cn(
                "group flex w-full items-center gap-2 rounded-md px-1 py-0.5 text-left",
                clickable &&
                  "cursor-pointer hover:bg-muted focus-visible:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              )}
            >
              <div className="relative h-6 min-w-0 flex-1 overflow-hidden rounded bg-muted/40">
                <div
                  className={cn(
                    "absolute inset-y-0 left-0 rounded",
                    isReject ? "bg-chart-2/60" : "bg-chart-4/60",
                  )}
                  style={{ width: `${Math.max(pct, 2)}%` }}
                  aria-hidden="true"
                />
                <div className="absolute inset-0 flex items-center px-2 text-xs">
                  <span className="truncate text-foreground">{STAGE_LABELS[key] ?? key}</span>
                </div>
              </div>
              <span className="w-16 shrink-0 text-right text-sm tabular-nums text-foreground">
                {value.toLocaleString()}
              </span>
            </RowTag>
          </li>
        );
      })}
    </ol>
  );
}