# Research: Manual Trade Permissions

## Decision: Use a Unified Current-Mode Trade History Read Model

**Rationale**: The main dashboard and manual trades interface currently read different trade sources. A unified read model gives both views the same de-duplicated, mode-scoped records and satisfies the requirement that dashboard Trade History appears in the manual trades interface.

**Alternatives considered**:

- Keep separate manual and broker lists: rejected because it preserves the current inconsistency.
- Merge only in the frontend: rejected because permission enforcement, duplicate handling, and stats would drift between views.

## Decision: Store Non-Manual `alert_only` Edits as Local Overrides

**Rationale**: Local overrides preserve the original source trade identity and source values while allowing paper-trading corrections to appear consistently in both history views. This avoids destructive rewrites of imported/source-owned trade records.

**Alternatives considered**:

- Overwrite source records: rejected because source records may be refreshed from broker or dashboard data.
- Convert edited trades into manual trades: rejected because it risks duplicates and loses source identity.

## Decision: Isolate History Data by Bot Mode

**Rationale**: The clarified requirement states each mode should collect its own isolated data. Storing and querying records, overrides, notes, and tags by mode prevents paper-trading corrections from leaking into demo/live review and keeps mode switches predictable.

**Alternatives considered**:

- Share annotations across modes: rejected because it violates mode isolation.
- Show `alert_only` corrections in all modes as read-only: rejected by clarification.

## Decision: Treat Legacy Unmodeled Records as `alert_only`

**Rationale**: Existing manual-trade records predate mode isolation and are closest to paper-trading data. Defaulting them to `alert_only` preserves access without contaminating demo/live histories.

**Alternatives considered**:

- Show legacy records in every mode: rejected because it breaks isolation.
- Hide legacy records until manually assigned: rejected because it risks appearing as data loss.

## Decision: Enforce Permissions at Backend Save Time

**Rationale**: UI controls should guide the user, but current mode can change while a page is open. Backend enforcement prevents stale clients from modifying protected fields outside `alert_only` or deleting non-manual records.

**Alternatives considered**:

- UI-only enforcement: rejected because it cannot protect against stale pages or direct requests.
- Separate endpoints per mode: rejected because mode already exists in config and branching endpoints would duplicate validation.

## Decision: Reuse Existing Auth and Polling Patterns

**Rationale**: Manual trades already use `JOURNAL_TOKEN` through Next.js proxy routes and the dashboard already polls trade history. Reusing those patterns keeps the feature aligned with the current deployment and security model.

**Alternatives considered**:

- Add a new authentication flow: rejected because no new actor or trust boundary exists.
- Add push/stream updates: rejected because existing 30-second polling satisfies the success criteria.

## Decision: Use Structured JSON as the First Agent Export Format

**Rationale**: JSON preserves nested source records, displayed values, annotations, overrides, schema metadata, and analysis context in one machine-readable package. That makes it friendlier for LLM and agentic workflows than a flat CSV while still being easy to chunk, validate, and transform later.

**Alternatives considered**:

- CSV only: rejected because annotations, overrides, and field metadata become lossy or require multiple files.
- Markdown report only: rejected because it is easier for humans to read but weaker for repeatable agent parsing.
- Multiple export formats in the first version: rejected because one documented JSON schema is enough to satisfy agent workflows and can be expanded later.
