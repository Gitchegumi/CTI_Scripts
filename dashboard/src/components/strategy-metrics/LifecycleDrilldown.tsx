"use client";

/**
 * Lifecycle-events drill-down for the second-row executive-summary cards.
 *
 * The second row (Prime suppressed, Pullback entries, Continuation events,
 * Rejected mgmt, SL moves, TP extension, Avg R captured) is aggregated from the
 * Signal Journal, not the evaluated_opportunities table that backs
 * MetricDrilldown. This sheet lazily fetches the underlying journal records via
 * the lifecycle-events endpoint and renders their metric-specific `fields`
 * generically, mirroring MetricDrilldown's interaction (lazy load, symbol
 * filter, "Load more", explicit empty/error states).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { fmtVal, isObjectValue } from "./status";
import type { ReportFilters } from "@/hooks/useData";
import type { StrategyMetricLifecycleEvent } from "@/types";

const DRILLDOWN_LIMIT = 100;

/** Maps a second-row card to its lifecycle drill-down. */
export interface LifecycleCardSpec {
  metric: string;
  title: string;
  description: string;
}

export interface LifecycleDrilldownState {
  open: boolean;
  metric: string;
  title: string;
  description: string;
}

export const LIFECYCLE_DRILLDOWN_CLOSED: LifecycleDrilldownState = {
  open: false,
  metric: "",
  title: "",
  description: "",
};

export function LifecycleDrilldown({
  state,
  appliedFilters,
  onClose,
}: {
  state: LifecycleDrilldownState;
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
          {appliedFilters ? (
            <SheetDescription>
              {appliedFilters.start} → {appliedFilters.end}
              {appliedFilters.symbol ? ` · ${appliedFilters.symbol}` : ""}
            </SheetDescription>
          ) : (
            <SheetDescription>{state.description}</SheetDescription>
          )}
        </SheetHeader>

        {state.open && (
          <LifecycleBody
            key={state.metric}
            metric={state.metric}
            appliedFilters={appliedFilters}
            description={state.description}
          />
        )}
      </SheetContent>
    </Sheet>
  );
}

function LifecycleBody({
  metric,
  appliedFilters,
  description,
}: {
  metric: string;
  appliedFilters: ReportFilters | null;
  description: string;
}) {
  const [events, setEvents] = useState<StrategyMetricLifecycleEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [symbol, setSymbol] = useState("");
  const seq = useRef(0);

  const fetchPage = useCallback(
    async (offset: number) => {
      if (!appliedFilters) return [];
      const { getStrategyMetricLifecycleEvents } = await import("@/lib/api");
      return getStrategyMetricLifecycleEvents({
        ...appliedFilters,
        metric,
        limit: DRILLDOWN_LIMIT,
        offset,
      });
    },
    [appliedFilters, metric],
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
        if (active && mySeq === seq.current) setEvents(data);
      } catch (e) {
        if (active && mySeq === seq.current) {
          setError(e instanceof Error ? e.message : "Failed to load records");
          setEvents([]);
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
    const q = symbol.trim().toLowerCase();
    if (!q) return events;
    return events.filter((e) => e.symbol.toLowerCase().includes(q));
  }, [events, symbol]);

  const hasMore = events.length > 0 && events.length % DRILLDOWN_LIMIT === 0;

  const handleLoadMore = useCallback(async () => {
    if (loadingMore || !appliedFilters) return;
    setLoadingMore(true);
    try {
      const next = await fetchPage(events.length);
      setEvents((cur) => [...cur, ...next]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load more records");
    } finally {
      setLoadingMore(false);
    }
  }, [fetchPage, events.length, loadingMore, appliedFilters]);

  return (
    <div className="space-y-4 px-4 pb-8">
      <p className="text-sm text-muted-foreground">{description}</p>

      <Input
        placeholder="Filter by symbol"
        value={symbol}
        onChange={(e) => setSymbol(e.target.value)}
        className="h-8"
      />

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
            {visible.map((e) => (
              <li key={e.id} className="rounded-lg border border-border bg-card">
                <div className="flex flex-wrap items-center gap-2 px-3 py-2 text-sm">
                  <span className="font-medium text-foreground">{e.symbol || "—"}</span>
                  {e.lifecycle_role && (
                    <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                      {e.lifecycle_role}
                    </span>
                  )}
                  {e.direction && e.direction !== "none" && (
                    <span className="text-xs text-muted-foreground">{e.direction}</span>
                  )}
                  {e.signal_type && (
                    <span className="text-xs text-muted-foreground">{e.signal_type}</span>
                  )}
                  <span className="ml-auto text-xs text-muted-foreground">
                    {e.timestamp ? new Date(e.timestamp).toLocaleString() : "—"}
                  </span>
                </div>
                {e.fields.length > 0 && (
                  <dl className="grid grid-cols-1 gap-x-4 gap-y-2 border-t border-border px-3 py-2 text-xs sm:grid-cols-2">
                    {e.fields.map((f) => (
                      <FieldRow key={`${e.id}-${f.label}`} label={f.label} value={f.value} />
                    ))}
                  </dl>
                )}
              </li>
            ))}
          </ul>

          {hasMore && (
            <Button
              variant="outline"
              onClick={handleLoadMore}
              disabled={loadingMore}
              className="w-full"
            >
              {loadingMore ? <Loader2 className="size-4 animate-spin" /> : null}
              {loadingMore ? "Loading…" : `Load more (${events.length} loaded)`}
            </Button>
          )}
        </>
      )}
    </div>
  );
}

/** One label/value detail row; object/array values render as readable JSON. */
function FieldRow({ label, value }: { label: string; value: unknown }) {
  const isObject = isObjectValue(value);
  return (
    <div className={isObject ? "flex flex-col gap-0.5 sm:col-span-2" : "flex flex-col gap-0.5"}>
      <dt className="text-muted-foreground">{label}</dt>
      {isObject ? (
        <dd className="mt-0.5 w-full overflow-x-auto rounded bg-muted/50 p-2 font-mono whitespace-pre-wrap break-all text-foreground">
          {fmtVal(value)}
        </dd>
      ) : (
        <dd className="break-words tabular-nums text-foreground">{fmtVal(value)}</dd>
      )}
    </div>
  );
}
