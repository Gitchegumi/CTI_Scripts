# Contract: Dashboard Managed Lifecycle

## Journal View

The journal dashboard must make lifecycle role visible without requiring raw JSON inspection.

Required display states:

- Entry row: pullback-originated trade entry with current SL/TP state.
- Management row: continuation event with accepted/rejected status and old/new SL/TP values when available.
- Warning row: opposite-direction continuation warning during an active trade.
- Outcome state: final managed result category and exit reason.

## Strategy Metrics View

The strategy metrics dashboard must expose managed lifecycle counters alongside existing signal counts:

- Pullback entries opened
- Continuation management observed
- Accepted and rejected continuation management events
- TP extensions
- SL tightenings
- Break-even moves
- Profit-protected SL wins
- Opposite-direction warnings
- Average R captured
- Managed vs original result comparison

## UX Requirements

- Existing filters and export controls remain usable.
- Lifecycle labels must be concise and scannable.
- Blank legacy fields must not render as errors.
- Management event details should be visible in row detail or equivalent existing detail surface.
