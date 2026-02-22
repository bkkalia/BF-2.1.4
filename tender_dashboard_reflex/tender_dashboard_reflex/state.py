from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel
from typing import Any
import os
import re
from pathlib import Path

import reflex as rx

from . import db


def _extract_real_tender_id(raw_id: str, title_ref: str) -> str:
    """Extract the real tender ID (e.g. 2026_PWD_128301_1) from title_ref
    when raw_id is just a portal serial number like '1', '138'."""
    # Already a proper ID (has underscores and year prefix like 2026_)
    if "_" in raw_id and len(raw_id) > 8:
        return raw_id
    # Extract last [YEAR_PORTAL_NUMBER_VERSION] pattern embedded in title_ref
    matches = re.findall(r"\[(\d{4}_[A-Z0-9]+_\d+_\d+)\]", title_ref or "")
    if matches:
        return matches[-1]
    return raw_id


def _clean_title_ref(title_ref: str) -> str:
    """Remove tender ID stamp from end of title and strip outer brackets."""
    # Remove [2026_PORTAL_NUMBER_VERSION] from the end
    cleaned = re.sub(r"\s*\[\d{4}_[A-Z0-9]+_\d+_\d+\]\s*$", "", title_ref).strip()
    # Strip leading/trailing outer bracket pair if the whole title is wrapped: [title text]
    if cleaned.startswith("[") and cleaned.endswith("]"):
        cleaned = cleaned[1:-1].strip()
    return cleaned or title_ref


class TenderRow(BaseModel):
    id: int = 0
    portal_name: str = ""
    tender_id_extracted: str = ""
    title_ref: str = ""
    department_name: str = ""
    published_at: str = ""
    closing_at: str = ""
    estimated_cost_value: str = ""
    tender_status: str = ""
    state_name: str = ""
    district: str = ""
    city: str = ""
    tender_url: str = ""
    status_url: str = ""


class Recommendation(BaseModel):
    title: str = ""
    value: str = ""


