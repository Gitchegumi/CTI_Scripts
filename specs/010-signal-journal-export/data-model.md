# Data Model: Signal Journal Export

## Signal Journal Record

Represents one existing entry from the Signal Journal JSONL file. Records are read only for this feature.

| Field | Meaning | Validation / Notes |
| --- | --- | --- |
| `signal_id` / `opportunity_id` | Stable signal or opportunity identity | At least one should be exported when present |
| `symbol` | Market symbol | Optional for malformed legacy records but included in CSV schema |
| `timeframe` | Signal timeframe | Optional; blank when absent |
| `strategy` | Strategy name/version context | Defaults only for display/export compatibility when absent |
| `mode` | Operating mode such as alert/demo/live | Optional; blank when absent |
| `direction` | BUY/SELL or equivalent direction | Optional for legacy records |
| `trend` | Trend context | Optional; blank when absent |
| `final_decision` | Final signal decision | Optional; blank when absent |
| `decision_reason` | Human-readable decision reason | Optional; blank when absent |
| `confidence` | Signal confidence | Export as stored |
| `failed_criteria_count` | Number of failed criteria | Optional; blank when absent |
| `near_miss`, `near_miss_reason` | Near-miss indicators | Optional; blank when absent |
| `first_blocker`, `all_blockers`, `blocking_layer` | Blocking diagnostics | Nested lists are JSON-encoded in CSV cells |
| `evaluated_at` | Preferred analysis timestamp | Used for range filtering when present |
| `created_at` / `signal_timestamp` | Fallback analysis timestamp | `signal_timestamp` supports legacy journal entries |
| `grade`, `status`, `pending_state` | Review state | Existing grade values remain unchanged |
| Trade result and P&L fields | Outcome evidence | Export when present, blank otherwise |

## Export Selection

The operator-selected export scope.

| Field | Required | Notes |
| --- | --- | --- |
| `start` | No | Inclusive lower date/time boundary |
| `end` | No | Inclusive upper date/time boundary |
| `grade` | No | Existing visible Signal Journal grade filter; omitted or `ALL` means all grades |
| `symbol` | No | Reserved for current/future visible filters |
| `status` | No | Reserved for current/future visible filters |
| `final_decision` | No | Reserved for current/future visible filters |
| `strategy` | No | Reserved for current/future visible filters |
| `mode` | No | Reserved for current/future visible filters |
| `graded_state` | No | Reserved for graded/pending state filters |

Validation rules:

- `start` and `end` must be parseable date/time strings when provided.
- When both are provided, `start` must not be after `end`.
- Date/time comparisons are inclusive.
- The analysis timestamp for each record is `evaluated_at` when present, otherwise `created_at`, otherwise `signal_timestamp`.
- Invalid filter values return a user-facing error and no file.

## CSV Export File

Represents the downloaded flat CSV.

| Property | Rule |
| --- | --- |
| Filename | `signal-journal-YYYY-MM-DD-to-YYYY-MM-DD.csv` when both boundaries exist; otherwise `signal-journal-selected-range.csv` or grade/scope-specific fallback |
| Content type | `text/csv; charset=utf-8` |
| Disposition | Attachment with filename |
| Ordering | Deterministic newest/oldest ordering chosen in implementation and covered by tests |
| Columns | Stable core optimization columns first, deterministic extra columns after |
| Complex values | JSON-encoded in a single cell |

## No-Records Result

Represents a valid export selection matching zero records.

| Property | Rule |
| --- | --- |
| Download | No file is downloaded |
| Message | User sees a clear no-records message |
| Status | Non-success file response, preferably JSON with a specific error |
