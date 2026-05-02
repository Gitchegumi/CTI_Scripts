# Contract: Dashboard UI

## Shared Trade History Behavior

- The main dashboard Trade History and `/manual-trades` page display the same current-mode unified trade history.
- Both views refresh within the existing trade-history polling cadence.
- Both views show only records, annotations, and overrides associated with the current bot mode.
- Legacy records without mode metadata appear only in `alert_only`.

## `/manual-trades` Page

### `alert_only` Mode

- Shows all current-mode historical trades from the unified history.
- Shows an Add Trade action.
- Allows every exposed field to be edited for every displayed trade.
- Allows delete only for manually created trades and only after confirmation.
- For non-manual historical trades, full-field edits are saved as local overrides.
- Displays when a record contains local overrides so the user can recognize corrected data.

### Non-`alert_only` Modes

- Shows all current-mode historical trades from the unified history.
- Hides or disables Add Trade.
- Allows notes and tags to be edited.
- Renders all non-annotation trade fields as read-only.
- Hides or disables delete for every trade.
- Communicates clearly when a attempted save includes protected fields.

## Main Dashboard Trade History

- Uses the same unified current-mode trade history data as `/manual-trades`.
- Displays locally overridden values for the current mode.
- Does not show records, overrides, notes, or tags from other modes.
- Maintains existing grouping, sorting, and summary behavior unless the unified data contract requires a field mapping.

## Empty, Loading, and Error States

- Loading state appears while current-mode history is being fetched.
- Empty state says no trades exist for the current mode.
- Upstream/API failures appear as a user-visible error and must not be presented as a valid empty history.
- Unauthorized access to protected manual-trade data returns the existing login/unauthorized behavior.

## Permission Indicators

Each displayed trade includes enough permission state for the UI to decide:

- Whether all fields are editable.
- Whether notes/tags are editable.
- Whether delete is available.
- Whether the record is manually created.
- Whether the displayed record includes local overrides.

The UI may derive presentation from backend permissions, but backend responses remain the authority for mutation outcomes.

## Agent Export

- `/manual-trades` exposes an export action for the current bot mode.
- The export action returns or downloads structured JSON suitable for LLM and agent workflows.
- The UI makes clear that exports are mode-isolated.
- Export errors are shown as user-visible failures, not as empty exports.
- The export action must not include records from other bot modes.
