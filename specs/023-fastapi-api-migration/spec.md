# Feature Specification: Refactor Python API Service to FastAPI

**Feature Branch**: `023-fastapi-api-migration`  
**Created**: 2026-06-28  
**Status**: Draft  
**Input**: User description: "Refactor Python API service to FastAPI" (GitHub issue #116)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dashboard and operator tooling keep working unchanged (Priority: P1)

An operator opens the TradeGumi dashboard and uses every existing screen — live
status, analytics drill-downs, the Signal Journal, manual trades, strategy
metrics, and the maintenance/purge controls. The dashboard talks to the same API
paths as before and receives the same response shapes and status codes, so
nothing in the operator's workflow changes after the backend is rebuilt on the
new framework.

**Why this priority**: This is the entire point of the refactor. The API exists
to serve the dashboard and operator tooling. If any endpoint changes its
behavior, status code, or response shape, the feature has failed regardless of
how clean the new internals are. Endpoint parity is the non-negotiable MVP.

**Independent Test**: Run the dashboard and operator tooling against the
rebuilt API with a representative dataset and confirm every screen renders and
every action succeeds exactly as it did against the previous implementation.
Equivalent automated parity tests exercise each endpoint's success and error
responses.

**Acceptance Scenarios**:

1. **Given** a healthy backend, **When** the dashboard requests live status, **Then** it receives the current configuration plus runtime state, including whether the trading worker is live, in the same shape as before.
2. **Given** a valid analytics date range, **When** the dashboard requests any analytics, journal, trades, or strategy-metrics endpoint, **Then** it receives the same response shape and HTTP status as the previous implementation.
3. **Given** a request missing required parameters, **When** it reaches an endpoint that requires them, **Then** the service returns the same validation error and status code (e.g. 400) as before.
4. **Given** a request for a path that does not exist, **When** it is received, **Then** the service returns the same not-found response as before.

### User Story 2 - Operator control actions still reach the worker safely (Priority: P1)

An operator changes the bot mode, challenge type, program, or phase, grades or
edits a Signal Journal entry, creates or deletes a manual trade, or runs a
maintenance purge. Each control action is accepted, validated, and — where
applicable — delivered to the trading worker through the existing command
channel. The operator gets a clear accepted/rejected/unavailable result and is
never told an action succeeded when it was not actually delivered.

**Why this priority**: Control actions change real trading behavior and durable
records. Silently dropping a command, or placing an order from the API, would be
a safety violation. This must hold from day one and is as critical as read
parity.

**Independent Test**: Issue each control action against the rebuilt API and
confirm valid commands are published to the command channel and acknowledged,
invalid commands are rejected with the existing error, and a command-channel
outage produces an explicit "not delivered" failure rather than a false success.

**Acceptance Scenarios**:

1. **Given** a valid configuration-change request, **When** it is submitted, **Then** a command is published to the worker and the operator receives an acceptance response carrying a command identifier.
2. **Given** an invalid configuration-change request, **When** it is submitted, **Then** it is rejected with the existing bad-request response and no command is published.
3. **Given** the command channel is unavailable, **When** a valid control action is submitted, **Then** the operator receives an explicit "not delivered — command channel unavailable" failure rather than a success.
4. **Given** a request to any protected control or export endpoint without a valid API token, **When** it is submitted, **Then** it is rejected as unauthorized, matching the existing protected-endpoint behavior.
5. **Given** any request to the API service, **When** it is processed, **Then** no order is ever placed with the broker by the API.

### User Story 3 - Partial outages degrade gracefully, durable analytics stay available (Priority: P2)

The durable analytics store is healthy but the hot-state cache and/or the broker
connection are down. The operator can still view durable analytics, the Signal
Journal, and strategy metrics. Endpoints that depend on the unavailable
dependencies degrade predictably (stale/empty hot state, an explicit
service-unavailable for broker-backed account/position/history data) instead of
taking down the whole service. Conversely, if the durable analytics store is
unreachable at startup, the service fails fast rather than serving broken data.

**Why this priority**: Resilience behavior already exists and operators rely on
it during partial outages, but it sits below raw endpoint and command parity in
criticality. It must be preserved, not improved.

**Independent Test**: Start the service with the durable store healthy but the
cache and broker unavailable, confirm analytics/journal/metrics endpoints still
serve while hot-state and broker-backed endpoints degrade as specified; then
start the service with the durable store unreachable and confirm it refuses to
start.

**Acceptance Scenarios**:

1. **Given** the durable analytics store is unreachable at startup, **When** the service starts, **Then** it fails fast and does not begin serving requests.
2. **Given** the durable store is healthy but the hot-state cache is down, **When** analytics, journal, and strategy-metrics endpoints are requested, **Then** they continue to serve successfully.
3. **Given** the broker connection is unavailable, **When** account, positions, or trade-history endpoints are requested, **Then** they return the existing service-unavailable response rather than erroring the whole service.
4. **Given** the live-status endpoint is requested while the hot-state cache is stale or empty, **When** it responds, **Then** it reports worker liveness from the worker heartbeat and degrades hot fields without failing.

### User Story 4 - Developers extend the API with clear route ownership (Priority: P3)

A developer adds or changes an API endpoint. Routes are organized by concern,
request/response handling is validated by the framework rather than hand-rolled,
and shared concerns (durable store access, cache/state access, auth/token
handling, read-only broker access) are provided through reusable dependencies.
Adding an endpoint no longer means editing one large hand-rolled routing block.

**Why this priority**: This is the underlying motivation for the refactor, but
it delivers developer value rather than operator value and can only be judged
once parity (P1) is proven. It is the last slice, not the first.

**Independent Test**: Review the resulting structure to confirm routes are
grouped by concern, shared dependencies are reused rather than duplicated per
route, and a new endpoint can be added by editing only its concern's module.

**Acceptance Scenarios**:

1. **Given** the rebuilt service, **When** a developer inspects it, **Then** routes are grouped by concern (status, data, config/actions, journal, trades, strategy metrics, purge).
2. **Given** a route that needs the durable store, cache, auth token, or read-only broker access, **When** it is implemented, **Then** it obtains that capability through a shared dependency rather than re-implementing it.
3. **Given** a request body or query parameters, **When** they are processed, **Then** validation is handled by the framework and produces responses compatible with today's behavior.

### Edge Cases

- A client disconnects before a response finishes streaming — the service handles the broken connection without crashing the worker process or leaking errors.
- A request body is empty or malformed JSON on a control endpoint — the service treats it as the existing implementation does (empty payload / validation error) rather than raising an unhandled error.
- Cross-origin preflight requests and standard cross-origin response headers continue to be served so the dashboard can call the API from its own origin.
- Legacy/aliased paths that the current service rewrites internally (e.g. the older manual-trades path) continue to resolve to the same handler.
- A required date-range or identifier parameter is present but invalid — the service returns the existing client-error response, not a server error.
- The hot-state cache returns stale data past the freshness threshold — worker-liveness is reported from the heartbeat, not assumed from cache presence.

## Clarifications

### Session 2026-06-28

- Q: Must response bodies match the previous implementation byte-for-byte, or only structurally? → A: Structural/semantic parity — same keys, values, types, and HTTP status codes; JSON whitespace/indentation and `Content-Length` may differ.
- Q: Should the rebuilt service expose auto-generated interactive API docs and schema, which the previous service did not? → A: Yes — expose interactive docs and an OpenAPI schema as a new developer-experience addition (the one intentional addition to the otherwise parity-only surface).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST continue to serve every existing dashboard/operator API path: live status, analytics data reads, configuration changes, operator actions, positions, trades (including manual trades), Signal Journal operations, strategy metrics, and purge.
- **FR-002**: For every existing endpoint, the system MUST return HTTP status codes and response shapes compatible with the previous implementation for both success and error cases. Parity is defined structurally/semantically (same keys, values, types, and status codes); byte-level differences such as JSON whitespace, indentation, or `Content-Length` are acceptable.
- **FR-003**: The system MUST remain a dedicated Python API service, separate from the trading worker process, and MUST NOT run the trading loop.
- **FR-004**: The system MUST NOT place orders with the broker. It MAY create read-only broker access for account, positions, and trade-history data only.
- **FR-005**: Configuration-change and operator-action requests MUST be validated and, where applicable, published to the trading worker over the existing command channel; the channel's behavior MUST be unchanged.
- **FR-006**: A control action that cannot be delivered (command channel unavailable) MUST return an explicit failure response and MUST NEVER report success for an undelivered command.
- **FR-007**: The live-status endpoint MUST report worker liveness derived from the worker heartbeat.
- **FR-008**: The system MUST fail fast at startup if the durable analytics store is unavailable, rather than starting in a degraded state.
- **FR-009**: When the durable store is healthy, the system MUST keep analytics, journal, and strategy-metrics endpoints available even when the hot-state cache and/or broker connection are unavailable.
- **FR-010**: Broker-dependent endpoints (account/positions/history) MUST degrade with the existing service-unavailable response when the broker is unavailable, without failing unrelated endpoints.
- **FR-011**: Endpoints currently protected by the API token MUST remain protected, rejecting unauthorized requests with the existing unauthorized response; endpoints currently open MUST remain open.
- **FR-012**: The durable analytics store MUST remain the source of truth for durable data, and the hot-state cache and command channel MUST retain their current roles.
- **FR-013**: Cross-origin request handling (preflight responses and cross-origin response headers) MUST continue to function so the dashboard can call the API from its own origin.
- **FR-014**: Internal path rewrites/aliases that the current service honors MUST continue to resolve to the same behavior.
- **FR-015**: Routes MUST be organized by concern, and shared concerns (durable store access, cache/state access, auth/token handling, read-only broker access) MUST be provided as reusable dependencies rather than duplicated per route.
- **FR-016**: The service entrypoint MUST start the rebuilt application and run until a termination signal, shutting down cleanly.
- **FR-017**: The system MUST include automated tests covering endpoint parity, authentication behavior, and command-channel failure handling.
- **FR-018**: Operator-facing documentation (quickstart / local development) MUST be updated if API startup or local development commands change.
- **FR-019**: Service packaging and the API entrypoint MUST be updated so the rebuilt service runs in its existing container with its required runtime dependencies.
- **FR-020**: The system MUST expose auto-generated interactive API documentation and an OpenAPI schema describing the existing endpoints. This is the only intentional addition to the public surface; it MUST NOT alter the behavior, paths, or responses of any existing `/api/*` endpoint, and unknown non-doc paths MUST still return the existing not-found response.

### Key Entities *(include if feature involves data)*

- **Live status**: A snapshot combining current configuration and runtime state, including worker-live indication derived from the worker heartbeat.
- **Operator command**: A validated control instruction (mode, challenge type, program, phase, and similar) published to the worker, carrying a command identifier and an accepted/rejected/undelivered outcome.
- **Signal Journal entry**: A durable record an operator can read, grade, invalidate, annotate, reset, export, or purge.
- **Manual trade record**: A durable operator-entered trade that can be listed, created, and deleted, subject to permission rules.
- **Strategy metrics / analytics result**: Durable, date-range-scoped aggregates (summaries, opportunities, lifecycle events, period comparisons, exports) served from the durable store.
- **Account / position / history data**: Read-only broker-sourced data served only when broker access is available.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of existing dashboard and operator workflows continue to function against the rebuilt service with no client-side changes required.
- **SC-002**: For every existing endpoint, success and error responses match the previous implementation's status codes and parsed response structure (keys, values, types) — verified by automated parity tests that assert on parsed structure rather than raw bytes.
- **SC-003**: 100% of valid control actions are delivered to the worker or explicitly reported as undelivered; zero control actions report success without delivery.
- **SC-004**: No order is ever placed by the API service under any tested condition.
- **SC-005**: With the durable store healthy and both the hot-state cache and broker unavailable, all analytics, journal, and strategy-metrics endpoints still return successful responses.
- **SC-006**: With the durable store unavailable at startup, the service refuses to start 100% of the time.
- **SC-007**: Automated tests cover endpoint parity, authentication behavior, and command-channel failure handling, and pass in the project's standard test run.
- **SC-008**: A developer can add a new endpoint by editing only the relevant concern's route module and reusing existing shared dependencies, without touching unrelated routes.

## Assumptions

- "Compatible response shapes and status codes" is measured against the current API service's observable behavior as the parity baseline; where the current behavior is itself the spec, it is preserved exactly rather than corrected.
- The worker/API/dashboard split established by the prior runtime-container work remains in force; this refactor changes only how the API service is built internally, not the process topology.
- The dashboard's own proxy/routing layer is out of scope and continues to call the same API paths.
- The durable analytics store, hot-state cache, and command channel remain the same backing services with the same roles; only the API service's internal framework changes.
- The existing API token mechanism remains the authentication method for protected endpoints; no new auth scheme is introduced.
- Read-only broker access reuses the existing read-only client wiring; the broker/execution abstraction is not otherwise reworked.
- Standard web-service performance and error-handling expectations apply; the refactor is not expected to change latency characteristics materially.

## Out of Scope

- Moving trading-loop behavior into the API service.
- Moving the dashboard's proxy/routing logic into the Python API service.
- Reworking the broker/execution client abstraction beyond read-only dependency wiring.
- Adding new endpoints or changing existing endpoint behavior beyond what is required to preserve parity. (The auto-generated documentation/schema endpoints in FR-020 are the sole intentional exception and add no new operational behavior.)
