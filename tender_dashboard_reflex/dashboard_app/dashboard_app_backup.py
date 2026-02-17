from __future__ import annotations

import reflex as rx

from tender_dashboard_reflex.state import DashboardState, TenderRow


def stat_card(title: str, value: rx.Var | str, accent: str) -> rx.Component:
    """KPI card with gradient background."""
    return rx.box(
        rx.text(title, size="2", color="white", weight="medium"),
        rx.heading(value, size="6", color="white", weight="bold"),
        padding="1rem",border_radius="12px",background=accent,box_shadow="lg",width="100%",min_height="85px",
    )


def filter_input(label: str, placeholder: str, value: rx.Var, on_change) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="2", weight="medium", color="gray.11"),
        rx.input(value=value, on_change=on_change, placeholder=placeholder, width="100%", size="2"),
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
                rx.heading("Filters", size="6", color="gray.12"),
                rx.spacer(),
                rx.icon_button(rx.icon("settings"), on_click=DashboardState.toggle_settings, variant="ghost", size="2"),
                width="100%", align="center",
            ),
            rx.divider(),
            rx.hstack(
                rx.switch(checked=DashboardState.show_live_only, on_change=DashboardState.toggle_live_only, size="2"),
                rx.text("Show Live Tenders Only", size="3", weight="medium", color="green.11"),
                width="100%", align="center",
            ),
            rx.divider(),
            filter_select("Portal Group", DashboardState.portal_group_options, DashboardState.selected_portal_group, DashboardState.set_selected_portal_group),
            filter_select("Individual Portal", DashboardState.portal_options, DashboardState.selected_portal, DashboardState.set_selected_portal),
            rx.vstack(
                rx.hstack(
                    rx.text("Search Query", size="2", weight="medium", color="gray.11"),
                    rx.select(DashboardState.search_logic_options, value=DashboardState.search_logic, on_change=DashboardState.set_search_logic, size="1", width="70px"),
                    width="100%", justify="between",
                ),
                rx.input(value=DashboardState.search_query, on_change=DashboardState.set_search_query, placeholder="term1, term2...", width="100%", size="2"),
                rx.text("Comma-separated terms", size="1", color="gray.9"),
                align="start", width="100%", spacing="1",
            ),
            rx.vstack(
                rx.hstack(
                    rx.text("Department Filter", size="2", weight="medium", color="gray.11"),
                    rx.select(DashboardState.search_logic_options, value=DashboardState.department_logic, on_change=DashboardState.set_department_logic, size="1", width="70px"),
                    width="100%", justify="between",
                ),
                rx.input(value=DashboardState.department_filter, on_change=DashboardState.set_department_filter, placeholder="dept1, dept2...", width="100%", size="2"),
                rx.text("Comma-separated departments", size="1", color="gray.9"),
                align="start", width="100%", spacing="1",
            ),
            rx.divider(),
            filter_select("Status", DashboardState.status_options, DashboardState.selected_status, DashboardState.set_selected_status),
            filter_input("From Date", "YYYY-MM-DD", DashboardState.from_date, DashboardState.set_from_date),
            filter_input("To Date", "YYYY-MM-DD", DashboardState.to_date, DashboardState.set_to_date),
            filter_select("State", DashboardState.state_options, DashboardState.selected_state, DashboardState.on_state_change),
            filter_select("District", DashboardState.district_options, DashboardState.selected_district, DashboardState.on_district_change),
            filter_select("City", DashboardState.city_options, DashboardState.selected_city, DashboardState.set_selected_city),
            filter_select("Tender Type", DashboardState.tender_type_options, DashboardState.selected_tender_type, DashboardState.set_selected_tender_type),
            filter_select("Work Type", DashboardState.work_type_options, DashboardState.selected_work_type, DashboardState.set_selected_work_type),
            filter_input("Min Amount", "100000", DashboardState.min_amount, DashboardState.set_min_amount),
            filter_input("Max Amount", "5000000", DashboardState.max_amount, DashboardState.set_max_amount),
            filter_select("Sort By", DashboardState.sort_options, DashboardState.selected_sort, DashboardState.set_selected_sort),
            filter_select("Sort Order", ["desc", "asc"], DashboardState.selected_sort_order, DashboardState.set_selected_sort_order),
            filter_select("Page Size", ["25", "50", "100", "200"], DashboardState.page_size.to_string(), DashboardState.set_page_size_value),
            rx.divider(),
            rx.button("Apply", on_click=DashboardState.apply_filters, color_scheme="blue", size="3", width="100%"),
            rx.button("Reset All", on_click=DashboardState.reset_filters, variant="outline", size="2", width="100%"),
            align="start", spacing="3", width="100%",
        ),
        padding="1.2rem", border_radius="12px", background="linear-gradient(135deg, #fefefe 0%, #f9fafb 100%)",
        border="1px solid", border_color="gray.6", height="100%", overflow_y="auto", max_height="calc(100vh - 120px)",
    )


