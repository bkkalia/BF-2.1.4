from __future__ import annotations

import reflex as rx

from tender_dashboard_reflex.state import DashboardState, TenderRow
from dashboard_app.portal_management import portal_management_page


def stat_card(title: str, value: rx.Var | str, accent: str, on_click=None) -> rx.Component:
    """KPI card with gradient background. Optionally clickable."""
    base_props = {
        "padding": "1rem",
        "border_radius": "12px",
        "background": accent,
        "box_shadow": "lg",
        "width": "100%",
        "min_height": "85px",
    }
    
    if on_click:
        return rx.box(
            rx.text(title, size="2", color="white", weight="medium"),
            rx.heading(value, size="6", color="white", weight="bold"),
            on_click=on_click,
            cursor="pointer",
            _hover={"transform": "scale(1.02)", "box_shadow": "xl", "transition": "all 0.2s"},
            **base_props,
        )
    else:
        return rx.box(
            rx.text(title, size="2", color="white", weight="medium"),
            rx.heading(value, size="6", color="white", weight="bold"),
            **base_props,
        )


def google_search_bar() -> rx.Component:
    """Google-style search bar at top of page."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.input(
                    value=DashboardState.search_query,
                    on_change=DashboardState.set_search_query,
                    placeholder="🔍 Search tenders by title, department, tender ID, organization... (comma-separated terms)",
                    width="100%",
                    size="3",
                    on_blur=DashboardState.apply_filters,  # Auto-apply on blur
                ),
                rx.button("Search", on_click=DashboardState.apply_filters, color_scheme="blue", size="3", width="120px"),
                width="100%",
                spacing="2",
            ),
            rx.hstack(
                rx.text("Search Logic:", size="2", weight="medium", color="gray.11"),
                rx.radio(
                    ["OR", "AND"],
                    value=DashboardState.search_logic,
                    on_change=DashboardState.set_search_logic,
                    direction="row",
                    size="2",
                    spacing="3",
                ),
                rx.divider(orientation="vertical", height="20px"),
                rx.text("Department Filter:", size="2", weight="medium", color="gray.11"),
                rx.input(
                    value=DashboardState.department_filter,
                    on_change=DashboardState.set_department_filter,
                    placeholder="dept1, dept2...",
                    size="2",
                    width="250px",
                ),
                rx.radio(
                    ["OR", "AND"],
                    value=DashboardState.department_logic,
                    on_change=DashboardState.set_department_logic,
                    direction="row",
                    size="2",
                    spacing="3",
                ),
                rx.divider(orientation="vertical", height="20px"),
                rx.text("Lifecycle:", size="2", weight="medium", color="gray.11"),
                rx.radio(
                    ["All", "Live", "Expired"],
                    value=DashboardState.lifecycle_filter,
                    on_change=DashboardState.set_lifecycle_filter,
                    direction="row",
                    size="2",
                    spacing="3",
                ),
                width="100%",
                align="center",
                wrap="wrap",
                spacing="3",
            ),
            align="start",
            spacing="2",
            width="100%",
        ),
        padding="1.2rem",
        border_radius="12px",
        background="linear-gradient(135deg, #ffffff 0%, #f8fafc 100%)",
        border="2px solid",
        border_color="blue.4",
        box_shadow="xl",
        width="100%",
    )


def filter_input(label: str, placeholder: str, value: rx.Var, on_change, input_type: str = "text") -> rx.Component:
    return rx.vstack(
        rx.text(label, size="2", weight="medium", color="gray.11"),
        rx.input(value=value, on_change=on_change, placeholder=placeholder, type=input_type, width="100%", size="2"),
        align="start", width="100%", spacing="1",
    )


def filter_select(label: str, options: list[str] | rx.Var, value: rx.Var, on_change) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="2", weight="medium", color="gray.11"),
        rx.select(options, value=value, on_change=on_change, width="100%", size="2"),
        align="start", width="100%", spacing="1",
    )


def sidebar_filters() -> rx.Component:
    """Stacked vertical filters in sidebar."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.heading("Advanced Filters", size="6", color="gray.12"),
                rx.spacer(),
                rx.icon_button(rx.icon("settings"), on_click=DashboardState.toggle_settings, variant="ghost", size="2"),
                width="100%", align="center",
            ),
            rx.divider(),
            filter_select("Portal Group", DashboardState.portal_group_options, DashboardState.selected_portal_group, DashboardState.set_selected_portal_group),
            filter_select("Individual Portal", DashboardState.portal_options, DashboardState.selected_portal, DashboardState.set_selected_portal),
            rx.divider(),
            filter_select("Status", DashboardState.status_options, DashboardState.selected_status, DashboardState.set_selected_status),
            filter_input("From Date", "yyyy-mm-dd", DashboardState.from_date, DashboardState.set_from_date, input_type="date"),
            filter_input("To Date", "yyyy-mm-dd", DashboardState.to_date, DashboardState.set_to_date, input_type="date"),
            filter_select("State", DashboardState.state_options, DashboardState.selected_state, DashboardState.on_state_change),
            filter_select("District", DashboardState.district_options, DashboardState.selected_district, DashboardState.on_district_change),
            filter_select("City", DashboardState.city_options, DashboardState.selected_city, DashboardState.set_selected_city),
            filter_select("Tender Type", DashboardState.tender_type_options, DashboardState.selected_tender_type, DashboardState.set_selected_tender_type),
            filter_select("Work Type", DashboardState.work_type_options, DashboardState.selected_work_type, DashboardState.set_selected_work_type),
            filter_input("Min Amount", "100000", DashboardState.min_amount, DashboardState.set_min_amount),
            filter_input("Max Amount", "5000000", DashboardState.max_amount, DashboardState.set_max_amount),
            filter_select("Sort By", DashboardState.sort_options, DashboardState.selected_sort, DashboardState.set_selected_sort),
            filter_select("Sort Order", ["desc", "asc"], DashboardState.selected_sort_order, DashboardState.set_selected_sort_order),
            filter_select("Page Size", ["25", "50", "100", "200"], str(DashboardState.page_size), DashboardState.set_page_size_value),
            rx.divider(),
            rx.button("Reset All Filters", on_click=DashboardState.reset_filters, variant="outline", size="2", width="100%"),
            align="start", spacing="3", width="100%",
        ),
        padding="1.2rem", border_radius="12px", background="linear-gradient(135deg, #fefefe 0%, #f9fafb 100%)",
        border="1px solid", border_color="gray.6", height="100%", overflow_y="auto", max_height="calc(100vh - 120px)",
    )


