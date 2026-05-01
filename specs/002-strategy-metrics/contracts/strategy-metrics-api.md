# Contract: Strategy Metrics API

The Python backend owns diagnostic storage and aggregation. The dashboard proxies browser requests through matching Next.js API routes.

## GET /api/strategy-metrics/summary

Returns aggregate diagnostics for a date range.

**Query Parameters**:

| Name | Required | Description |
| --- | --- | --- |
| `start` | Yes | Inclusive ISO date or timestamp. |
| `end` | Yes | Exclusive ISO date or timestamp. |
| `symbol` | No | Optional symbol filter. |

**Response 200**:

```json
{
  "start": "2026-04-24T00:00:00-05:00",
  "end": "2026-05-01T00:00:00-05:00",
  "total_evaluated": 840,
  "emitted_count": 0,
  "rejected_count": 520,
  "skipped_count": 320,
  "indeterminate_count": 0,
  "near_miss_count": 42,
  "criterion_summaries": [
    {
      "criterion_name": "keltner",
      "evaluated_count": 520,
      "pass_count": 390,
      "fail_count": 130,
      "pass_rate": 0.75,
      "fail_rate": 0.25,
      "near_miss_contribution": 18,
      "average_failure_margin": 0.14,
      "incomplete_count": 0
    }
  ],
  "top_blockers": [
    {
      "criterion_name": "keltner",
      "blocked_count": 130,
      "frequency_component": 0.25,
      "margin_component": 0.62,
      "quality_component": 0.71,
      "combined_score": 0.53,
      "example_opportunity_ids": ["opp_001", "opp_002"]
    }
  ],
  "data_quality_warnings": []
}
```

**Errors**:

- `400`: invalid date range or unsupported query parameter.
- `401`: dashboard proxy request is not authenticated.
- `500`: diagnostic aggregation failed.

## GET /api/strategy-metrics/opportunities

Returns evaluated opportunities for drill-down.

**Query Parameters**:

| Name | Required | Description |
| --- | --- | --- |
| `start` | Yes | Inclusive ISO date or timestamp. |
| `end` | Yes | Exclusive ISO date or timestamp. |
| `symbol` | No | Optional symbol filter. |
| `decision` | No | `emitted`, `rejected`, `skipped`, or `indeterminate`. |
| `near_miss` | No | `true` to return only near-misses. |
| `limit` | No | Default 100; maximum 1000. |

**Response 200**:

```json
[
  {
    "id": "opp_001",
    "evaluated_at": "2026-04-30T09:15:05-05:00",
    "symbol": "EURUSD",
    "direction": "BUY",
    "trend": "Uptrend",
    "final_decision": "rejected",
    "decision_reason": "criteria_failed",
    "confidence": 0.61,
    "failed_criteria_count": 1,
    "near_miss": true,
    "data_complete": true,
    "criteria": [
      {
        "criterion_name": "keltner",
        "measured_value": 1.08342,
        "threshold_value": 1.08330,
        "threshold_operator": "lte",
        "passed": false,
        "margin": 0.00012,
        "required": true,
        "blocked_signal": true,
        "data_quality": "complete"
      }
    ]
  }
]
```

## GET /api/strategy-metrics/compare

Returns two summaries plus deltas.

**Query Parameters**:

| Name | Required | Description |
| --- | --- | --- |
| `base_start` | Yes | Baseline inclusive start. |
| `base_end` | Yes | Baseline exclusive end. |
| `compare_start` | Yes | Comparison inclusive start. |
| `compare_end` | Yes | Comparison exclusive end. |
| `symbol` | No | Optional symbol filter. |

**Response 200**:

```json
{
  "baseline": { "total_evaluated": 820, "emitted_count": 2, "near_miss_count": 31 },
  "comparison": { "total_evaluated": 840, "emitted_count": 0, "near_miss_count": 42 },
  "deltas": {
    "total_evaluated": 20,
    "emitted_count": -2,
    "near_miss_count": 11,
    "top_blocker_changed": true
  }
}
```

## GET /api/strategy-metrics/export

Returns a downloadable JSON diagnostic summary for a date range.

**Query Parameters**: same as `/summary`, plus `include_opportunities=true|false`.

**Response 200**: JSON object containing summary and, when requested, opportunity details.
