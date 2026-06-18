/**
 * Journal label utilities — convert raw snake_case identifiers into
 * human-readable display text and determine whether a reached target
 * was the original take-profit or an extended target created by a
 * continuation management event.
 */

/**
 * Mapping of known stats-exclusion / lifecycle / management identifiers
 * to human-readable display labels.  Unknown identifiers fall back to
 * a generic title-case conversion.
 */
const LABEL_MAP: Record<string, string> = {
  // Stats-exclusion reasons
  duplicate_setup: "Duplicate setup",
  late_signal: "Late signal",
  stale_signal: "Stale signal",
  missing_entry_context: "Missing entry context",
  manual_invalidated: "Manually invalidated",
  continuation_management_event: "Continuation management event",

  // Lifecycle roles
  entry: "Entry",
  management: "Management",
  outcome: "Outcome",
  warning: "Warning",
  legacy_signal: "Legacy signal",

  // Management rejection reasons
  no_active_trade: "No active trade",
  management_disabled: "Management disabled",
  insufficient_progress: "Insufficient progress",
  risk_increase: "Risk increase",
  extension_cap_reached: "Extension cap reached",
  duplicate_management_event: "Duplicate management event",
  opposite_direction_continuation_warning: "Opposite direction warning",
  trade_closed_before_management: "Trade closed before management",

  // Management reasons
  accepted: "Accepted",

  // Managed result categories
  win: "Win",
  loss: "Loss",
  breakeven: "Breakeven",

  // Managed exit reasons
  tp_hit: "TP hit",
  sl_hit_with_loss: "SL hit (loss)",
  sl_hit_at_break_even: "SL hit (break even)",
  sl_hit_with_profit: "SL hit (profit)",
  manual_close_profit: "Manual close (profit)",
  manual_close_loss: "Manual close (loss)",
};

/**
 * Convert a raw snake_case identifier into a human-readable label.
 *
 * Known identifiers use an explicit mapping for consistency.  Unknown
 * identifiers are converted via a generic title-case fallback so the
 * UI never shows a raw `continuation_management_event`-style string.
 */
export function statsUseLabel(value?: string | null): string {
  if (!value) return "None";
  const key = value.trim().toLowerCase();
  if (LABEL_MAP[key]) return LABEL_MAP[key];
  return genericTitleCase(value);
}

/**
 * Generic snake_case → Title Case conversion (fallback for unknown identifiers).
 */
function genericTitleCase(value: string): string {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

/**
 * Determine whether a journal entry's reached target was the original
 * take-profit or an extended target created by a continuation management
 * event.
 *
 * Returns `"original"`, `"extended"`, or `null` when the target has not
 * been reached (or the data is insufficient to determine it).
 *
 * Logic: compare `current_take_profit` against `initial_take_profit`
 * (or `take_profit` when `initial_take_profit` is absent).  If the
 * current TP differs from the original, the target was extended.
 */
export function reachedTargetType(entry: {
  initial_take_profit?: number | null;
  take_profit?: number | null;
  current_take_profit?: number | null;
  outcome?: string | null;
  status?: string | null;
  trade_grade?: string | null;
  grade?: string | null;
}): "original" | "extended" | null {
  // Only meaningful when the trade reached TP
  const grade = (entry.trade_grade ?? entry.grade ?? "").toUpperCase();
  const outcome = (entry.outcome ?? "").toLowerCase();
  const reachedTP =
    grade === "TP_HIT" ||
    outcome === "tp" ||
    outcome === "manually_closed" && grade === "TP_HIT";

  if (!reachedTP) return null;

  const originalTP = entry.initial_take_profit ?? entry.take_profit;
  const currentTP = entry.current_take_profit;

  if (originalTP == null || currentTP == null) return "original";

  // If current TP differs from original, the target was extended
  if (Math.abs(currentTP - originalTP) > 1e-9) return "extended";

  return "original";
}

/**
 * Return a display label for the reached-target type.
 */
export function reachedTargetLabel(entry: Parameters<typeof reachedTargetType>[0]): string | null {
  const type = reachedTargetType(entry);
  if (type === null) return null;
  return type === "extended" ? "Extended target" : "Original target";
}