def tender_card(row: TenderRow) -> rx.Component:
    """Card view for tender with prominent Tender ID and copy button."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.badge(row.portal_name, color_scheme="violet", size="2"),
                rx.badge(row.tender_status, color_scheme="green", size="2"),
                rx.spacer(),
                rx.text(f"Closing: {row.closing_at}", size="2", weight="bold", color="red.11"),
                width="100%", wrap="wrap", align="center",
            ),
            rx.divider(),
            # Prominent Tender ID with copy button
            rx.hstack(
                rx.vstack(
                    rx.text("Tender ID", size="1", color="gray.10", weight="medium"),
                    rx.text(row.tender_id_extracted, size="3", weight="bold", color="blue.11", font_family="monospace"),
                    align="start", spacing="0",
                ),
                rx.spacer(),
                rx.tooltip(
                    rx.icon_button(
                        rx.icon("copy"),
                        size="2",
                        variant="soft",
                        color_scheme="blue",
                        on_click=rx.set_clipboard(row.tender_id_extracted),
                    ),
                    content="Copy Tender ID",
                ),
                width="100%", align="center",
            ),
            rx.divider(),
            rx.text(row.title_ref, size="3", weight="bold", color="gray.12", line_height="1.5"),
            rx.hstack(
                rx.text("📋", size="2"),
                rx.text(row.department_name, size="2", color="gray.11", weight="medium"),
                width="100%",
            ),
            rx.hstack(
                rx.text(f"Published: {row.published_at}", size="2", color="gray.10"),
                rx.spacer(),
                rx.text(f"Cost: {row.estimated_cost_value}", size="2", color="green.10", weight="bold"),
                width="100%",
            ),
            rx.hstack(
                rx.cond(row.state_name != "-", rx.text(f"📍 {row.state_name}", size="2"), rx.box()),
                rx.cond(row.district != "-", rx.text(f"• {row.district}", size="2"), rx.box()),
                rx.cond(row.city != "-", rx.text(f"• {row.city}", size="2"), rx.box()),
                width="100%",
            ),
            rx.hstack(
                rx.cond(
                    row.tender_url != "",
                    rx.link(
                        rx.button(rx.icon("external-link"), "Direct URL", size="2", color_scheme="blue", variant="solid"),
                        href=row.tender_url,
                        is_external=True,
                    ),
                    rx.box(),
                ),
                rx.cond(
                    row.status_url != "",
                    rx.link(
                        rx.button(rx.icon("file-text"), "Status URL", size="2", color_scheme="purple", variant="solid"),
                        href=row.status_url,
                        is_external=True,
                    ),
                    rx.box(),
                ),
                spacing="2", width="100%",
            ),
            align="start", spacing="3", width="100%",
        ),
        border="1px solid", border_color="gray.6", border_radius="12px", padding="1.2rem",
        background="white", _hover={"box_shadow": "xl", "border_color": "blue.6", "transform": "translateY(-2px)", "transition": "all 0.2s"},
        width="100%",
    )


def tender_table() -> rx.Component:
    """Table view for tenders with Tender ID copy button."""
    return rx.box(
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Portal"),
                    rx.table.column_header_cell("Tender ID"),
                    rx.table.column_header_cell("Title"),
                    rx.table.column_header_cell("Department"),
                    rx.table.column_header_cell("Closing"),
                    rx.table.column_header_cell("Cost"),
                    rx.table.column_header_cell("Status"),
                    rx.table.column_header_cell("Actions"),
                ),
            ),
            rx.table.body(
                rx.foreach(
                    DashboardState.rows,
                    lambda row: rx.table.row(
                        rx.table.cell(rx.badge(row.portal_name, size="1", color_scheme="violet")),
                        rx.table.cell(
                            rx.hstack(
                                rx.text(row.tender_id_extracted, size="2", weight="bold", color="blue.11", font_family="monospace"),
                                rx.tooltip(
                                    rx.icon_button(rx.icon("copy"), size="1", variant="ghost", on_click=rx.set_clipboard(row.tender_id_extracted)),
                                    content="Copy",
                                ),
                                spacing="1",
                            )
                        ),
                        rx.table.cell(rx.text(row.title_ref, size="2", max_width="350px", overflow="hidden", text_overflow="ellipsis", white_space="nowrap")),
                        rx.table.cell(rx.text(row.department_name, size="2", max_width="200px", overflow="hidden", text_overflow="ellipsis")),
                        rx.table.cell(rx.text(row.closing_at, size="2", color="red.10", weight="bold")),
                        rx.table.cell(rx.text(row.estimated_cost_value, size="2", color="green.10", weight="medium")),
                        rx.table.cell(rx.badge(row.tender_status, size="1", color_scheme="green")),
                        rx.table.cell(
                            rx.hstack(
                                rx.cond(row.tender_url != "", rx.link(rx.icon_button(rx.icon("external-link"), size="1", variant="soft", color_scheme="blue"), href=row.tender_url, is_external=True), rx.box()),
                                rx.cond(row.status_url != "", rx.link(rx.icon_button(rx.icon("file-text"), size="1", variant="soft", color_scheme="purple"), href=row.status_url, is_external=True), rx.box()),
                                spacing="1",
                            )
                        ),
                    ),
                )
            ),
            variant="surface", width="100%",
        ),
        overflow_x="auto", width="100%",
    )


def settings_panel() -> rx.Component:
    """Settings dialog."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Dashboard Settings"),
            rx.vstack(
                rx.text("View Mode", size="2", weight="medium"),
                rx.radio(["cards", "table"], value=DashboardState.view_mode, on_change=DashboardState.set_view_mode),
                rx.divider(),
                rx.text("Filter Position", size="2", weight="medium"),
                rx.radio(DashboardState.filter_position_options, value=DashboardState.selected_filter_position, on_change=DashboardState.set_selected_filter_position),
                rx.divider(),
                rx.text("About", size="2", weight="medium"),
                rx.text("Tender Dashboard v2.1 - Google-style search, calendar pickers, copy Tender IDs, full-width layout", size="2", color="gray.10"),
                align="start", spacing="3", width="100%",
            ),
            rx.dialog.close(rx.button("Close", size="2", variant="soft")),
        ),
        open=DashboardState.show_settings,
        on_open_change=DashboardState.toggle_settings,
    )


