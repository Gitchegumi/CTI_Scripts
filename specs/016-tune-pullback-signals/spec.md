# Feature Specification: Tune Pullback Signal Alerts

**Feature Branch**: `016-tune-pullback-signals`
**Created**: 2026-06-05
**Status**: Draft
**Input**: User description: "GitHub issue #99: Tune pullback signal rules so valid pullback opportunities become alerts."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Valid Pullbacks Become Alerts (Priority: P1)

As the strategy owner, I want valid trend pullbacks to emit alert and journal signals so the pullback entry becomes available before the later continuation entry.

**Why this priority**: The attached June 1-5 metrics show 1,542 pullback-type evaluated opportunities and 2 `CTI-v1.2-pullback` strategy counts, but `signal-journal-all-2026-06-05.csv` contains 92 journaled Discord rows, all continuation, and zero pullback rows.

**Independent Test**: Replay periods containing larger-trend pullbacks into the value area with rejection and exhaustion, then confirm pullback signals are emitted, journaled, and visible in exported alert history.

**Acceptance Scenarios**:

1. **Given** a larger uptrend, a pullback into the value area, a valid lower-wick rejection candle, and exhaustion evidence, **When** the opportunity is evaluated, **Then** a BUY pullback signal is emitted before continuation confirmation is required.
2. **Given** a larger downtrend, a pullback into the value area, a valid upper-wick rejection candle, and exhaustion evidence, **When** the opportunity is evaluated, **Then** a SELL pullback signal is emitted before continuation confirmation is required.
3. **Given** a valid pullback setup and a continuation setup later in the same move, **When** both opportunities are evaluated, **Then** the pullback signal is not suppressed merely because a continuation signal could also appear later.

---

### User Story 2 - Pullback Gates Are Tuned Conservatively (Priority: P1)

As the strategy owner, I want the trigger candle, value-area sequence, and momentum exhaustion gates to accept realistic pullbacks without turning every retracement into an alert.

**Why this priority**: Current diagnostics show the main blockers are highly restrictive across 18,713 pullback rule evaluations: pullback trigger candles pass 1,342 / 18,713 (7.17%), the value-area sequence passes 3,405 / 18,713 (18.20%), and Stoch RSI exhaustion passes 6,596 / 18,713 (35.25%).

**Independent Test**: Evaluate controlled examples for long and short pullbacks that include valid rejection candles, value-area contact within a reasonable zone, and recent exhaustion memory; verify they pass while weak or directionally wrong setups still fail.

**Acceptance Scenarios**:

1. **Given** a pullback candle with a small body and a long rejection wick in the intended direction near or through the value area, **When** pullback trigger evaluation runs, **Then** the candle can pass as a valid entry trigger.
2. **Given** price retraces into a configurable zone around the value area after a prior outer-band move in the trend direction, **When** the pullback sequence is evaluated, **Then** the sequence can pass without requiring exact midline contact.
3. **Given** momentum recently reached exhaustion within the configured lookback window, **When** the pullback is evaluated, **Then** the momentum gate can pass without requiring a perfect current-bar crossover.
4. **Given** a candle has no meaningful rejection wick, violates trend structure, lacks a prior trend-side outer-band move, or shows no recent exhaustion, **When** the opportunity is evaluated, **Then** the pullback is rejected with the matching reason.

---

### User Story 3 - Pullback Diagnostics Explain Outcomes (Priority: P2)

As the strategy owner, I want metrics and exports to show how many pullback candidates were evaluated, rejected, emitted, journaled, and suppressed so future tuning is guided by evidence rather than guesswork.

**Why this priority**: The issue includes useful near-miss and criterion pass-rate data, but the operator needs a clear before-and-after view that distinguishes real rule improvements from random alert volume changes.

**Independent Test**: Run mixed pass, fail, suppression, and alert cases, then inspect metrics and journal exports for complete pullback counts and stable blocker names.

**Acceptance Scenarios**:

1. **Given** pullback candidates are evaluated during a reporting period, **When** metrics are generated, **Then** the report includes counts for candidates evaluated, candidates blocked by each gate, near misses, alerts emitted, alerts journaled, and alerts suppressed by prime-signal logic.
2. **Given** a pullback candidate fails the trigger candle, value-area sequence, momentum exhaustion, structure, or trend context gate, **When** diagnostics are recorded, **Then** the first blocker and relevant supporting values are visible in the report.
3. **Given** pullback alerts are emitted and later exported, **When** the Signal Journal export is reviewed, **Then** rows can be filtered by pullback signal type and distinguished from continuation rows.

