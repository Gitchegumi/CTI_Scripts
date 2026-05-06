# Research: Journal and Dashboard Controls

## Decision: Treat UI end dates as inclusive calendar dates

**Rationale**: The user selects a calendar day, so the expected behavior is "through the selected day." The safest implementation is to convert date-only `end` inputs to an exclusive internal boundary at the next local/application calendar day while preserving full ISO timestamps when callers provide them.

**Alternatives considered**:

- Keep raw date-only `end` as midnight of that day. Rejected because it causes the observed day-1 behavior.
- Make all UI labels say "exclusive end." Rejected because it is less intuitive and would still surprise dashboard users.

## Decision: Export Signal Journal CSV first, with JSON optional

**Rationale**: CSV satisfies the minimum optimization workflow and is easy to inspect in spreadsheets. JSON can be added if it follows existing export patterns, but CSV is the acceptance-critical format.

**Alternatives considered**:

- JSON only. Rejected because the requirement says CSV is the minimum.
- Multiple archive files. Rejected as unnecessary for a single-operator local journal.

## Decision: Signal Journal export and purge respect the active grade filter

**Rationale**: The page already exposes grade filtering and optimization often targets Pending or completed subsets. Respecting the active filter makes the export/purge action predictable. When the filter is All, the action applies to all Signal Journal entries after confirmation.

**Alternatives considered**:

- Always export/purge all records. Rejected because it is riskier for destructive purge and less useful for targeted optimization.
- Add date filters first. Deferred because current page filtering is grade-based; date filters are not required to satisfy this feature.

## Decision: Reset to Pending preserves notes and original signal diagnostics

**Rationale**: Notes may contain context unrelated to the accidental grade. Resetting must clear grade-completion markers such as grade and grade timestamp, but should keep original signal data and free-form notes.

**Alternatives considered**:

- Clear notes on reset. Rejected because it discards operator context.
- Delete and recreate the journal entry. Rejected because it risks losing identity and diagnostics.

## Decision: Keep `alert_only` internal, display "Developing"

**Rationale**: Stored data, environment configuration, mode endpoints, and compatibility contracts already use `alert_only`. A display-label mapping avoids migration risk while improving operator language.

**Alternatives considered**:

- Rename the internal value to `developing`. Rejected because it would require migration and broader compatibility work.
- Show both labels everywhere. Rejected because it adds clutter; raw value may remain in technical export metadata where useful.

## Decision: Dashboard trade history must prefer local manual records when broker/source history fails

**Rationale**: Manual trades are local operational data and should not disappear because an upstream broker history call fails. Broker/source failures should be logged and treated as missing source records, not as a fatal dashboard-history failure.

**Alternatives considered**:

- Require broker/source history before returning any dashboard history. Rejected because it caused the visible 500 failure and hides manual records.
- Remove source trade merging. Rejected because source history remains useful when available.

## Decision: Missing trade correlations are optional empty data

**Rationale**: Trade correlations enrich confidence display but are not required to render trade history. Missing correlation data should resolve to `[]` via an intentional endpoint or fallback, avoiding repeated noisy 404s.

**Alternatives considered**:

- Generate a static file on every startup. Considered acceptable if already aligned with state-file generation, but not required.
- Remove correlation support. Rejected because existing UI can still use it when available.

## Decision: Hydration risk should be removed from unstable date/client-only rendering

**Rationale**: React hydration error #418 commonly appears when server and client render different text. The affected dashboard pieces use timestamps, locale formatting, client-only data, and polling. Planning should include isolating these values so server-rendered markup does not conflict with client-rendered content.

**Alternatives considered**:

- Ignore the minified React error if data loads. Rejected because it can mask real dashboard rendering faults.
- Disable server rendering for the whole dashboard. Rejected unless a narrower client-only boundary cannot solve the mismatch.