def export_dialog() -> rx.Component:
    """Export options dialog."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("📥 Export Tenders to Excel"),
            rx.vstack(
                rx.text("Export current filtered results to Excel files (one file per portal)", size="2", color="gray.11"),
                rx.divider(),
                rx.vstack(
                    rx.text("Include Expired Tenders", size="2", weight="medium"),
                    rx.hstack(
                        rx.text("Include expired tenders from last", size="2"),
                        rx.input(
                            value=str(DashboardState.export_expired_days),
                            on_change=DashboardState.set_export_expired_days,
                            type="number",
                            width="80px",
                            size="2",
                        ),
                        rx.text("days", size="2"),
                        align="center",
                        spacing="2",
                    ),
                    rx.text("(Set to 0 to exclude expired tenders)", size="1", color="gray.10"),
                    align="start",
                    spacing="2",
                    width="100%",
                ),
                rx.divider(),
                rx.callout(
                    "Columns: Department Name, S.No, e-Published Date, Closing Date, Opening Date, Organisation Chain, Title, Tender ID, Direct URL, Status URL",
                    icon="info",
                    size="1",
                    color_scheme="blue",
                ),
                rx.hstack(
                    rx.dialog.close(rx.button("Cancel", size="2", variant="soft")),
                    rx.button(
                        rx.icon("download"),
                        "Export to Excel",
                        on_click=DashboardState.export_to_excel,
                        color_scheme="green",
                        size="2",
                        loading=DashboardState.exporting,
                    ),
                    justify="end",
                    spacing="2",
                    width="100%",
                ),
                align="start",
                spacing="3",
                width="100%",
            ),
        ),
        open=DashboardState.show_export_dialog,
        on_open_change=DashboardState.toggle_export_dialog,
    )


def public_export_interface() -> rx.Component:
    """Public export interface for website data."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.heading("📤 Public Website Export", size="5", color="gray.12"),
                rx.spacer(),
                rx.icon_button(
                    rx.icon("info"),
                    variant="ghost",
                    size="2",
                ),
                width="100%",
                align="center",
            ),
            rx.text("Export all live tenders + expired tenders from a specific portal for public website", size="2", color="gray.10"),
            rx.divider(),
            filter_select("Select Portal", DashboardState.portal_options, DashboardState.public_export_portal, DashboardState.set_public_export_portal),
            rx.vstack(
                rx.text("Include Expired Days", size="2", weight="medium", color="gray.11"),
                rx.hstack(
                    rx.text("Include tenders expired within last", size="2"),
                    rx.input(
                        value=str(DashboardState.public_export_expired_days),
                        on_change=DashboardState.set_public_export_expired_days,
                        type="number",
                        width="80px",
                        size="2",
                    ),
                    rx.text("days", size="2"),
                    align="center",
                    spacing="2",
                ),
                align="start",
                spacing="1",
                width="100%",
            ),
            rx.button(
                rx.icon("globe"),
                "Generate Public Export",
                on_click=DashboardState.public_export_to_excel,
                color_scheme="violet",
                size="3",
                width="100%",
                loading=DashboardState.public_exporting,
            ),
            align="start",
            spacing="3",
            width="100%",
        ),
        padding="1.2rem",
        border_radius="12px",
        background="linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%)",
        border="2px solid",
        border_color="violet.5",
        box_shadow="lg",
    )


