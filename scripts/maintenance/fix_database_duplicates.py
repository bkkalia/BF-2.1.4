"""
Critical Database Fixes - Remove Duplicates & Add Constraints
Run this script to fix data quality issues found in analysis.
"""

import sqlite3
import shutil
from datetime import datetime
from pathlib import Path

DB_PATH = Path("D:/Dev84/BF 2.1.4/data/blackforest_tenders.sqlite3")

def backup_database():
    """Create backup before modifications"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"blackforest_tenders_before_dedup_{timestamp}.sqlite3"
    backup_path = DB_PATH.parent / backup_filename
    
    print(f"\n📦 Creating backup: {backup_path.name}")
    shutil.copy2(DB_PATH, backup_path)
    print(f"✅ Backup created successfully\n")
    return backup_path

def get_duplicate_stats(conn):
    """Get statistics on duplicates"""
    cursor = conn.execute("""
        SELECT COUNT(*) as total_rows
        FROM tenders
    """)
    total = cursor.fetchone()[0]
    
    cursor = conn.execute("""
        SELECT COUNT(DISTINCT 
            LOWER(TRIM(portal_name)) || '|' ||
            LOWER(TRIM(tender_id_extracted)) || '|' ||
            LOWER(TRIM(closing_date))
        ) as unique_rows
        FROM tenders
        WHERE tender_id_extracted IS NOT NULL 
          AND tender_id_extracted != ''
    """)
    unique = cursor.fetchone()[0]
    duplicates = total - unique
    
    return total, unique, duplicates

def remove_duplicates(conn):
    """Remove duplicate tenders, keeping most recent insertion"""
    
    print("🔍 Analyzing duplicates...")
    total_before, unique_before, dup_count_before = get_duplicate_stats(conn)
    
    print(f"   Total tenders: {total_before:,}")
    print(f"   Unique tenders: {unique_before:,}")
    print(f"   Duplicates: {dup_count_before:,}")
    
    if dup_count_before == 0:
        print("✅ No duplicates found!")
        return 0
    
    print(f"\n🧹 Removing {dup_count_before:,} duplicate tenders...")
    
    # Keep the tender with highest ID (most recent) for each unique combination
    cursor = conn.execute("""
        DELETE FROM tenders
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM tenders
            WHERE tender_id_extracted IS NOT NULL 
              AND tender_id_extracted != ''
            GROUP BY 
                LOWER(TRIM(portal_name)),
                LOWER(TRIM(tender_id_extracted)),
                LOWER(TRIM(closing_date))
        )
        AND tender_id_extracted IS NOT NULL 
        AND tender_id_extracted != ''
    """)
    
    deleted_count = cursor.rowcount
    print(f"✅ Deleted {deleted_count:,} duplicate rows")
    
    # Verify
    total_after, unique_after, dup_count_after = get_duplicate_stats(conn)
    
    print(f"\n📊 After cleanup:")
    print(f"   Total tenders: {total_after:,}")
    print(f"   Unique tenders: {unique_after:,}")
    print(f"   Duplicates remaining: {dup_count_after:,}")
    
    return deleted_count

def add_unique_constraint(conn):
    """Add unique constraint to prevent future duplicates"""
    
    print("\n🔒 Adding UNIQUE constraint to prevent future duplicates...")
    
    try:
        # Check if index already exists
        cursor = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' 
              AND name='idx_tenders_unique_portal_tender_date'
        """)
        
        if cursor.fetchone():
            print("ℹ️  Unique constraint already exists")
            return False
        
        # Create unique index
        conn.execute("""
            CREATE UNIQUE INDEX idx_tenders_unique_portal_tender_date
            ON tenders(
                LOWER(TRIM(portal_name)),
                LOWER(TRIM(tender_id_extracted)),
                LOWER(TRIM(closing_date))
            )
            WHERE tender_id_extracted IS NOT NULL 
              AND tender_id_extracted != ''
        """)
        
        print("✅ Unique constraint added successfully")
        print("   This will prevent duplicate tenders from being inserted in future")
        return True
        
    except sqlite3.IntegrityError as e:
        print(f"❌ Error: {e}")
        print("   There may still be duplicates. Re-run duplicate removal.")
        return False

def vacuum_database(conn):
    """Optimize database after deletions"""
    print("\n🗜️  Optimizing database (VACUUM)...")
    conn.execute("VACUUM")
    print("✅ Database optimized")

def main():
    print("="*80)
    print("DATABASE CLEANUP - REMOVE DUPLICATES & ADD CONSTRAINTS")
    print("="*80)
    
    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        return
    
    # Create backup
    backup_path = backup_database()
    
    # Connect and fix
    conn = sqlite3.connect(str(DB_PATH))
    
    try:
        # Remove duplicates
        deleted = remove_duplicates(conn)
        
        # Add unique constraint
        add_unique_constraint(conn)
        
        # Commit changes
        conn.commit()
        
        # Optimize
        vacuum_database(conn)
        
        print("\n" + "="*80)
        print("✅ DATABASE CLEANUP COMPLETE")
        print("="*80)
        print(f"   Rows deleted: {deleted:,}")
        print(f"   Backup saved: {backup_path.name}")
        print(f"\nℹ️  If anything goes wrong, restore from backup:")
        print(f"   copy \"{backup_path}\" \"{DB_PATH}\"")
        print("="*80)
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error during cleanup: {e}")
        print(f"   Database rolled back - no changes made")
        print(f"   Backup is safe at: {backup_path}")
        raise
    
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