---

### User Story 4 - Existing Strategy Protections Remain Intact (Priority: P2)

As the strategy owner, I want pullback tuning to preserve trend context, structure, prime-signal controls, and continuation behavior so the change creates earlier valid entries rather than lower-quality noise.

**Why this priority**: The goal is not to lower every threshold blindly; it is to restore useful pullback entries while keeping the system conservative enough for alert/demo review.

**Independent Test**: Run continuation regression cases, invalid pullback cases, and prime-suppression cases alongside the new valid pullback cases; verify existing protections still produce expected outcomes.

**Acceptance Scenarios**:

1. **Given** an opportunity lacks larger-trend context, **When** pullback evaluation runs, **Then** no pullback alert is emitted.
2. **Given** a pullback violates the expected higher-low or lower-high structure, **When** it is evaluated, **Then** no pullback alert is emitted.
3. **Given** a continuation setup that was valid before this change, **When** it is evaluated, **Then** continuation behavior remains distinguishable and unchanged except for any intended interaction with earlier pullback alerts.
4. **Given** a pullback would be suppressed by prime-signal rules, **When** the reporting period is summarized, **Then** the suppression is counted separately from rule-gate rejection.

### Edge Cases

- A rejection candle pierces the value area and closes back in the intended direction: treat as eligible if the body and wick proportions show meaningful rejection.
- A rejection candle has a long wick in the wrong direction: reject as directionally invalid.
- Price approaches but does not exactly touch the midline: evaluate against the configured value-area zone rather than an exact touch requirement.
- Price never made a prior trend-side outer-band move before the pullback: reject the pullback sequence even if current price is near the midline.
- Momentum exhaustion occurred recently but is no longer perfect on the current candle: allow within the configured memory window.
- Momentum exhaustion is stale or absent: reject the momentum gate.
- A valid pullback and a continuation signal occur close together: preserve both signal identities and report any suppression explicitly.
- No pullback candidates occur in a replay period: metrics should show zero evaluated rather than implying rule failure.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST emit pullback alerts when a larger-trend setup retraces into the value area, shows directional rejection, satisfies exhaustion evidence, and does not violate configured protections.
- **FR-002**: System MUST preserve continuation signals as distinct from pullback signals in alerts, journal rows, metrics, and exports.
- **FR-003**: Pullback trigger evaluation MUST accept directionally valid hammer-style and shooting-star-style rejection candles when the candle body is small relative to the full candle range and the rejection wick supports the intended trade direction.
- **FR-004**: Pullback trigger evaluation MUST use configurable body-to-range and wick requirements, with a conservative default that accepts body size around one-third or less of the candle range.
- **FR-005**: BUY pullback trigger evaluation MUST allow long lower-wick rejection near or through the value area.
- **FR-006**: SELL pullback trigger evaluation MUST allow long upper-wick rejection near or through the value area.
- **FR-007**: Pullback trigger evaluation MUST reject candles with no meaningful rejection wick, the wrong rejection direction, or a body that is too large for the configured pullback trigger profile.
- **FR-008**: Pullback value-area sequence evaluation MUST require a prior outer-area move in the trend direction before accepting a retracement as a pullback.
- **FR-009**: Pullback value-area sequence evaluation MUST allow a configurable zone around the midline or comparable value area rather than requiring exact contact.
- **FR-010**: Pullback value-area tolerance MUST be configurable and measurable in a normalized way so operators can widen or narrow the zone without changing unrelated strategy behavior.
- **FR-011**: Pullback momentum evaluation MUST treat exhaustion as the goal and MUST allow recent overextension memory within a configurable lookback window.
- **FR-012**: Pullback momentum evaluation MUST NOT require a perfect current-candle crossover when recent exhaustion evidence is still valid.
- **FR-013**: MACD MUST NOT be a hard blocker for pullback entries by default.
- **FR-014**: System MUST allow MACD to remain available as confidence or diagnostic context for pullback entries.
- **FR-015**: System MUST provide a configuration option to make MACD a hard pullback blocker only when explicitly enabled.
- **FR-016**: Pullback evaluation MUST preserve larger-trend context and MUST NOT classify a valid pullback as trendless solely because the immediate lower timeframe weakens during the retracement.
- **FR-017**: Pullback evaluation MUST preserve structure requirements that prevent entries after the relevant higher-low or lower-high structure is broken.
- **FR-018**: System MUST record stable diagnostics for pullback candidates evaluated, candidates blocked by each criterion, near misses, alerts emitted, alerts journaled, and alerts suppressed by prime-signal logic.
- **FR-019**: System MUST include enough pullback diagnostic detail in metrics to compare trigger candle failure rate, value-area sequence failure rate, and momentum exhaustion failure rate before and after tuning.
- **FR-020**: Signal Journal exports MUST include pullback rows when pullback alerts are emitted and journaled during the selected period.
- **FR-021**: Discord or operator-facing alert output MUST include pullback alerts when valid pullback setups pass the tuned rules.
- **FR-022**: Tuning MUST be conservative and test-backed so improved pullback alert coverage does not flood alerts with directionally weak or structure-broken setups.
- **FR-023**: Tests MUST cover valid BUY and SELL pullbacks, rejected trigger candles, rejected value-area sequences, rejected momentum exhaustion, MACD-as-diagnostic behavior, optional MACD hard-block behavior, metrics counts, journal export rows, and continuation regression behavior.

