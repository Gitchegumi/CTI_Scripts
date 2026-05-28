# Contract: Signal Journal Outcome Fields

## Storage and Read Compatibility

Signal Journal records may include these additive fields:

```json
{
  "status": "closed",
  "outcome": "tp",
  "outcome_source": "live_price_observation_1s",
  "exit_time": "2026-05-27T14:05:01Z",
  "exit_price": 1.1042,
  "outcome_checked_at": "2026-05-27T14:05:01.123456+00:00",
  "observations_to_outcome": 24,
  "bars_to_outcome": null,
  "max_favorable_excursion": 0.0042,
  "max_adverse_excursion": 0.0005,
  "ambiguous_reason": null,
  "manually_overridden": false,
  "manual_override_reason": null
}
```

Rules:

- Missing `status` defaults to a value compatible with existing pending/open grade state.
- Missing `outcome` defaults to `none`.
- Manual grades set `manually_overridden=true` and `outcome_source=manual` unless reset clears that state.
- Existing CSV export includes new fields when practical.
- Existing grade filters keep working from `grade`/`trade_grade`.

## Prime Compatibility

- Auto `tp` or `sl` closes active prime state.
- Unresolved, ambiguous, expired, or invalidated states are handled according to existing prime suppression rules.
- Invalidated-by-prime increments remain auditable.