class DashboardState(rx.State):
    loading: bool = False
    error_message: str = ""
    toast_message: str = ""
    toast_type: str = "info"  # info, success, error
    show_toast: bool = False
    
    # Export options (current view)
    show_export_dialog: bool = False
    export_expired_days: int = 30
    exporting: bool = False
    
    # Public export interface (for website)
    show_public_export: bool = False
    public_export_portal: str = "All"
    public_export_expired_days: int = 30
    public_exporting: bool = False

    portal_options: list[str] = ["All"]
    portal_group_options: list[str] = ["All", "North India", "PSUs", "CPPP", "State Portals", "Others"]
    status_options: list[str] = ["All", "Live", "Archived", "open", "closed"]
    state_options: list[str] = ["All"]
    district_options: list[str] = ["All"]
    city_options: list[str] = ["All"]
    tender_type_options: list[str] = ["All"]
    work_type_options: list[str] = ["All"]
    sort_options: list[str] = [
        "published_at",
        "closing_at",
        "estimated_cost_value",
        "portal_name",
        "department_name",
    ]
    filter_position_options: list[str] = ["left", "right"]
    view_mode_options: list[str] = ["cards", "table"]
    search_logic_options: list[str] = ["AND", "OR"]

    selected_portal: str = "All"
    selected_portal_group: str = "All"
    selected_status: str = "All"
    selected_state: str = "All"
    selected_district: str = "All"
    selected_city: str = "All"
    selected_tender_type: str = "All"
    selected_work_type: str = "All"

    from_date: str = ""
    to_date: str = ""
    min_amount: str = ""
    max_amount: str = ""
    search_query: str = ""
    department_filter: str = ""
    department_logic: str = "OR"
    search_logic: str = "OR"
    lifecycle_filter: str = "Live"  # All, Live, Expired
    selected_sort: str = "published_at"
    selected_sort_order: str = "desc"
    selected_filter_position: str = "left"
    view_mode: str = "cards"
    show_settings: bool = False

    page: int = 1
    page_size: int = 25
    total_count: int = 0
    total_pages: int = 0

    live_tenders: int = 0
    expired_tenders: int = 0
    total_tenders: int = 0
    filtered_results: int = 0
    match_percent: str = "0.0%"
    departments: int = 0
    due_today: int = 0
    due_3_days: int = 0
    due_7_days: int = 0
    data_sources: int = 0

    current_time: str = ""

    rows: list[TenderRow] = []
    recommendations: list[Recommendation] = []

    def _filters(self) -> db.TenderFilters:
        # Map lifecycle_filter to show_live_only
        show_live_only = self.lifecycle_filter == "Live"
        show_expired_only = self.lifecycle_filter == "Expired"
        
        return db.TenderFilters(
            portal=self.selected_portal,
            portal_group=self.selected_portal_group,
            status=self.selected_status,
            state=self.selected_state,
            district=self.selected_district,
            city=self.selected_city,
            tender_type=self.selected_tender_type,
            work_type=self.selected_work_type,
            from_date=self.from_date,
            to_date=self.to_date,
            min_amount=self.min_amount,
            max_amount=self.max_amount,
            search_query=self.search_query,
            search_logic=self.search_logic,
            department_filter=self.department_filter,
            department_logic=self.department_logic,
            show_live_only=show_live_only,
            show_expired_only=show_expired_only,
        )

    def load_initial_data(self):
        self.loading = True
        self.error_message = ""
        try:
            self.portal_options = ["All", *db.get_portal_options()]
            self.state_options = ["All", *db.get_state_options()]
            self.tender_type_options = ["All", *db.get_tender_type_options()]
            self.work_type_options = ["All", *db.get_work_type_options()]
            self._refresh_location_options()
            self.refresh_data()
        except Exception as ex:
            self.error_message = f"{type(ex).__name__}: {ex} | DB={db.DB_PATH}"
            self.loading = False

    def set_selected_portal(self, value: str):
        self.selected_portal = value
        self.apply_filters()

    def set_selected_portal_group(self, value: str):
        self.selected_portal_group = value
        # When group changes, reset portal selection and update portal options based on group
        self.selected_portal = "All"
        self.apply_filters()

    def set_selected_status(self, value: str):
        self.selected_status = value
        self.apply_filters()

    def set_selected_city(self, value: str):
        self.selected_city = value
        self.apply_filters()

    def set_selected_tender_type(self, value: str):
        self.selected_tender_type = value
        self.apply_filters()

    def set_selected_work_type(self, value: str):
        self.selected_work_type = value
        self.apply_filters()

    def set_selected_sort(self, value: str):
        self.selected_sort = value
        self.apply_filters()

    def set_selected_sort_order(self, value: str):
        self.selected_sort_order = value
        self.apply_filters()

    def set_from_date(self, value: str):
        self.from_date = value
        self.apply_filters()

    def set_to_date(self, value: str):
        self.to_date = value
        self.apply_filters()

    def set_min_amount(self, value: str):
        self.min_amount = value
        self.apply_filters()

    def set_max_amount(self, value: str):
        self.max_amount = value
        self.apply_filters()

    def set_search_query(self, value: str):
        self.search_query = value

    def set_search_logic(self, value: str):
        self.search_logic = value
        self.apply_filters()

    def set_department_filter(self, value: str):
        self.department_filter = value

    def set_department_logic(self, value: str):
        self.department_logic = value
        self.apply_filters()
    
    def set_lifecycle_filter(self, value: str):
        """Set lifecycle filter: All, Live, or Expired."""
        self.lifecycle_filter = value
        self.apply_filters()

    def toggle_settings(self):
        self.show_settings = not self.show_settings

    def set_view_mode(self, value: str):
        if value in self.view_mode_options:
            self.view_mode = value

    def set_selected_filter_position(self, value: str):
        if value in self.filter_position_options:
            self.selected_filter_position = value

    def _refresh_location_options(self):
        self.district_options = ["All", *db.get_district_options(self.selected_state)]
        self.city_options = ["All", *db.get_city_options(self.selected_state, self.selected_district)]

    def refresh_data(self):
        filters = self._filters()

        summary = db.get_summary(filters)
        self.total_tenders = int(summary["total_tenders"])
        self.live_tenders = int(summary["live_tenders"])
        self.expired_tenders = int(summary["expired_tenders"])
        self.filtered_results = int(summary["filtered_results"])
        self.match_percent = str(summary["match_percent"])
        self.departments = int(summary["departments"])
        self.due_today = int(summary["due_today"])
        self.due_3_days = int(summary["due_3_days"])
        self.due_7_days = int(summary["due_7_days"])
        self.data_sources = int(summary["data_sources"])

        row_data, total_count = db.search_tenders(
            filters=filters,
            page=self.page,
            page_size=self.page_size,
            sort_by=self.selected_sort,
            sort_order=self.selected_sort_order,
        )
        self.total_count = total_count
        self.total_pages = (total_count + self.page_size - 1) // self.page_size

        self.rows = [
            TenderRow(
                id=int(item.get("id") or 0),
                portal_name=str(item.get("portal_name") or "-"),
                tender_id_extracted=_extract_real_tender_id(
                    str(item.get("tender_id_extracted") or ""),
                    str(item.get("title_ref") or ""),
                ),
                title_ref=_clean_title_ref(str(item.get("title_ref") or "-")),
                department_name=str(item.get("department_name") or "-"),
                published_at=self._fmt_date(item.get("published_at")),
                closing_at=self._fmt_date(item.get("closing_at")),
                estimated_cost_value=self._fmt_money(item.get("estimated_cost_value")),
                tender_status=str(item.get("tender_status") or "-"),
                state_name=str(item.get("state_name") or "-"),
                district=str(item.get("district") or "-"),
                city=str(item.get("city") or "-"),
                tender_url=str(item.get("tender_url") or ""),
                status_url=str(item.get("status_url") or ""),
            )
            for item in row_data
        ]

        self.recommendations = [
            Recommendation(title=entry["title"], value=entry["value"])
            for entry in db.get_recommendations(filters)
        ]
        self.current_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.loading = False

    def _fmt_money(self, value: object) -> str:
        if value is None:
            return "-"
        try:
            amount = float(str(value))
            if amount >= 1e7:
                return f"₹{amount / 1e7:.2f} Cr"
            if amount >= 1e5:
                return f"₹{amount / 1e5:.2f} L"
            if amount >= 1e3:
                return f"₹{amount / 1e3:.2f} K"
            return f"₹{amount:.2f}"
        except Exception:
            return "-"

    def _fmt_date(self, date_value: object) -> str:
        if not date_value:
            return "-"
        text = str(date_value).strip()
        if not text:
            return "-"
        try:
            return datetime.fromisoformat(text.replace(" ", "T")).strftime("%d-%m-%Y")
        except Exception:
            return text

    def on_state_change(self, value: str):
        self.selected_state = value
        self.selected_district = "All"
        self.selected_city = "All"
        self._refresh_location_options()

    def on_district_change(self, value: str):
        self.selected_district = value
        self.selected_city = "All"
        self.city_options = ["All", *db.get_city_options(self.selected_state, self.selected_district)]

    def apply_filters(self):
        self.page = 1
        self.loading = True
        self.refresh_data()

    def reset_filters(self):
        self.selected_portal = "All"
        self.selected_portal_group = "All"
        self.selected_status = "All"
        self.selected_state = "All"
        self.selected_district = "All"
        self.selected_city = "All"
        self.selected_tender_type = "All"
        self.selected_work_type = "All"
        self.from_date = ""
        self.to_date = ""
        self.min_amount = ""
        self.max_amount = ""
        self.search_query = ""
        self.department_filter = ""
        self.search_logic = "OR"
        self.department_logic = "OR"
        self.lifecycle_filter = "Live"
        self.selected_sort = "published_at"
        self.selected_sort_order = "desc"
        self.page = 1
        self._refresh_location_options()
        self.loading = True
        self.refresh_data()
    
    # Clickable KPI filters
    def filter_by_due_today(self):
        """Filter to show only tenders due today."""
        from datetime import date
        today = date.today().strftime("%Y-%m-%d")
        self.from_date = ""
        self.to_date = today
        self.apply_filters()
    
    def filter_by_due_3_days(self):
        """Filter to show only tenders due in next 3 days."""
        from datetime import date, timedelta
        today = date.today()
        three_days = (today + timedelta(days=3)).strftime("%Y-%m-%d")
        self.from_date = ""
        self.to_date = three_days
        self.apply_filters()
    
    def filter_by_due_7_days(self):
        """Filter to show only tenders due in next 7 days."""
        from datetime import date, timedelta
        today = date.today()
        seven_days = (today + timedelta(days=7)).strftime("%Y-%m-%d")
        self.from_date = ""
        self.to_date = seven_days
        self.apply_filters()
    
    def clear_date_filters(self):
        """Clear date filter to show all departments/counts."""
        self.from_date = ""
        self.to_date = ""
        self.apply_filters()

    def set_page_size_value(self, value: str):
        try:
            self.page_size = int(value)
        except ValueError:
            self.page_size = 25

    def next_page(self):
        if self.page < self.total_pages:
            self.page += 1
    
    def show_toast_notification(self, message: str, toast_type: str = "info"):
        """Show toast notification to user."""
        self.toast_message = message
        self.toast_type = toast_type
        self.show_toast = True
    
    def hide_toast(self):
        """Hide toast notification."""
        self.show_toast = False
    
    def toggle_export_dialog(self):
        """Toggle export options dialog."""
        self.show_export_dialog = not self.show_export_dialog
    
    def set_export_expired_days(self, value: str):
        """Set number of days for expired tenders to include in export."""
        try:
            self.export_expired_days = int(value)
        except ValueError:
            self.export_expired_days = 30
    
    async def export_to_excel(self):
        """Export filtered tenders to Excel files (one per portal)."""
        self.exporting = True
        self.loading = True
        yield
        
        try:
            # Import pandas and openpyxl for Excel export
            try:
                import pandas as pd
            except ImportError:
                self.show_toast_notification("pandas not installed. Run: pip install pandas openpyxl", "error")
                self.exporting = False
                self.loading = False
                yield
                return
            
            # Get export data grouped by portal
            filters = self._filters()
            portals_data = db.export_tenders_by_portal(filters, self.export_expired_days)
            
            if not portals_data:
                self.show_toast_notification("No tenders to export with current filters", "error")
                self.exporting = False
                self.loading = False
                yield
                return
            
            # Create exports directory if it doesn't exist
            export_dir = Path("Tender84_Exports") / datetime.now().strftime("%Y%m%d_%H%M%S")
            export_dir.mkdir(parents=True, exist_ok=True)
            
            # Export each portal to separate file
            exported_files = []
            for portal_name, tenders in portals_data.items():
                # Clean portal name for filename
                safe_portal_name = "".join(c if c.isalnum() or c in (' ', '_') else '_' for c in portal_name)
                safe_portal_name = safe_portal_name.replace(' ', '_').lower()
                
                # Create DataFrame with exact column order
                df = pd.DataFrame(tenders)
                
                # Ensure column order matches template
                column_order = [
                    "Department Name",
                    "S.No",
                    "e-Published Date",
                    "Closing Date",
                    "Opening Date",
                    "Organisation Chain",
                    "Title and Ref.No./Tender ID",
                    "Tender ID (Extracted)",
                    "Direct URL",
                    "Status URL"
                ]
                df = df[column_order]
                
                # Export to Excel
                filename = f"{safe_portal_name}_tenders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                filepath = export_dir / filename
                df.to_excel(filepath, index=False, engine='openpyxl')
                exported_files.append(filename)
            
            # Show success message
            total_files = len(exported_files)
            total_tenders = sum(len(tenders) for tenders in portals_data.values())
            message = f"✅ Exported {total_tenders} tenders to {total_files} file(s) in {export_dir.name}"
            self.show_toast_notification(message, "success")
            
        except Exception as ex:
            error_msg = f"Export failed: {type(ex).__name__}: {ex}"
            self.show_toast_notification(error_msg, "error")
        
        finally:
            self.exporting = False
            self.loading = False
            self.show_export_dialog = False
            yield
            self.loading = True
            self.refresh_data()

    def toggle_public_export(self):
        """Toggle public export interface."""
        self.show_public_export = not self.show_public_export
    
    def set_public_export_portal(self, value: str):
        """Set portal for public export."""
        self.public_export_portal = value
    
    def set_public_export_expired_days(self, value: str):
        """Set expired days for public export."""
        try:
            self.public_export_expired_days = int(value)
        except ValueError:
            self.public_export_expired_days = 30
    
    async def public_export_to_excel(self):
        """Export all live tenders + X days expired for a specific portal (for website)."""
        self.public_exporting = True
        self.loading = True
        yield
        
        try:
            # Import pandas
            try:
                import pandas as pd
            except ImportError:
                self.show_toast_notification("pandas not installed. Run: pip install openpyxl", "error")
                self.public_exporting = False
                self.loading = False
                yield
                return
            
            # Validate portal selection
            if self.public_export_portal == "All":
                self.show_toast_notification("Please select a specific portal for public export", "error")
                self.public_exporting = False
                self.loading = False
                yield
                return
            
            # Create filters for live + expired tenders
            from datetime import date, timedelta
            from . import db
            
            # Set cutoff date for expired tenders
            cutoff_date = (date.today() - timedelta(days=self.public_export_expired_days)).strftime("%Y-%m-%d")
            
            # Build filter for specific portal, no lifecycle filter (get all)
            filters = db.TenderFilters(
                portal=self.public_export_portal,
                show_live_only=False,
                show_expired_only=False,
                from_date=cutoff_date,  # Only get tenders from last X days
                to_date=""
            )
            
            # Get tenders for this portal
            portals_data = db.export_tenders_by_portal(filters, self.public_export_expired_days)
            
            if not portals_data or self.public_export_portal not in portals_data:
                self.show_toast_notification(f"No tenders found for {self.public_export_portal}", "error")
                self.public_exporting = False
                self.loading = False
                yield
                return
            
            # Create public exports directory
            export_dir = Path("Public_Exports") / datetime.now().strftime("%Y%m%d")
            export_dir.mkdir(parents=True, exist_ok=True)
            
            # Get tenders for selected portal
            tenders = portals_data[self.public_export_portal]
            
            # Clean portal name for filename
            safe_portal_name = "".join(c if c.isalnum() or c in (' ', '_') else '_' for c in self.public_export_portal)
            safe_portal_name = safe_portal_name.replace(' ', '_').lower()
            
            # Create DataFrame
            df = pd.DataFrame(tenders)
            
            # Column order
            column_order = [
                "Department Name",
                "S.No",
                "e-Published Date",
                "Closing Date",
                "Opening Date",
                "Organisation Chain",
                "Title and Ref.No./Tender ID",
                "Tender ID (Extracted)",
                "Direct URL",
                "Status URL"
            ]
            df = df[column_order]
            
            # Export to Excel
            filename = f"{safe_portal_name}_public_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            filepath = export_dir / filename
            df.to_excel(filepath, index=False, engine='openpyxl')
            
            # Success message
            live_count = len([t for t in tenders if t.get("Status URL", "").lower() == "live"])
            expired_count = len(tenders) - live_count
            message = f"✅ Public export: {live_count} live + {expired_count} expired tenders → {filename}"
            self.show_toast_notification(message, "success")
            
        except Exception as ex:
            error_msg = f"Public export failed: {type(ex).__name__}: {ex}"
            self.show_toast_notification(error_msg, "error")
        
        finally:
            self.public_exporting = False
            self.loading = False
            yield
            self.loading = True
            self.refresh_data()

    def prev_page(self):
        if self.page > 1:
            self.page -= 1
            self.loading = True
            self.refresh_data()