### Key Entities *(include if feature involves data)*

- **Pullback Candidate**: A potential pullback opportunity evaluated inside a larger trend, including direction, trend context, structure context, value-area position, trigger candle evidence, exhaustion evidence, and suppression state.
- **Pullback Alert**: An emitted operator-facing signal with pullback signal type, direction, symbol, strategy identity, entry context, and diagnostic details.
- **Trigger Candle Profile**: The candle-shape evidence used for pullback entry, including body-to-range proportion, rejection wick direction, rejection wick size, and position relative to the value area.
- **Value-Area Sequence**: The trend-side outer-area move followed by a retracement into a configurable zone around the midline or comparable value area.
- **Exhaustion Memory**: Recent momentum-overextension evidence that remains valid for a small configurable lookback window.
- **Pullback Diagnostic Summary**: Reporting data that counts pullback candidates by evaluated, rejected-by-gate, near-miss, emitted, journaled, and suppressed outcomes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Replay or simulation periods that include valid pullback setups produce at least one `signal_type=pullback` journal row and at least one pullback operator alert.
- **SC-002**: Valid controlled BUY and SELL pullback scenarios pass the tuned rule stack in 100% of required allowed-case tests.
- **SC-003**: Required invalid pullback scenarios identify the expected rejection category in 100% of blocker-focused tests.
- **SC-004**: Pullback trigger candle failure rate is reduced by at least 15 percentage points from the current 92.83% failure baseline in representative replay data without causing invalid trigger fixtures to pass.
- **SC-005**: Value-area sequence tolerance is configurable and its accepted/rejected candidate counts are visible in reporting for every evaluated replay period.
- **SC-006**: MACD is absent as a hard pullback blocker in default behavior, while an explicit hard-block configuration is covered by tests.
- **SC-007**: Metrics reports show counts for evaluated, rejected, near-miss, emitted, journaled, and prime-suppressed pullback candidates for every reporting period with pullback evaluation enabled.
- **SC-008**: Existing continuation regression tests remain passing and continuation rows remain distinguishable from pullback rows in journal exports.

## Assumptions

- The primary user is the strategy owner/operator reviewing Discord alerts, Signal Journal exports, and strategy metrics.
- The feature tunes alert qualification and diagnostics only; funded execution behavior, risk sizing, watchlist membership, and market-data provider behavior remain out of scope.
- Existing 15m bridge and larger-trend context should be preserved because the issue evidence shows this trend bridge is useful rather than restrictive.
- Configuration defaults should remain conservative and can be adjusted after review of replay metrics.
- The attached data files are treated as the baseline for current behavior: `signal-journal-all-2026-06-05.csv` has 92 journaled Discord rows, all continuation, zero pullback journal rows, and 70 prime-suppressed follow-on signals; `strategy-metrics-2026-06-01-to-2026-06-05.json` has 128,966 total evaluations, 18,713 pullback rule evaluations, 1,542 pullback-type opportunities, 2 `CTI-v1.2-pullback` strategy counts, and pullback trigger failures at roughly 92.83%.
