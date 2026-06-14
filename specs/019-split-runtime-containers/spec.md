# Feature Specification: Split Runtime into API, Dashboard, and Worker Containers

**Feature Branch**: `019-split-runtime-containers`  
**Created**: 2026-06-13  
**Status**: Draft  
**Input**: User description: "https://github.com/Gitchegumi/CTI_Scripts/issues/112 — Split runtime into API, dashboard, and worker containers"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Trading continues when the dashboard fails (Priority: P1)

As an operator, I need the trading engine (market data polling, watchlist scanning, signal processing, alerts, and metric writes) to keep running even if the dashboard UI crashes, hangs, or is restarted, so that trading activity is never interrupted by a presentation-layer problem.

**Why this priority**: This is the core motivation for the split. Today a dashboard failure can terminate the trading loop, which is the most damaging failure mode because it silently stops trades and alerts. Decoupling the worker from the UI delivers the primary value on its own.

**Independent Test**: Stop or kill the dashboard service while the worker is mid-cycle, and confirm the worker continues polling, scanning, generating signals, sending alerts, and writing metrics without interruption or restart.

**Acceptance Scenarios**:

1. **Given** all three services are running, **When** the dashboard service is stopped or crashes, **Then** the worker continues its trading cycle uninterrupted and the API continues serving analytics.
2. **Given** the dashboard service has crashed, **When** the dashboard service is restarted, **Then** it reconnects to the API and resumes displaying live data without requiring the worker or API to restart.

---

### User Story 2 - Dashboard and API survive a worker failure (Priority: P2)

As an operator, I need the API and dashboard to remain available for reviewing analytics and history even if the worker crashes or is restarted, so that I can still inspect what happened and why trading stopped.

**Why this priority**: A worker crash should not blind the operator. Keeping the read/analytics path alive during a worker outage is essential for diagnosis and confidence, but it is secondary to keeping trading itself alive (P1).

**Independent Test**: Stop or kill the worker service and confirm the API still responds to analytics requests and the dashboard still renders previously persisted data.

**Acceptance Scenarios**:

1. **Given** all three services are running, **When** the worker service crashes, **Then** the API continues responding to analytics requests and the dashboard continues rendering persisted data.
2. **Given** the worker has crashed, **When** the worker service is restarted, **Then** it resumes its trading cycle without requiring the API or dashboard to restart.

---

### User Story 3 - Independent health monitoring and isolated restarts (Priority: P2)

As an operator, I need each service to report its own health and to be restartable on its own, so that I can detect exactly which component is unhealthy and recover it without disturbing the others.

**Why this priority**: Mixed health monitoring across unrelated concerns is a named problem in the issue. Per-service health and isolated restart policies make outages observable and recoverable, which materially improves operability — but trading and analytics availability (P1/P2) come first.

**Independent Test**: Query each service's health independently and confirm each reports status for only its own concern; trigger a restart of one service and confirm the others are unaffected.

**Acceptance Scenarios**:

1. **Given** all three services are running, **When** the operator checks health, **Then** each service exposes a health status that reflects only its own responsibilities.
2. **Given** one service is unhealthy, **When** its restart policy fires, **Then** only that service restarts and the other two remain running.

---

### User Story 4 - Operator-issued commands reach the worker (Priority: P3)

As an operator, I need commands I issue through the API (for example, pausing scanning or triggering an action) to be delivered to the worker even though they no longer share a process, so that control of the trading engine is preserved after the split.

**Why this priority**: Command passing must keep working for the system to be usable, but it builds on the decoupled services being in place first, so it is sequenced last.

**Independent Test**: Issue a command through the API and confirm the worker receives and acts on it, with both services running as separate containers.

**Acceptance Scenarios**:

1. **Given** the API and worker are running as separate services, **When** the operator issues a command through the API, **Then** the worker receives the command and acts on it.
2. **Given** the worker is temporarily down, **When** a command is issued, **Then** the command is not silently lost and is either delivered when the worker returns or reported as undeliverable.

---

### Edge Cases

