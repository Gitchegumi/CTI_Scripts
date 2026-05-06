# Contract: Strategy Metrics Date Ranges

## Scope

Applies to Strategy Metrics summary, opportunities, comparison, and export reads.

## Request Parameters

| Parameter | Required | Behavior |
| --- | --- | --- |
| `start` | Yes | Date-only values are treated as the beginning of that calendar date in application/operator time. |
| `end` | Yes | Date-only values include the full selected calendar date by converting to an exclusive boundary at the next calendar day. |
| `symbol` | No | Filters records by symbol when provided. |
| `include_opportunities` | Export only | Includes opportunity records when true. |

## Response Requirements

- Response `start` and `end` metadata must expose the normalized internal boundaries or document the selected range semantics.
- Summaries, opportunity lists, comparison periods, and exports must use the same range normalization.
- Records on the selected end date through 23:59:59.999 must be included.
- Records after the selected end date must be excluded.

## Error Behavior

- Missing `start` or `end` returns a validation error.
- Invalid date values return a validation error rather than silently returning an empty range.

## Validation

- Create records at selected-day start, middle, and end; verify inclusion.
- Create records on the following day; verify exclusion.
- Verify summary and opportunities use matching counts for the same range.
