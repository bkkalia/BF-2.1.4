# BlackForest v3 Migration Master Plan (Reflex + FastAPI + Skill Engine)

Status: Draft v1 (2026-04-30)
Scope: Migration plan from current BF 2.x mixed system to Reflex + FastAPI architecture with phased SQLite -> Docker -> PostgreSQL adoption.

## 1. Vision
Build a production-grade, skill-based tender scraping platform where:
- Reflex is the primary operator UI.
- FastAPI is the only backend/API surface.
- Scraper logic is skill-driven (portal capabilities are plugged in, not hardcoded in UI flows).
- PostgreSQL is the long-term source of truth.
- SQLite remains valid during transition for speed and continuity.

## 2. Current Baseline
- 42 NIC-style portals scraping successfully.
- Existing scraping engine is proven in production workloads.
- Strong operational learnings: duplicate control, checkpointing, run logs, recovery paths.
- Current pain: architecture coupling and legacy desktop-era code patterns.

## 3. Non-Goals (Explicit)
- No new Tkinter/PyQt/PySide workflows.
- No investment in desktop GUI feature parity.
- No major redesign of successful scraper logic before encapsulation.

## 4. Principles
1. Preserve what works (scraping reliability first).
2. Isolate concerns (UI, API, skills, persistence, workers).
3. Ship in vertical slices (end-to-end value each phase).
4. Keep backward-compatible data paths until PostgreSQL cutover is complete.
5. Measure everything (success rates, run duration, extraction quality, error classes).

## 5. Target Milestones

### Phase 0: Foundation Freeze (1-2 weeks)
Goals:
- Freeze stable migration baseline package.
- Define v3 repository layout.
- Document contracts (API, skill, data models).
Deliverables:
- Final migration bundle and setup docs.
- v3 architecture docs (this package).
- Technical decision record for SQLite -> PostgreSQL strategy.

### Phase 1: FastAPI Shell + Reflex Integration (2-4 weeks)
Goals:
- Introduce FastAPI backend as the runtime entry point.
- Reflex UI interacts via API endpoints/WebSocket streams.
- Keep SQLite datastore to minimize risk.
Deliverables:
- `api/` app bootstrap, health endpoints, run endpoints.
- WebSocket live event stream for run logs/progress.
- Single run orchestration path from Reflex -> FastAPI -> worker.
Exit Criteria:
- Existing 42 NIC portals can run from Reflex through FastAPI path.

### Phase 2: Skill Engine Extraction (3-6 weeks)
Goals:
- Formalize portal skill interface.
- Move portal-specific behavior behind skill contracts.
- Keep NIC default skill as primary implementation.
Deliverables:
- `skills/base.py` interface and lifecycle contract.
- `skills/nic_standard/` implementation.
- Skill registry and portal-to-skill mapping table.
Exit Criteria:
- 42 NIC portals mapped to `NIC_STANDARD` skill with same or better success rate.

### Phase 3: Worker and Scheduling Layer (2-4 weeks)
Goals:
- Decouple run execution from request-response lifecycle.
- Introduce queue-based background execution.
- Improve retry, timeout, and observability behavior.
Deliverables:
- Worker process contract and task schemas.
- Retry policy per error class.
- Scheduler for periodic scraping windows.
Exit Criteria:
- Manual + scheduled runs supported with reliable resume/retry behavior.

### Phase 4: Dockerized Local and Staging Runtime (1-3 weeks)
Goals:
- Standard local and staging environment.
- Reproducible service startup.
Deliverables:
- Docker Compose for FastAPI, Reflex, worker, optional Redis.
- Environment templates and secrets handling guidance.
Exit Criteria:
- New developer can run full stack with one command.

### Phase 5: PostgreSQL Cutover (3-6 weeks)
Goals:
- Migrate persistence from SQLite to PostgreSQL with zero functional regression.
- Keep analytics and run history intact.
Deliverables:
- SQLAlchemy/Alembic schema for v3.
- Backfill and verification scripts (SQLite -> PostgreSQL).
- Dual-write or staged cutover strategy.
Exit Criteria:
- PostgreSQL becomes primary source of truth.
- Validation report confirms parity for key entities and metrics.

## 6. Cross-Cutting Workstreams
- Observability: structured logs, run IDs, metrics, error taxonomy.
- Security: API auth, secret management, role-based controls.
- QA: smoke suite for each skill, regression for 42 NIC portals.
- Data Quality: duplicate, null, date normalization, portal-level anomaly checks.

## 7. Risk Register
1. Skill refactor changes scraper behavior.
Mitigation: contract tests + portal canary runs.

2. Data migration mismatch between SQLite and PostgreSQL.
Mitigation: staged sync + row-count and key-level verification scripts.

3. Operational complexity jump after containerization.
Mitigation: minimal service set first, documented local defaults.

4. Run orchestration regressions under queue model.
Mitigation: idempotent run commands + resume checkpoints + durable event logs.

## 8. Success Metrics
- Portal scrape success rate (target >= current baseline).
- Median run duration and p95 run duration.
- Duplicate rate and invalid record rate.
- Mean time to detect and recover from portal breakages.
- Time to onboard a new portal skill.

## 9. Recommended v3 Repository Structure
```
blackforest-v3/
  api/
    app.py
    routes/
    schemas/
    deps/
  dashboard/
    reflex_app/
  skills/
    base.py
    registry.py
    nic_standard/
  scraper_core/
    engine/
    browser/
    extractors/
    normalizers/
  workers/
    tasks/
    scheduler/
  persistence/
    sqlite/
    postgres/
    migrations/
  shared/
    config/
    logging/
    events/
    errors/
  tests/
    unit/
    integration/
    portal_smoke/
```

## 10. Immediate Next 14-Day Plan
1. Freeze interfaces: run request/response models, event schemas.
2. Build FastAPI bootstrap with health + run endpoints.
3. Wire Reflex scraping page to API/WebSocket.
4. Wrap current proven run path behind service layer without changing extraction logic.
5. Run smoke suite on a subset of NIC portals (5-8) then full 42-portal campaign.
