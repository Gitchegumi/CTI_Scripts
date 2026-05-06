# Data Model: Journal and Dashboard Controls

## StrategyMetricsRange

Represents user-selected date filters for Strategy Metrics summary, opportunities, comparison, and export.

| Field | Description | Validation |
| --- | --- | --- |
| `start` | User-selected start date or timestamp | Required |
| `end` | User-selected end date or timestamp | Required |
| `normalized_start` | Inclusive internal lower boundary | Must be at or before `normalized_end` |
| `normalized_end` | Exclusive internal upper boundary | Date-only inputs become next calendar day start |
| `timezone_context` | Application/operator timezone used for date-only normalization | Must be documented |

## SignalJournalEntry

Represents one emitted signal record in the Signal Journal JSONL file.

| Field | Description | Validation |
| --- | --- | --- |
| `signal_id` | Stable signal identity | Required, unique enough for row-level actions |
| `symbol` | Trading symbol | Required |
| `direction` | BUY or SELL | Required |
| `strategy` | Strategy/version label | Optional fallback allowed |
| `confidence` | Signal confidence | Optional numeric |
| `entry_price`, `stop_loss`, `take_profit` | Emitted signal price fields | Optional for legacy records, required for current records |
| `signal_timestamp` | Emission timestamp | Required for current records |
| `grade` | PENDING, TP_HIT, SL_HIT, MANUAL_CLOSE, EXPIRED | Missing legacy values default to PENDING for display/export |
| `grade_timestamp` | Timestamp of grade completion | Null when Pending |
| `notes` | Operator notes | Preserved on reset |
| diagnostic fields | Indicator and strategy diagnostic values available on record | Optional; exported when present |
| outcome fields | Outcome labels or measurements if already available | Optional; blank/null when absent |

### State Transitions

```text
PENDING -> TP_HIT
PENDING -> SL_HIT
PENDING -> MANUAL_CLOSE
PENDING -> EXPIRED
TP_HIT | SL_HIT | MANUAL_CLOSE | EXPIRED -> PENDING
```

Reset to Pending clears grade-completion markers and preserves notes plus original signal/diagnostic fields.

## SignalJournalExport

Portable optimization data file.

| Field | Description | Validation |
| --- | --- | --- |
| `schema_version` | Export schema/version identifier | Required in metadata or JSON wrapper |
| `generated_at` | Export timestamp | Required |
| `scope` | Active filters used for export | Required |
| `format` | CSV minimum, optional JSON | Required |
| `records` | Exported Signal Journal entries | May be empty |

## SignalJournalPurgeScope

Defines which Signal Journal entries are removed after confirmation.

| Field | Description | Validation |
| --- | --- | --- |
| `grade_filter` | Active grade filter or All | Required |
| `matched_count` | Count presented to user before confirmation | Required |
| `confirmed` | Confirmation flag | Must be true before deletion |

## ManualTradeRecord

Existing unified manual trade record with explicit Developing-mode P&L correction behavior.

| Field | Description | Validation |
| --- | --- | --- |
| `id` | Canonical trade identity | Required |
| `bot_mode` | Internal mode value | `alert_only`, `demo`, or `live` |
| `display_mode` | User-facing label | `alert_only` displays as Developing |
| `pnl` | Correctable P&L value | Editable only when current mode is `alert_only` |
| `pnl_percent` | Optional percentage P&L | Recomputed or updated consistently with P&L decision |
| `has_overrides` | Whether local corrections are applied | True when non-source facts are overridden |
| `permissions` | Current-mode edit/delete permissions | Must match backend enforcement |

## DashboardTradeHistoryRecord

Dashboard-ready trade row normalized from manual and optional source records.

| Field | Description | Validation |
| --- | --- | --- |
| `id` | Stable row key | Required |
| `symbol`, `side` | Trade identity fields | Required for display |
| `open_time`, `close_time` | Display timestamps | Must be safe for hydration handling |
| `open_price`, `close_price`, `pnl` | Trade metrics | Missing numeric values default for display only |
| `notes`, `tags` | Optional annotations | Optional |
| `source` | manual or source identifier | Required |

## TradeCorrelationData

Optional confidence/correlation metadata associated with trade history rows.

| Field | Description | Validation |
| --- | --- | --- |
| `trade_id` | Trade history id | Optional row match |
| `confidence` | Signal confidence for linked trade | Optional numeric |

Missing correlation data is represented as an empty list.
