# BlackForest v3 Target Architecture (Reflex + FastAPI + Skill-Based Scraping)

Status: Draft v1 (2026-04-30)

## 1. Architecture Summary
v3 separates UI, API, scraping execution, and persistence into explicit service boundaries.

- Reflex: operator dashboard and workflow control.
- FastAPI: orchestration API + run/event endpoints.
- Worker layer: executes scraping tasks asynchronously.
- Skill engine: portal-specific behavior modules behind a standard interface.
- Persistence: SQLite during transition, PostgreSQL as final primary datastore.

## 2. Logical Layers

### Presentation Layer
- Reflex dashboard pages for run control, portal management, run history, and quality views.
- No direct scraping logic embedded in UI state handlers.

### API Layer
- FastAPI routes:
  - `/health`
  - `/runs` (create/start/cancel/status)
  - `/portals` (CRUD + mapping to skills)
  - `/skills` (list/version/status)
  - `/metrics` (operational KPIs)
- WebSocket stream for live run events and logs.

### Application Service Layer
- Run service: validates requests, submits jobs, emits lifecycle events.
- Portal service: manages portal config and skill assignment.
- Skill service: registry, loading, validation.

### Worker Execution Layer
- Pulls queued run tasks.
- Resolves skill for target portal.
- Executes extraction pipeline with checkpoint and retry policy.
- Emits structured events.

### Persistence Layer
- Short term: SQLite compatibility adapter.
- Final: PostgreSQL normalized schema.
- Optional cache/queue backend for runtime scaling.

## 3. Data and Control Flow
1. User starts run in Reflex.
2. Reflex calls FastAPI `POST /runs`.
3. FastAPI validates payload and enqueues job.
4. Worker picks job and resolves portal skill.
5. Skill-driven extraction executes and writes run/tender records.
6. Worker emits progress events.
7. FastAPI forwards event stream to Reflex clients.
8. Run completes with summary and quality metrics.

## 4. Skill-Based Extension Model
All portal-specific behavior is isolated in skills.

### Base Skill Contract (high-level)
- `fetch_department_list(context)`
- `open_department(context, department)`
- `extract_tender_list(context)`
- `extract_tender_details(context, tender_ref)`
- `normalize_record(raw)`
- `health_check(context)`

### Why this matters
- New portal onboarding is additive, not invasive.
- Existing 42 NIC portals can use one stable `NIC_STANDARD` skill.
- Non-NIC portals can be onboarded as separate skill modules.

## 5. Reliability Controls
- Retry policy with classified exceptions.
- Circuit-breaker style portal cooldown on repeated failures.
- Checkpointing for long-running departments.
- Idempotent writes keyed by canonical portal+tender ID identity.
- Quality gates for null/invalid critical fields.

## 6. Observability Standards
Each run has a globally unique run ID.

Required telemetry:
- Run lifecycle events (queued, started, progress, retry, failed, completed).
- Portal and skill identifiers on each event.
- Duration and throughput metrics.
- Quality counters (new, skipped, changed-closing-date, invalid).

## 7. Security and Operations
- Token-based API auth for control endpoints.
- Role model: admin/operator/viewer.
- Secrets via env file/secret store; never hardcode.
- Audit trail for destructive operations (run cancel, portal disable).

## 8. Deployment Stages
1. Local dev: SQLite + single worker.
2. Staging: Docker Compose (API + dashboard + worker + optional queue).
3. Production: PostgreSQL + scaled worker replicas.

## 9. Migration Constraints
- Preserve successful extraction behavior for 42 NIC portals.
- Maintain compatibility with existing run-history expectations.
- Introduce schema and runtime changes in controlled phases.

## 10. Architecture Decision Guidance
- If change affects extraction correctness, gate with portal smoke tests.
- If change affects persistence, include migration and rollback scripts.
- If change affects API contracts, version schemas and clients.