def tender_card(row: TenderRow) -> rx.Component:
    """Card view for tender."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.badge(row.portal_name, color_scheme="violet", size="2"),
                rx.badge(row.tender_status, color_scheme="green", size="2"),
                rx.spacer(),
                rx.text(row.closing_at, size="2", weight="medium", color="red.11"),
                width="100%", wrap="wrap",
            ),
            rx.text(f"ID: {row.tender_id_extracted}", size="2", weight="bold", color="blue.11"),
            rx.text(row.title_ref, size="3", weight="bold", color="gray.12", line_height="1.4"),
            rx.text(f"Dept: {row.department_name}", size="2", color="gray.11"),
            rx.hstack(
                rx.text(f"Published: {row.published_at}", size="2", color="gray.10"),
                rx.text(f"Cost: {row.estimated_cost_value}", size="2", color="green.10", weight="medium"),
                wrap="wrap", width="100%",
            ),
            rx.hstack(
                rx.cond(row.state_name != "-", rx.text(f"📍 {row.state_name}", size="2"), rx.box()),
                rx.cond(row.district != "-", rx.text(f"• {row.district}", size="2"), rx.box()),
                rx.cond(row.city != "-", rx.text(f"• {row.city}", size="2"), rx.box()),
                width="100%",
            ),
            rx.hstack(
                rx.cond(row.tender_url != "", rx.link(rx.button("Direct URL", size="2", color_scheme="blue", variant="soft"), href=row.tender_url, is_external=True), rx.box()),
                rx.cond(row.status_url != "", rx.link(rx.button("Status URL", size="2", color_scheme="purple", variant="soft"), href=row.status_url, is_external=True), rx.box()),
                spacing="2",
            ),
            align="start", spacing="2", width="100%",
        ),
        border="1px solid", border_color="gray.6", border_radius="12px", padding="1rem",
        background="white", _hover={"box_shadow": "lg", "border_color": "blue.6"}, width="100%",
    )


def tender_table() -> rx.Component:
    """Table view for tenders."""
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
                        rx.table.cell(rx.text(row.tender_id_extracted, size="2", weight="medium", color="blue.11")),
                        rx.table.cell(rx.text(row.title_ref, size="2", max_width="300px", overflow="hidden", text_overflow="ellipsis", white_space="nowrap")),
                        rx.table.cell(rx.text(row.department_name, size="2")),
                        rx.table.cell(rx.text(row.closing_at, size="2", color="red.10", weight="medium")),
                        rx.table.cell(rx.text(row.estimated_cost_value, size="2", color="green.10")),
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
                rx.text("Tender Dashboard v2.0 - Enhanced filtering, portal groups, advanced search, tabular view", size="2", color="gray.10"),
                align="start", spacing="3", width="100%",
            ),
            rx.dialog.close(rx.button("Close", size="2", variant="soft")),
        ),
        open=DashboardState.show_settings,
        on_open_change=DashboardState.toggle_settings,
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
            rx.badge(f"Records: {DashboardState.total_count}", size="2", color_scheme="blue"),
            rx.badge(f"Page {DashboardState.page} / {DashboardState.total_pages}", size="2", color_scheme="purple"),
            rx.select(DashboardState.view_mode_options, value=DashboardState.view_mode, on_change=DashboardState.set_view_mode, size="2", width="120px"),
            width="100%", align="center",
        ),
        rx.cond(
            DashboardState.loading,
            rx.center(rx.spinner(size="3"), width="100%", padding="3rem"),
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
    """Main dashboard page."""
    return rx.container(
        rx.vstack(
            rx.hstack(
                rx.vstack(
                    rx.heading("🎯 Tender Dashboard", size="8", color="gray.12"),
                    rx.text("Advanced filtering & analytics", size="3", color="gray.10"),
                    align="start", spacing="1",
                ),
                rx.spacer(),
                rx.vstack(
                    rx.text(DashboardState.current_time, size="2", color="gray.10"),
                    rx.cond(DashboardState.show_live_only, rx.text("Live Tenders Only", size="2", color="green.10"), rx.text("All Tenders", size="2", color="gray.10")),
                    align="end",
                ),
                width="100%", align="center",
            ),
            rx.cond(DashboardState.error_message != "", rx.callout(DashboardState.error_message, color_scheme="red", size="2")),
            rx.grid(
                stat_card("Live", DashboardState.live_tenders, "linear-gradient(135deg, #16a34a 0%, #22c55e 100%)"),
               stat_card("Expired", DashboardState.expired_tenders, "linear-gradient(135deg, #6b7280 0%, #9ca3af 100%)"),
                stat_card("Total", DashboardState.total_tenders, "linear-gradient(135deg, #2563eb 0%, #3b82f6 100%)"),
                stat_card("Filtered", DashboardState.filtered_results, "linear-gradient(135deg, #0284c7 0%, #0ea5e9 100%)"),
                stat_card("Match %", DashboardState.match_percent, "linear-gradient(135deg, #0d9488 0%, #14b8a6 100%)"),
                stat_card("Due Today", DashboardState.due_today, "linear-gradient(135deg, #dc2626 0%, #ef4444 100%)"),
                stat_card("Due 3d", DashboardState.due_3_days, "linear-gradient(135deg, #ea580c 0%, #f97316 100%)"),
                stat_card("Due 7d", DashboardState.due_7_days, "linear-gradient(135deg, #9333ea 0%, #a855f7 100%)"),
                stat_card("Depts", DashboardState.departments, "linear-gradient(135deg, #c026d3 0%, #d946ef 100%)"),
                stat_card("Portals", DashboardState.data_sources, "linear-gradient(135deg, #7c3aed 0%, #8b5cf6 100%)"),
                columns="5", spacing="2", width="100%",
            ),
            rx.divider(),
            rx.cond(
                DashboardState.selected_filter_position == "left",
                rx.hstack(rx.box(sidebar_filters(), width="300px"), rx.box(main_content(), flex="1"), spacing="4", align="start", width="100%"),
                rx.hstack(rx.box(main_content(), flex="1"), rx.box(sidebar_filters(), width="300px"), spacing="4", align="start", width="100%"),
            ),
            settings_panel(),
            spacing="4", width="100%",
            on_mount=DashboardState.load_initial_data,
        ),
        max_width="1800px", padding="1.5rem",
    )


app = rx.App()
app.add_page(index, title="Tender Dashboard - Enhanced")
