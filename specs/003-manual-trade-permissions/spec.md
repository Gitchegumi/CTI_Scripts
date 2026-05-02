# Feature Specification: Manual Trade Permissions

**Feature Branch**: `003-manual-trade-permissions`  
**Created**: 2026-05-01  
**Status**: Draft  
**Input**: User description: "When the bot is set to `alert_only`, then the manual trades interface should show all trade history and allow all fields to be edited even for already recorded historical trades. Currently, the Trade History on the main dashboard does not show up in the manual trades interface. When the bot is set to any other setting, the only editable fields should be `notes` and `tags`"

## Clarifications

### Session 2026-05-01

- Q: In `alert_only`, should historical trades be deletable as well as editable? -> A: Any historical trade can be fully edited, but only manually created trades can be deleted.
- Q: How should `alert_only` edits to non-manual historical trades be stored? -> A: Store local overrides for edited fields and display the merged corrected record.
- Q: Should saved `alert_only` corrections remain visible after switching to another bot mode? -> A: Each bot mode should collect and display its own isolated trade-history and edit data.
- Q: How should existing records without a bot-mode value be classified? -> A: Assign existing unmodeled trade/edit data to `alert_only`.
- Q: Why is the trade-history data being collected and how should it be exported? -> A: Export mode-isolated strategy evaluation data in an LLM-friendly structured format for AI agent analysis and strategy adjustment workflows.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Review Complete History in Manual Trades (Priority: P1)

As the trader, I want the manual trades interface to show the same complete trade history that appears on the main dashboard so that I can review and maintain all recorded trading activity from one place.

**Why this priority**: The current manual trades interface omits trades that are visible in the main dashboard Trade History, which prevents the user from managing historical records consistently.

**Independent Test**: Populate the main dashboard Trade History with recorded historical trades, open the manual trades interface, and confirm every dashboard trade appears with matching core details and ordering.

**Acceptance Scenarios**:

1. **Given** historical trades are visible in the main dashboard Trade History, **When** the trader opens the manual trades interface, **Then** those same historical trades are visible there.
2. **Given** manual and non-manual historical trades both exist, **When** the manual trades interface loads, **Then** all trade types appear in one history list without duplicates.
3. **Given** no trade history exists for the current bot mode, **When** the manual trades interface loads, **Then** the trader sees an empty state rather than a missing or partial table.

---

### User Story 2 - Edit Historical Trades in Alert-Only Mode (Priority: P2)

As the trader running the bot in `alert_only`, I want to edit every field on any historical trade, including trades that were already recorded before this feature, so that paper-trading records can be corrected and completed after review.

**Why this priority**: `alert_only` is a non-execution mode where recorded trades represent user-maintained evaluation data, so historical record correction is expected and low risk.

**Independent Test**: Set the bot to `alert_only`, open an already recorded historical trade in the manual trades interface, edit each displayed field, save, reload, and confirm every change persists.

**Acceptance Scenarios**:

1. **Given** the bot is set to `alert_only`, **When** the trader edits a historical trade, **Then** every trade field shown in the interface is editable.
2. **Given** the bot is set to `alert_only` and a historical trade was not originally created through the manual trades interface, **When** the trader opens that trade for editing, **Then** the same full-field edit controls are available.
3. **Given** the trader saves full-field edits in `alert_only`, **When** the manual trades interface and main dashboard Trade History refresh, **Then** both views show the updated trade record.
4. **Given** the bot is set to `alert_only` and a historical trade was manually created, **When** the trader deletes that trade after confirmation, **Then** it is removed from the unified history.
5. **Given** the bot is set to `alert_only` and a historical trade was not manually created, **When** the trader reviews that trade, **Then** full-field editing is available but deletion is not available.
6. **Given** full-field edits were saved in `alert_only`, **When** the bot is switched to another mode, **Then** those `alert_only` corrections do not appear in the other mode's isolated trade history.

---

### User Story 3 - Restrict Edits Outside Alert-Only Mode (Priority: P3)

As the trader running the bot in any mode other than `alert_only`, I want historical trade records protected from accidental data changes while still being able to add notes and tags for journaling.

**Why this priority**: Demo, live, or any other execution-capable mode should preserve trade facts while still supporting review annotations.

**Independent Test**: Set the bot to a non-`alert_only` mode, open historical trades in the manual trades interface, and confirm only notes and tags can be changed while all other fields are read-only.

**Acceptance Scenarios**:

1. **Given** the bot is set to any mode other than `alert_only`, **When** the trader opens a historical trade for editing, **Then** only notes and tags are editable.
2. **Given** the bot is set to any mode other than `alert_only`, **When** the trader attempts to change trade facts such as symbol, direction, prices, times, size, status, or profit/loss, **Then** those fields cannot be modified.
3. **Given** the trader saves notes or tags in a non-`alert_only` mode, **When** the manual trades interface and main dashboard Trade History refresh, **Then** the annotation changes are visible without changing protected trade facts.
4. **Given** notes or tags are saved in one non-`alert_only` mode, **When** the trader switches to another bot mode, **Then** those annotation changes do not appear outside the mode where they were saved.

