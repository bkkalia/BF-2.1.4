# BlackForest v3 Skill System Specification

Status: Draft v1 (2026-04-30)
Audience: Backend engineers, scraper engineers, platform maintainers

## 1. Objective
Define a robust skill framework so portal scraping behavior is modular, testable, and easy to extend.

## 2. Core Concepts
- Skill: encapsulated scraping strategy for a family of portals.
- Skill family: e.g., `NIC_STANDARD` for NIC-based portals.
- Portal mapping: each portal references one skill + skill config.
- Skill version: immutable version label for reproducible runs.

## 3. Initial Target
- Migrate and stabilize 42 successful NIC portals under one `NIC_STANDARD` implementation.
- Add extension points for portal-specific overrides without forking the whole skill.

## 4. Skill Interface (Contract)

### Required methods
- `validate_config(config) -> ValidationResult`
- `bootstrap(context) -> None`
- `fetch_departments(context) -> list[Department]`
- `fetch_tender_refs(context, department) -> list[TenderRef]`
- `fetch_tender_detail(context, tender_ref) -> RawTender`
- `normalize(raw_tender, context) -> TenderRecord`
- `teardown(context) -> None`

### Optional hooks
- `before_department(context, department)`
- `after_department(context, department, result)`
- `handle_captcha(context, page_state)`
- `on_retry(context, error, attempt)`

## 5. Data Contracts

### Department
- `id`
- `name`
- `count_hint`
- `direct_url` (optional)

### TenderRef
- `tender_id_raw`
- `title_ref_raw`
- `detail_url` (optional)

### TenderRecord (normalized)
- `portal_name`
- `tender_id_extracted`
- `department_name`
- `published_date`
- `closing_date`
- `title_ref`
- `status_url`
- `direct_url`
- `source_skill`
- `source_skill_version`

## 6. Skill Registry Requirements
- Register skills by unique `skill_key` and `version`.
- Validate skill compatibility at startup.
- Refuse duplicate key/version pairs.
- Provide list endpoint for operations UI.

## 7. Portal Configuration Model
Each portal record should include:
- `portal_slug`
- `portal_name`
- `base_url`
- `org_list_url`
- `skill_key` (default `NIC_STANDARD` for current 42)
- `skill_version`
- `skill_config` JSON
- `enabled`

## 8. Error Taxonomy
All skills should classify errors into:
- `TRANSIENT` (retryable: timeout, stale session, connection reset)
- `RATE_LIMIT` (backoff and schedule shift)
- `PORTAL_CHANGE` (needs skill update)
- `DATA_QUALITY` (extract/normalize failures)
- `FATAL` (stop run)

## 9. Testing Requirements

### Unit tests
- Config validation
- Normalization rules
- Error classification

### Integration tests
- Department list extraction for sample portal snapshots
- Tender detail extraction for known pages

### Smoke tests
- Daily/weekly run against live canary portals (subset of 42)

### Acceptance for new skill
- >= 90% extraction completeness on test portal set
- Deterministic normalization for tender identity
- No regression on existing skill families

## 10. Onboarding a New Portal Skill
1. Create new skill package under `skills/`.
2. Implement base interface + tests.
3. Add sample fixtures.
4. Register skill in registry.
5. Map one staging portal.
6. Run smoke and quality checks.
7. Promote to production mapping.

## 11. Versioning and Rollback
- Version format: `MAJOR.MINOR.PATCH`.
- Breaking extraction changes increment MAJOR.
- Keep previous stable version deployable for immediate rollback.

## 12. Operational KPIs per Skill
- Success rate by portal and skill version.
- Average tenders per run vs historical baseline.
- Retry rate and error class distribution.
- Mean extraction latency per department.