def toast_notification() -> rx.Component:
    """Toast notification component."""
    return rx.cond(
        DashboardState.show_toast,
        rx.box(
            rx.hstack(
                rx.cond(
                    DashboardState.toast_type == "success",
                    rx.icon("check", size=20, color="white"),
                    rx.cond(
                        DashboardState.toast_type == "error",
                        rx.icon("x", size=20, color="white"),
                        rx.icon("info", size=20, color="white"),
                    ),
                ),
                rx.text(DashboardState.toast_message, size="2", weight="medium", color="white"),
                rx.icon_button(
                    rx.icon("x", size=16),
                    on_click=DashboardState.hide_toast,
                    variant="ghost",
                    size="1",
                    color_scheme="gray",
                ),
                align="center",
                spacing="2",
                width="100%",
                justify="between",
            ),
            position="fixed",
            top="20px",
            right="20px",
            padding="1rem 1.5rem",
            border_radius="8px",
            min_width="350px",
            background=rx.cond(
                DashboardState.toast_type == "success",
                "linear-gradient(135deg, #16a34a 0%, #22c55e 100%)",
                rx.cond(
                    DashboardState.toast_type == "error",
                    "linear-gradient(135deg, #dc2626 0%, #ef4444 100%)",
                    "linear-gradient(135deg, #2563eb 0%, #3b82f6 100%)",
                ),
            ),
            box_shadow="xl",
            z_index="9999",
        ),
    )