- What happens when the shared command channel (Redis) is unavailable — does the worker keep trading on its last known configuration, and does the API surface that commands cannot currently be delivered?
- What happens when the durable analytics store (Postgres) is unavailable — does the worker continue trading and buffer or defer metric writes rather than crashing?
- How does the dashboard behave when the API is unreachable — does it show a clear degraded state rather than a blank or broken page?
- What happens during startup ordering, e.g. the dashboard starts before the API, or the worker starts before Redis/Postgres are ready?
- How are in-flight commands handled when the worker restarts mid-command?
- How is a "split-brain" situation avoided where two worker instances run simultaneously after a restart?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST run the trading engine (market data polling, watchlist scanning, signal processing, alert dispatch, and metric writes) as an independent service with no public HTTP port.
- **FR-002**: The system MUST run the analytics HTTP service as an independent service that exposes its endpoints on the designated API port.
- **FR-003**: The system MUST run the dashboard UI as an independent service that obtains its data exclusively through the API service rather than by sharing a process with the trading engine.
- **FR-004**: The failure or restart of any one service MUST NOT cause either of the other two services to fail or restart.
- **FR-005**: The system MUST allow operator commands accepted by the API service to be delivered to the worker service through a shared command channel.
- **FR-006**: The system MUST use a durable shared store for analytics data so that the API can serve analytics that the worker produced, independent of the worker's current run state.
- **FR-007**: Each service MUST expose an independent health indicator that reflects only that service's own responsibilities.
- **FR-008**: Each service MUST have its own restart policy so that recovery of one service is isolated from the others.
- **FR-009**: The three services MUST be defined as separate deployable units within the project's container orchestration so they can be started, stopped, and scaled individually.
- **FR-010**: When the shared command channel is unavailable, the worker MUST continue trading on its current configuration and the system MUST NOT silently drop operator commands.
- **FR-011**: When the durable analytics store is unavailable, the worker MUST NOT crash the trading cycle solely because metric writes cannot be completed.
- **FR-012**: The system MUST preserve existing operator-facing capabilities (alerts, analytics views, and command controls) after the split, with no loss of currently available functionality.

### Key Entities *(include if feature involves data)*

- **Worker service (tradegumi-worker)**: The trading engine; consumes market data, produces signals/alerts and analytics metrics, and reacts to operator commands. Has no inbound public HTTP surface.
- **API service (tradegumi-api)**: The analytics and control surface; serves analytics derived from durable storage and forwards operator commands to the worker via the shared command channel.
- **Dashboard service (tradegumi-dashboard)**: The operator-facing UI; reads and writes exclusively through the API service.
- **Command message**: An operator-issued instruction created at the API and consumed by the worker; must be deliverable across separate processes and not silently lost.
- **Analytics record**: Metric/signal data produced by the worker and read by the API from durable storage; the contract that lets analytics outlive any single worker run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Killing the dashboard service during an active trading cycle results in zero interruptions to the worker's polling, signal generation, alerting, and metric writes (0 missed cycles attributable to the dashboard).
- **SC-002**: Killing the worker service leaves the API responding to analytics requests and the dashboard rendering persisted data, with the analytics path remaining available throughout.
- **SC-003**: Restarting any single service leaves the other two services running continuously, with no restarts of those two services observed.
- **SC-004**: An operator can determine which specific service is unhealthy from per-service health indicators in 100% of single-service failure scenarios.
- **SC-005**: A command issued through the API while the worker is running is acted on by the worker, and a command issued while the worker is briefly down is either delivered on the worker's return or reported as undeliverable — never silently lost.
- **SC-006**: All operator-facing capabilities available before the split (alerts, analytics views, command controls) remain available after the split, verified against the pre-split feature set.

## Assumptions

- The split is delivered using the project's existing container orchestration (docker-compose), with one service definition per component, consistent with the issue's acceptance criteria.
- Redis is the shared command channel and Postgres is the durable analytics store, per issue #112 and its dependency on issue #108; the Redis/Postgres infrastructure from #108 is already in place before this work begins.
- The API service continues to listen on its current port (8199) and the dashboard on its current port (3000); only the process/container boundaries change, not the external port contract.
- This is an architectural restructuring of an existing system; it preserves current behavior and does not introduce new operator-facing trading features beyond the decoupling itself.
- Service-to-service communication patterns (e.g., pub/sub vs. queue semantics for commands) are deferred to the planning phase and are not constrained by this specification beyond the delivery guarantees stated in FR-005 and FR-010.
- A single worker instance runs at a time; horizontal scaling of the worker is out of scope for this feature.
