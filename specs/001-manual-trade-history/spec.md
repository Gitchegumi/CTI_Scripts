# Feature Specification: Manual Trade History Page

**Feature Branch**: `001-manual-trade-history`
**Created**: 2026-04-28
**Status**: Draft
**Input**: User description: "https://tradegumi.gitchegumi.com/manual-trades shows a 404 error
rather than displaying the trade history. Trade history should be editable if the
`trading_mode` is set to `alert_only` and should allow for notes and tags if any other mode
is set. It should populate with Trade History. Any manually added trades should also show up
on Trade History on the main dashboard."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — View Trade History at `/manual-trades` (Priority: P1)

A trader navigates to `https://tradegumi.gitchegumi.com/manual-trades` and expects to see
their trade history. Instead they get a 404 error. The page must load successfully and
display all available trade history — both automatically executed broker trades and manually
entered paper trades.

**Why this priority**: The page is completely broken in production. All other improvements
on this page depend on it being accessible first.

**Independent Test**: Navigate to `/manual-trades` while authenticated; the page renders
with a trade history table (or an empty-state message if no trades exist). No 404, no
blank screen, no unhandled error.

**Acceptance Scenarios**:

1. **Given** a trader is authenticated, **When** they navigate to `/manual-trades`,
   **Then** the page renders with a trade history table populated with all available
   closed trades.
2. **Given** no closed trades exist, **When** the page loads, **Then** an informative
   empty-state message is displayed (not a 404 or error).
3. **Given** the trader is not authenticated, **When** they navigate to `/manual-trades`,
   **Then** they are redirected to the login page and returned to `/manual-trades` after
   successful login.

---

### User Story 2 — Full Trade CRUD in Alert-Only Mode (Priority: P2)

When the system is in `alert_only` mode, the trader is paper-trading — no real orders are
placed. They want to manually record trades they would have taken, update them as the
trade evolves (e.g., add exit price when closing), and delete incorrect entries.

**Why this priority**: Alert-only is the primary evaluation mode before risking real
capital. Accurate manual trade tracking is essential for validating strategy performance.

**Independent Test**: With `trading_mode=alert_only`, a trader can: (a) add a new trade
entry with symbol, direction, entry price, entry time; (b) edit that trade to add an exit
price and exit time; (c) delete the trade. All changes persist across page reloads.

**Acceptance Scenarios**:

1. **Given** `trading_mode` is `alert_only`, **When** the trader clicks "Add Trade",
   **Then** a form appears allowing entry of symbol, direction (long/short), entry price,
   optional exit price, entry time, optional exit time, and notes.
2. **Given** a manual trade exists, **When** the trader clicks "Edit" on that trade,
   **Then** a pre-filled form appears allowing modification of any field.
3. **Given** a manual trade exists, **When** the trader clicks "Delete" and confirms,
   **Then** the trade is permanently removed and no longer appears in any trade history view.
4. **Given** `trading_mode` is **not** `alert_only`, **When** the trader views the page,
   **Then** the "Add Trade" button and edit/delete actions for trade data are not available.

---

### User Story 3 — Notes and Tags in Demo/Live Modes (Priority: P3)

When the system is in `demo` or `live` mode, trades are placed automatically by the bot.
The trader cannot add or delete trade records (those come from the broker), but they want
to annotate each trade with free-form notes and one or more tags to support journaling
and post-session review.

**Why this priority**: Annotations are the key review tool for strategy improvement once
real-capital trading begins. Tags enable pattern analysis across trades (e.g., "missed-entry",
"CTI-setup", "news-spike").

**Independent Test**: With `trading_mode=demo` or `live`, a trader can open the notes/tags
panel on any trade, type a note, add tags, save, and see the annotation persist after a
page reload. The trade's price/P/L data remains unchanged.

**Acceptance Scenarios**:

1. **Given** `trading_mode` is `demo` or `live`, **When** the trader clicks to annotate a
   trade, **Then** a panel or modal appears showing the current note and tags, with inputs
   to edit them.
2. **Given** a note is entered and saved, **When** the trader reloads the page, **Then**
   the note is still present on that trade.
3. **Given** a tag is added to a trade, **When** the trader filters by that tag, **Then**
   only trades with that tag are shown.
4. **Given** `trading_mode` is `alert_only`, **When** the trader edits a trade, **Then**
   notes are also editable as part of the existing edit form (not a separate annotations panel).

---

### User Story 4 — Manual Trades Appear on Main Dashboard (Priority: P4)

A trader adds a manual paper trade on the `/manual-trades` page. They return to the main
dashboard and expect to see that trade in the Trade History component, so there is a single
unified view of all trading activity.

**Why this priority**: Splitting manual and automated trades into separate views undermines
the purpose of the dashboard as the single source of truth for performance.

