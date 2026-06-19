"use client";

/**
 * Opportunity explorer (spec 022 US5).
 *
 * Browses the evaluated opportunities in bounded pages — it renders only what
 * has been loaded and offers "Load more" up to the evaluated total, never
 * fetching the full set at once (FR-021/SC-006). Supports a client-side search
 * over the loaded page and row expansion to the full criteria list (FR-022).
 */
import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Loader2, Search } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { StatusBadge, DecisionBadge, passStatus, CriterionMeasure } from "./status";
import type { StrategyMetricOpportunity } from "@/types";

export function OpportunityExplorer({
  opportunities,
  totalEvaluated,
  loadingMore,
  onLoadMore,
}: {
  opportunities: StrategyMetricOpportunity[];
  totalEvaluated: number;
  loadingMore: boolean;
  onLoadMore: () => void;
}) {
  const [query, setQuery] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return opportunities;
    return opportunities.filter(
      (o) =>
        o.symbol.toLowerCase().includes(q) ||
        o.final_decision.toLowerCase().includes(q) ||
        (o.decision_reason ?? "").toLowerCase().includes(q),
    );
  }, [opportunities, query]);

  const hasMore = opportunities.length < totalEvaluated;

  return (
    <Card aria-label="Opportunity explorer">
      <CardHeader className="flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle className="text-sm">Opportunity explorer</CardTitle>
        <div className="relative w-56">
          <Search className="absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search symbol / decision / reason"
            aria-label="Search opportunities"
            className="h-8 pl-7"
          />
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {opportunities.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground">No evaluated opportunities for this range.</div>
        ) : visible.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground">No opportunities match “{query}”.</div>
        ) : (
          <ul className="space-y-1.5">
            {visible.map((o) => {
              const expanded = expandedId === o.id;
              return (
                <li key={o.id} className="rounded-lg border border-border bg-card">
                  <button
                    type="button"
                    onClick={() => setExpandedId(expanded ? null : o.id)}
                    aria-expanded={expanded}
                    className="flex w-full flex-wrap items-center gap-2 px-3 py-2 text-left text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {expanded ? <ChevronDown className="size-3.5 text-muted-foreground" /> : <ChevronRight className="size-3.5 text-muted-foreground" />}
                    <span className="font-medium text-foreground">{o.symbol}</span>
                    <DecisionBadge decision={o.final_decision} />
                    {o.near_miss ? <StatusBadge status="near-miss" /> : (
                      <span className="text-xs text-muted-foreground">{o.failed_criteria_count} failed</span>
                    )}
                    <span className="text-xs text-muted-foreground">{o.decision_reason}</span>
                    <span className="ml-auto text-xs text-muted-foreground">{new Date(o.evaluated_at).toLocaleString()}</span>
                  </button>
                  {expanded && (
                    <div className="border-t border-border px-3 py-2">
                      <ul className="space-y-1">
                        {o.criteria.map((c) => (
                          <li key={`${o.id}-${c.criterion_name}`} className="flex flex-wrap items-center gap-2 text-xs">
                            <StatusBadge status={passStatus(c.passed, o.near_miss)} />
                            <span className="text-foreground">{c.criterion_name}</span>
                            <CriterionMeasure
                              measured={c.measured_value}
                              operator={c.threshold_operator}
                              threshold={c.threshold_value}
                            />
                            {c.margin != null && <span className="text-muted-foreground">margin {c.margin}</span>}
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

        {hasMore && (
          <Button
            variant="outline"
            onClick={onLoadMore}
            disabled={loadingMore}
            className="w-full"
          >
            {loadingMore ? <Loader2 className="size-4 animate-spin" /> : null}
            {loadingMore ? "Loading…" : `Load more (${opportunities.length} / ${totalEvaluated})`}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
