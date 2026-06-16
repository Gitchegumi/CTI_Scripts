"use client";

/**
 * Compact horizontal bar list for ranked diagnosis views (top blockers,
 * near-miss reasons). Renders as plain, SSR-safe, accessible markup with
 * tabular-aligned values; degrades to an empty-state message when there is no
 * data (spec 022 FR-020/FR-031).
 */
import { cn } from "@/lib/utils";

export interface BarListItem {
  label: string;
  value: number;
  /** Optional secondary text shown under the label. */
  hint?: string;
  /** Tailwind background color class for the bar fill. */
  barClassName?: string;
  /** Optional click handler (e.g. open the criterion drilldown). */
  onClick?: () => void;
}

export function BarList({
  items,
  emptyMessage = "No data for this range.",
  className,
}: {
  items: BarListItem[];
  emptyMessage?: string;
  className?: string;
}) {
  if (!items.length) {
    return <div className="py-6 text-sm text-muted-foreground">{emptyMessage}</div>;
  }
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <ul className={cn("space-y-1.5", className)}>
      {items.map((item) => {
        const pct = Math.round((item.value / max) * 100);
        const RowTag = item.onClick ? "button" : "div";
        return (
          <li key={item.label}>
            <RowTag
              {...(item.onClick ? { onClick: item.onClick, type: "button" as const } : {})}
              className={cn(
                "group flex w-full items-center gap-2 rounded-md px-1 py-0.5 text-left",
                item.onClick && "cursor-pointer hover:bg-muted focus-visible:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              )}
            >
              <div className="relative h-6 flex-1 overflow-hidden rounded bg-muted/40">
                <div
                  className={cn("absolute inset-y-0 left-0 rounded", item.barClassName ?? "bg-chart-4/70")}
                  style={{ width: `${pct}%` }}
                  aria-hidden="true"
                />
                <div className="absolute inset-0 flex items-center px-2 text-xs">
                  <span className="truncate text-foreground">{item.label}</span>
                </div>
              </div>
              <span className="w-10 shrink-0 text-right text-sm tabular-nums text-foreground">
                {item.value.toLocaleString()}
              </span>
            </RowTag>
            {item.hint && <div className="px-2 text-xs text-muted-foreground">{item.hint}</div>}
          </li>
        );
      })}
    </ul>
  );
}
