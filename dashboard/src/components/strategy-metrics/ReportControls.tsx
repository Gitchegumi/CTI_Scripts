"use client";

/**
 * Report controls for the strategy-metrics dashboard (spec 022 US1).
 *
 * Filters are edited as local *draft* state and never trigger a fetch on change.
 * The report runs only when "Apply Filters" is activated (FR-001/FR-002). The
 * control is disabled while a fetch is in flight (FR-003/FR-004), the date range
 * is validated before running (FR-006), and a "pending changes" hint appears
 * when the draft differs from the applied filters (FR-035).
 */
import { useMemo, useState } from "react";
import { Play, Download, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { ReportFilters } from "@/hooks/useData";

const DECISION_OPTIONS = ["emitted", "rejected", "skipped", "indeterminate"] as const;
const ANY = "any";

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function defaultStart(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return isoDate(d);
}

function normalize(draft: ReportFilters): ReportFilters {
  return {
    start: draft.start,
    end: draft.end,
    symbol: draft.symbol || undefined,
    strategy: draft.strategy || undefined,
    signal_type: draft.signal_type || undefined,
    decision: draft.decision || undefined,
    first_blocker: draft.first_blocker || undefined,
  };
}

function sameFilters(a: ReportFilters | null, b: ReportFilters): boolean {
  if (!a) return false;
  return JSON.stringify(normalize(a)) === JSON.stringify(normalize(b));
}

export function ReportControls({
  appliedFilters,
  loading,
  onApply,
  onExport,
}: {
  appliedFilters: ReportFilters | null;
  loading: boolean;
  onApply: (filters: ReportFilters) => void;
  onExport: () => void;
}) {
  const [draft, setDraft] = useState<ReportFilters>(
    () =>
      appliedFilters ?? {
        start: defaultStart(7),
        end: isoDate(new Date()),
      },
  );

  const set = <K extends keyof ReportFilters>(key: K, value: string) =>
    setDraft((d) => ({ ...d, [key]: value }));

  const rangeError = draft.start && draft.end && draft.start > draft.end
    ? "Start date must be on or before the end date."
    : null;

  const dirty = useMemo(() => !sameFilters(appliedFilters, draft), [appliedFilters, draft]);

  function handleApply() {
    if (rangeError || loading) return;
    onApply(normalize(draft));
  }

  return (
    <section aria-label="Report controls" className="rounded-lg border border-border bg-card p-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
        <Field label="Start">
          <Input type="date" value={draft.start} max={draft.end || undefined}
            onChange={(e) => set("start", e.target.value)} aria-invalid={!!rangeError} />
        </Field>
        <Field label="End">
          <Input type="date" value={draft.end} min={draft.start || undefined}
            onChange={(e) => set("end", e.target.value)} aria-invalid={!!rangeError} />
        </Field>
        <Field label="Symbol">
          <Input value={draft.symbol ?? ""} placeholder="All"
            onChange={(e) => set("symbol", e.target.value.toUpperCase())} />
        </Field>
        <Field label="Strategy">
          <Input value={draft.strategy ?? ""} placeholder="All"
            onChange={(e) => set("strategy", e.target.value)} />
        </Field>
        <Field label="Signal type">
          <Input value={draft.signal_type ?? ""} placeholder="All"
            onChange={(e) => set("signal_type", e.target.value)} />
        </Field>
        <Field label="Decision">
          <Select value={draft.decision || ANY}
            onValueChange={(v) => set("decision", v === ANY ? "" : v)}>
            <SelectTrigger className="w-full"><SelectValue placeholder="All" /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>All</SelectItem>
              {DECISION_OPTIONS.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}
            </SelectContent>
          </Select>
        </Field>
        <Field label="First blocker">
          <Input value={draft.first_blocker ?? ""} placeholder="All"
            onChange={(e) => set("first_blocker", e.target.value)} />
        </Field>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button onClick={handleApply} disabled={loading || !!rangeError} aria-keyshortcuts="Enter">
          {loading ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
          {loading ? "Running…" : "Apply Filters"}
        </Button>
        <Button variant="outline" onClick={onExport} disabled={loading}>
          <Download className="size-4" />
          Export
        </Button>
        {rangeError && (
          <span role="alert" className="text-sm text-destructive">{rangeError}</span>
        )}
        {!rangeError && dirty && appliedFilters && (
          <span className="text-xs text-chart-3">Filters changed — apply to update the report.</span>
        )}
      </div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-xs text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}
