"use client";

/**
 * Generic metric drill-down (issue #144).
 *
 * Opens as a right-side Sheet — the same interaction pattern as
 * CriterionDrilldown — and lazily fetches the opportunities behind any
 * aggregate metric (summary card, near-miss reason, pipeline funnel stage).
 *
 * The component accepts a `metricTitle`, `metricDescription`, the page-level
 * `appliedFilters`, and an optional set of extra API params (e.g.
 * `decision=emitted`, `near_miss=true`) that scope the fetch to the clicked
 * metric. It supports in-drilldown filtering, pagination via "Load more",
 * and explicit empty/error states.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { StatusBadge, DecisionBadge, passStatus } from "./status";
import type { ReportFilters } from "@/hooks/useData";
import type { StrategyMetricOpportunity } from "@/types";

const DRILLDOWN_LIMIT = 100;
const ANY = "any";

function fmtVal(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

/** Extra params forwarded to getStrategyMetricOpportunities beyond the page filters. */
export interface MetricExtraParams {
  decision?: string;
  near_miss?: boolean;
  near_miss_reason?: string;
  first_blocker?: string;
  criterion?: string;
}

interface InnerFilters {
  symbol: string;
  decision: string;
  signal_type: string;
  nearMiss: string; // any | near | clean
  blocker: string;
}

const EMPTY_FILTERS: InnerFilters = {
  symbol: "",
  decision: ANY,
  signal_type: "",
  nearMiss: ANY,
  blocker: "",
};

export interface MetricDrilldownState {
  open: boolean;
  title: string;
  description: string;
  extraParams: MetricExtraParams;
}

export const METRIC_DRILLDOWN_CLOSED: MetricDrilldownState = {
  open: false,
  title: "",
  description: "",
  extraParams: {},
};

export function MetricDrilldown({
  state,
  appliedFilters,
  onClose,
}: {
  state: MetricDrilldownState;
  appliedFilters: ReportFilters | null;
  onClose: () => void;
}) {
  return (
    <Sheet
      open={state.open}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <SheetContent side="right" className="w-full gap-0 overflow-y-auto sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle>{state.title}</SheetTitle>
          {appliedFilters && (
            <SheetDescription>
              {appliedFilters.start} → {appliedFilters.end}
              {appliedFilters.symbol ? ` · ${appliedFilters.symbol}` : ""}
              {appliedFilters.strategy ? ` · ${appliedFilters.strategy}` : ""}
              {appliedFilters.signal_type ? ` · ${appliedFilters.signal_type}` : ""}
            </SheetDescription>
          )}
          {!appliedFilters && <SheetDescription>{state.description}</SheetDescription>}
        </SheetHeader>

        {state.open && (
          <DrilldownBody
            key={state.title}
            extraParams={state.extraParams}
            appliedFilters={appliedFilters}
            description={state.description}
          />
        )}
      </SheetContent>
    </Sheet>
  );
}