class PortalRow(BaseModel):
    """Portal statistics row model."""
    portal_slug: str = ""
    portal_name: str = ""
    base_url: str = ""
    last_updated: str = ""
    total_tenders: int = 0
    live_tenders: int = 0
    expired_tenders: int = 0
    category: str = "State"  # Central, State, PSU
    days_since_update: int = -1  # Days since last update (-1 if unknown)


class ExportHistoryEntry(BaseModel):
    """Export history entry model."""
    timestamp: str = ""
    export_type: str = ""
    portals: list[str] = []
    total_tenders: int = 0
    file_count: int = 0
    export_dir: str = ""
    settings: dict[str, Any] = {}


class DataRow(BaseModel):
    """Data row for data visualization grid - displays ALL database columns."""
    row_num: int = 0
    portal_name: str = ""
    tender_id_extracted: str = ""
    title_ref: str = ""
    department_name: str = ""
    organisation_chain: str = ""
    serial_no: str = ""
    published_date: str = ""
    opening_date: str = ""
    closing_date: str = ""
    emd_amount: str = ""
    estimated_cost: str = ""
    lifecycle_status: str = ""
    tender_status: str = ""
    state_name: str = ""
    district: str = ""
    city: str = ""
    pincode: str = ""
    location_text: str = ""
    tender_type: str = ""
    work_type: str = ""
    payment_type: str = ""
    direct_url: str = ""
    status_url: str = ""
    is_live: str = ""
    run_id: str = ""
    first_seen_at: str = ""
    last_seen_at: str = ""