---

### User Story 4 - Export Agent-Ready Strategy Data (Priority: P4)

As the trader working with AI agents, I want to export mode-isolated trade history, corrections, annotations, and metadata in a format that is easy for LLMs and agentic workflows to consume so that strategy evaluation and adjustment can be assisted by AI without manual data wrangling.

**Why this priority**: The larger purpose of collecting this data is to evaluate strategy behavior and support AI-assisted strategy improvement, so the stored data needs a clean path out of the dashboard into analysis workflows.

**Independent Test**: Select a bot mode and export the current-mode trade dataset, then confirm the export includes records, annotations, overrides, permissions, source identity, schema/version metadata, and a concise analysis context without including unrelated modes.

**Acceptance Scenarios**:

1. **Given** mode-isolated trade history exists, **When** the trader exports data for the current mode, **Then** the export contains only records and edits associated with that mode.
2. **Given** corrected non-manual trades exist, **When** the trader exports agent-ready data, **Then** the export includes both the displayed corrected values and enough override/source metadata to explain what was changed.
3. **Given** notes and tags exist, **When** the trader exports agent-ready data, **Then** those annotations are included alongside the trade records they describe.
4. **Given** an AI agent receives the export, **When** it parses the file, **Then** records, fields, mode, source identity, and schema version are explicit without requiring dashboard-specific context.

### Edge Cases

- The bot mode changes while the manual trades interface is open; the interface must re-evaluate edit permissions before saving and prevent disallowed field updates.
- A historical trade appears in both the dashboard source and manual-trade source; the manual trades interface must show one record and preserve the canonical trade identity.
- A non-`alert_only` save request includes protected field changes along with notes or tags; the protected changes must be rejected or ignored while allowed annotation changes remain clear to the user.
- A historical trade has missing optional fields; in `alert_only`, those fields may be completed, while in other modes they remain read-only unless they are notes or tags.
- The trade history source is temporarily unavailable; the manual trades interface must show a user-friendly failure state and avoid presenting incomplete history as complete.
- A delete request targets a historical trade that was not manually created; the system must prevent deletion even when the bot mode is `alert_only`.
- A source historical trade is refreshed after local `alert_only` field overrides exist; the displayed trade must preserve the local overrides while retaining the original trade identity.
- The bot mode changes after trades, overrides, notes, or tags have been saved; the manual trades interface and main dashboard Trade History must show only the data associated with the newly current mode.
- An existing trade, override, note, or tag has no stored bot-mode value; it must be treated as `alert_only` data.
- The export contains a large number of trades; the system must preserve a consistent schema and include enough metadata for chunking or downstream agent processing.
- The export is generated after local overrides exist; the system must clearly identify original source values, displayed corrected values, and overridden fields.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The manual trades interface MUST display all historical trades that are visible in the main dashboard Trade History.
- **FR-002**: The manual trades interface MUST include both manually recorded trades and other recorded historical trades in a single unified history view.
- **FR-003**: The unified history view MUST avoid duplicate rows when the same trade is available from multiple history sources.
- **FR-004**: The manual trades interface MUST clearly preserve the current trade identity for each historical trade so edits update the intended record.
- **FR-005**: When the bot mode is `alert_only`, users MUST be able to edit every field exposed for any trade in the manual trades interface, including already recorded historical trades.
- **FR-006**: Full-field edits made in `alert_only` MUST persist and be reflected in both the manual trades interface and the main dashboard Trade History.
- **FR-007**: When the bot mode is not `alert_only`, users MUST only be able to edit notes and tags for any historical trade.
- **FR-008**: When the bot mode is not `alert_only`, the system MUST prevent modification of all non-annotation trade fields, including symbol, direction, entry details, exit details, size, status, fees, and profit/loss.
- **FR-009**: Permission checks for editable fields MUST be enforced at save time based on the current bot mode, not only when the page initially renders.
- **FR-010**: The user interface MUST make read-only fields visually distinguishable from editable notes and tags when the bot mode is not `alert_only`.
- **FR-011**: If a save attempt includes fields that are not editable in the current bot mode, the system MUST avoid silently changing protected trade data and MUST communicate the outcome to the user.
- **FR-012**: Notes and tags MUST remain editable for all historical trades in every bot mode.
- **FR-013**: When the bot mode is `alert_only`, users MUST be able to delete manually created trades after confirmation.
- **FR-014**: The system MUST prevent deletion of historical trades that were not manually created, regardless of bot mode.
- **FR-015**: When a non-manual historical trade is edited in `alert_only`, the system MUST store the edited field values as local overrides rather than replacing the original source record.
- **FR-016**: The manual trades interface and main dashboard Trade History MUST display local overrides merged with the original source record for any corrected non-manual historical trade.
- **FR-017**: Trade history, manual trades, local overrides, notes, and tags MUST be isolated by bot mode.
- **FR-018**: The manual trades interface and main dashboard Trade History MUST display only records and edits associated with the current bot mode.
- **FR-019**: Switching bot modes MUST NOT merge, copy, or display trade-history data, overrides, notes, or tags from another mode.
- **FR-020**: Existing trade-history records, overrides, notes, and tags without a stored bot-mode value MUST be classified as `alert_only` data.
- **FR-021**: Users MUST be able to export the current bot mode's unified trade-history dataset for AI-assisted strategy evaluation.
- **FR-022**: Exported data MUST use a structured, documented, machine-readable format suitable for LLMs and agentic workflows.
- **FR-023**: Exported data MUST include schema version, generated timestamp, bot mode, export scope, record counts, field descriptions or metadata, and the unified trade records.
- **FR-024**: Exported records MUST include source identity, manual/non-manual origin, displayed values, notes, tags, local override metadata when present, and enough context to evaluate strategy outcomes.
- **FR-025**: Exports MUST preserve mode isolation and MUST NOT include records, annotations, or overrides from another bot mode unless explicitly requested by a future feature.

