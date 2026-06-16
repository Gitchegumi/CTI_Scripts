/**
 * Helpers for the executive-summary "real zero vs unavailable" distinction
 * (spec 022 US3, FR-008/FR-009). A metric value of `null`/`undefined`/NaN is
 * treated as *unavailable* (hidden or marked), while the number `0` is a real,
 * displayable zero. Components must bind every card to a backing field and use
 * these helpers so a missing metric is never shown as a misleading `0`.
 */

export type MetricValue = number | null | undefined;

export const UNAVAILABLE_LABEL = "Unavailable";
export const UNAVAILABLE_TEXT = "—";

export interface MetricDisplay {
  /** True when the backing data supplied a usable number. */
  available: boolean;
  /** True only for a genuine zero value (available && value === 0). */
  isZero: boolean;
  /** Pre-formatted text to render (`—` when unavailable). */
  text: string;
  /** The raw numeric value when available, else null. */
  value: number | null;
}

/** Format an integer-ish metric with thousands separators. */
export function formatNumber(value: number): string {
  return value.toLocaleString();
}

/** Format a 0..1 rate as a whole percentage (e.g. 0.42 -> "42%"). */
export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

/** Resolve how a single summary metric should be displayed. */
export function metricDisplay(value: MetricValue): MetricDisplay {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return { available: false, isZero: false, text: UNAVAILABLE_TEXT, value: null };
  }
  return { available: true, isZero: value === 0, text: formatNumber(value), value };
}

/** Whether a metric should be rendered at all (used to hide unavailable cards). */
export function isMetricAvailable(value: MetricValue): boolean {
  return metricDisplay(value).available;
}
