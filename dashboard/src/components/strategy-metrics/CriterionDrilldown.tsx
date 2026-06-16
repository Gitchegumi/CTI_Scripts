"use client";

/**
 * Criterion drilldown (spec 022 US2).
 *
 * Opens as a right-side Sheet over the loaded report (preserving its context —
 * FR-030/SC-013). Lazily loads the opportunities that failed the selected
 * criterion via the criterion-scoped endpoint (FR-023), shows the per-criterion
 * measured/threshold/operator/expected-vs-actual/blocker detail failed-first
 * (FR-013/FR-014), supports in-drilldown filtering (FR-015), expansion to the
 * full criteria list (FR-016), and an explicit no-data state (FR-017).
 *
 * The body is keyed by criterion name so each selection mounts with fresh state;
 * all data fetching sets state only after an await (never synchronously in the
 * effect body).
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { StatusBadge, DecisionBadge, passStatus } from "./status";
import { formatPercent } from "@/lib/metrics-availability";
import type { ReportFilters } from "@/hooks/useData";
import type {
  StrategyCriterionSummary,
  StrategyMetricOpportunity,
  StrategyMetricsSummary,
} from "@/types";

const DRILLDOWN_LIMIT = 100;
const ANY = "any";

function fmtVal(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

interface InnerFilters {
  symbol: string;
  decision: string;
  signal_type: string;
  nearMiss: string; // any | near | clean
  blocker: string;
}

const EMPTY_FILTERS: InnerFilters = { symbol: "", decision: ANY, signal_type: "", nearMiss: ANY, blocker: "" };

export function CriterionDrilldown({
  criterionName,
  appliedFilters,
  summary,
  onClose,
}: {
  criterionName: string | null;
  appliedFilters: ReportFilters | null;
  summary: StrategyMetricsSummary | null;
  onClose: () => void;
}) {
  const criterionSummary = useMemo(
    () => summary?.criterion_summaries.find((c) => c.criterion_name === criterionName) ?? null,
    [summary, criterionName],
  );

  return (
    <Sheet open={criterionName !== null} onOpenChange={(open) => { if (!open) onClose(); }}>
      <SheetContent side="right" className="w-full gap-0 overflow-y-auto sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            {criterionName ?? "Criterion"}
            {criterionSummary?.layer && (
              <span className="rounded bg-muted px-1.5 py-0.5 text-xs font-normal text-muted-foreground">
                {criterionSummary.layer}
              </span>
            )}
          </SheetTitle>
          <SheetDescription>Opportunities that failed this criterion, most recent first.</SheetDescription>
        </SheetHeader>

        {criterionName !== null && (
          <DrilldownBody
            key={criterionName}
            criterionName={criterionName}
            appliedFilters={appliedFilters}
            criterionSummary={criterionSummary}
          />
        )}
      </SheetContent>
    </Sheet>
  );
}

function DrilldownBody({
  criterionName,
  appliedFilters,
  criterionSummary,
}: {
  criterionName: string;
  appliedFilters: ReportFilters | null;
  criterionSummary: StrategyCriterionSummary | null;
}) {
  const [opps, setOpps] = useState<StrategyMetricOpportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<InnerFilters>(EMPTY_FILTERS);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const seq = useRef(0);

  useEffect(() => {
    if (!appliedFilters) {
      return;
    }
    let active = true;
    const mySeq = ++seq.current;
    (async () => {
      const { getStrategyMetricOpportunities } = await import("@/lib/api");
      if (!active) return;
      setLoading(true);
      setError(null);
      try {
        const data = await getStrategyMetricOpportunities({
          ...appliedFilters,
          criterion: criterionName,
          limit: DRILLDOWN_LIMIT,
        });
        if (active && mySeq === seq.current) setOpps(data);
      } catch (e) {
        if (active && mySeq === seq.current) {
          setError(e instanceof Error ? e.message : "Failed to load criterion failures");
          setOpps([]);
        }
      } finally {
        if (active && mySeq === seq.current) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [criterionName, appliedFilters]);

  const visible = useMemo(() => {
    return opps.filter((o) => {
      if (filters.symbol && !o.symbol.toLowerCase().includes(filters.symbol.toLowerCase())) return false;
      if (filters.decision !== ANY && o.final_decision !== filters.decision) return false;
      if (filters.signal_type && !(o.strategy ?? "").toLowerCase().includes(filters.signal_type.toLowerCase())) return false;
      if (filters.nearMiss === "near" && !o.near_miss) return false;
      if (filters.nearMiss === "clean" && o.near_miss) return false;
      if (filters.blocker && !(o.decision_reason ?? "").toLowerCase().includes(filters.blocker.toLowerCase())) return false;
      return true;
    });
  }, [opps, filters]);

  const noData = !loading && criterionSummary != null && criterionSummary.evaluated_count === 0;

  return (
    <div className="space-y-4 px-4 pb-8">
      {criterionSummary && (
        <div className="grid grid-cols-3 gap-2 text-sm">
          <Stat label="Evaluated" value={criterionSummary.evaluated_count} />
          <Stat label="Pass" value={`${criterionSummary.pass_count} (${formatPercent(criterionSummary.pass_rate)})`} className="text-chart-1" />
          <Stat label="Fail" value={`${criterionSummary.fail_count} (${formatPercent(criterionSummary.fail_rate)})`} className="text-chart-2" />
          <Stat label="Near-miss" value={criterionSummary.near_miss_contribution} className="text-chart-3" />
          <Stat label="Avg miss" value={criterionSummary.average_failure_margin ?? "—"} />
          <Stat label="Incomplete" value={criterionSummary.incomplete_count} className="text-chart-3" />
        </div>
      )}

      <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
        <Input placeholder="Symbol" value={filters.symbol}
          onChange={(e) => setFilters((f) => ({ ...f, symbol: e.target.value }))} className="h-8" />
        <Select value={filters.decision} onValueChange={(v) => setFilters((f) => ({ ...f, decision: v }))}>
          <SelectTrigger className="h-8"><SelectValue placeholder="Decision" /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ANY}>Any decision</SelectItem>
            {["emitted", "rejected", "skipped", "indeterminate"].map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}
          </SelectContent>
        </Select>
        <Input placeholder="Signal type" value={filters.signal_type}
          onChange={(e) => setFilters((f) => ({ ...f, signal_type: e.target.value }))} className="h-8" />
        <Select value={filters.nearMiss} onValueChange={(v) => setFilters((f) => ({ ...f, nearMiss: v }))}>
          <SelectTrigger className="h-8"><SelectValue placeholder="Near miss" /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ANY}>Any</SelectItem>
            <SelectItem value="near">Near miss</SelectItem>
            <SelectItem value="clean">Clean reject</SelectItem>
          </SelectContent>
        </Select>
        <Input placeholder="Blocker" value={filters.blocker}
          onChange={(e) => setFilters((f) => ({ ...f, blocker: e.target.value }))} className="h-8" />
      </div>

      {loading ? (
        <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" /> Loading failures…
        </div>
      ) : error ? (
        <div className="rounded border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
      ) : noData ? (
        <div className="py-8 text-center text-sm text-muted-foreground">
          No opportunities evaluated this criterion in the selected range.
        </div>
      ) : visible.length === 0 ? (
        <div className="py-8 text-center text-sm text-muted-foreground">No failures match the current drilldown filters.</div>
      ) : (
        <ul className="space-y-2">
          {visible.map((o) => {
            const crit = o.criteria.find((c) => c.criterion_name === criterionName);
            const expanded = expandedId === o.id;
            return (
              <li key={o.id} className="rounded-lg border border-border bg-card">
                <div className="flex flex-wrap items-center gap-2 px-3 py-2 text-sm">
                  <span className="font-medium text-foreground">{o.symbol}</span>
                  <DecisionBadge decision={o.final_decision} />
                  {o.near_miss && <StatusBadge status="near-miss" />}
                  <span className="text-xs text-muted-foreground">{new Date(o.evaluated_at).toLocaleString()}</span>
                  <button
                    type="button"
                    onClick={() => setExpandedId(expanded ? null : o.id)}
                    aria-expanded={expanded}
                    className="ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {expanded ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
                    {expanded ? "Hide" : "All criteria"}
                  </button>
                </div>
                {crit && (
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1 border-t border-border px-3 py-2 text-xs md:grid-cols-4">
                    <Detail label="Measured" value={fmtVal(crit.measured_value)} />
                    <Detail label="Threshold" value={`${crit.threshold_operator} ${fmtVal(crit.threshold_value)}`} />
                    <Detail label="Actual pass" value={String(crit.passed)} />
                    <Detail label="Expected pass" value={crit.expected_pass == null ? "—" : String(crit.expected_pass)} />
                    <Detail label="Margin" value={crit.margin ?? "—"} />
                    <Detail label="Blocker" value={crit.reason || o.decision_reason || "—"} className="col-span-2 md:col-span-3" />
                  </div>
                )}
                {expanded && (
                  <div className="border-t border-border px-3 py-2">
                    <div className="mb-1 text-xs font-medium text-muted-foreground">All criteria</div>
                    <ul className="space-y-1">
                      {o.criteria.map((c) => (
                        <li key={`${o.id}-${c.criterion_name}`} className="flex items-center gap-2 text-xs">
                          <StatusBadge status={passStatus(c.passed, o.near_miss)} />
                          <span className="text-foreground">{c.criterion_name}</span>
                          <span className="text-muted-foreground">
                            {fmtVal(c.measured_value)} vs {c.threshold_operator} {fmtVal(c.threshold_value)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function Stat({ label, value, className }: { label: string; value: React.ReactNode; className?: string }) {
  return (
    <div className="rounded border border-border bg-background/40 px-2 py-1.5">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={`tabular-nums font-medium ${className ?? "text-foreground"}`}>{value}</div>
    </div>
  );
}

function Detail({ label, value, className }: { label: string; value: React.ReactNode; className?: string }) {
  return (
    <div className={className}>
      <span className="text-muted-foreground">{label}: </span>
      <span className="tabular-nums text-foreground">{value}</span>
    </div>
  );
}
