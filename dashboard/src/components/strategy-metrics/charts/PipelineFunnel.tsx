"use client";

/**
 * Pipeline funnel (evaluated → candidate → rules evaluated → emitted/rejected)
 * rendered as ordered, proportional stepped bars (spec 022 FR-019). SSR-safe,
 * labelled, and degrades to an empty-state when no stages are present.
 *
 * Labels render above bars in a stacked layout so they never overlap bar content,
 * regardless of how narrow the bar becomes at the tail of the funnel.
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
  rejected: "Rejected",
  rejected_count: "Rejected",
};

const STAGE_ORDER = [
  "total_evaluated",
  "candidate",
  "candidates",
  "signal_rules_evaluated",
  "rules_evaluated",
  "emitted",
  "emitted_count",
  "rejected",
  "rejected_count",
];

export function PipelineFunnel({ funnel }: { funnel: Record<string, number> | undefined }) {
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
    <ol className="space-y-3">
      {entries.map(([key, value]) => {
        const pct = Math.round((value / max) * 100);
        const isReject = key.startsWith("rejected");
        return (
          <li key={key} className="flex flex-col gap-1">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">
                {STAGE_LABELS[key] ?? key}
              </span>
              <span className="text-xs tabular-nums text-foreground">
                {value.toLocaleString()}
              </span>
            </div>
            <div className="relative h-6 w-full overflow-hidden rounded bg-muted/40">
              <div
                className={cn("absolute inset-y-0 left-0 rounded", isReject ? "bg-chart-2/60" : "bg-chart-4/60")}
                style={{ width: `${Math.max(pct, 2)}%` }}
                aria-hidden="true"
              />
            </div>
          </li>
        );
      })}
    </ol>
  );
}