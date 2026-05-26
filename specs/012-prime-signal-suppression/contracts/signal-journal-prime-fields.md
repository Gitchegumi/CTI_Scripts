# Contract: Signal Journal Prime Fields

## Storage Fields

New actionable Signal Journal rows include:

```json
{
  "prime_active": true,
  "prime_suppressed_signal_count": 0,
  "prime_suppressed_last_at": null,
  "prime_closed_reason": null,
  "prime_closed_at": null,
  "prime_close_ambiguous": false,
  "prime_suppressed_same_direction_count": 0,
  "prime_suppressed_opposite_direction_count": 0
}
```

Optional compact metadata may be present:

```json
{
  "prime_suppressed_signal_ids": ["EURUSD:SELL:2026-05-26T14:10:00+00:00"]
}
```

## Export Fields

CSV exports must include at least:

```text
prime_active
prime_suppressed_signal_count
prime_suppressed_last_at
prime_closed_reason
prime_closed_at
prime_close_ambiguous
```

When directional counts are implemented, CSV and JSON-style records include:

```text
prime_suppressed_same_direction_count
prime_suppressed_opposite_direction_count
```

When suppressed IDs/details are stored, JSON exports include the structured metadata. CSV may serialize compact values only when readability remains acceptable.

## Compatibility Rules

- Missing fields on legacy records are treated as inactive/zero/blank.
- Existing export filters continue to work with prime fields present.
- Existing unknown extra-field preservation remains valid.
