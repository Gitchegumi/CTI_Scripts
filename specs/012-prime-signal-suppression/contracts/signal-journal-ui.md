# Contract: Signal Journal UI

## Card/Detail Display

When a journal record has `prime_suppressed_signal_count > 0`, the signal journal card or detail view shows one compact line:

```text
Suppressed by this prime: 4
```

When directional counts are available and at least one opposite-direction signal was suppressed, the display may show:

```text
Suppressed by this prime: 4 total, 2 opposite direction
```

## Display Rules

- Do not show the line when the count is zero or missing.
- Keep the display compact and subordinate to grade, entry, target, stop, and stats eligibility evidence.
- Do not add a new noisy panel for suppressed details.
- Legacy records must render without errors.

## Type Shape

Journal entry types should accept:

```ts
prime_active?: boolean;
prime_suppressed_signal_count?: number;
prime_suppressed_last_at?: string | null;
prime_closed_reason?: string | null;
prime_closed_at?: string | null;
prime_close_ambiguous?: boolean;
prime_suppressed_same_direction_count?: number;
prime_suppressed_opposite_direction_count?: number;
```