class PortalManagementState(rx.State):
    """State for Portal Management page."""
    loading: bool = False
    portal_rows: list[PortalRow] = []
    
    # Export settings
    show_export_dialog: bool = False
    export_days_filter: int = 0  # 0 = all portals, >0 = portals updated in last X days
    export_expired_days: int = 30  # Days of expired tenders to include
    export_live_only: bool = False  # Export only live tenders
    export_selected_portals: list[str] = []  # Selected portal slugs for export
    exporting: bool = False
    export_base_dir: str = "Portal_Exports"
    last_export_path: str = ""
    
    # Toast notifications
    toast_message: str = ""
    toast_type: str = "info"
    show_toast: bool = False
    
    # Filters/settings
    days_filter: int = 0  # Filter portals by last updated (0 = all)
    sort_by: str = "portal_name"  # portal_name, total_tenders, live_tenders, last_updated
    sort_order: str = "asc"
    category_filter: str = "All"  # All, Central, State, PSU
    
    # Export history
    show_export_history: bool = False
    export_history: list[ExportHistoryEntry] = []
    
    @rx.var
    def total_portals(self) -> int:
        """Total number of portals."""
        return len(self.portal_rows)
    
    @rx.var
    def total_all_tenders(self) -> int:
        """Total tenders across all portals."""
        return sum(p.total_tenders for p in self.portal_rows)
    
    @rx.var
    def total_live_tenders(self) -> int:
        """Total live tenders across all portals."""
        return sum(p.live_tenders for p in self.portal_rows)
    
    @rx.var
    def total_expired_tenders(self) -> int:
        """Total expired tenders across all portals."""
        return sum(p.expired_tenders for p in self.portal_rows)
    
    @rx.var
    def selected_count(self) -> int:
        """Number of selected portals."""
        return len(self.export_selected_portals)
    
    def is_portal_selected(self, portal_slug: str) -> bool:
        """Check if a portal is selected."""
        return portal_slug in self.export_selected_portals
    
    def load_portal_statistics(self):
        """Load portal statistics from database."""
        self.loading = True
        yield
        
        try:
            # Get portal stats
            portal_stats = db.get_portal_statistics(self.days_filter)
            
            # Convert to PortalRow objects
            all_rows = [
                PortalRow(
                    portal_slug=p["portal_slug"],
                    portal_name=p["portal_name"],
                    base_url=p["base_url"],
                    last_updated=p["last_updated"],
                    total_tenders=p["total_tenders"],
                    live_tenders=p["live_tenders"],
                    expired_tenders=p["expired_tenders"],
                    category=p.get("category", "State"),
                    days_since_update=p.get("days_since_update", -1),
                )
                for p in portal_stats
            ]
            
            # Apply category filter
            if self.category_filter and self.category_filter != "All":
                self.portal_rows = [p for p in all_rows if p.category == self.category_filter]
            else:
                self.portal_rows = all_rows
            
            # Apply sorting
            self._apply_sort()
            
        except Exception as ex:
            self.show_toast_notification(f"Error loading portal data: {ex}", "error")
        finally:
            self.loading = False
            yield
    
    def _apply_sort(self):
        """Sort portal rows based on current sort settings."""
        reverse = self.sort_order == "desc"
        
        if self.sort_by == "portal_name":
            self.portal_rows.sort(key=lambda p: p.portal_name.lower(), reverse=reverse)
        elif self.sort_by == "total_tenders":
            self.portal_rows.sort(key=lambda p: p.total_tenders, reverse=reverse)
        elif self.sort_by == "live_tenders":
            self.portal_rows.sort(key=lambda p: p.live_tenders, reverse=reverse)
        elif self.sort_by == "last_updated":
            self.portal_rows.sort(key=lambda p: p.last_updated or "", reverse=reverse)
    
    def set_days_filter(self, value: str):
        """Set days filter for portals."""
        try:
            self.days_filter = int(value)
            self.load_portal_statistics()
        except ValueError:
            self.days_filter = 0
    
    def set_sort_by(self, value: str):
        """Set sort column."""
        self.sort_by = value
        self._apply_sort()
    
    def set_sort_order(self, value: str):
        """Set sort order."""
        self.sort_order = value
        self._apply_sort()
    
    def toggle_export_dialog(self):
        """Toggle export settings dialog."""
        self.show_export_dialog = not self.show_export_dialog
    
    def set_export_days_filter(self, value: str):
        """Set export days filter."""
        try:
            self.export_days_filter = int(value)
        except ValueError:
            self.export_days_filter = 0

    def set_export_base_dir(self, value: str):
        """Set base directory where export files are written."""
        try:
            self.export_base_dir = str(value).strip() or "Portal_Exports"
        except Exception:
            self.export_base_dir = "Portal_Exports"

    def open_export_base_dir(self):
        """Open the export base directory in the OS file explorer (server-side action)."""
        try:
            import os
            import sys
            from pathlib import Path
            import subprocess

            # Prefer opening the exact last export path when available
            if self.last_export_path:
                target = Path(self.last_export_path)
                if target.exists():
                    # If target is a file, open its containing folder and select if possible
                    if target.is_file():
                        folder = target.parent
                        path_to_open = str(folder.resolve())
                        if os.name == "nt":
                            # Windows: explorer /select,<file>
                            subprocess.Popen(["explorer", "/select,", str(target.resolve())])
                        else:
                            # macOS/Linux: open folder
                            if sys.platform == "darwin":
                                subprocess.Popen(["open", path_to_open])
                            else:
                                subprocess.Popen(["xdg-open", path_to_open])
                        self.show_toast_notification(f"Opened export file location: {path_to_open}", "success")
                        return
                    else:
                        path_to_open = str(target.resolve())
                        if os.name == "nt":
                            os.startfile(path_to_open)
                        else:
                            if sys.platform == "darwin":
                                subprocess.Popen(["open", path_to_open])
                            else:
                                subprocess.Popen(["xdg-open", path_to_open])
                        self.show_toast_notification(f"Opened export folder: {path_to_open}", "success")
                        return

            # Fallback to base export folder
            base = Path(self.export_base_dir)
            if not base.exists():
                base.mkdir(parents=True, exist_ok=True)

            path_to_open = str(base.resolve())
            if os.name == "nt":
                os.startfile(path_to_open)
            else:
                if sys.platform == "darwin":
                    subprocess.Popen(["open", path_to_open])
                else:
                    subprocess.Popen(["xdg-open", path_to_open])

            self.show_toast_notification(f"Opened folder: {path_to_open}", "success")
        except Exception as ex:
            self.show_toast_notification(f"Failed to open folder: {ex}", "error")

    def toggle_sort_order(self):
        """Toggle sort order between asc and desc and re-apply sort."""
        try:
            self.sort_order = "desc" if self.sort_order == "asc" else "asc"
            # Apply sorting immediately
            self._apply_sort()
        except Exception:
            pass
    
    def set_export_expired_days(self, value: str):
        """Set expired days for export."""
        try:
            self.export_expired_days = int(value)
        except ValueError:
            self.export_expired_days = 30
    
    def toggle_export_live_only(self):
        """Toggle live only export."""
        self.export_live_only = not self.export_live_only
    
    def toggle_portal_selection(self, portal_slug: str):
        """Toggle portal selection for export."""
        if portal_slug in self.export_selected_portals:
            self.export_selected_portals.remove(portal_slug)
        else:
            self.export_selected_portals.append(portal_slug)
    
    def select_all_portals(self):
        """Select all visible portals."""
        self.export_selected_portals = [p.portal_slug for p in self.portal_rows]
    
    def deselect_all_portals(self):
        """Deselect all portals."""
        self.export_selected_portals = []
    
    async def export_selected_portals_to_excel(self):
        """Export selected portals to individual Excel files."""
        self.exporting = True
        yield
        
        try:
            import pandas as pd
            
            if not self.export_selected_portals:
                self.show_toast_notification("Please select at least one portal to export", "error")
                self.exporting = False
                yield
                return
            
            # Create export directory
            export_dir = Path("Portal_Exports") / datetime.now().strftime("%Y%m%d_%H%M%S")
            export_dir.mkdir(parents=True, exist_ok=True)
            
            exported_files = []
            total_tenders = 0
            
            # Export each selected portal
            for portal_slug in self.export_selected_portals:
                # Find portal data
                portal = next((p for p in self.portal_rows if p.portal_slug == portal_slug), None)
                if not portal:
                    continue
                
                # Get tender data
                tenders = db.export_portal_data(
                    portal_slug=portal.portal_slug,
                    portal_name=portal.portal_name,
                    base_url=portal.base_url,
                    expired_days=self.export_expired_days,
                    live_only=self.export_live_only
                )
                
                if not tenders:
                    continue
                
                # Create filename from base_url
                filename_base = db.portal_url_to_filename(portal.base_url, portal.portal_name)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{filename_base}_tenders_{timestamp}.xlsx"
                
                # Create DataFrame
                df = pd.DataFrame(tenders)
                
                # Column order
                column_order = [
                    "Department Name",
                    "S.No",
                    "e-Published Date",
                    "Closing Date",
                    "Opening Date",
                    "Organisation Chain",
                    "Title and Ref.No./Tender ID",
                    "Tender ID (Extracted)",
                    "Direct URL",
                    "Status URL"
                ]
                df = df[column_order]
                
                # Export to Excel
                filepath = export_dir / filename
                df.to_excel(filepath, index=False, engine='openpyxl')
                
                exported_files.append(filename)
                total_tenders += len(tenders)
            
            # Log export history
            portal_names = [p.portal_name for p in self.portal_rows if p.portal_slug in self.export_selected_portals]
            db.log_export_history(
                export_type="selected_portals",
                portals=portal_names,
                total_tenders=total_tenders,
                file_count=len(exported_files),
                export_dir=export_dir.name,
                settings={
                    "live_only": self.export_live_only,
                    "expired_days": self.export_expired_days,
                }
            )
            
            # Success message
            message = f"✅ Exported {len(exported_files)} portal(s) with {total_tenders} tenders to {export_dir.name}"
            self.show_toast_notification(message, "success")
            
        except Exception as ex:
            error_msg = f"Export failed: {type(ex).__name__}: {ex}"
            self.show_toast_notification(error_msg, "error")
        
        finally:
            self.exporting = False
            self.show_export_dialog = False
            yield

    async def export_selected_portals_single_excel(self):
        """Export selected portals into a single Excel workbook (one sheet per portal + combined sheet)."""
        self.exporting = True
        yield

        try:
            import pandas as pd

            if not self.export_selected_portals:
                self.show_toast_notification("Please select at least one portal to export", "error")
                self.exporting = False
                yield
                return

            # Create export directory
            export_dir = Path("Portal_Exports") / datetime.now().strftime("%Y%m%d_%H%M%S")
            export_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"portals_selected_tenders_{timestamp}.xlsx"
            filepath = export_dir / filename

            # Create ExcelWriter and write each portal to its own sheet
            column_order = [
                "Department Name",
                "S.No",
                "e-Published Date",
                "Closing Date",
                "Opening Date",
                "Organisation Chain",
                "Title and Ref.No./Tender ID",
                "Tender ID (Extracted)",
                "Direct URL",
                "Status URL",
            ]

            with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
                combined_rows = []

                for portal_slug in self.export_selected_portals:
                    portal = next((p for p in self.portal_rows if p.portal_slug == portal_slug), None)
                    if not portal:
                        continue

                    tenders = db.export_portal_data(
                        portal_slug=portal.portal_slug,
                        portal_name=portal.portal_name,
                        base_url=portal.base_url,
                        expired_days=self.export_expired_days,
                        live_only=self.export_live_only,
                    )

                    if not tenders:
                        continue

                    df = pd.DataFrame(tenders)
                    # Ensure expected columns exist
                    column_order = [
                        "Department Name",
                        "S.No",
                        "e-Published Date",
                        "Closing Date",
                        "Opening Date",
                        "Organisation Chain",
                        "Title and Ref.No./Tender ID",
                        "Tender ID (Extracted)",
                        "Direct URL",
                        "Status URL",
                    ]
                    # Reindex to keep columns present; missing columns will be filled with NaN
                    df = df.reindex(columns=column_order)

                    sheet_name = portal.portal_slug[:31] if portal.portal_slug else portal.portal_name[:31]
                    # Avoid empty sheet name
                    if not sheet_name:
                        sheet_name = f"portal_{portal_slug}"

                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    combined_rows.extend(tenders)

                # Write combined sheet
                if combined_rows:
                    combined_df = pd.DataFrame(combined_rows)
                    combined_df = combined_df.reindex(columns=column_order)
                    combined_df.to_excel(writer, sheet_name="All_Portals", index=False)

            # Log export history and record full path
            portal_names = [p.portal_name for p in self.portal_rows if p.portal_slug in self.export_selected_portals]
            full_path = str(filepath.resolve())
            self.last_export_path = full_path
            db.log_export_history(
                export_type="selected_portals_single_file",
                portals=portal_names,
                total_tenders=len(combined_rows),
                file_count=1,
                export_dir=export_dir.name,
                settings={
                    "live_only": self.export_live_only,
                    "expired_days": self.export_expired_days,
                    "export_path": full_path,
                }
            )

            message = f"✅ Exported {len(portal_names)} portal(s) into single file: {filename}"
            self.show_toast_notification(message, "success")

        except Exception as ex:
            error_msg = f"Export failed: {type(ex).__name__}: {ex}"
            self.show_toast_notification(error_msg, "error")

        finally:
            self.exporting = False
            self.show_export_dialog = False
            yield

    async def export_all_portals_single_excel(self):
        """Export all visible portals into a single Excel workbook (one sheet per portal + combined sheet)."""
        self.exporting = True
        yield

        try:
            import pandas as pd

            portals_to_export = self.portal_rows
            if not portals_to_export:
                self.show_toast_notification("No portals available for export", "error")
                self.exporting = False
                yield
                return

            # Create export directory
            export_dir = Path("Portal_Exports") / datetime.now().strftime("%Y%m%d_%H%M%S")
            export_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"portals_all_tenders_{timestamp}.xlsx"
            filepath = export_dir / filename

            column_order = [
                "Department Name",
                "S.No",
                "e-Published Date",
                "Closing Date",
                "Opening Date",
                "Organisation Chain",
                "Title and Ref.No./Tender ID",
                "Tender ID (Extracted)",
                "Direct URL",
                "Status URL",
            ]

            with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
                combined_rows = []

                for portal in portals_to_export:
                    tenders = db.export_portal_data(
                        portal_slug=portal.portal_slug,
                        portal_name=portal.portal_name,
                        base_url=portal.base_url,
                        expired_days=self.export_expired_days,
                        live_only=self.export_live_only,
                    )

                    if not tenders:
                        continue

                    df = pd.DataFrame(tenders)
                    column_order = [
                        "Department Name",
                        "S.No",
                        "e-Published Date",
                        "Closing Date",
                        "Opening Date",
                        "Organisation Chain",
                        "Title and Ref.No./Tender ID",
                        "Tender ID (Extracted)",
                        "Direct URL",
                        "Status URL",
                    ]
                    df = df.reindex(columns=column_order)

                    sheet_name = portal.portal_slug[:31] if portal.portal_slug else portal.portal_name[:31]
                    if not sheet_name:
                        sheet_name = f"portal_{portal.portal_slug}"

                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    combined_rows.extend(tenders)

                if combined_rows:
                    combined_df = pd.DataFrame(combined_rows)
                    combined_df = combined_df.reindex(columns=column_order)
                    combined_df.to_excel(writer, sheet_name="All_Portals", index=False)

            portal_names = [p.portal_name for p in portals_to_export]
            full_path = str(filepath.resolve())
            self.last_export_path = full_path
            db.log_export_history(
                export_type="all_portals_single_file",
                portals=portal_names,
                total_tenders=len(combined_rows),
                file_count=1,
                export_dir=export_dir.name,
                settings={
                    "live_only": self.export_live_only,
                    "expired_days": self.export_expired_days,
                    "export_path": full_path,
                }
            )

            message = f"✅ Exported all portals into single file: {filename}"
            self.show_toast_notification(message, "success")

        except Exception as ex:
            error_msg = f"Export failed: {type(ex).__name__}: {ex}"
            self.show_toast_notification(error_msg, "error")

        finally:
            self.exporting = False
            yield
    
    def show_toast_notification(self, message: str, toast_type: str = "info"):
        """Show toast notification."""
        self.toast_message = message
        self.toast_type = toast_type
        self.show_toast = True
    
    def hide_toast(self):
        """Hide toast notification."""
        self.show_toast = False
    
    def set_category_filter(self, value: str):
        """Set category filter and reload data."""
        self.category_filter = value
        self.load_portal_statistics()
    
    async def export_category_portals(self, category: str):
        """Export all portals in a category."""
        self.exporting = True
        yield
        
        try:
            import pandas as pd
            
            # Get all portals in this category
            category_portals = [p for p in self.portal_rows if p.category == category]
            
            if not category_portals:
                self.show_toast_notification(f"No portals found in {category} category", "error")
                self.exporting = False
                yield
                return
            
            # Create export directory
            export_dir = Path("Portal_Exports") / datetime.now().strftime("%Y%m%d_%H%M%S")
            export_dir.mkdir(parents=True, exist_ok=True)
            
            exported_files = []
            total_tenders = 0
            
            # Export each portal in category
            for portal in category_portals:
                # Get tender data
                tenders = db.export_portal_data(
                    portal_slug=portal.portal_slug,
                    portal_name=portal.portal_name,
                    base_url=portal.base_url,
                    expired_days=self.export_expired_days,
                    live_only=self.export_live_only
                )
                
                if not tenders:
                    continue
                
                # Create filename from base_url
                filename_base = db.portal_url_to_filename(portal.base_url, portal.portal_name)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{filename_base}_tenders_{timestamp}.xlsx"
                
                # Create DataFrame
                df = pd.DataFrame(tenders)
                
                # Column order
                column_order = [
                    "Department Name",
                    "S.No",
                    "e-Published Date",
                    "Closing Date",
                    "Opening Date",
                    "Organisation Chain",
                    "Title and Ref.No./Tender ID",
                    "Tender ID (Extracted)",
                    "Direct URL",
                    "Status URL"
                ]
                df = df[column_order]
                
                # Export to Excel
                filepath = export_dir / filename
                df.to_excel(filepath, index=False, engine='openpyxl')
                
                exported_files.append(filename)
                total_tenders += len(tenders)
            
            # Log export history
            portal_names = [p.portal_name for p in category_portals]
            db.log_export_history(
                export_type=f"category_{category.lower()}",
                portals=portal_names,
                total_tenders=total_tenders,
                file_count=len(exported_files),
                export_dir=export_dir.name,
                settings={
                    "live_only": self.export_live_only,
                    "expired_days": self.export_expired_days,
                    "category": category,
                }
            )
            
            # Success message
            message = f"✅ Exported {category} category: {len(exported_files)} portal(s) with {total_tenders} tenders"
            self.show_toast_notification(message, "success")
            
        except Exception as ex:
            error_msg = f"Category export failed: {type(ex).__name__}: {ex}"
            self.show_toast_notification(error_msg, "error")
        
        finally:
            self.exporting = False
            yield
    
    def load_export_history(self):
        """Load export history."""
        try:
            history_data = db.get_export_history(limit=20)
            self.export_history = [
                ExportHistoryEntry(
                    timestamp=entry.get("timestamp", ""),
                    export_type=entry.get("export_type", ""),
                    portals=entry.get("portals", []),
                    total_tenders=entry.get("total_tenders", 0),
                    file_count=entry.get("file_count", 0),
                    export_dir=entry.get("export_dir", ""),
                    settings=entry.get("settings", {}),
                )
                for entry in history_data
            ]
            self.show_export_history = True
        except Exception as ex:
            self.show_toast_notification(f"Failed to load export history: {ex}", "error")
    
    def close_export_history(self):
        """Close export history dialog."""
        self.show_export_history = False
    
    def navigate_to_dashboard_with_portal(self, portal_slug: str):
        """Navigate to main dashboard with portal pre-selected."""
        return rx.redirect("/")


