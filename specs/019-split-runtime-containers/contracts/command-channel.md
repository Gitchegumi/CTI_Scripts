# Contract: API → Worker Command Channel

Replaces the in-memory `set_runtime_state`/`force_rescan` mutation path with a
cross-process channel over Redis. Satisfies FR-005 (commands reach the worker)
and FR-010 (commands are never silently lost when the channel/worker is down).

## Transport

- **Fast path**: Redis pub/sub channel `tradegumi:commands`.
- **Durable path**: Redis key `tradegumi:desired_config` (last-write-wins),
  holding the current desired mode/program/phase/challenge_type.
- The worker subscribes to `tradegumi:commands` for immediate delivery **and**
  reconciles against `tradegumi:desired_config` on each loop iteration and at
  startup. This makes config commands at-least-once / idempotent.

## Message format (published to `tradegumi:commands`)

```json
{
  "command_id": "f7c1e1a0-...-9b",
  "type": "set_mode",
  "payload": { "mode": "demo" },
  "issued_at": "2026-06-13T14:05:00Z",
  "source": "dashboard"
}
```

`type` ∈ `set_mode` | `set_program` | `set_phase` | `set_challenge_type` | `rescan`.
`payload` is empty `{}` for `rescan`.

## API behavior (publisher)

For each control endpoint that today mutates runtime state:

| Endpoint (existing) | Command emitted |
| --- | --- |
| `POST /api/config/mode` | `set_mode` + update `desired_config.mode` |
| `POST /api/config/program` | `set_program` + update `desired_config.program` |
| `POST /api/config/phase` | `set_phase` + update `desired_config.phase` |
| `POST /api/config/challenge_type` | `set_challenge_type` + update `desired_config.challenge_type` |
| `POST /api/action/rescan` | `rescan` (no desired_config change) |

Rules:
1. **Validate first.** Reject unknown `type` or invalid value with `400`; nothing
   is published.
2. **Update desired_config, then publish.** Write the durable key before/with the
   pub/sub publish so a worker that missed the message still reconciles.
3. **Never claim success on a dropped command.** If the Redis publish/write
   fails, respond with a non-2xx status (e.g. `503`) and a body indicating the
   command was not delivered. Do **not** return `200 {status: ...}` as the
   in-memory version did.
4. **Response (success)**: `200 { "status": "accepted", "command_id": "..." }`.
   Optionally the API may poll `tradegumi:command_ack:<command_id>` briefly and
   return `applied` when the worker confirms.

## Worker behavior (consumer)

1. On startup, read `tradegumi:desired_config` and apply it before the first loop
   (so a config set while the worker was down takes effect on boot).
2. Subscribe to `tradegumi:commands`; apply messages as they arrive.
3. On each loop iteration, reconcile current runtime config against
   `tradegumi:desired_config`; apply any drift. Handle `rescan` as a one-shot
   (sets the existing force-rescan behavior).
4. Applying a config command MUST take effect without a process restart
   (Constitution V) and MUST be reflected in the next heartbeat (`mode`, etc.).
5. Optionally write `tradegumi:command_ack:<command_id>` (short TTL) after apply.
6. If Redis is unavailable, continue trading on the last-applied config; do not
   crash (FR-010).

## What the command channel MUST NOT carry

- No order-placement or trade-execution instruction. Order placement is
  worker-internal and risk-gated; there is no command that asks the worker to
  place an arbitrary order (Constitution III, Risk-First).

## Observability

Each of: command accepted (API), command published, command consumed, command
applied, command rejected (validation), and command-channel-unavailable MUST be
logged and surfaced per Observable-by-Default (Constitution IV).