function DrilldownBody({
  extraParams,
  appliedFilters,
  description,
}: {
  extraParams: MetricExtraParams;
  appliedFilters: ReportFilters | null;
  description: string;
}) {
  const [opps, setOpps] = useState<StrategyMetricOpportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<InnerFilters>(EMPTY_FILTERS);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const seq = useRef(0);

  const fetchPage = useCallback(
    async (offset: number) => {
      if (!appliedFilters) return [];
      const { getStrategyMetricOpportunities } = await import("@/lib/api");
      return getStrategyMetricOpportunities({
        ...appliedFilters,
        ...extraParams,
        limit: DRILLDOWN_LIMIT,
        offset,
      });
    },
    [appliedFilters, extraParams],
  );

  useEffect(() => {
    if (!appliedFilters) return;
    let active = true;
    const mySeq = ++seq.current;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchPage(0);
        if (active && mySeq === seq.current) setOpps(data);
      } catch (e) {
        if (active && mySeq === seq.current) {
          setError(e instanceof Error ? e.message : "Failed to load records");
          setOpps([]);
        }
      } finally {
        if (active && mySeq === seq.current) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [fetchPage]);

  const visible = useMemo(() => {
    return opps.filter((o) => {
      if (filters.symbol && !o.symbol.toLowerCase().includes(filters.symbol.toLowerCase()))
        return false;
      if (filters.decision !== ANY && o.final_decision !== filters.decision) return false;
      if (filters.signal_type && !(o.strategy ?? "").toLowerCase().includes(filters.signal_type.toLowerCase()))
        return false;
      if (filters.nearMiss === "near" && !o.near_miss) return false;
      if (filters.nearMiss === "clean" && o.near_miss) return false;
      if (filters.blocker && !(o.decision_reason ?? "").toLowerCase().includes(filters.blocker.toLowerCase()))
        return false;
      return true;
    });
  }, [opps, filters]);

  const hasMore = opps.length > 0 && opps.length % DRILLDOWN_LIMIT === 0;

  const handleLoadMore = useCallback(async () => {
    if (loadingMore || !appliedFilters) return;
    setLoadingMore(true);
    try {
      const next = await fetchPage(opps.length);
      setOpps((cur) => [...cur, ...next]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load more records");
    } finally {
      setLoadingMore(false);
    }
  }, [fetchPage, opps.length, loadingMore, appliedFilters]);

  return (
    <div className="space-y-4 px-4 pb-8">
      <p className="text-sm text-muted-foreground">{description}</p>

      {/* In-drilldown filters */}
      <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
        <Input
          placeholder="Symbol"
          value={filters.symbol}
          onChange={(e) => setFilters((f) => ({ ...f, symbol: e.target.value }))}
          className="h-8"
        />
        <Select
          value={filters.decision}
          onValueChange={(v) => setFilters((f) => ({ ...f, decision: v }))}
        >
          <SelectTrigger className="h-8">
            <SelectValue placeholder="Decision" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ANY}>Any decision</SelectItem>
            {["emitted", "rejected", "skipped", "indeterminate"].map((d) => (
              <SelectItem key={d} value={d}>
                {d}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          placeholder="Signal type"
          value={filters.signal_type}
          onChange={(e) => setFilters((f) => ({ ...f, signal_type: e.target.value }))}
          className="h-8"
        />
        <Select
          value={filters.nearMiss}
          onValueChange={(v) => setFilters((f) => ({ ...f, nearMiss: v }))}
        >
          <SelectTrigger className="h-8">
            <SelectValue placeholder="Near miss" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ANY}>Any</SelectItem>
            <SelectItem value="near">Near miss</SelectItem>
            <SelectItem value="clean">Clean reject</SelectItem>
          </SelectContent>
        </Select>
        <Input
          placeholder="Blocker"
          value={filters.blocker}
          onChange={(e) => setFilters((f) => ({ ...f, blocker: e.target.value }))}
          className="h-8"
        />
      </div>

      {loading ? (
        <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" /> Loading…
        </div>
      ) : error ? (
        <div className="rounded border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      ) : visible.length === 0 ? (
        <div className="py-8 text-center text-sm text-muted-foreground">
          No records matched the selected metric/filter combination.
        </div>
      ) : (
        <>
          <ul className="space-y-2">
            {visible.map((o) => {
              const expanded = expandedId === o.id;
              return (
                <li key={o.id} className="rounded-lg border border-border bg-card">
                  <div className="flex flex-wrap items-center gap-2 px-3 py-2 text-sm">
                    <span className="font-medium text-foreground">{o.symbol}</span>
                    <DecisionBadge decision={o.final_decision} />
                    {o.near_miss && <StatusBadge status="near-miss" />}
                    <span className="text-xs text-muted-foreground">
                      {o.decision_reason}
                    </span>
                    <span className="ml-auto text-xs text-muted-foreground">
                      {new Date(o.evaluated_at).toLocaleString()}
                    </span>
                    <button
                      type="button"
                      onClick={() => setExpandedId(expanded ? null : o.id)}
                      aria-expanded={expanded}
                      className="ml-2 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      {expanded ? (
                        <ChevronDown className="size-3" />
                      ) : (
                        <ChevronRight className="size-3" />
                      )}
                      {expanded ? "Hide" : "Criteria"}
                    </button>
                  </div>
                  {expanded && (
                    <div className="border-t border-border px-3 py-2">
                      <ul className="space-y-1">
                        {o.criteria.map((c) => (
                          <li
                            key={`${o.id}-${c.criterion_name}`}
                            className="flex flex-wrap items-center gap-2 text-xs"
                          >
                            <StatusBadge status={passStatus(c.passed, o.near_miss)} />
                            <span className="text-foreground">{c.criterion_name}</span>
                            <span className="text-muted-foreground">
                              {fmtVal(c.measured_value)} vs {c.threshold_operator}{" "}
                              {fmtVal(c.threshold_value)}
                            </span>
                            {c.margin != null && (
                              <span className="text-muted-foreground">
                                margin {c.margin}
                              </span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>

          {hasMore && (
            <Button
              variant="outline"
              onClick={handleLoadMore}
              disabled={loadingMore}
              className="w-full"
            >
              {loadingMore ? <Loader2 className="size-4 animate-spin" /> : null}
              {loadingMore ? "Loading…" : `Load more (${opps.length} loaded)`}
            </Button>
          )}
        </>
      )}
    </div>
  );
}