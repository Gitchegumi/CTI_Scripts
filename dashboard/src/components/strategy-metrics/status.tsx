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

/** Format a measured/threshold value; objects are pretty-printed JSON (issue #152). */
export function fmtVal(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v, null, 2);
  return String(v);
}

/** Returns true when the value is an object that needs preformatted rendering. */
export function isObjectValue(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === "object";
}

/**
 * Renders a criterion's "measured vs operator threshold" detail (issue #152).
 *
 * Scalar values stay on one inline line. When either side is an object, the pair
 * is rendered in a readable preformatted block instead of squashed onto a single
 * line of JSON — shared across every drill-down so the layout never drifts.
 */
export function CriterionMeasure({
  measured,
  operator,
  threshold,
}: {
  measured: unknown;
  operator: string;
  threshold: unknown;
}) {
  if (isObjectValue(measured) || isObjectValue(threshold)) {
    return (
      <div className="mt-1 w-full overflow-x-auto rounded bg-muted/50 p-2 font-mono text-xs whitespace-pre-wrap break-all">
        <span className="text-muted-foreground">measured: </span>
        {fmtVal(measured)}
        {"\n"}
        <span className="text-muted-foreground">{operator} threshold: </span>
        {fmtVal(threshold)}
      </div>
    );
  }
  return (
    <span className="text-muted-foreground">
      {fmtVal(measured)} vs {operator} {fmtVal(threshold)}
    </span>
  );
}
