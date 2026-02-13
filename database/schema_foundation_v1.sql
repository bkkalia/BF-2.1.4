PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

BEGIN;

CREATE TABLE IF NOT EXISTS portals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portal_slug TEXT NOT NULL UNIQUE,
    portal_code TEXT NOT NULL,
    portal_name TEXT NOT NULL,
    base_url TEXT,
    source_data_file TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    health_status TEXT NOT NULL DEFAULT 'unknown',
    last_health_check_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portal_id INTEGER NOT NULL,
    run_scope TEXT NOT NULL DEFAULT 'all',
    status TEXT NOT NULL DEFAULT 'running',
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT,
    expected_total_tenders INTEGER NOT NULL DEFAULT 0,
    extracted_total_tenders INTEGER NOT NULL DEFAULT 0,
    skipped_existing_total INTEGER NOT NULL DEFAULT 0,
    output_file_type TEXT,
    output_file_path TEXT,
    notes TEXT,
    FOREIGN KEY (portal_id) REFERENCES portals(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS tender_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portal_id INTEGER NOT NULL,
    portal_tender_uid TEXT NOT NULL,

    title_ref TEXT,
    tender_id_extracted TEXT,
    department_name TEXT,
    organization_chain TEXT,

    published_at TEXT,
    opening_at TEXT,
    closing_at TEXT,

    direct_url TEXT,
    status_url TEXT,

    emd_amount_raw TEXT,
    emd_amount_value REAL,
    estimated_cost_raw TEXT,
    estimated_cost_value REAL,

    tender_type TEXT,
    payment_type TEXT,
    work_type TEXT,

    location_text TEXT,
    city TEXT,
    district TEXT,
    state_name TEXT,
    state_code TEXT,
    pincode TEXT,

    is_live INTEGER NOT NULL DEFAULT 1 CHECK (is_live IN (0, 1)),
    tender_status TEXT NOT NULL DEFAULT 'open',
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    closed_at TEXT,
    archived_at TEXT,

    source_run_id INTEGER,
    extra_json TEXT,

    FOREIGN KEY (portal_id) REFERENCES portals(id) ON DELETE RESTRICT,
    FOREIGN KEY (source_run_id) REFERENCES scrape_runs(id) ON DELETE SET NULL,
    UNIQUE (portal_id, portal_tender_uid)
);

