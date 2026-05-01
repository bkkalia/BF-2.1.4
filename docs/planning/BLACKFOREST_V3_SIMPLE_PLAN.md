# BlackForest v3 Simple Plan

Status: Practical baseline (2026-04-30)

## Goal
Build v3 with the fewest moving parts first:
- Reflex UI
- FastAPI backend
- Existing scraper logic (wrapped, not rewritten)
- SQLite now, PostgreSQL later

No desktop GUI scope.

## Core Rule
If a change does not improve reliability, maintainability, or speed for current scraping, do not add it now.

## 4-Step Roadmap

## Step 1: Keep Current Scraping, Add FastAPI Boundary
- Keep existing proven scraper behavior.
- Add FastAPI endpoints for:
  - start run
  - stop run
  - run status
  - run logs/events
- Reflex calls FastAPI only.

Definition of done:
- 42 NIC portals still run successfully through new API path.

## Step 2: Introduce Simple Skill Layer
- Create one skill first: `NIC_STANDARD`.
- Move current NIC logic behind this one skill wrapper.
- Do not create multiple skill families yet.

Definition of done:
- Portal config maps to `NIC_STANDARD` and run output is unchanged.

## Step 3: Containerize Only Essentials
- Docker Compose with only:
  - `api`
  - `dashboard`
  - `worker`
- Keep SQLite volume-mounted.
- Skip extra services unless required.

Definition of done:
- New machine startup works in under 15 minutes.

## Step 4: Move to PostgreSQL
- Add PostgreSQL when Step 1-3 are stable.
- Migrate data after schema and tests are ready.
- Keep rollback path to SQLite during cutover.

Definition of done:
- Data parity checks pass and portal success rate is not reduced.

## Weekly Execution Model (Simple)
- Week 1-2: API boundary + Reflex integration
- Week 3: NIC skill wrapper
- Week 4: Docker baseline
- Week 5-6: PostgreSQL schema + migration dry run

## Must-Track Metrics (Only 5)
1. Portal run success rate
2. Average run duration
3. Retry/failure count by portal
4. New vs skipped tender counts
5. Data integrity errors (duplicate/invalid IDs)

## What Not To Do Yet
- No early microservices split.
- No complex plugin marketplace mechanics.
- No advanced AI/LLM integration in migration phase.
- No major scraper rewrite before parity is proven.

## Decision Filter
Before adding any new component, ask:
1. Does it help current 42 portals run better?
2. Is it required right now for FastAPI + Reflex migration?
3. Can we defer it to post-migration hardening?

If answer to #1 and #2 is no, defer.
