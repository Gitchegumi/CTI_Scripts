"use client";

/**
 * Failure diagnosis section (spec 022 US4, FR-019/FR-020).
 *
 * Surfaces data already computed server-side: ranked top blockers, a clickable
 * criterion pass/fail table (opens the drilldown), near-miss reason counts, and
 * the pipeline funnel. Everything degrades gracefully when a range has no data.
 */
import { ChevronRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { BarList, type BarListItem } from "./charts/BarList";
import { PipelineFunnel } from "./charts/PipelineFunnel";
import { formatPercent } from "@/lib/metrics-availability";
import type { StrategyMetricsSummary } from "@/types";

function countMapToItems(
  map: Record<string, number> | undefined,
  barClassName: string,
  onClick?: (key: string) => void,
): BarListItem[] {
  return Object.entries(map ?? {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([label, value]) => ({
      label,
      value,
      barClassName,
      onClick: onClick ? () => onClick(label) : undefined,
    }));
}

export function FailureDiagnosis({
  summary,
  onSelectCriterion,
}: {
  summary: StrategyMetricsSummary | null;
  onSelectCriterion: (criterionName: string) => void;
}) {
  const blockers: BarListItem[] = (summary?.top_blockers ?? []).slice(0, 8).map((b) => ({
    label: b.criterion_name,
    value: b.blocked_count,
    hint: `impact ${b.combined_score.toFixed(2)}`,
    barClassName: "bg-chart-2/60",
    onClick: () => onSelectCriterion(b.criterion_name),
  }));
  const nearMiss = countMapToItems(summary?.near_miss_reason_counts, "bg-chart-3/60");
  const criteria = summary?.criterion_summaries ?? [];

  return (
    <section aria-label="Failure diagnosis" className="space-y-4">
      <h2 className="text-sm font-semibold text-muted-foreground">Failure diagnosis</h2>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader><CardTitle className="text-sm">Top blockers by impact</CardTitle></CardHeader>
          <CardContent>
            <BarList items={blockers} emptyMessage="No blockers ranked for this range." />
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm">Near-miss reasons</CardTitle></CardHeader>
          <CardContent>
            <BarList items={nearMiss} emptyMessage="No near misses for this range." />
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm">Pipeline funnel</CardTitle></CardHeader>
          <CardContent>
            <PipelineFunnel funnel={summary?.pipeline_funnel} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-sm">Criterion pass / fail (click a row to drill in)</CardTitle></CardHeader>
        <CardContent className="px-0">
          {criteria.length ? (
            <div className="max-h-96 overflow-auto">
              <Table>
                <TableHeader className="sticky top-0 bg-card">
                  <TableRow>
                    <TableHead>Criterion</TableHead>
                    <TableHead>Layer</TableHead>
                    <TableHead className="text-right">Pass</TableHead>
                    <TableHead className="text-right">Fail</TableHead>
                    <TableHead className="text-right">Near-miss</TableHead>
                    <TableHead className="text-right">Avg miss</TableHead>
                    <TableHead className="text-right">Incomplete</TableHead>
                    <TableHead aria-label="Open drilldown" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {criteria.map((c) => (
                    <TableRow
                      key={c.criterion_name}
                      tabIndex={0}
                      role="button"
                      aria-label={`Drill into ${c.criterion_name}`}
                      className="cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      onClick={() => onSelectCriterion(c.criterion_name)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onSelectCriterion(c.criterion_name);
                        }
                      }}
                    >
                      <TableCell className="font-medium text-foreground">{c.criterion_name}</TableCell>
                      <TableCell className="text-muted-foreground">{c.layer || "—"}</TableCell>
                      <TableCell className="text-right tabular-nums text-chart-1">
                        {c.pass_count} ({formatPercent(c.pass_rate)})
                      </TableCell>
                      <TableCell className="text-right tabular-nums text-chart-2">
                        {c.fail_count} ({formatPercent(c.fail_rate)})
                      </TableCell>
                      <TableCell className="text-right tabular-nums text-chart-3">{c.near_miss_contribution}</TableCell>
                      <TableCell className="text-right tabular-nums text-muted-foreground">
                        {c.average_failure_margin ?? "—"}
                      </TableCell>
                      <TableCell className="text-right tabular-nums text-chart-3">{c.incomplete_count}</TableCell>
                      <TableCell className="text-right"><ChevronRight className="size-4 text-muted-foreground" /></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="px-6 py-6 text-sm text-muted-foreground">No criterion diagnostics in this range.</div>
          )}
        </CardContent>
      </Card>
    </section>
  );
}
