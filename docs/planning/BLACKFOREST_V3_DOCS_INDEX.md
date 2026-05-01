# BlackForest v3 Documentation Index

Status: Canonical v3 docs set (2026-04-30)

This index points to the new, migration-focused documentation for v3.

## Read First
1. `docs/planning/BLACKFOREST_V3_SIMPLE_PLAN.md` (start here)
2. `docs/planning/BLACKFOREST_V3_MIGRATION_MASTER_PLAN.md`
3. `docs/architecture/BLACKFOREST_V3_TARGET_ARCHITECTURE.md`
4. `docs/guides/BLACKFOREST_V3_SKILL_SYSTEM_SPEC.md`
5. `docs/guides/BLACKFOREST_V3_SETUP_AND_ROLLOUT.md`

## Purpose of Each Document
- `BLACKFOREST_V3_MIGRATION_MASTER_PLAN.md`
  - End-to-end migration strategy and phased roadmap.
  - Defines goals, risks, milestones, and success metrics.

- `BLACKFOREST_V3_TARGET_ARCHITECTURE.md`
  - Layered target architecture for Reflex + FastAPI + workers + skills.
  - Defines system boundaries and run data flow.

- `BLACKFOREST_V3_SKILL_SYSTEM_SPEC.md`
  - Skill plugin contract, registry requirements, versioning, and testing gates.
  - Designed for scaling beyond the current 42 NIC portals.

- `BLACKFOREST_V3_SETUP_AND_ROLLOUT.md`
  - Practical rollout path: SQLite first, then Docker, then PostgreSQL cutover.
  - Includes checklists and acceptance criteria.

## Scope Guardrails
- These v3 docs intentionally exclude desktop GUI planning (Tkinter/PyQt/PySide).
- Focus is on web-first operations through Reflex and API-first orchestration through FastAPI.