def main_content() -> rx.Component:
    """Main content area."""
    return rx.vstack(
        rx.heading("Quick Insights", size="5", color="gray.12"),
        rx.grid(
            rx.foreach(
                DashboardState.recommendations,
                lambda item: rx.box(
                    rx.text(item.title, size="2", color="gray.11", weight="medium"),
                    rx.heading(item.value, size="4", color="blue.11"),
                    border="1px solid", border_color="blue.4", border_radius="10px", padding="0.85rem",
                    background="linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%)",
                ),
            ),
            columns="4", spacing="2", width="100%",
        ),
        rx.divider(),
        rx.hstack(
            rx.heading("Tender Results", size="5", color="gray.12"),
            rx.spacer(),
            rx.button(
                rx.icon("download"),
                "Export Current View",
                on_click=DashboardState.toggle_export_dialog,
                color_scheme="green",
                size="2",
                variant="soft",
            ),
            rx.badge(f"Records: {DashboardState.total_count}", size="2", color_scheme="blue"),
            rx.badge(f"Page {DashboardState.page} / {DashboardState.total_pages}", size="2", color_scheme="purple"),
            rx.select(DashboardState.view_mode_options, value=DashboardState.view_mode, on_change=DashboardState.set_view_mode, size="2", width="120px"),
            width="100%", align="center",
        ),
        rx.cond(
            DashboardState.loading,
            rx.center(
                rx.vstack(
                    rx.spinner(size="3", color="blue"),
                    rx.text("Loading tenders...", size="2", color="gray.11", weight="medium"),
                    spacing="2",
                ),
                width="100%",
                padding="3rem"
            ),
            rx.cond(
                DashboardState.view_mode == "cards",
                rx.vstack(rx.foreach(DashboardState.rows, tender_card), spacing="2", width="100%"),
                tender_table(),
            ),
        ),
        rx.hstack(
            rx.button("◀ Previous", on_click=DashboardState.prev_page, variant="soft", size="2"),
            rx.text(f"Page {DashboardState.page} of {DashboardState.total_pages}", size="2", color="gray.10"),
            rx.button("Next ▶", on_click=DashboardState.next_page, color_scheme="blue", size="2"),
            justify="center", spacing="3", width="100%",
        ),
        align="start", spacing="4", width="100%",
    )