class DataVisualizationState(rx.State):
    """State for Data Visualization page."""
    loading: bool = False
    data_rows: list[DataRow] = []
    
    # Pagination
    page: int = 1
    per_page: int = 50
    total_records: int = 0
    
    # Filters
    selected_portal: str = "All"
    lifecycle_filter: str = "All"  # All, Live, Expired
    portal_options: list[str] = ["All"]
    
    # Database statistics (for schema tab)
    db_total_records: int = 0
    db_active_records: int = 0
    db_portal_count: int = 0
    
    @rx.var
    def total_pages(self) -> int:
        """Calculate total pages."""
        if self.total_records == 0:
            return 1
        return (self.total_records + self.per_page - 1) // self.per_page
    
    @rx.var
    def showing_from(self) -> int:
        """Calculate first record number on current page."""
        return (self.page - 1) * self.per_page + 1
    
    @rx.var
    def showing_to(self) -> int:
        """Calculate last record number on current page."""
        end = self.page * self.per_page
        return min(end, self.total_records)
    
    def load_data(self):
        """Load tender data with filters and pagination."""
        self.loading = True
        yield
        
        try:
            # Build filters
            filters = db.TenderFilters(
                portal=self.selected_portal,
                show_live_only=self.lifecycle_filter == "Live",
                show_expired_only=self.lifecycle_filter == "Expired",
            )
            
            # Get total count
            self.total_records = db.get_tender_count(filters)
            
            # Get paginated data
            offset = (self.page - 1) * self.per_page
            rows_data = db.get_tender_data_paginated(filters, limit=self.per_page, offset=offset)
            
            # Convert to DataRow objects
            self.data_rows = [
                DataRow(
                    row_num=offset + idx + 1,
                    portal_name=row.get("portal_name", ""),
                    tender_id_extracted=row.get("tender_id_extracted", ""),
                    title_ref=row.get("title_ref", ""),
                    department_name=row.get("department_name", ""),
                    published_date=row.get("published_date", ""),
                    closing_date=row.get("closing_date", ""),
                    estimated_cost=row.get("estimated_cost", ""),
                    tender_status=row.get("tender_status", ""),
                    state_name=row.get("state_name", ""),
                    district=row.get("district", ""),
                    city=row.get("city", ""),
                    direct_url=row.get("direct_url", ""),
                )
                for idx, row in enumerate(rows_data)
            ]
            
            # Load portal options
            self.portal_options = ["All", *db.get_portal_options()]
            
            # Load database statistics for schema tab
            self.load_db_statistics()
            
        except Exception as ex:
            print(f"Error loading data: {ex}")
        finally:
            self.loading = False
            yield
    
    def load_db_statistics(self):
        """Load database statistics for schema visualization."""
        try:
            stats = db.get_database_statistics()
            self.db_total_records = stats.get("total_records", 0)
            self.db_active_records = stats.get("active_records", 0)
            self.db_portal_count = stats.get("portal_count", 0)
        except Exception as ex:
            print(f"Error loading DB statistics: {ex}")
    
    def set_selected_portal(self, value: str):
        """Set selected portal filter."""
        self.selected_portal = value
        self.page = 1  # Reset to first page
        self.load_data()
    
    def set_lifecycle_filter(self, value: str):
        """Set lifecycle filter."""
        self.lifecycle_filter = value
        self.page = 1  # Reset to first page
        self.load_data()
    
    def next_page(self):
        """Go to next page."""
        if self.page < self.total_pages:
            self.page += 1
            self.load_data()
    
    def prev_page(self):
        """Go to previous page."""
        if self.page > 1:
            self.page -= 1
            self.load_data()
    
    def first_page(self):
        """Go to first page."""
        self.page = 1
        self.load_data()
    
    def last_page(self):
        """Go to last page."""
        self.page = self.total_pages
        self.load_data()


