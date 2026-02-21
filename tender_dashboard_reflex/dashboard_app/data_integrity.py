# pyright: reportArgumentType=false, reportCallIssue=false, reportAttributeAccessIssue=false
"""Data Integrity Verification page - Monitor and validate data quality."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict

import reflex as rx


class IntegrityMetric(rx.Base):
    """Data class for integrity metrics."""
    title: str
    value: str | int
    status: str  # "good", "warning", "error"
    description: str = ""
    icon: str = "info"


class DuplicateRecord(rx.Base):
    """Data class for duplicate tender records."""
    portal_name: str
    tender_id: str
    count: int


class MissingFieldRecord(rx.Base):
    """Data class for missing field records."""
    portal_name: str
    department_name: str
    missing_count: int
    field_name: str


class PortalIntegrity(rx.Base):
    """Data class for per-portal integrity metrics."""
    portal_name: str
    total_tenders: int
    duplicate_groups: int
    duplicate_rows: int
    missing_tender_ids: int
    missing_closing_dates: int
    integrity_score: int
    status: str  # "excellent", "good", "fair", "poor"


class DataIntegrityState(rx.State):
    """State for data integrity verification."""
    
    # Overall metrics
    total_tenders: int = 0
    duplicate_groups: int = 0
    duplicate_extra_rows: int = 0
    missing_tender_ids: int = 0
    missing_closing_dates: int = 0
    invalid_tender_ids: int = 0
    distinct_portals: int = 0
    
    # Per-portal metrics
    portal_metrics: List[PortalIntegrity] = []
    selected_portal: str = "All Portals"
    
    # Detailed records
    duplicate_records: List[DuplicateRecord] = []
    missing_field_records: List[MissingFieldRecord] = []
    
    # Status
    last_check_time: str = "Never"
    checking: bool = False
    cleanup_running: bool = False
    check_log: List[str] = []
    
    # Action modals and dialogs
    show_detail_modal: bool = False
    selected_portal_detail: str = ""
    show_cleanup_dialog: bool = False
    cleanup_action: str = ""  # "duplicates", "invalid", "all"
    cleanup_portal: str = ""
    cleanup_preview_count: int = 0
    cleanup_preview_details: str = ""
    
    # Portal detail data
    portal_detail_duplicates: List[Dict] = []
    portal_detail_invalid_ids: List[Dict] = []
    portal_detail_missing_dates: List[Dict] = []
    
    def on_load(self):
        """Run integrity check on page load."""
        self.run_integrity_check()
    
    def run_integrity_check(self):
        """Run comprehensive data integrity check."""
        self.checking = True
        self.check_log = []
        yield
        
        try:
            db_path = Path(__file__).parent.parent.parent / "database" / "blackforest_tenders.sqlite3"
            
            if not db_path.exists():
                self.check_log.append("❌ Database not found")
                self.checking = False
                yield
                return
            
            self.check_log.append(f"📂 Checking database: {db_path.name}")
            yield
            
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 1. Total tenders
            cursor.execute("SELECT COUNT(*) as count FROM tenders")
            self.total_tenders = cursor.fetchone()["count"]
            self.check_log.append(f"✅ Total tenders: {self.total_tenders:,}")
            yield
            
            # 2. Distinct portals
            cursor.execute("SELECT COUNT(DISTINCT LOWER(TRIM(COALESCE(portal_name, '')))) as count FROM tenders WHERE portal_name IS NOT NULL")
            self.distinct_portals = cursor.fetchone()["count"]
            self.check_log.append(f"✅ Active portals: {self.distinct_portals}")
            yield
            
            # 3. Check duplicates
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM (
                    SELECT
                        LOWER(TRIM(COALESCE(portal_name, ''))) as portal_key,
                        TRIM(COALESCE(tender_id_extracted, '')) as tender_key,
                        COUNT(*) as c
                    FROM tenders
                    WHERE TRIM(COALESCE(tender_id_extracted, '')) <> ''
                    GROUP BY portal_key, tender_key
                    HAVING c > 1
                )
            """)
            self.duplicate_groups = cursor.fetchone()["count"]
            
            cursor.execute("""
                SELECT SUM(c - 1) as count
                FROM (
                    SELECT
                        LOWER(TRIM(COALESCE(portal_name, ''))) as portal_key,
                        TRIM(COALESCE(tender_id_extracted, '')) as tender_key,
                        COUNT(*) as c
                    FROM tenders
                    WHERE TRIM(COALESCE(tender_id_extracted, '')) <> ''
                    GROUP BY portal_key, tender_key
                    HAVING c > 1
                )
            """)
            result = cursor.fetchone()
            self.duplicate_extra_rows = result["count"] if result["count"] else 0
            
            if self.duplicate_groups > 0:
                self.check_log.append(f"⚠️ Found {self.duplicate_groups} duplicate groups ({self.duplicate_extra_rows} extra rows)")
            else:
                self.check_log.append("✅ No duplicate tender IDs found")
            yield
            
            # Get duplicate details (top 20)
            cursor.execute("""
                SELECT 
                    portal_name,
                    tender_id_extracted as tender_id,
                    COUNT(*) as count
                FROM tenders
                WHERE TRIM(COALESCE(tender_id_extracted, '')) <> ''
                GROUP BY LOWER(TRIM(COALESCE(portal_name, ''))), TRIM(COALESCE(tender_id_extracted, ''))
                HAVING COUNT(*) > 1
                ORDER BY count DESC, portal_name ASC
                LIMIT 20
            """)
            self.duplicate_records = [
                DuplicateRecord(
                    portal_name=row["portal_name"],
                    tender_id=row["tender_id"],
                    count=row["count"]
                )
                for row in cursor.fetchall()
            ]
            
            # 4. Missing tender IDs
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM tenders
                WHERE tender_id_extracted IS NULL
                   OR TRIM(tender_id_extracted) = ''
                   OR LOWER(TRIM(tender_id_extracted)) IN ('nan', 'none', 'null', 'na', 'n/a', '-')
            """)
            self.missing_tender_ids = cursor.fetchone()["count"]
            
            if self.missing_tender_ids > 0:
                self.check_log.append(f"⚠️ Found {self.missing_tender_ids} records with missing/invalid tender IDs")
            else:
                self.check_log.append("✅ All records have valid tender IDs")
            yield
            
            # 5. Invalid tender IDs (placeholder values)
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM tenders
                WHERE LOWER(TRIM(COALESCE(tender_id_extracted, ''))) IN ('nan', 'none', 'null', 'na', 'n/a', '-')
            """)
            self.invalid_tender_ids = cursor.fetchone()["count"]
            
            if self.invalid_tender_ids > 0:
                self.check_log.append(f"⚠️ Found {self.invalid_tender_ids} records with placeholder tender IDs")
            yield
            
            # 6. Missing closing dates
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM tenders
                WHERE closing_date IS NULL
                   OR TRIM(closing_date) = ''
            """)
            self.missing_closing_dates = cursor.fetchone()["count"]
            
            if self.missing_closing_dates > 0:
                self.check_log.append(f"⚠️ Found {self.missing_closing_dates} records with missing closing dates")
            else:
                self.check_log.append("✅ All records have closing dates")
            yield
            
            # Get missing field details (top 20 departments)
            cursor.execute("""
                SELECT 
                    portal_name,
                    department_name,
                    COUNT(*) as missing_count
                FROM tenders
                WHERE closing_date IS NULL OR TRIM(closing_date) = ''
                GROUP BY portal_name, department_name
                ORDER BY missing_count DESC
                LIMIT 20
            """)
            self.missing_field_records = [
                MissingFieldRecord(
                    portal_name=row["portal_name"] or "Unknown",
                    department_name=row["department_name"] or "Unknown",
                    missing_count=row["missing_count"],
                    field_name="closing_date"
                )
                for row in cursor.fetchall()
            ]
            
            # 7. Per-portal integrity metrics
            self.check_log.append("📊 Calculating per-portal metrics...")
            yield
            
            cursor.execute("""
                SELECT 
                    COALESCE(portal_name, 'Unknown') as portal_name,
                    COUNT(*) as total_tenders,
                    -- Duplicates for this portal
                    (SELECT COUNT(*) FROM (
                        SELECT COUNT(*) as c
                        FROM tenders t2
                        WHERE LOWER(TRIM(COALESCE(t2.portal_name, ''))) = LOWER(TRIM(COALESCE(t1.portal_name, '')))
                          AND TRIM(COALESCE(t2.tender_id_extracted, '')) <> ''
                        GROUP BY TRIM(COALESCE(t2.tender_id_extracted, ''))
                        HAVING c > 1
                    )) as duplicate_groups,
                    -- Extra duplicate rows
                    (SELECT COALESCE(SUM(c - 1), 0) FROM (
                        SELECT COUNT(*) as c
                        FROM tenders t2
                        WHERE LOWER(TRIM(COALESCE(t2.portal_name, ''))) = LOWER(TRIM(COALESCE(t1.portal_name, '')))
                          AND TRIM(COALESCE(t2.tender_id_extracted, '')) <> ''
                        GROUP BY TRIM(COALESCE(t2.tender_id_extracted, ''))
                        HAVING c > 1
                    )) as duplicate_rows,
                    -- Missing tender IDs
                    (SELECT COUNT(*) FROM tenders t2
                     WHERE LOWER(TRIM(COALESCE(t2.portal_name, ''))) = LOWER(TRIM(COALESCE(t1.portal_name, '')))
                       AND (t2.tender_id_extracted IS NULL 
                            OR TRIM(t2.tender_id_extracted) = ''
                            OR LOWER(TRIM(t2.tender_id_extracted)) IN ('nan', 'none', 'null', 'na', 'n/a', '-'))
                    ) as missing_tender_ids,
                    -- Missing closing dates
                    (SELECT COUNT(*) FROM tenders t2
                     WHERE LOWER(TRIM(COALESCE(t2.portal_name, ''))) = LOWER(TRIM(COALESCE(t1.portal_name, '')))
                       AND (t2.closing_date IS NULL OR TRIM(t2.closing_date) = '')
                    ) as missing_closing_dates
                FROM tenders t1
                WHERE portal_name IS NOT NULL
                GROUP BY LOWER(TRIM(COALESCE(portal_name, '')))
                ORDER BY total_tenders DESC
            """)
            
            portal_rows = cursor.fetchall()
            self.portal_metrics = []
            
            for row in portal_rows:
                total = row["total_tenders"]
                dup_groups = row["duplicate_groups"]
                dup_rows = row["duplicate_rows"]
                missing_ids = row["missing_tender_ids"]
                missing_dates = row["missing_closing_dates"]
                
                # Calculate portal-specific integrity score
                score = 100
                if total > 0:
                    if dup_rows > 0:
                        score -= min(30, (dup_rows / total) * 100)
                    if missing_ids > 0:
                        score -= min(40, (missing_ids / total) * 100)
                    if missing_dates > 0:
                        score -= min(20, (missing_dates / total) * 100)
                score = max(0, int(score))
                
                # Determine status
                if score >= 95:
                    status = "excellent"
                elif score >= 85:
                    status = "good"
                elif score >= 70:
                    status = "fair"
                else:
                    status = "poor"
                
                self.portal_metrics.append(PortalIntegrity(
                    portal_name=row["portal_name"],
                    total_tenders=total,
                    duplicate_groups=dup_groups,
                    duplicate_rows=dup_rows,
                    missing_tender_ids=missing_ids,
                    missing_closing_dates=missing_dates,
                    integrity_score=score,
                    status=status
                ))
            
            self.check_log.append(f"✅ Analyzed {len(self.portal_metrics)} portal(s)")
            yield
            
            conn.close()
            
            self.last_check_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.check_log.append(f"✅ Integrity check complete at {self.last_check_time}")
            
        except Exception as e:
            self.check_log.append(f"❌ Error during integrity check: {str(e)}")
        
        self.checking = False
        yield
    
    def run_cleanup(self):
        """Run cleanup script to remove duplicates and invalid records."""
        self.cleanup_running = True
        self.check_log.append("🧹 Starting cleanup process...")
        yield
        
        try:
            import subprocess
            import sys
            
            db_path = Path(__file__).parent.parent.parent / "database" / "blackforest_tenders.sqlite3"
            backup_dir = Path(__file__).parent.parent.parent / "db_backups"
            backup_dir.mkdir(exist_ok=True)
            
            cleanup_script = Path(__file__).parent.parent.parent / "tools" / "cleanup_tender_records.py"
            
            if not cleanup_script.exists():
                self.check_log.append("❌ Cleanup script not found")
                self.cleanup_running = False
                yield
                return
            
            # Run cleanup script
            result = subprocess.run(
                [sys.executable, str(cleanup_script), "--db", str(db_path), "--backup-dir", str(backup_dir)],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                self.check_log.append("✅ Cleanup completed successfully")
                self.check_log.append(result.stdout)
                # Re-run integrity check
                yield from self.run_integrity_check()
            else:
                self.check_log.append(f"❌ Cleanup failed: {result.stderr}")
        
        except Exception as e:
            self.check_log.append(f"❌ Error during cleanup: {str(e)}")
        
        self.cleanup_running = False
        yield
    
    @rx.var
    def integrity_score(self) -> int:
        """Calculate overall integrity score (0-100)."""
        if self.total_tenders == 0:
            return 100
        
        score = 100
        
        # Deduct for duplicates
        if self.duplicate_extra_rows > 0:
            duplicate_penalty = min(30, (self.duplicate_extra_rows / self.total_tenders) * 100)
            score -= duplicate_penalty
        
        # Deduct for missing IDs
        if self.missing_tender_ids > 0:
            missing_id_penalty = min(40, (self.missing_tender_ids / self.total_tenders) * 100)
            score -= missing_id_penalty
        
        # Deduct for missing dates
        if self.missing_closing_dates > 0:
            missing_date_penalty = min(20, (self.missing_closing_dates / self.total_tenders) * 100)
            score -= missing_date_penalty
        
        return max(0, int(score))
    
    @rx.var
    def score_color(self) -> str:
        """Get color based on integrity score."""
        score = self.integrity_score
        if score >= 90:
            return "green"
        elif score >= 70:
            return "yellow"
        else:
            return "red"
    
    @rx.var
    def portal_options(self) -> List[str]:
        """Get list of portals for dropdown."""
        return ["All Portals"] + [p.portal_name for p in self.portal_metrics]
    
    @rx.var
    def filtered_portal_metrics(self) -> List[PortalIntegrity]:
        """Get portal metrics filtered by selected portal."""
        if self.selected_portal == "All Portals":
            return self.portal_metrics
        return [p for p in self.portal_metrics if p.portal_name == self.selected_portal]
    
    def set_selected_portal(self, value: str):
        """Set selected portal for filtering."""
        self.selected_portal = value
    
    # ==================== Action Methods ====================
    
    def show_portal_details(self, portal_name: str):
        """Load and show detailed records for a specific portal."""
        self.selected_portal_detail = portal_name
        self.show_detail_modal = True
        
        try:
            db_path = Path(__file__).parent.parent.parent / "database" / "blackforest_tenders.sqlite3"
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Load duplicate records
            cursor.execute("""
                SELECT portal_name, tender_id_extracted as tender_id, COUNT(*) as count
                FROM tenders
                WHERE LOWER(TRIM(portal_name)) = LOWER(TRIM(?))
                    AND tender_id_extracted IS NOT NULL
                    AND TRIM(tender_id_extracted) != ''
                GROUP BY LOWER(TRIM(portal_name)), LOWER(TRIM(tender_id_extracted))
                HAVING COUNT(*) > 1
                ORDER BY count DESC
                LIMIT 100
            """, (portal_name,))
            self.portal_detail_duplicates = [dict(row) for row in cursor.fetchall()]
            
            # Load records with invalid/missing tender IDs
            cursor.execute("""
                SELECT id, department_name, tender_id_extracted as tender_id, closing_date
                FROM tenders
                WHERE LOWER(TRIM(portal_name)) = LOWER(TRIM(?))
                    AND (
                        tender_id_extracted IS NULL
                        OR TRIM(tender_id_extracted) = ''
                        OR LOWER(TRIM(tender_id_extracted)) IN ('nan', 'none', 'null', 'n/a', 'na', '-', '--')
                    )
                ORDER BY department_name
                LIMIT 100
            """, (portal_name,))
            self.portal_detail_invalid_ids = [dict(row) for row in cursor.fetchall()]
            
            # Load records with missing closing dates
            cursor.execute("""
                SELECT id, department_name, tender_id_extracted as tender_id, closing_date
                FROM tenders
                WHERE LOWER(TRIM(portal_name)) = LOWER(TRIM(?))
                    AND (
                        closing_date IS NULL
                        OR TRIM(closing_date) = ''
                        OR LOWER(TRIM(closing_date)) IN ('nan', 'none', 'null', 'n/a', 'na', '-', '--')
                    )
                ORDER BY department_name
                LIMIT 100
            """, (portal_name,))
            self.portal_detail_missing_dates = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            
        except Exception as e:
            self.check_log.append(f"❌ Error loading portal details: {str(e)}")
    
    def close_detail_modal(self):
        """Close the detail modal."""
        self.show_detail_modal = False
        self.selected_portal_detail = ""
        self.portal_detail_duplicates = []
        self.portal_detail_invalid_ids = []
        self.portal_detail_missing_dates = []
    
    def preview_cleanup_action(self, action: str, portal: str):
        """Preview what will be affected by a cleanup action."""
        self.cleanup_action = action
        self.cleanup_portal = portal
        
        try:
            db_path = Path(__file__).parent.parent.parent / "database" / "blackforest_tenders.sqlite3"
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            portal_filter = ""
            params = []
            if portal != "All Portals":
                portal_filter = "AND LOWER(TRIM(portal_name)) = LOWER(TRIM(?))"
                params.append(portal)
            
            if action == "duplicates":
                # Count duplicate rows that will be deleted (keeping newest)
                query = f"""
                    SELECT COUNT(*) as count
                    FROM tenders t1
                    WHERE tender_id_extracted IS NOT NULL 
                        AND TRIM(tender_id_extracted) != ''
                        {portal_filter}
                        AND id NOT IN (
                            SELECT MAX(id)
                            FROM tenders t2
                            WHERE LOWER(TRIM(t2.tender_id_extracted)) = LOWER(TRIM(t1.tender_id_extracted))
                                AND LOWER(TRIM(t2.portal_name)) = LOWER(TRIM(t1.portal_name))
                                {portal_filter.replace('?', '?' if not params else '?')}
                            GROUP BY LOWER(TRIM(t2.tender_id_extracted)), LOWER(TRIM(t2.portal_name))
                        )
                """
                cursor.execute(query, params * 2 if params else [])
                count = cursor.fetchone()[0]
                self.cleanup_preview_count = count
                self.cleanup_preview_details = f"Will delete {count} duplicate tender(s), keeping the newest record for each tender ID."
                
            elif action == "invalid":
                # Count records with invalid/missing IDs or dates
                query = f"""
                    SELECT COUNT(*) as count
                    FROM tenders
                    WHERE (
                        tender_id_extracted IS NULL
                        OR TRIM(tender_id_extracted) = ''
                        OR LOWER(TRIM(tender_id_extracted)) IN ('nan', 'none', 'null', 'n/a', 'na', '-', '--')
                        OR closing_date IS NULL
                        OR TRIM(closing_date) = ''
                        OR LOWER(TRIM(closing_date)) IN ('nan', 'none', 'null', 'n/a', 'na', '-', '--')
                    )
                    {portal_filter}
                """
                cursor.execute(query, params)
                count = cursor.fetchone()[0]
                self.cleanup_preview_count = count
                self.cleanup_preview_details = f"Will delete {count} record(s) with missing or invalid tender IDs or closing dates."
                
            elif action == "all":
                # Count all problematic records
                query_dup = f"""
                    SELECT COUNT(*) as count
                    FROM tenders t1
                    WHERE tender_id_extracted IS NOT NULL 
                        AND TRIM(tender_id_extracted) != ''
                        {portal_filter}
                        AND id NOT IN (
                            SELECT MAX(id)
                            FROM tenders t2
                            WHERE LOWER(TRIM(t2.tender_id_extracted)) = LOWER(TRIM(t1.tender_id_extracted))
                                AND LOWER(TRIM(t2.portal_name)) = LOWER(TRIM(t1.portal_name))
                                {portal_filter.replace('?', '?' if not params else '?')}
                            GROUP BY LOWER(TRIM(t2.tender_id_extracted)), LOWER(TRIM(t2.portal_name))
                        )
                """
                cursor.execute(query_dup, params * 2 if params else [])
                dup_count = cursor.fetchone()[0]
                
                query_inv = f"""
                    SELECT COUNT(*) as count
                    FROM tenders
                    WHERE (
                        tender_id_extracted IS NULL
                        OR TRIM(tender_id_extracted) = ''
                        OR LOWER(TRIM(tender_id_extracted)) IN ('nan', 'none', 'null', 'n/a', 'na', '-', '--')
                        OR closing_date IS NULL
                        OR TRIM(closing_date) = ''
                        OR LOWER(TRIM(closing_date)) IN ('nan', 'none', 'null', 'n/a', 'na', '-', '--')
                    )
                    {portal_filter}
                """
                cursor.execute(query_inv, params)
                inv_count = cursor.fetchone()[0]
                
                total_count = dup_count + inv_count
                self.cleanup_preview_count = total_count
                self.cleanup_preview_details = f"Will delete {dup_count} duplicate(s) and {inv_count} invalid record(s). Total: {total_count} records."
            
            conn.close()
            self.show_cleanup_dialog = True
            
        except Exception as e:
            self.check_log.append(f"❌ Error previewing cleanup: {str(e)}")
    
    def cancel_cleanup(self):
        """Cancel cleanup operation."""
        self.show_cleanup_dialog = False
        self.cleanup_action = ""
        self.cleanup_portal = ""
        self.cleanup_preview_count = 0
        self.cleanup_preview_details = ""
    
    def confirm_cleanup(self):
        """Execute the confirmed cleanup action."""
        self.show_cleanup_dialog = False
        self.cleanup_running = True
        yield
        
        try:
            db_path = Path(__file__).parent.parent.parent / "database" / "blackforest_tenders.sqlite3"
            
            # Create backup
            backup_dir = Path(__file__).parent.parent.parent / "db_backups"
            backup_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"backup_before_cleanup_{timestamp}.sqlite3"
            
            import shutil
            shutil.copy2(db_path, backup_path)
            self.check_log.append(f"💾 Backup created: {backup_path.name}")
            yield
            
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            portal_filter = ""
            params = []
            if self.cleanup_portal != "All Portals":
                portal_filter = "AND LOWER(TRIM(portal_name)) = LOWER(TRIM(?))"
                params.append(self.cleanup_portal)
            
            deleted_total = 0
            
            if self.cleanup_action in ["duplicates", "all"]:
                # Delete duplicate records (keep newest)
                query = f"""
                    DELETE FROM tenders
                    WHERE id IN (
                        SELECT t1.id
                        FROM tenders t1
                        WHERE tender_id_extracted IS NOT NULL 
                            AND TRIM(tender_id_extracted) != ''
                            {portal_filter}
                            AND t1.id NOT IN (
                                SELECT MAX(id)
                                FROM tenders t2
                                WHERE LOWER(TRIM(t2.tender_id_extracted)) = LOWER(TRIM(t1.tender_id_extracted))
                                    AND LOWER(TRIM(t2.portal_name)) = LOWER(TRIM(t1.portal_name))
                                GROUP BY LOWER(TRIM(t2.tender_id_extracted)), LOWER(TRIM(t2.portal_name))
                            )
                    )
                """
                cursor.execute(query, params)
                dup_deleted = cursor.rowcount
                deleted_total += dup_deleted
                self.check_log.append(f"🗑️ Deleted {dup_deleted} duplicate record(s)")
                yield
            
            if self.cleanup_action in ["invalid", "all"]:
                # Delete records with invalid/missing data
                query = f"""
                    DELETE FROM tenders
                    WHERE (
                        tender_id_extracted IS NULL
                        OR TRIM(tender_id_extracted) = ''
                        OR LOWER(TRIM(tender_id_extracted)) IN ('nan', 'none', 'null', 'n/a', 'na', '-', '--')
                        OR closing_date IS NULL
                        OR TRIM(closing_date) = ''
                        OR LOWER(TRIM(closing_date)) IN ('nan', 'none', 'null', 'n/a', 'na', '-', '--')
                    )
                    {portal_filter}
                """
                cursor.execute(query, params)
                inv_deleted = cursor.rowcount
                deleted_total += inv_deleted
                self.check_log.append(f"🗑️ Deleted {inv_deleted} invalid record(s)")
                yield
            
            conn.commit()
            conn.close()
            
            portal_msg = f"for '{self.cleanup_portal}'" if self.cleanup_portal != "All Portals" else "across all portals"
            self.check_log.append(f"✅ Cleanup complete {portal_msg}: {deleted_total} records deleted")
            
            # Re-run integrity check
            yield from self.run_integrity_check()
            
        except Exception as e:
            self.check_log.append(f"❌ Error during cleanup: {str(e)}")
        
        self.cleanup_running = False
        self.cleanup_action = ""
        self.cleanup_portal = ""
        self.cleanup_preview_count = 0
        self.cleanup_preview_details = ""
        yield
    
    def export_portal_issues(self, portal: str):
        """Export problematic records for a portal to Excel."""
        try:
            db_path = Path(__file__).parent.parent.parent / "database" / "blackforest_tenders.sqlite3"
            export_dir = Path(__file__).parent.parent.parent / "Tender84_Exports"
            export_dir.mkdir(exist_ok=True)
            
            import pandas as pd
            import sqlite3
            
            conn = sqlite3.connect(str(db_path))
            
            # Get duplicates
            query_dup = """
                SELECT portal_name, tender_id_extracted as tender_id, department_name, closing_date, COUNT(*) as duplicate_count
                FROM tenders
                WHERE LOWER(TRIM(portal_name)) = LOWER(TRIM(?))
                    AND tender_id_extracted IS NOT NULL
                    AND TRIM(tender_id_extracted) != ''
                GROUP BY LOWER(TRIM(tender_id_extracted))
                HAVING COUNT(*) > 1
                ORDER BY duplicate_count DESC
            """
            df_duplicates = pd.read_sql_query(query_dup, conn, params=(portal,))
            
            # Get invalid records
            query_invalid = """
                SELECT id, portal_name, department_name, tender_id_extracted as tender_id, closing_date
                FROM tenders
                WHERE LOWER(TRIM(portal_name)) = LOWER(TRIM(?))
                    AND (
                        tender_id_extracted IS NULL
                        OR TRIM(tender_id_extracted) = ''
                        OR LOWER(TRIM(tender_id_extracted)) IN ('nan', 'none', 'null', 'n/a', 'na', '-', '--')
                        OR closing_date IS NULL
                        OR TRIM(closing_date) = ''
                        OR LOWER(TRIM(closing_date)) IN ('nan', 'none', 'null', 'n/a', 'na', '-', '--')
                    )
                ORDER BY department_name
            """
            df_invalid = pd.read_sql_query(query_invalid, conn, params=(portal,))
            
            conn.close()
            
            # Export to Excel
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"portal_issues_{portal.replace(' ', '_')}_{timestamp}.xlsx"
            filepath = export_dir / filename
            
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                df_duplicates.to_excel(writer, sheet_name='Duplicates', index=False)
                df_invalid.to_excel(writer, sheet_name='Invalid Records', index=False)
            
            self.check_log.append(f"📊 Exported issues to: {filename}")
            
        except Exception as e:
            self.check_log.append(f"❌ Error exporting issues: {str(e)}")


def metric_card(title: str, value: rx.Var | str | int, status: str, icon: str, description: str = "") -> rx.Component:
    """Metric card with status indicator."""
    status_colors = {
        "good": "green",
        "warning": "yellow",
        "error": "red",
    }
    
    color = status_colors.get(status, "gray")
    
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(icon, size=24, color=f"{color}.9"),
                rx.vstack(
                    rx.text(title, size="2", color="gray.10", weight="medium"),
                    rx.heading(value, size="5", color="gray.12", weight="bold"),
                    align="start",
                    spacing="0",
                ),
                align="center",
                spacing="3",
                width="100%",
            ),
            rx.cond(
                description != "",
                rx.text(description, size="1", color="gray.9"),
                rx.box(),
            ),
            align="start",
            spacing="2",
            width="100%",
        ),
        padding="1rem",
        border_radius="10px",
        border="2px solid",
        border_color=f"{color}.5",
        background="white",
        width="100%",
    )


def duplicate_records_table() -> rx.Component:
    """Table showing duplicate tender records."""
    return rx.box(
        rx.vstack(
            rx.heading("Duplicate Tender IDs (Top 20)", size="4", weight="bold"),
            rx.cond(
                DataIntegrityState.duplicate_groups > 0,
                rx.vstack(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Portal"),
                                rx.table.column_header_cell("Tender ID"),
                                rx.table.column_header_cell("Count", justify="end"),
                            ),
                        ),
                        rx.table.body(
                            rx.foreach(
                                DataIntegrityState.duplicate_records,
                                lambda record: rx.table.row(
                                    rx.table.cell(record.portal_name),
                                    rx.table.cell(
                                        rx.text(record.tender_id, font_family="monospace", size="2")
                                    ),
                                    rx.table.cell(
                                        rx.badge(record.count, color_scheme="red"),
                                        justify="end",
                                    ),
                                ),
                            ),
                        ),
                        width="100%",
                        variant="surface",
                    ),
                    spacing="3",
                    width="100%",
                ),
                rx.callout(
                    "✅ No duplicate tender IDs found",
                    icon="check-circle",
                    color_scheme="green",
                ),
            ),
            align="start",
            spacing="3",
            width="100%",
        ),
        padding="1.2rem",
        border_radius="10px",
        border="1px solid",
        border_color="gray.6",
        background="white",
    )


def missing_fields_table() -> rx.Component:
    """Table showing records with missing required fields."""
    return rx.box(
        rx.vstack(
            rx.heading("Missing Closing Dates (Top 20 Departments)", size="4", weight="bold"),
            rx.cond(
                DataIntegrityState.missing_closing_dates > 0,
                rx.vstack(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Portal"),
                                rx.table.column_header_cell("Department"),
                                rx.table.column_header_cell("Missing Count", justify="end"),
                            ),
                        ),
                        rx.table.body(
                            rx.foreach(
                                DataIntegrityState.missing_field_records,
                                lambda record: rx.table.row(
                                    rx.table.cell(record.portal_name),
                                    rx.table.cell(record.department_name),
                                    rx.table.cell(
                                        rx.badge(record.missing_count, color_scheme="orange"),
                                        justify="end",
                                    ),
                                ),
                            ),
                        ),
                        width="100%",
                        variant="surface",
                    ),
                    spacing="3",
                    width="100%",
                ),
                rx.callout(
                    "✅ All records have closing dates",
                    icon="check-circle",
                    color_scheme="green",
                ),
            ),
            align="start",
            spacing="3",
            width="100%",
        ),
        padding="1.2rem",
        border_radius="10px",
        border="1px solid",
        border_color="gray.6",
        background="white",
    )


def check_log_display() -> rx.Component:
    """Display check log messages."""
    return rx.box(
        rx.vstack(
            rx.heading("Integrity Check Log", size="4", weight="bold"),
            rx.box(
                rx.foreach(
                    DataIntegrityState.check_log,
                    lambda msg: rx.text(msg, size="2", font_family="monospace", color="gray.11"),
                ),
                max_height="300px",
                overflow_y="auto",
                padding="0.5rem",
                border_radius="6px",
                background="gray.2",
                width="100%",
            ),
            align="start",
            spacing="3",
            width="100%",
        ),
        padding="1.2rem",
        border_radius="10px",
        border="1px solid",
        border_color="gray.6",
        background="white",
    )


def cleanup_confirmation_dialog() -> rx.Component:
    """Dialog to confirm cleanup actions with preview."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.dialog.title(
                    rx.hstack(
                        rx.icon("alert-triangle", size=20, color="orange"),
                        rx.text("Confirm Cleanup Action", weight="bold"),
                        spacing="2",
                    )
                ),
                rx.dialog.description(
                    rx.vstack(
                        rx.text(
                            f"You are about to modify the database:",
                            size="3",
                        ),
                        rx.box(
                            rx.vstack(
                                rx.text(
                                    rx.cond(
                                        DataIntegrityState.cleanup_portal == "All Portals",
                                        "🌐 All Portals",
                                        f"🏛️ Portal: {DataIntegrityState.cleanup_portal}"
                                    ),
                                    weight="bold",
                                    size="3",
                                ),
                                rx.text(
                                    rx.cond(
                                        DataIntegrityState.cleanup_action == "duplicates",
                                        "🗑️ Action: Remove Duplicates",
                                        rx.cond(
                                            DataIntegrityState.cleanup_action == "invalid",
                                            "🗑️  Action: Remove Invalid Records",
                                            "🗑️  Action: Fix All Issues (Duplicates + Invalid)"
                                        )
                                    ),
                                    size="3",
                                ),
                                rx.text(
                                    DataIntegrityState.cleanup_preview_details,
                                    italic=True,
                                    size="2",
                                    color="gray",
                                ),
                                spacing="2",
                            ),
                            padding="1rem",
                            border_radius="8px",
                            background="gray.2",
                            width="100%",
                        ),
                        rx.callout(
                            "✅ A backup will be created automatically before any changes.",
                            icon="shield-check",
                            color_scheme="green",
                            size="1",
                        ),
                        rx.callout(
                            f"⚠️ This will permanently delete {DataIntegrityState.cleanup_preview_count} record(s).",
                            icon="alert-circle",
                            color_scheme="orange",
                            size="1",
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    margin_top="0.5rem",
                    margin_bottom="1rem",
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button(
                            rx.icon("x"),
                            "Cancel",
                            on_click=DataIntegrityState.cancel_cleanup,
                            variant="soft",
                            color_scheme="gray",
                            size="3",
                        ),
                    ),
                    rx.button(
                        rx.icon("trash-2"),
                        "Confirm Cleanup",
                        on_click=DataIntegrityState.confirm_cleanup,
                        variant="solid",
                        color_scheme="red",
                        size="3",
                    ),
                    spacing="3",
                    justify="end",
                    width="100%",
                ),
                spacing="4",
                width="100%",
            ),
            max_width="500px",
        ),
        open=DataIntegrityState.show_cleanup_dialog,
    )