### Key Entities

- **Historical Trade**: A recorded trade shown in trade history. Key attributes include trade identity, source, origin indicating whether it was manually created, symbol, direction, entry and exit details, size, status, fees, profit/loss, notes, and tags.
- **Bot Mode**: The current operating mode controlling edit permissions. `alert_only` allows full historical trade edits; all other modes allow only notes and tags.
- **Trade Annotation**: User-maintained review data attached to a historical trade. Key attributes include notes and tags.
- **Trade Override**: Local corrected field values for a non-manual historical trade edited in `alert_only`. Key attributes include the original trade identity, overridden fields, and the corrected values shown in unified trade history.
- **Mode-Isolated History**: The set of trades, overrides, notes, and tags collected for one bot mode. Key attributes include bot mode, associated historical trades, manual records, annotations, and overrides.
- **Unified Trade History**: The combined set of historical trades shown consistently in the manual trades interface and main dashboard Trade History.
- **Agent Export**: A structured export package for AI analysis. Key attributes include schema version, generated timestamp, bot mode, export scope, summary counts, field metadata, trade records, annotations, overrides, and analysis context.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of trades visible in the main dashboard Trade History are also visible in the manual trades interface after the same refresh cycle.
- **SC-002**: In `alert_only`, the trader can edit and save every exposed field on an already recorded historical trade in under 2 minutes.
- **SC-003**: In any non-`alert_only` mode, attempts to modify protected trade fields result in zero persisted changes to those fields.
- **SC-004**: Notes and tags can be updated successfully for any historical trade in every bot mode.
- **SC-005**: Duplicate trade rows caused by overlapping history sources are eliminated for 100% of trades with the same canonical identity.
- **SC-006**: After saving an allowed edit, both the manual trades interface and main dashboard Trade History show the updated data within one normal refresh interval.
- **SC-007**: After switching bot modes, 100% of displayed trade-history records and edits belong to the newly current mode.
- **SC-008**: 100% of existing records without a bot-mode value appear only when the current mode is `alert_only`.
- **SC-009**: The trader can export current-mode agent-ready trade data in under 30 seconds for at least 1,000 records.
- **SC-010**: 100% of exported records include explicit bot mode, source identity, displayed trade values, notes, tags, and override metadata when applicable.
- **SC-011**: An AI agent can determine the export schema version, scope, field meanings, and record count from the export metadata without reading dashboard code.

## Assumptions

- The manual trades interface is the existing `/manual-trades` experience described by the prior manual trade history specification.
- "All trade history" means the complete historical trade set for the current bot mode currently shown by the main dashboard Trade History, plus any manual trade records already maintained by the manual trades feature for that same mode.
- The system already has a single current bot mode value that can distinguish `alert_only` from all other modes.
- Notes and tags are considered annotations and are safe to edit regardless of bot mode.
- In non-`alert_only` modes, historical trade facts are protected even when the trade was originally entered manually.
- Trade history and user edits from one bot mode should remain available when returning to that mode, but should not appear while another mode is active.
- Existing records without mode metadata are legacy paper-trading data and should be associated with `alert_only`.
- The preferred first export format is structured JSON because it preserves nested annotations, overrides, metadata, and schema descriptions for LLM/agent workflows.
- Agent Export v1 includes trade history, annotations, overrides, and any linked strategy or signal identifiers already available in the unified history data; it does not require new strategy diagnostics collection.
