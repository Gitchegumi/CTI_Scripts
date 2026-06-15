# Contract: Forex Market Session Status

## Purpose

Define the expected forex session-decision behavior shared by signal checks, forced rescans, loop state, and diagnostics.

## Inputs

- `symbol`: Configured CTI symbol.
- `when`: Optional timezone-aware timestamp. If omitted, the current runtime time is used.

## Output

```json
{
  "symbol": "EURUSD",
  "category": "forex",
  "is_open": true,
  "reason": "open",
  "evaluated_at": "2026-06-14T21:40:00-05:00",
  "session_boundary": null
}
```

## Required Behavior

- Sunday 15:59:59 Central is closed for forex instruments.
- Sunday 16:00:00 Central / 17:00:00 Eastern is open for forex instruments.
- Sunday 21:40:00 Central is open for forex instruments.
- Normal weekdays between the Sunday open and Friday close are open for forex instruments.
- Friday 15:59:59 Central is still open for forex instruments.
- Friday 16:00:00 Central / 17:00:00 Eastern is closed for forex instruments.
- Saturday is closed for forex instruments.

## Compatibility

Existing boolean callers may continue to use a boolean open/closed helper. New diagnostics should be derived from the same underlying decision so boolean and structured status cannot disagree.
