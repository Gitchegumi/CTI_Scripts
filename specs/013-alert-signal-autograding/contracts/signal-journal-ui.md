# Contract: Signal Journal UI/API

## API Shape

Journal API entries should pass through the additive outcome fields without requiring clients to send them on manual grade or notes updates.

Important fields:

- `status`
- `outcome`
- `outcome_source`
- `exit_time`
- `exit_price`
- `outcome_checked_at`
- `manually_overridden`
- `manual_override_reason`
- `ambiguous_reason`

## UI Display

Journal cards/details show compact outcome metadata:

- Status and outcome near existing grade information.
- Source label only when it helps distinguish auto, midpoint, historical, manual, or prime-filter outcomes.
- Exit time and exit price when closed.
- Manual override indicator when true.
- Ambiguous reason in detail view.

Rules:

- Main journal cards stay readable and avoid long explanatory text.
- Existing manual grade, invalidate, reset, export, and purge controls remain in place.
- Legacy entries missing new fields render without errors.
