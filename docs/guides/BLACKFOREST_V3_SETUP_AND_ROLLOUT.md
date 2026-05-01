# BlackForest v3 Setup and Rollout Guide

Status: Draft v1 (2026-04-30)
Focus: SQLite first, then Docker, then PostgreSQL

## 1. Rollout Strategy

### Step A: SQLite-first runtime (starting point)
Use SQLite to keep migration risk low while architecture is being restructured.

### Step B: Dockerized local/staging
Introduce containerized runtime for reproducibility and easier team onboarding.

### Step C: PostgreSQL cutover
Migrate to PostgreSQL once API/worker/skill boundaries are stable and tested.

## 2. Phase A - SQLite First (Weeks 1-4)

### Goals
- FastAPI + Reflex integrated end-to-end.
- Skill engine wrappers active.
- Current 42 NIC portals remain stable.

### Setup Checklist
1. Create Python environment.
2. Install dependencies.
3. Configure env file (`APP_ENV`, DB path, ports, log level).
4. Start FastAPI service.
5. Start Reflex dashboard.
6. Verify health endpoint and first portal run.

### Must-pass checks
- Dashboard can trigger runs through API.
- WebSocket events visible in UI.
- SQLite writes include run + tender records.
- Duplicate and closing-date logic still correct.

## 3. Phase B - Docker Introduction (Weeks 4-6)

### Goals
- One-command startup for API, dashboard, worker.
- Environment parity across developers.

### Compose services
- `api`
- `dashboard`
- `worker`
- `optional: redis`

### Deliverables
- `docker-compose.yml`
- `.env.example`
- startup scripts
- troubleshooting doc for ports/volumes

### Must-pass checks
- Fresh clone -> stack up in < 15 minutes.
- Run events flow correctly between services.
- Logs and artifacts mounted to host paths.

## 4. Phase C - PostgreSQL Migration (Weeks 6-12)

### Goals
- PostgreSQL becomes primary datastore.
- Historical continuity preserved.

### Migration plan
1. Define v3 DB schema in migrations (Alembic).
2. Implement persistence adapters (SQLite and PostgreSQL).
3. Build data migration scripts (extract, transform, load).
4. Run dry-run migration on staging snapshot.
5. Validate row counts, keys, and run summaries.
6. Cut over write path to PostgreSQL.
7. Keep SQLite read-only fallback during stabilization window.

### Validation checklist
- Portal counts and run counts match expected tolerances.
- Canonical `(portal, tender_id)` identity preserved.
- Date fields and status fields correctly normalized.
- No major performance regression on common queries.

## 5. Environment Variables (Recommended)
- `BF_APP_ENV`
- `BF_API_HOST`
- `BF_API_PORT`
- `BF_REFLEX_PORT`
- `BF_SQLITE_PATH`
- `BF_DATABASE_URL` (PostgreSQL)
- `BF_LOG_LEVEL`
- `BF_SECRET_KEY`

## 6. Definition of Done for v3 Migration Start
- FastAPI is the primary control plane.
- Reflex is the only operator UI.
- Skill registry is active and all 42 NIC portals mapped.
- CI smoke test suite exists for canary portals.
- PostgreSQL migration scripts tested in staging.

## 7. Recommended Team Track Split
- Track 1: API + worker orchestration
- Track 2: Skill extraction + NIC baseline hardening
- Track 3: Persistence and migration (SQLite/PostgreSQL)
- Track 4: QA/observability and documentation

## 8. Immediate 30-Day Execution Plan
1. Week 1: finalize contracts and bootstrap FastAPI routes.
2. Week 2: wire Reflex run flows and event streaming.
3. Week 3: formalize skill base interface and NIC standard skill package.
4. Week 4: run full 42-portal campaign, baseline metrics and issues.

## 9. Notes on Legacy Removal
- Do not add any new desktop GUI paths.
- Keep only shared logic that is consumed by v3 API/worker/skills.
- Archive old desktop-specific docs and keep v3 docs as primary reference set.
