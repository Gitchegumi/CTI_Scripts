# Contract: Strategy Metrics Dashboard UI

## Route

`/strategy-metrics`

## Required Controls

- Date range selector with a sensible default of the last 7 days.
- Optional symbol filter.
- Toggle for summary view versus comparison view.
- Export action for the selected date range.

## Summary View

The page must show:

- Total evaluated opportunities.
- Emitted, rejected, skipped, and indeterminate counts.
- Near-miss count.
- Top three blockers by combined score.
- Criterion table with pass rate, fail rate, near-miss contribution, average failure margin, and incomplete count.
- Opportunity drill-down table with filters for near-miss and final decision.
- Empty-state messaging when no opportunities exist for the selected range.
- Data-quality warnings when criteria are missing or malformed.

## Comparison View

The page must show:

- Baseline date range and comparison date range.
- Delta in evaluated opportunities.
- Delta in emitted signals.
- Delta in near-misses.
- Changes in top blocker ranking.
- Clear indication when either period lacks enough data for meaningful comparison.

## Interaction Rules

- Diagnostics may identify review candidates but must not offer one-click threshold changes.
- Individual opportunity details must show all evaluated criteria and failed margins.
- The UI must distinguish "no evaluated opportunities" from "evaluated opportunities but no emitted signals".
- The dashboard must remain usable on desktop and mobile widths without overlapping controls or text.
