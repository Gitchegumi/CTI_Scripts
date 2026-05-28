# Data Model: Alert Signal Auto-Grading

## PriceObservation

Represents one observed market price for one symbol.

Fields:

- `symbol`: normalized instrument symbol such as `EURUSD`.
- `timestamp`: provider observation timestamp when available.
- `bid`: executable bid price, optional.
- `ask`: executable ask price, optional.
- `mid`: midpoint price, optional and derived from bid/ask when both are available.
- `source`: one of `dashboard_poll`, `oanda_pricing_stream`, `historical_candle`, `manual_backfill`.
- `observed_at`: same semantic as provider timestamp when present.
- `received_at`: local time the backend accepted the observation.

Validation rules:

- `symbol` and at least one of `bid`, `ask`, or `mid` are required.
- If both `bid` and `ask` are present, `mid` may be derived as their average.
- Timestamps must be parseable or safely defaulted to receive time.

## RollingPriceHistory

Bounded in-memory collection of recent `PriceObservation` records grouped by symbol.

Fields:

- `observations_by_symbol`: symbol-keyed rolling deque/list.
- `max_observations_per_symbol`: hard upper bound.
- `max_age_seconds`: optional age bound.
- `latest_by_symbol`: fast read path for dashboard/API consumers.

Validation rules:

- History is pruned after each publish.
- History must not grow unbounded.
- Out-of-order observations may be retained but evaluator ordering must remain deterministic.

## Signal Journal Outcome Fields

Additive fields on a Signal Journal entry.

Fields:

- `status`: `pending`, `open_simulated`, `closed`, `ambiguous`, `invalidated`, or `expired`.
- `outcome`: `tp`, `sl`, `ambiguous`, `expired`, `manually_closed`, `invalidated_by_prime`, `invalidated_by_system`, or `none`.
- `outcome_source`: `live_price_observation_1s`, `live_price_observation_1s_mid`, `oanda_pricing_stream`, `historical_candle`, `manual`, or `system_prime_filter`.
- `exit_time`: observation time or manual close time.
- `exit_price`: price that triggered or recorded the outcome.
- `outcome_checked_at`: latest evaluator check time.
- `observations_to_outcome`: count of observations considered after signal open when available.
- `bars_to_outcome`: count of candle bars considered when historical data is used.
- `max_favorable_excursion`: best favorable movement seen while open.
- `max_adverse_excursion`: worst adverse movement seen while open.
- `ambiguous_reason`: explanation when outcome ordering cannot be resolved.
- `manually_overridden`: boolean.
- `manual_override_reason`: optional human-entered reason.

Compatibility rules:

- Legacy entries missing these fields default to pending/open-compatible values during reads.
- Existing `grade` and `trade_grade` remain readable and continue to support existing filters.
- Manual grades set manual outcome state and prevent evaluator overwrite unless reset behavior clears eligibility.

## Outcome Evaluation

State transition for one eligible signal and one or more observations.

States:

- `pending` -> `open_simulated` when an unresolved alert/developing entry becomes eligible.
- `open_simulated` -> `closed` with `tp` when the first ordered target touch occurs.
- `open_simulated` -> `closed` with `sl` when the first ordered stop touch occurs.
- `open_simulated` -> `ambiguous` with `ambiguous` when target and stop are both hit in one unresolved cycle.
- `open_simulated` -> `expired` or `invalidated` when existing journal/prime rules mark the setup no longer active.
- Any state -> manual state through existing manual grade or invalidation flows.
- Manual state -> `pending` only through explicit reset unless manually locked.

BUY rules:

- Target touch when bid >= take_profit.
- Stop touch when bid <= stop_loss.

SELL rules:

- Target touch when ask <= take_profit.
- Stop touch when ask >= stop_loss.

Midpoint fallback:

- If bid/ask are missing and midpoint is used, outcome source must identify midpoint grading.

## Prime Signal State

Existing per-symbol prime journal fields remain authoritative.

Rules:

- A prime with `status=closed` and `outcome` of `tp` or `sl` is no longer unresolved.
- A prime with `status=ambiguous`, `pending`, or `open_simulated` remains blocking unless existing behavior explicitly resolves it.
- Blocking a new same-symbol signal records or increments invalidated-by-prime evidence.
- A resolved prior prime must be deactivated before the new same-symbol signal becomes prime.
