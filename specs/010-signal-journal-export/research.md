# Research: Signal Journal Export

## Decision: Return a real CSV attachment from the backend and preserve headers through the dashboard proxy

**Rationale**: The current backend route sends CSV content as `text/csv` but lacks `Content-Disposition`, and the dashboard proxy reconstructs a new response while preserving only `Content-Type`. A browser Blob download can still work with a local filename, but the end-to-end export contract is incomplete and brittle because the server never declares the response as an attachment. Setting `Content-Disposition: attachment; filename="..."` at the Python API and forwarding it from the Next proxy fixes the root cause while keeping the existing fetch/blob pattern.

**Alternatives considered**:

- Frontend-only filename workaround: rejected because it leaves the file response contract broken.
- JSON response with client-side CSV generation: rejected because existing backend CSV helper already centralizes export schema.
- Streaming response: deferred because current JSONL exports are small enough and the lightweight API uses buffered responses elsewhere.

## Decision: Filter export records by evaluated timestamp first, then created/signal timestamp fallback

**Rationale**: The user explicitly prefers `evaluated_at` when available and `created_at` otherwise. Existing journal records often use `signal_timestamp`; treating `signal_timestamp` as a legacy created timestamp fallback preserves current data without migration. This keeps exports deterministic and avoids mutating old entries.

**Alternatives considered**:

- Require all records to have `evaluated_at`: rejected because legacy records would disappear.
- Use grade timestamp: rejected because grading may happen long after signal evaluation and would distort optimization windows.
- Use display grouping timestamp only: rejected because it is currently derived from `signal_timestamp` and does not cover newer diagnostic fields.

## Decision: Return a non-file no-records response for empty export selections

**Rationale**: The acceptance criteria require a clear message and no empty/broken file when no records match. A JSON `404` with a short error message lets the existing frontend error path avoid file creation, and tests can assert both status and content. Keeping empty CSV generation available at the helper level for direct unit compatibility is less important than route-level no-download behavior.

**Alternatives considered**:

- Download a header-only CSV: rejected by the new acceptance criteria.
- Return `204 No Content`: rejected because it carries less user-facing context and can be ambiguous in the browser.

## Decision: Reuse the visible grade filter now and design query parameters for additional filters

**Rationale**: The current Signal Journal page exposes grade filtering only. The new export should immediately respect that filter and date/time range, while the API contract reserves optional symbol/status/final decision/strategy/mode/graded state parameters for future visible filters when added. This avoids inventing hidden UI filters while keeping the backend filter shape ready for deterministic analysis exports.

**Alternatives considered**:

- Add all possible filters immediately: rejected because most are not visible on the current page and would expand scope into broader journal search UX.
- Grade-only export: rejected because it does not solve stale old-run data pollution.

## Decision: Keep CSV flat with deterministic field ordering and JSON-encode complex nested values

**Rationale**: Optimization analysis needs stable columns. Existing records may contain legacy or future extra fields, and nested blockers/criteria/diagnostics are not guaranteed to be scalar. A stable core field list plus deterministic extra field ordering, with JSON serialization for nested values, preserves evidence while keeping the CSV flat.

**Alternatives considered**:

- Drop nested/extra fields: rejected because diagnostic evidence may matter later.
- Generate multiple related CSV files: deferred because the task prioritizes a reliable flat CSV.