def portal_detail_modal() -> rx.Component:
    """Modal showing detailed records for a specific portal."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.dialog.title(
                    rx.hstack(
                        rx.icon("list", size=20),
                        rx.text(f"Details: ", weight="bold"),
                        rx.text(DataIntegrityState.selected_portal_detail, weight="bold", color="blue"),
                        spacing="2",
                    )
                ),
                rx.tabs.root(
                    rx.tabs.list(
                        rx.tabs.trigger("Duplicates", value="duplicates"),
                        rx.tabs.trigger("Invalid IDs", value="invalid_ids"),
                        rx.tabs.trigger("Missing Dates", value="missing_dates"),
                    ),
                    rx.tabs.content(
                        rx.box(
                            rx.cond(
                                DataIntegrityState.portal_detail_duplicates.length() > 0,
                                rx.vstack(
                                    rx.text(
                                        f"Found {DataIntegrityState.portal_detail_duplicates.length()} duplicate tender ID(s) (showing up to 100):",
                                        size="2",
                                        color="gray",
                                        margin_bottom="0.5rem",
                                    ),
                                    rx.table.root(
                                        rx.table.header(
                                            rx.table.row(
                                                rx.table.column_header_cell("Tender ID"),
                                                rx.table.column_header_cell("Count", justify="end"),
                                            ),
                                        ),
                                        rx.table.body(
                                            rx.foreach(
                                                DataIntegrityState.portal_detail_duplicates,
                                                lambda dup: rx.table.row(
                                                    rx.table.cell(dup["tender_id"]),
                                                    rx.table.cell(
                                                        rx.badge(dup["count"].to(str), color_scheme="orange"),
                                                        justify="end",
                                                    ),
                                                ),
                                            ),
                                        ),
                                        width="100%",
                                        size="1",
                                    ),
                                    spacing="2",
                                    max_height="400px",
                                    overflow_y="auto",
                                    width="100%",
                                ),
                                rx.callout(
                                    "✓ No duplicate tender IDs found",
                                    icon="check-circle",
                                    color_scheme="green",
                                ),
                            ),
                            width="100%",
                        ),
                        value="duplicates",
                    ),
                    rx.tabs.content(
                        rx.box(
                            rx.cond(
                                DataIntegrityState.portal_detail_invalid_ids.length() > 0,
                                rx.vstack(
                                    rx.text(
                                        f"Found {DataIntegrityState.portal_detail_invalid_ids.length()} record(s) with invalid/missing tender IDs (showing up to 100):",
                                        size="2",
                                        color="gray",
                                        margin_bottom="0.5rem",
                                    ),
                                    rx.table.root(
                                        rx.table.header(
                                            rx.table.row(
                                                rx.table.column_header_cell("Department"),
                                                rx.table.column_header_cell("Tender ID"),
                                                rx.table.column_header_cell("Closing Date"),
                                            ),
                                        ),
                                        rx.table.body(
                                            rx.foreach(
                                                DataIntegrityState.portal_detail_invalid_ids,
                                                lambda rec: rx.table.row(
                                                    rx.table.cell(rec["department_name"]),
                                                    rx.table.cell(
                                                        rx.badge(
                                                            rx.cond(
                                                                rec["tender_id"],
                                                                rec["tender_id"],
                                                                "NULL"
                                                            ),
                                                            color_scheme="red",
                                                            size="1",
                                                        )
                                                    ),
                                                    rx.table.cell(rec["closing_date"]),
                                                ),
                                            ),
                                        ),
                                        width="100%",
                                        size="1",
                                    ),
                                    spacing="2",
                                    max_height="400px",
                                    overflow_y="auto",
                                    width="100%",
                                ),
                                rx.callout(
                                    "✓ No invalid tender IDs found",
                                    icon="check-circle",
                                    color_scheme="green",
                                ),
                            ),
                            width="100%",
                        ),
                        value="invalid_ids",
                    ),
                    rx.tabs.content(
                        rx.box(
                            rx.cond(
                                DataIntegrityState.portal_detail_missing_dates.length() > 0,
                                rx.vstack(
                                    rx.text(
                                        f"Found {DataIntegrityState.portal_detail_missing_dates.length()} record(s) with missing closing dates (showing up to 100):",
                                        size="2",
                                        color="gray",
                                        margin_bottom="0.5rem",
                                    ),
                                    rx.table.root(
                                        rx.table.header(
                                            rx.table.row(
                                                rx.table.column_header_cell("Department"),
                                                rx.table.column_header_cell("Tender ID"),
                                                rx.table.column_header_cell("Closing Date"),
                                            ),
                                        ),
                                        rx.table.body(
                                            rx.foreach(
                                                DataIntegrityState.portal_detail_missing_dates,
                                                lambda rec: rx.table.row(
                                                    rx.table.cell(rec["department_name"]),
                                                    rx.table.cell(rec["tender_id"]),
                                                    rx.table.cell(
                                                        rx.badge(
                                                            rx.cond(
                                                                rec["closing_date"],
                                                                rec["closing_date"],
                                                                "NULL"
                                                            ),
                                                            color_scheme="orange",
                                                            size="1",
                                                        )
                                                    ),
                                                ),
                                            ),
                                        ),
                                        width="100%",
                                        size="1",
                                    ),
                                    spacing="2",
                                    max_height="400px",
                                    overflow_y="auto",
                                    width="100%",
                                ),
                                rx.callout(
                                    "✓ No missing closing dates found",
                                    icon="check-circle",
                                    color_scheme="green",
                                ),
                            ),
                            width="100%",
                        ),
                        value="missing_dates",
                    ),
                    default_value="duplicates",
                    width="100%",
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button(
                            rx.icon("x"),
                            "Close",
                            on_click=DataIntegrityState.close_detail_modal,
                            variant="soft",
                            color_scheme="gray",
                            size="2",
                        ),
                    ),
                    justify="end",
                    width="100%",
                    margin_top="1rem",
                ),
                spacing="4",
                width="100%",
            ),
            max_width="800px",
            max_height="600px",
        ),
        open=DataIntegrityState.show_detail_modal,
    )


def portal_integrity_table() -> rx.Component:
    """Table showing per-portal integrity metrics."""
    def get_status_color(status: str) -> str:
        if status == "excellent":
            return "green"
        elif status == "good":
            return "blue"
        elif status == "fair":
            return "yellow"
        else:
            return "red"
    
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.heading("🏛️ Per-Portal Integrity Metrics", size="4", weight="bold"),
                rx.spacer(),
                rx.hstack(
                    rx.text("Filter:", size="2", weight="medium"),
                    rx.select(
                        DataIntegrityState.portal_options,
                        value=DataIntegrityState.selected_portal,
                        on_change=DataIntegrityState.set_selected_portal,
                        size="2",
                    ),
                    align="center",
                    spacing="2",
                ),
                width="100%",
                align="center",
            ),
            rx.cond(
                DataIntegrityState.portal_metrics.length() > 0,
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Portal"),
                            rx.table.column_header_cell("Total Tenders", justify="end"),
                            rx.table.column_header_cell("Duplicates", justify="end"),
                            rx.table.column_header_cell("Missing IDs", justify="end"),
                            rx.table.column_header_cell("Missing Dates", justify="end"),
                            rx.table.column_header_cell("Score", justify="end"),
                            rx.table.column_header_cell("Status", justify="center"),
                            rx.table.column_header_cell("Actions", justify="center"),
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(
                            DataIntegrityState.filtered_portal_metrics,
                            lambda portal: rx.table.row(
                                rx.table.cell(
                                    rx.text(portal.portal_name, weight="medium"),
                                ),
                                rx.table.cell(
                                    rx.text(portal.total_tenders.to(str), font_family="monospace"),
                                    justify="end",
                                ),
                                rx.table.cell(
                                    rx.cond(
                                        portal.duplicate_groups > 0,
                                        rx.badge(
                                            f"{portal.duplicate_groups} ({portal.duplicate_rows} rows)",
                                            color_scheme="orange",
                                            size="1",
                                        ),
                                        rx.text("✓", color="green"),
                                    ),
                                    justify="end",
                                ),
                                rx.table.cell(
                                    rx.cond(
                                        portal.missing_tender_ids > 0,
                                        rx.badge(portal.missing_tender_ids.to(str), color_scheme="red", size="1"),
                                        rx.text("✓", color="green"),
                                    ),
                                    justify="end",
                                ),
                                rx.table.cell(
                                    rx.cond(
                                        portal.missing_closing_dates > 0,
                                        rx.badge(portal.missing_closing_dates.to(str), color_scheme="orange", size="1"),
                                        rx.text("✓", color="green"),
                                    ),
                                    justify="end",
                                ),
                                rx.table.cell(
                                    rx.text(
                                        f"{portal.integrity_score}/100",
                                        weight="bold",
                                        color=rx.cond(
                                            portal.integrity_score >= 90,
                                            "green",
                                            rx.cond(
                                                portal.integrity_score >= 70,
                                                "orange",
                                                "red"
                                            )
                                        ),
                                    ),
                                    justify="end",
                                ),
                                rx.table.cell(
                                    rx.badge(
                                        portal.status.to_string().capitalize(),
                                        color_scheme=rx.cond(
                                            portal.status == "excellent",
                                            "green",
                                            rx.cond(
                                                portal.status == "good",
                                                "blue",
                                                rx.cond(
                                                    portal.status == "fair",
                                                    "yellow",
                                                    "red"
                                                )
                                            )
                                        ),
                                        size="2",
                                    ),
                                    justify="center",
                                ),
                                rx.table.cell(
                                    rx.hstack(
                                        rx.button(
                                            rx.icon("eye", size=14),
                                            on_click=lambda p=portal.portal_name: DataIntegrityState.show_portal_details(p),
                                            variant="soft",
                                            color_scheme="blue",
                                            size="1",
                                            title="View details",
                                        ),
                                        rx.cond(
                                            portal.duplicate_groups > 0,
                                            rx.button(
                                                rx.icon("trash-2", size=14),
                                                on_click=lambda p=portal.portal_name: DataIntegrityState.preview_cleanup_action("duplicates", p),
                                                variant="soft",
                                                color_scheme="orange",
                                                size="1",
                                                title="Clean duplicates",
                                            ),
                                            rx.box(),
                                        ),
                                        rx.cond(
                                            (portal.missing_tender_ids > 0) | (portal.missing_closing_dates > 0),
                                            rx.button(
                                                rx.icon("x-circle", size=14),
                                                on_click=lambda p=portal.portal_name: DataIntegrityState.preview_cleanup_action("invalid", p),
                                                variant="soft",
                                                color_scheme="red",
                                                size="1",
                                                title="Remove invalid records",
                                            ),
                                            rx.box(),
                                        ),
                                        rx.cond(
                                            (portal.duplicate_groups > 0) | (portal.missing_tender_ids > 0) | (portal.missing_closing_dates > 0),
                                            rx.button(
                                                rx.icon("download", size=14),
                                                on_click=lambda p=portal.portal_name: DataIntegrityState.export_portal_issues(p),
                                                variant="soft",
                                                color_scheme="violet",
                                                size="1",
                                                title="Export issues",
                                            ),
                                            rx.box(),
                                        ),
                                        spacing="1",
                                        justify="center",
                                    ),
                                    justify="center",
                                ),
                            ),
                        ),
                    ),
                    width="100%",
                    variant="surface",
                ),
                rx.callout(
                    "No portal metrics available. Click 'Re-check' to analyze.",
                    icon="info",
                    color_scheme="blue",
                ),
            ),
            align="start",
            spacing="3",
            width="100%",
        ),
        padding="1.2rem",
        border_radius="10px",
        border="1px solid",
        border_color="gray.6",
        background="white",
    )


def data_integrity_page() -> rx.Component:
    """Data integrity verification page."""
    return rx.box(
        rx.vstack(
            # Header
            rx.hstack(
                rx.heading("🔍 Data Integrity Verification", size="7", weight="bold"),
                rx.spacer(),
                rx.hstack(
                    rx.button(
                        rx.icon("refresh-cw"),
                        "Re-check",
                        on_click=DataIntegrityState.run_integrity_check,
                        variant="soft",
                        color_scheme="blue",
                        size="2",
                        loading=DataIntegrityState.checking,
                    ),
                    rx.button(
                        rx.icon("wrench"),
                        "Fix All Issues",
                        on_click=lambda: DataIntegrityState.preview_cleanup_action("all", "All Portals"),
                        variant="soft",
                        color_scheme="violet",
                        size="2",
                        disabled=DataIntegrityState.cleanup_running | DataIntegrityState.checking,
                    ),
                    rx.button(
                        rx.icon("trash-2"),
                        "Run Cleanup",
                        on_click=DataIntegrityState.run_cleanup,
                        variant="soft",
                        color_scheme="red",
                        size="2",
                        loading=DataIntegrityState.cleanup_running,
                    ),
                    spacing="2",
                ),
                width="100%",
                align="center",
            ),
            
            rx.text(
                f"Last checked: {DataIntegrityState.last_check_time}",
                size="2",
                color="gray.10",
            ),
            
            rx.divider(),
            
            # Overall integrity score
            rx.box(
                rx.vstack(
                    rx.heading("Overall Integrity Score", size="4", weight="bold"),
                    rx.hstack(
                        rx.heading(
                            f"{DataIntegrityState.integrity_score}/100",
                            size="8",
                            color=f"{DataIntegrityState.score_color}.9",
                            weight="bold",
                        ),
                        rx.badge(
                            rx.cond(
                                DataIntegrityState.integrity_score >= 90,
                                "Excellent",
                                rx.cond(
                                    DataIntegrityState.integrity_score >= 70,
                                    "Fair",
                                    "Poor"
                                ),
                            ),
                            color_scheme=DataIntegrityState.score_color,
                            size="3",
                        ),
                        align="center",
                        spacing="4",
                    ),
                    align="start",
                    spacing="2",
                ),
                padding="1.5rem",
                border_radius="12px",
                background=f"linear-gradient(135deg, white 0%, {DataIntegrityState.score_color}.50 100%)",
                border="2px solid",
                border_color=f"{DataIntegrityState.score_color}.5",
                box_shadow="lg",
                width="100%",
            ),
            
            # Metrics grid
            rx.grid(
                metric_card(
                    "Total Tenders",
                    DataIntegrityState.total_tenders.to(str),
                    "good",
                    "database",
                    f"Across {DataIntegrityState.distinct_portals} portals",
                ),
                metric_card(
                    "Duplicate Groups",
                    DataIntegrityState.duplicate_groups.to(str),
                    rx.cond(DataIntegrityState.duplicate_groups == 0, "good", "warning"),
                    "copy",
                    f"{DataIntegrityState.duplicate_extra_rows} extra rows",
                ),
                metric_card(
                    "Missing Tender IDs",
                    DataIntegrityState.missing_tender_ids.to(str),
                    rx.cond(DataIntegrityState.missing_tender_ids == 0, "good", "error"),
                    "alert-triangle",
                    "Records without valid IDs",
                ),
                metric_card(
                    "Missing Closing Dates",
                    DataIntegrityState.missing_closing_dates.to(str),
                    rx.cond(DataIntegrityState.missing_closing_dates == 0, "good", "warning"),
                    "calendar",
                    "Records without dates",
                ),
                columns="4",
                spacing="4",
                width="100%",
            ),
            
            rx.divider(),
            
            # Per-portal integrity metrics
            portal_integrity_table(),
            
            rx.divider(),
            
            # Detailed tables
            rx.grid(
                duplicate_records_table(),
                missing_fields_table(),
                columns="2",
                spacing="4",
                width="100%",
            ),
            
            # Check log
            check_log_display(),
            
            # Documentation link
            rx.callout(
                rx.vstack(
                    rx.text("📚 For more information on data integrity verification:", size="2", weight="medium"),
                    rx.text("See DATA_INTEGRITY_VERIFICATION.md for comprehensive documentation, SQL queries, and best practices.", size="2"),
                    align="start",
                    spacing="1",
                ),
                icon="book-open",
                color_scheme="blue",
                size="2",
            ),
            
            spacing="4",
            width="100%",
            on_mount=DataIntegrityState.on_load,
        ),
        
        # Dialogs and modals
        cleanup_confirmation_dialog(),
        portal_detail_modal(),
        
        width="100%",
        max_width="100%",
        padding="1.5rem",
    )