CREATE TABLE IF NOT EXISTS tender_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_item_id INTEGER NOT NULL,
    run_id INTEGER NOT NULL,

    title_ref TEXT,
    department_name TEXT,
    organization_chain TEXT,
    published_at TEXT,
    opening_at TEXT,
    closing_at TEXT,
    direct_url TEXT,
    status_url TEXT,

    emd_amount_raw TEXT,
    emd_amount_value REAL,
    estimated_cost_raw TEXT,
    estimated_cost_value REAL,

    tender_type TEXT,
    payment_type TEXT,
    work_type TEXT,

    location_text TEXT,
    city TEXT,
    district TEXT,
    state_name TEXT,
    state_code TEXT,
    pincode TEXT,

    is_live INTEGER NOT NULL DEFAULT 1 CHECK (is_live IN (0, 1)),
    tender_status TEXT NOT NULL DEFAULT 'open',
    captured_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (tender_item_id) REFERENCES tender_items(id) ON DELETE CASCADE,
    FOREIGN KEY (run_id) REFERENCES scrape_runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tender_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_item_id INTEGER NOT NULL,
    old_status TEXT,
    new_status TEXT NOT NULL,
    changed_at TEXT NOT NULL DEFAULT (datetime('now')),
    reason TEXT,
    run_id INTEGER,
    FOREIGN KEY (tender_item_id) REFERENCES tender_items(id) ON DELETE CASCADE,
    FOREIGN KEY (run_id) REFERENCES scrape_runs(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS tender_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_item_id INTEGER NOT NULL,
    file_type TEXT,
    file_name TEXT,
    file_url TEXT,
    local_path TEXT,
    file_hash TEXT,
    file_size_bytes INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (tender_item_id) REFERENCES tender_items(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_alert_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    portal_id INTEGER,
    query_text TEXT,
    min_amount REAL,
    max_amount REAL,
    state_code TEXT,
    city TEXT,
    district TEXT,
    work_type TEXT,
    is_live_only INTEGER NOT NULL DEFAULT 1 CHECK (is_live_only IN (0, 1)),
    is_enabled INTEGER NOT NULL DEFAULT 1 CHECK (is_enabled IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (portal_id) REFERENCES portals(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS backup_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backup_date TEXT NOT NULL,
    source_db_path TEXT NOT NULL,
    backup_db_path TEXT NOT NULL,
    backup_status TEXT NOT NULL,
    details TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_runs_portal_started ON scrape_runs(portal_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_tender_items_portal_live_close ON tender_items(portal_id, is_live, closing_at);
CREATE INDEX IF NOT EXISTS idx_tender_items_portal_status ON tender_items(portal_id, tender_status, closing_at);
CREATE INDEX IF NOT EXISTS idx_tender_items_amount_live ON tender_items(is_live, estimated_cost_value, emd_amount_value);
CREATE INDEX IF NOT EXISTS idx_tender_items_geo ON tender_items(state_code, district, city, pincode);
CREATE INDEX IF NOT EXISTS idx_tender_items_work_live ON tender_items(is_live, work_type, tender_type, payment_type);
CREATE INDEX IF NOT EXISTS idx_tender_items_seen ON tender_items(last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_tender_items_extracted_id ON tender_items(portal_id, tender_id_extracted);

CREATE INDEX IF NOT EXISTS idx_snapshots_tender_captured ON tender_snapshots(tender_item_id, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_run ON tender_snapshots(run_id);

CREATE INDEX IF NOT EXISTS idx_status_history_tender_changed ON tender_status_history(tender_item_id, changed_at DESC);

CREATE INDEX IF NOT EXISTS idx_alert_rules_user_enabled ON user_alert_rules(user_id, is_enabled);

CREATE VIEW IF NOT EXISTS v_live_tenders AS
SELECT
    ti.id,
    p.portal_slug,
    p.portal_code,
    p.portal_name,
    ti.portal_tender_uid,
    ti.tender_id_extracted,
    ti.title_ref,
    ti.department_name,
    ti.organization_chain,
    ti.published_at,
    ti.opening_at,
    ti.closing_at,
    ti.direct_url,
    ti.status_url,
    ti.estimated_cost_value,
    ti.emd_amount_value,
    ti.tender_type,
    ti.payment_type,
    ti.work_type,
    ti.city,
    ti.district,
    ti.state_name,
    ti.state_code,
    ti.pincode,
    ti.last_seen_at
FROM tender_items ti
JOIN portals p ON p.id = ti.portal_id
WHERE ti.is_live = 1;

CREATE VIEW IF NOT EXISTS v_archive_tenders AS
SELECT
    ti.id,
    p.portal_slug,
    p.portal_code,
    p.portal_name,
    ti.portal_tender_uid,
    ti.tender_id_extracted,
    ti.title_ref,
    ti.department_name,
    ti.organization_chain,
    ti.published_at,
    ti.opening_at,
    ti.closing_at,
    ti.direct_url,
    ti.status_url,
    ti.estimated_cost_value,
    ti.emd_amount_value,
    ti.tender_type,
    ti.payment_type,
    ti.work_type,
    ti.city,
    ti.district,
    ti.state_name,
    ti.state_code,
    ti.pincode,
    ti.closed_at,
    ti.archived_at,
    ti.last_seen_at
FROM tender_items ti
JOIN portals p ON p.id = ti.portal_id
WHERE ti.is_live = 0;

CREATE VIRTUAL TABLE IF NOT EXISTS tender_search_fts USING fts5(
    title_ref,
    department_name,
    organization_chain,
    location_text,
    work_type,
    content='tender_items',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS trg_tender_items_ai_fts
AFTER INSERT ON tender_items
BEGIN
    INSERT INTO tender_search_fts(rowid, title_ref, department_name, organization_chain, location_text, work_type)
    VALUES (new.id, new.title_ref, new.department_name, new.organization_chain, new.location_text, new.work_type);
END;

CREATE TRIGGER IF NOT EXISTS trg_tender_items_au_fts
AFTER UPDATE ON tender_items
BEGIN
    INSERT INTO tender_search_fts(tender_search_fts, rowid, title_ref, department_name, organization_chain, location_text, work_type)
    VALUES ('delete', old.id, old.title_ref, old.department_name, old.organization_chain, old.location_text, old.work_type);
    INSERT INTO tender_search_fts(rowid, title_ref, department_name, organization_chain, location_text, work_type)
    VALUES (new.id, new.title_ref, new.department_name, new.organization_chain, new.location_text, new.work_type);
END;

CREATE TRIGGER IF NOT EXISTS trg_tender_items_ad_fts
AFTER DELETE ON tender_items
BEGIN
    INSERT INTO tender_search_fts(tender_search_fts, rowid, title_ref, department_name, organization_chain, location_text, work_type)
    VALUES ('delete', old.id, old.title_ref, old.department_name, old.organization_chain, old.location_text, old.work_type);
END;

COMMIT;