class ColumnMapping(BaseModel):
    """Column mapping model for Excel import."""
    db_column: str = ""
    db_display_name: str = ""
    excel_column: str = ""
    is_required: bool = False
    is_mapped: bool = False
    sample_data: str = ""


class ExcelImportState(rx.State):
    """State for Excel/CSV import with smart column matching."""
    
    # File upload
    max_file_size_mb: int = 50  # Maximum file size in MB
    file_uploaded: bool = False
    uploading: bool = False
    file_name: str = ""
    file_rows: int = 0
    file_columns: int = 0
    file_size_text: str = ""
    file_path: str = ""
    
    # Column mapping
    excel_columns: list[str] = []
    column_mappings: list[ColumnMapping] = []
    auto_matched_columns: int = 0
    total_required_columns: int = 10
    all_required_mapped: bool = False
    
    # Import settings
    portal_name: str = ""
    base_url: str = ""
    skip_duplicates: bool = True
    validate_data: bool = True
    
    # Import progress
    importing: bool = False
    import_progress: int = 0
    import_status: str = ""
    import_processed: int = 0
    import_success: int = 0
    import_skipped: int = 0
    import_errors: int = 0
    import_completed: bool = False
    import_duration: str = ""
    error_messages: list[str] = []
    
    @rx.var
    def has_errors(self) -> bool:
        """Check if there are any error messages."""
        return len(self.error_messages) > 0
    
    @rx.var
    def excel_columns_with_unmapped(self) -> list[str]:
        """Get excel columns with '(Not Mapped)' option."""
        return ["(Not Mapped)"] + self.excel_columns
    
    # Setter methods (auto_setters disabled in rxconfig)
    def set_portal_name(self, value: str):
        """Set portal name."""
        self.portal_name = value
    
    def set_base_url(self, value: str):
        """Set base URL."""
        self.base_url = value
    
    def set_skip_duplicates(self, value: bool):
        """Set skip duplicates flag."""
        self.skip_duplicates = value
    
    def set_validate_data(self, value: bool):
        """Set validate data flag."""
        self.validate_data = value
    
    def toggle_skip_duplicates(self, value: bool):
        """Toggle skip duplicates."""
        self.skip_duplicates = value
    
    def toggle_validate_data(self, value: bool):
        """Toggle validate data."""
        self.validate_data = value
    
    # Database columns definition
    _db_columns_config = {
        "tender_id_extracted": {
            "display": "Tender ID (Extracted)",
            "required": True,
            "keywords": ["tender", "id", "extracted", "tender_id", "tenderid"],
        },
        "department_name": {
            "display": "Department Name",
            "required": True,
            "keywords": ["department", "dept", "name", "department_name"],
        },
        "serial_no": {
            "display": "Serial No.",
            "required": True,
            "keywords": ["serial", "no", "s.no", "sno", "number", "s_no"],
        },
        "published_date": {
            "display": "Published Date",
            "required": True,
            "keywords": ["published", "date", "e-published", "epublished", "publish"],
        },
        "closing_date": {
            "display": "Closing Date",
            "required": True,
            "keywords": ["closing", "close", "date", "deadline"],
        },
        "opening_date": {
            "display": "Opening Date",
            "required": False,
            "keywords": ["opening", "open", "date"],
        },
        "organisation_chain": {
            "display": "Organisation Chain",
            "required": False,
            "keywords": ["organisation", "organization", "chain", "org"],
        },
        "title_ref": {
            "display": "Title and Ref.No.",
            "required": True,
            "keywords": ["title", "ref", "reference", "no", "tender_id"],
        },
        "direct_url": {
            "display": "Direct URL",
            "required": True,
            "keywords": ["direct", "url", "link", "tender_url"],
        },
        "status_url": {
            "display": "Status URL",
            "required": False,
            "keywords": ["status", "url", "link"],
        },
        "emd_amount": {
            "display": "EMD Amount",
            "required": False,
            "keywords": ["emd", "amount", "deposit", "earnest"],
        },
    }
    
    async def handle_upload(self, files: list[rx.UploadFile]):
        """Handle file upload and auto-detect columns."""
        self.uploading = True
        yield
        
        try:
            import pandas as pd
            from pathlib import Path
            import os
            
            if not files or len(files) == 0:
                self.error_messages = ["No file uploaded"]
                self.uploading = False
                yield
                return
            
            upload = files[0]
            upload_filename = upload.filename or "upload"
            self.file_name = upload_filename
            
            # Save file temporarily
            upload_dir = Path("temp_uploads")
            upload_dir.mkdir(exist_ok=True)
            upload_path = upload_dir / upload_filename
            
            # Read file content
            file_content = await upload.read()
            upload_path.write_bytes(file_content)
            
            self.file_path = str(upload_path)
            self.file_size_text = self._format_file_size(len(file_content))
            
            # Read Excel/CSV based on extension
            if upload_filename.endswith('.csv'):
                df = pd.read_csv(upload_path)
            else:
                df = pd.read_excel(upload_path)
            
            self.file_rows = len(df)
            self.file_columns = len(df.columns)
            self.excel_columns = list(df.columns)
            
            # Auto-detect and match columns
            self._smart_match_columns(df)
            
            # Auto-detect portal name from filename
            self._auto_detect_portal_name(upload_filename)
            
            self.file_uploaded = True
            
        except Exception as ex:
            self.error_messages = [f"Error uploading file: {str(ex)}"]
            self.file_uploaded = False
        finally:
            self.uploading = False
            yield
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        size: float = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def _smart_match_columns(self, df):
        """Smart column matching algorithm."""
        import re
        
        mappings = []
        matched_count = 0
        
        for db_col, config in self._db_columns_config.items():
            mapping = ColumnMapping(
                db_column=db_col,
                db_display_name=config["display"],
                is_required=config["required"],
                is_mapped=False,
            )
            
            # Try to find matching Excel column
            matched_excel_col = self._find_matching_column(
                self.excel_columns, 
                db_col, 
                config["keywords"]
            )
            
            if matched_excel_col:
                mapping.excel_column = matched_excel_col
                mapping.is_mapped = True
                
                # Get sample data (first non-null value)
                try:
                    sample_values = df[matched_excel_col].dropna().head(1)
                    if len(sample_values) > 0:
                        mapping.sample_data = str(sample_values.iloc[0])[:50]
                except:
                    mapping.sample_data = ""
                
                if config["required"]:
                    matched_count += 1
            
            mappings.append(mapping)
        
        self.column_mappings = mappings
        self.auto_matched_columns = matched_count
        self.all_required_mapped = (matched_count == self.total_required_columns)
    
    def _find_matching_column(self, excel_cols: list[str], db_col: str, keywords: list[str]) -> str:  # type: ignore[return]
        """Find matching Excel column using smart matching."""
        import re
        
        def normalize(s: str) -> str:
            """Normalize string for matching."""
            return re.sub(r'[^a-z0-9]', '', s.lower())
        
        db_normalized = normalize(db_col)
        
        # Strategy 1: Exact match (case-insensitive)
        for excel_col in excel_cols:
            if excel_col.lower() == db_col.lower():
                return excel_col
        
        # Strategy 2: Normalized exact match
        for excel_col in excel_cols:
            if normalize(excel_col) == db_normalized:
                return excel_col
        
        # Strategy 3: Keyword matching
        for excel_col in excel_cols:
            excel_normalized = normalize(excel_col)
            # Check if all keywords in DB column appear in Excel column
            for keyword in keywords:
                keyword_normalized = normalize(keyword)
                if keyword_normalized in excel_normalized:
                    # Additional check: multiple keywords match
                    match_count = sum(1 for kw in keywords if normalize(kw) in excel_normalized)
                    if match_count >= 2:  # At least 2 keywords match
                        return excel_col
        
        # Strategy 4: Any keyword match (single keyword)
        best_match = None
        best_score = 0
        
        for excel_col in excel_cols:
            excel_normalized = normalize(excel_col)
            score = sum(1 for kw in keywords if normalize(kw) in excel_normalized)
            if score > best_score:
                best_score = score
                best_match = excel_col
        
        if best_score > 0:
            return best_match or ""
        
        return ""
    
    def _auto_detect_portal_name(self, filename: str):
        """Auto-detect portal name from filename."""
        import re
        
        # Remove extension
        name = filename.rsplit('.', 1)[0]
        
        # Common portal patterns
        patterns = {
            r'hptenders': 'hptenders.gov.in',
            r'eprocure': 'eprocure',
            r'etenders': 'etenders',
            r'cppp': 'eprocure.gov.in',
            r'ddtenders': 'ddtenders.gov.in',
            r'tender': 'custom',
        }
        
        for pattern, portal in patterns.items():
            if re.search(pattern, name.lower()):
                self.portal_name = portal
                # Set base URL based on portal
                if 'hptenders' in name.lower():
                    self.base_url = 'https://hptenders.gov.in'
                elif 'cppp' in name.lower() or 'eprocure.gov' in name.lower():
                    self.base_url = 'https://eprocure.gov.in'
                return
        
        # Default
        self.portal_name = "imported"
        self.base_url = ""
    
    def update_column_mapping(self, db_column: str, excel_column: str):
        """Update column mapping manually."""
        for mapping in self.column_mappings:
            if mapping.db_column == db_column:
                mapping.excel_column = excel_column
                mapping.is_mapped = (excel_column != "" and excel_column != "(Not Mapped)")
                break
        
        # Recalculate match status
        matched = sum(1 for m in self.column_mappings if m.is_mapped and m.is_required)
        self.auto_matched_columns = matched
        self.all_required_mapped = (matched == self.total_required_columns)
    
    async def start_import(self):
        """Start importing data to database."""
        self.importing = True
        self.import_progress = 0
        self.import_status = "Starting import..."
        self.import_processed = 0
        self.import_success = 0
        self.import_skipped = 0
        self.import_errors = 0
        self.error_messages = []
        yield
        
        try:
            import pandas as pd
            from datetime import datetime
            import sys
            import os
            
            # Add parent directory to path to import tender_store
            workspace_root = Path(__file__).parent.parent.parent
            sys.path.insert(0, str(workspace_root))
            
            from tender_store import TenderDataStore
            
            # Read the uploaded file
            self.import_status = "Reading file..."
            yield
            
            if self.file_path.endswith('.csv'):
                df = pd.read_csv(self.file_path)
            else:
                df = pd.read_excel(self.file_path)
            
            # Create mapping dict: excel_column -> db_column
            excel_to_db = {}
            for mapping in self.column_mappings:
                if mapping.is_mapped and mapping.excel_column:
                    excel_to_db[mapping.excel_column] = mapping.db_column
            
            # Initialize database
            db_path = workspace_root / "database" / "blackforest_tenders.sqlite3"
            store = TenderDataStore(str(db_path))
            
            # Get or create run_id
            run_id = store.start_run(
                portal_name=self.portal_name or "imported",
                base_url=self.base_url or "",
            )
            
            # Convert DataFrame to tender list
            tenders = []
            start_time = datetime.now()
            total_rows = len(df)
            
            for idx, row in df.iterrows():
                row_num = int(idx) + 1  # type: ignore[arg-type]
                self.import_processed = row_num
                self.import_progress = int(row_num / total_rows * 90)  # Reserve 10% for DB write
                self.import_status = f"Processing row {row_num}/{total_rows}..."
                
                if row_num % 10 == 0:  # Update UI every 10 rows
                    yield
                
                try:
                    tender = {"portal_name": self.portal_name or "imported"}
                    
                    # Map columns
                    for excel_col, db_col in excel_to_db.items():
                        value = row.get(excel_col, "")
                        # Convert to string, handle NaN
                        if pd.isna(value):
                            value = ""
                        else:
                            value = str(value).strip()
                        tender[db_col] = value
                    
                    # Validate required fields if enabled
                    if self.validate_data:
                        if not tender.get("tender_id_extracted"):
                            self.import_errors += 1
                            self.error_messages.append(f"Row {row_num}: Missing tender ID")
                            continue
                    
                    tenders.append(tender)
                    
                except Exception as ex:
                    self.import_errors += 1
                    self.error_messages.append(f"Row {row_num}: {str(ex)}")
            
            # Import to database
            self.import_status = "Importing to database..."
            self.import_progress = 95
            yield
            
            result = store.replace_run_tenders(run_id, tenders)
            
            self.import_success = int(result)
            self.import_skipped = 0
            
            # Calculate duration
            end_time = datetime.now()
            duration = end_time - start_time
            minutes = int(duration.total_seconds() // 60)
            seconds = int(duration.total_seconds() % 60)
            self.import_duration = f"{minutes} minute{'s' if minutes != 1 else ''} {seconds} second{'s' if seconds != 1 else ''}"
            
            self.import_progress = 100
            self.import_status = f"Import completed! {self.import_success} tenders imported successfully."
            self.import_completed = True
            
        except Exception as ex:
            self.error_messages.append(f"Import failed: {str(ex)}")
            self.import_status = f"Import failed: {str(ex)}"
            import traceback
            print(f"Import error: {traceback.format_exc()}")
        finally:
            self.importing = False
            yield
    
    def clear_upload(self):
        """Clear upload and reset state."""
        import os
        from pathlib import Path
        
        # Delete temp file
        if self.file_path and os.path.exists(self.file_path):
            try:
                os.remove(self.file_path)
            except:
                pass
        
        # Reset state
        self.file_uploaded = False
        self.file_name = ""
        self.file_rows = 0
        self.file_columns = 0
        self.file_size_text = ""
        self.file_path = ""
        self.excel_columns = []
        self.column_mappings = []
        self.auto_matched_columns = 0
        self.all_required_mapped = False
        self.portal_name = ""
        self.base_url = ""
        self.importing = False
        self.import_progress = 0
        self.import_status = ""
        self.import_processed = 0
        self.import_success = 0
        self.import_skipped = 0
        self.import_errors = 0
        self.import_completed = False
        self.import_duration = ""
        self.error_messages = []
