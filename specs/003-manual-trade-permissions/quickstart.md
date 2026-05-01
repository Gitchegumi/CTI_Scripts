# Quickstart: Manual Trade Permissions

## Prerequisites

- `JOURNAL_TOKEN` is configured for protected dashboard/manual-trade routes.
- TradeGumi backend API is reachable by the dashboard.
- Existing `.env` mode changes through `/api/config/mode` continue to work.

## Validation Steps

1. Start the backend and dashboard in the normal local or Docker workflow.
2. Authenticate to the dashboard and open `/`.
3. Set the bot mode to `alert_only`.
4. Confirm the main dashboard Trade History and `/manual-trades` show the same current-mode trade set after refresh.
5. On `/manual-trades`, add a manual trade with notes and tags.
6. Confirm the manual trade appears in the main dashboard Trade History within one normal refresh interval.
7. Edit every exposed field on the manual trade and confirm the dashboard and manual-trades page both show the updated values.
8. Delete the manual trade and confirm it disappears from both views.
9. In `alert_only`, edit a non-manual historical trade from the unified history.
10. Confirm the corrected values appear in both views and the original source trade is not deleted or converted into a manual record.
11. Switch to `demo` mode.
12. Confirm `alert_only` trades, overrides, notes, and tags do not appear in `demo` history.
13. In `demo`, confirm only notes and tags are editable.
14. Attempt to submit a protected trade-field change in `demo`; confirm the system rejects or ignores the protected change and communicates the outcome.
15. Save notes and tags in `demo`, refresh both views, and confirm only annotation fields changed.
16. Switch back to `alert_only` and confirm prior `alert_only` records and overrides reappear.
17. Verify any legacy records without mode metadata appear only in `alert_only`.
18. Export the current-mode agent-ready dataset from `/manual-trades`.
19. Confirm the export is valid JSON and includes `schema_version`, `generated_at`, `bot_mode`, `scope`, `summary`, `field_metadata`, `analysis_context`, and `records`.
20. Confirm exported records include notes, tags, source identity, displayed values, and override metadata where applicable.
21. Switch modes and repeat export; confirm the export contains only records associated with the newly current mode.

## Test Expectations

- Python tests cover schema migration, legacy defaulting to `alert_only`, current-mode filtering, duplicate identity merge, local override merge, annotation persistence, permission enforcement, and agent export schema/content.
- Dashboard validation covers mode-aware controls, read-only states, unified history loading, save/delete error handling, and agent export behavior.
