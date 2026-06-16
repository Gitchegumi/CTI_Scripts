/**
 * Status indicators for the strategy-metrics dashboard.
 *
 * Every status pairs a color with a non-color cue (icon + text label) so the
 * page stays interpretable without color perception (spec 022 FR-026, SC-011).
 */
import { Check, X, AlertTriangle, Ban, Minus, CircleDashed } from "lucide-react";
import { cn } from "@/lib/utils";

export type CriterionStatus = "pass" | "fail" | "near-miss" | "blocker" | "incomplete" | "unavailable";

const STATUS_STYLES: Record<
  CriterionStatus,
  { label: string; icon: React.ComponentType<{ className?: string }>; className: string }
> = {
  pass: { label: "Pass", icon: Check, className: "text-chart-1 border-chart-1/40 bg-chart-1/10" },
  fail: { label: "Fail", icon: X, className: "text-chart-2 border-chart-2/40 bg-chart-2/10" },
  "near-miss": { label: "Near miss", icon: AlertTriangle, className: "text-chart-3 border-chart-3/40 bg-chart-3/10" },
  blocker: { label: "Blocker", icon: Ban, className: "text-chart-2 border-chart-2/40 bg-chart-2/10" },
  incomplete: { label: "Incomplete", icon: CircleDashed, className: "text-chart-3 border-chart-3/40 bg-chart-3/10" },
  unavailable: { label: "Unavailable", icon: Minus, className: "text-muted-foreground border-border bg-muted/40" },
};

export function StatusBadge({
  status,
  label,
  className,
}: {
  status: CriterionStatus;
  label?: string;
  className?: string;
}) {
  const style = STATUS_STYLES[status];
  const Icon = style.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-xs font-medium",
        style.className,
        className,
      )}
    >
      <Icon className="size-3" aria-hidden="true" />
      {label ?? style.label}
    </span>
  );
}

const DECISION_STATUS: Record<string, CriterionStatus> = {
  emitted: "pass",
  rejected: "fail",
  skipped: "incomplete",
  indeterminate: "unavailable",
};

/** Badge for an opportunity's final decision, colored + labelled consistently. */
export function DecisionBadge({ decision }: { decision: string }) {
  const status = DECISION_STATUS[decision] ?? "unavailable";
  return <StatusBadge status={status} label={decision} />;
}

/** Map a criterion's boolean pass state (true/false/null) to a status. */
export function passStatus(passed: boolean | null | undefined, nearMiss = false): CriterionStatus {
  if (passed === true) return "pass";
  if (passed === false) return nearMiss ? "near-miss" : "fail";
  return "incomplete";
}
