from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel
from typing import Any
import os
from pathlib import Path

import reflex as rx

from tender_dashboard_reflex import db


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
                tender_id_extracted=str(item.get("tender_id_extracted") or "-"),
                title_ref=str(item.get("title_ref") or "-"),
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
            amount = float(value)
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
        # Set the portal filter in DashboardState
        dashboard_state = self.get_state(DashboardState)
        dashboard_state.portal_filter = portal_slug
        # Navigate will be handled by rx.link in UI
        return rx.redirect("/")