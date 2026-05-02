# Data Model: Manual Trade Permissions

## Historical Trade

Represents one trade shown in current-mode unified history.

### Fields

- `id`: Canonical display identifier, stable across dashboard and manual-trades views.
- `source`: Origin system for the base trade, such as `manual` or `execution_history`.
- `source_trade_id`: Source-owned trade identifier when available.
- `bot_mode`: Mode that owns this record's displayed data: `alert_only`, `demo`, or `live`.
- `is_manual`: Whether the trade was manually created by the user.
- `symbol`: Trade symbol.
- `direction`: `long`/`short` in manual forms and mapped to `BUY`/`SELL` for dashboard display where needed.
- `entry_price`, `exit_price`: Entry and exit prices.
- `entry_time`, `exit_time`: ISO-8601 timestamps.
- `volume`: Trade size when known.
- `status`: `open` or `closed`.
- `fees`: Financing or fee value when known.
- `pnl`, `pnl_percent`: Profit/loss values.
- `notes`: Mode-scoped annotation text.
- `tags`: Mode-scoped tag list.
- `created_at`, `updated_at`: Local timestamps for user-maintained data.
- `has_overrides`: Whether displayed values include local corrected fields.

### Validation Rules

- Legacy records without `bot_mode` are treated as `alert_only`.
- A single unified list must not contain duplicate records with the same `(source, source_trade_id, bot_mode)`.
- Required manual fields remain symbol, direction, entry price, and entry time.
- Non-manual source records retain source identity even when displayed values are overridden.

## Manual Trade

User-created trade record, primarily created in `alert_only`.

### Fields

- Inherits Historical Trade fields.
- `is_manual` is always true.
- `source` is `manual`.

### Rules

- Can be created in `alert_only`.
- Can be fully edited in `alert_only`.
- Can be deleted only in `alert_only` and only after confirmation.
- In non-`alert_only` modes, existing manual records for that mode expose only notes and tags for editing.

## Trade Annotation

Mode-scoped notes and tags attached to a historical trade.

### Fields

- `trade_identity`: Canonical `(source, source_trade_id)` or manual trade id.
- `bot_mode`: Mode that owns this annotation.
- `notes`: Free-form text.
- `tags`: List of text tags.
- `created_at`, `updated_at`: Local timestamps.

### Rules

- Notes and tags are editable in every mode.
- Annotation data from one mode must not appear in another mode.
- Legacy annotations without mode metadata are classified as `alert_only`.

## Trade Override

Local corrected field values for a non-manual historical trade edited in `alert_only`.

### Fields

- `trade_identity`: Canonical `(source, source_trade_id)`.
- `bot_mode`: Always `alert_only` for the first implementation because full edits are only allowed there.
- `overridden_fields`: Set of field names corrected locally.
- `values`: Corrected values for the overridden fields.
- `created_at`, `updated_at`: Local timestamps.

### Rules

- Overrides are merged over the original source record for display.
- Overrides must not replace or delete the source record.
- Overrides must not appear in other bot modes.
- Overrides are not deletable through non-manual trade deletion; deleting applies only to manually created trades.

## Mode-Isolated History

The current-mode view combining source trades, manual trades, annotations, and overrides.

### Composition

1. Read current bot mode.
2. Fetch source historical trades for that mode where available.
3. Fetch manual trades with matching `bot_mode`, treating missing mode as `alert_only`.
4. Apply mode-matching annotations.
5. Apply mode-matching local overrides for non-manual trades.
6. De-duplicate by canonical identity and sort by close/entry time.

### State Transitions

- `alert_only` create manual trade: no record -> manual historical trade.
- `alert_only` edit manual trade: manual historical trade -> updated manual historical trade.
- `alert_only` edit non-manual trade: source historical trade -> source historical trade plus trade override.
- Any mode annotate trade: historical trade -> historical trade plus annotation.
- `alert_only` delete manual trade: manual historical trade -> removed from that mode's history.
- Mode switch: active view changes to the target mode's isolated history; no data is copied between modes.

## Agent Export

Structured package containing mode-isolated trade-history data for LLM and agentic strategy evaluation workflows.

### Fields

- `schema_version`: Export schema version.
- `schema_name`: Canonical export name, `Agent Export`.
- `generated_at`: ISO-8601 timestamp for export creation.
- `bot_mode`: Mode represented in the export.
- `scope`: Export boundaries, including filters, date range, symbols, and whether records include overrides.
- `chunking`: Chunk metadata for bounded agent context windows.
- `summary`: Record counts, win/loss totals, P/L totals, tag counts, and override counts.
- `field_metadata`: Short descriptions of exported fields so agents can interpret data without dashboard code.
- `records`: Unified historical trade records for the selected mode.
- `analysis_context`: Purpose and caveats for AI strategy evaluation, including mode isolation, local override semantics, and legacy `alert_only` defaulting.

### Rules

- The export contains only one bot mode unless a future feature explicitly adds multi-mode comparison exports.
- Records include displayed values and source/override metadata where available.
- Records include linked strategy or signal context only when that context is already available in unified history data.
- Export schema changes must increment `schema_version`.
- Export output must be deterministic for the same input data and filters, except for `generated_at`.