def index() -> rx.Component:
    """Main dashboard page with full-width responsive layout."""
    return rx.box(
        rx.vstack(
            # Navigation bar
            rx.hstack(
                rx.link(
                    rx.button(
                        rx.icon("bar-chart-2"),
                        "Dashboard",
                        variant="soft",
                        size="2",
                    ),
                    href="/",
                ),
                rx.link(
                    rx.button(
                        rx.icon("globe"),
                        "Portal Management",
                        variant="soft",
                        size="2",
                    ),
                    href="/portals",
                ),
                spacing="2",
                padding="0.5rem 0",
            ),
            
            rx.divider(),
            
            # Header
            rx.hstack(
                rx.vstack(
                    rx.heading("🎯 Tender Dashboard", size="8", color="gray.12"),
                    rx.text("Advanced filtering & analytics", size="3", color="gray.10"),
                    align="start", spacing="1",
                ),
                rx.spacer(),
                rx.vstack(
                    rx.text(DashboardState.current_time, size="2", color="gray.10"),
                    rx.cond(
                        DashboardState.lifecycle_filter == "Live",
                        rx.text("✓ Live Tenders Only", size="2", color="green.10", weight="bold"),
                        rx.cond(
                            DashboardState.lifecycle_filter == "Expired",
                            rx.text("⏱ Expired Tenders", size="2", color="gray.10", weight="bold"),
                            rx.text("All Tenders", size="2", color="gray.10"),
                        ),
                    ),
                    align="end",
                ),
                width="100%", align="center",
            ),
            
            # Error message
            rx.cond(DashboardState.error_message != "", rx.callout(DashboardState.error_message, color_scheme="red", size="2")),
            
            # Google-style search bar
            google_search_bar(),
            
            # KPI cards
            rx.grid(
                stat_card("Live", DashboardState.live_tenders, "linear-gradient(135deg, #16a34a 0%, #22c55e 100%)"),
                stat_card("Expired", DashboardState.expired_tenders, "linear-gradient(135deg, #6b7280 0%, #9ca3af 100%)"),
                stat_card("Total", DashboardState.total_tenders, "linear-gradient(135deg, #2563eb 0%, #3b82f6 100%)"),
                stat_card("Filtered", DashboardState.filtered_results, "linear-gradient(135deg, #0284c7 0%, #0ea5e9 100%)"),
                stat_card("Match %", DashboardState.match_percent, "linear-gradient(135deg, #0d9488 0%, #14b8a6 100%)"),
                stat_card("Due Today", DashboardState.due_today, "linear-gradient(135deg, #dc2626 0%, #ef4444 100%)", on_click=DashboardState.filter_by_due_today),
                stat_card("Due 3d", DashboardState.due_3_days, "linear-gradient(135deg, #ea580c 0%, #f97316 100%)", on_click=DashboardState.filter_by_due_3_days),
                stat_card("Due 7d", DashboardState.due_7_days, "linear-gradient(135deg, #9333ea 0%, #a855f7 100%)", on_click=DashboardState.filter_by_due_7_days),
                stat_card("Depts", DashboardState.departments, "linear-gradient(135deg, #c026d3 0%, #d946ef 100%)", on_click=DashboardState.clear_date_filters),
                stat_card("Portals", DashboardState.data_sources, "linear-gradient(135deg, #7c3aed 0%, #8b5cf6 100%)"),
                columns="5", spacing="2", width="100%",
            ),
            
            rx.divider(),
            
            # Public export interface for website
            public_export_interface(),
            
            rx.divider(),
            
            # Main content with sidebar
            rx.cond(
                DashboardState.selected_filter_position == "left",
                rx.hstack(rx.box(sidebar_filters(), width="320px", flex_shrink="0"), rx.box(main_content(), flex="1"), spacing="4", align="start", width="100%"),
                rx.hstack(rx.box(main_content(), flex="1"), rx.box(sidebar_filters(), width="320px", flex_shrink="0"), spacing="4", align="start", width="100%"),
            ),
            
            # Export dialog
            export_dialog(),
            
            # Settings dialog
            settings_panel(),
            
            # Toast notification
            toast_notification(),
            
            spacing="4", width="100%",
            on_mount=DashboardState.load_initial_data,
        ),
        width="100%",
        max_width="100%",
        padding="1.5rem",
    )


app = rx.App()
app.add_page(index, route="/", title="Tender Dashboard - Enhanced v2.1")
app.add_page(portal_management_page, route="/portals", title="Portal Management")