**Independent Test**: After adding a manual trade on `/manual-trades`, navigate to the
main dashboard at `/`; the new trade appears in the Trade History component within
the normal polling interval.

**Acceptance Scenarios**:

1. **Given** a manual trade is added on `/manual-trades`, **When** the trader views the
   main dashboard, **Then** that trade appears in the Trade History component.
2. **Given** a manual trade is deleted, **When** the trader views the main dashboard,
   **Then** that trade no longer appears in the Trade History component.
3. **Given** both manual and automated trades exist, **When** the Trade History component
   loads, **Then** both types appear together, sorted by close time (most recent first).

---

### Edge Cases

- What happens when `/manual-trades` is accessed without a valid `JOURNAL_TOKEN` cookie?
  → Must redirect to `/journal/login` with a `?from=/manual-trades` parameter so the user
  is returned after login.
- What happens when the trader adds a manual trade in `alert_only` mode but the API
  endpoint is unavailable?
  → Display a user-friendly error message; do not lose the form data.
- What happens when a note or tag exceeds a reasonable length?
  → Notes are capped at 1,000 characters; individual tags are capped at 50 characters.
  Exceeding the limit shows an inline error, not a silent truncation.
- What happens when the trader switches `trading_mode` from `alert_only` to `demo`?
  → Existing manual trades remain visible and annotatable, but the "Add Trade" and
  edit/delete actions are hidden.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST render the `/manual-trades` page without a 404 or unhandled
  error for authenticated users.
- **FR-002**: System MUST display all closed trades (automated broker trades AND manually
  entered trades) in a unified trade history table on `/manual-trades`.
- **FR-003**: In `alert_only` mode, users MUST be able to add new manual trade entries
  with: symbol, direction, entry price, entry time, and optional exit price/time/notes.
- **FR-004**: In `alert_only` mode, users MUST be able to edit any field of an existing
  manual trade entry.
- **FR-005**: In `alert_only` mode, users MUST be able to delete a manual trade entry
  after a confirmation step.
- **FR-006**: In `demo` and `live` modes, users MUST be able to add and edit a free-form
  text note on any trade (manual or automated).
- **FR-007**: In `demo` and `live` modes, users MUST be able to add, view, and remove
  free-form text tags on any trade.
- **FR-008**: Manual trades added via `/manual-trades` MUST appear in the main dashboard
  Trade History component within the component's normal data refresh interval.
- **FR-009**: Unauthenticated requests to `/manual-trades` MUST redirect to the login
  page and return the user to `/manual-trades` after successful authentication.
- **FR-010**: The trade history table on `/manual-trades` MUST support filtering by
  symbol, trade direction, and tag.

### Key Entities

- **ManualTrade**: A user-entered paper trade record. Attributes: symbol, direction
  (long/short), entry price, optional exit price, entry time, optional exit time, P/L
  (computed), status (open/closed), notes, tags (list of strings).
- **TradeAnnotation**: Notes and tags attached to any trade (manual or automated). May
  be stored as part of the trade record or as a separate annotation store.
- **ClosedTrade**: An automatically executed trade record from the broker. Read-only for
  price/time/P/L data; supports annotation (notes and tags).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `/manual-trades` loads and renders for authenticated users in under 3 seconds,
  with zero 404 or unhandled error responses.
- **SC-002**: 100% of manually added trades appear in the main dashboard Trade History
  within one polling cycle (≤30 seconds) after being saved.
- **SC-003**: Traders can add or edit a note on any trade in under 30 seconds from
  opening the annotation interface to seeing the saved result.
- **SC-004**: Tag filtering reduces the displayed trade list to only matching trades with
  no false positives or omissions.

## Assumptions

- Authentication is preserved: the `/manual-trades` page remains protected by the same
  `JOURNAL_TOKEN` middleware as the journal. The session/token mechanism is reused, not
  replaced.
- Tags are free-form text strings (not a predefined list). The trader types them freely;
  the system normalizes them to lowercase and trims whitespace.
- Automated broker trades are read-only for core data (price, time, P/L, volume). Only
  annotations (notes and tags) are writable on automated trades.
- In `alert_only` mode, P/L for manual trades is computed from entry/exit prices using a
  simplified pip-value calculation (or can be entered manually if no calculation is
  performed — this is acceptable for paper trading purposes).
- The main dashboard Trade History component (`TradeHistory.tsx`) will receive manual
  trades merged into its existing data feed. Manual trades are mapped to the `ClosedTrade`
  shape the component already expects.
- The production 404 is caused by either a stale deployment or a missing/misconfigured
  `JOURNAL_TOKEN` environment variable in the production environment — confirming and
  fixing the deployment is in scope for this feature.
