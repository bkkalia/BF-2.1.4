from __future__ import annotations

import reflex as rx

from tender_dashboard_reflex.state import DashboardState, TenderRow


def stat_card(title: str, value: rx.Var | str, accent: str) -> rx.Component:
    return rx.box(
        rx.text(title, size="2", color="white"),
        rx.heading(value, size="6", color="white"),
        padding="0.9rem",
        border_radius="12px",
        background=accent,
        box_shadow="md",
        width="100%",
    )


def filter_select(label: str, options: list[str] | rx.Var, value: rx.Var, on_change) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="2", weight="medium"),
        rx.select(options, value=value, on_change=on_change),
        align="start",
        width="100%",
    )


def filter_panel() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.heading("Filters", size="6"),
                rx.spacer(),
                filter_select(
                    "Position",
                    DashboardState.filter_position_options,
                    DashboardState.selected_filter_position,
                    DashboardState.set_selected_filter_position,
                ),
                align="start",
                width="100%",
            ),
            rx.grid(
                filter_select("Portal", DashboardState.portal_options, DashboardState.selected_portal, DashboardState.set_selected_portal),
                filter_select("Status", DashboardState.status_options, DashboardState.selected_status, DashboardState.set_selected_status),
                filter_select("State", DashboardState.state_options, DashboardState.selected_state, DashboardState.on_state_change),
                filter_select("District", DashboardState.district_options, DashboardState.selected_district, DashboardState.on_district_change),
                filter_select("City", DashboardState.city_options, DashboardState.selected_city, DashboardState.set_selected_city),
                columns="5",
                spacing="3",
                width="100%",
            ),
            rx.grid(
                filter_select("Tender Type", DashboardState.tender_type_options, DashboardState.selected_tender_type, DashboardState.set_selected_tender_type),
                filter_select("Work Type", DashboardState.work_type_options, DashboardState.selected_work_type, DashboardState.set_selected_work_type),
                filter_select("Sort By", DashboardState.sort_options, DashboardState.selected_sort, DashboardState.set_selected_sort),
                filter_select("Sort Order", ["desc", "asc"], DashboardState.selected_sort_order, DashboardState.set_selected_sort_order),
                filter_select("Page Size", ["25", "50", "100"], DashboardState.page_size.to_string(), DashboardState.set_page_size_value),
                columns="5",
                spacing="3",
                width="100%",
            ),
            rx.grid(
                rx.vstack(
                    rx.text("From Date", size="2", weight="medium"),
                    rx.input(type="date", value=DashboardState.from_date, on_change=DashboardState.set_from_date),
                    align="start",
                    width="100%",
                ),
                rx.vstack(
                    rx.text("To Date", size="2", weight="medium"),
                    rx.input(type="date", value=DashboardState.to_date, on_change=DashboardState.set_to_date),
                    align="start",
                    width="100%",
                ),
                rx.vstack(
                    rx.text("Min Amount", size="2", weight="medium"),
                    rx.input(value=DashboardState.min_amount, on_change=DashboardState.set_min_amount, placeholder="100000"),
                    align="start",
                    width="100%",
                ),
                rx.vstack(
                    rx.text("Max Amount", size="2", weight="medium"),
                    rx.input(value=DashboardState.max_amount, on_change=DashboardState.set_max_amount, placeholder="5000000"),
                    align="start",
                    width="100%",
                ),
                rx.vstack(
                    rx.text("Global Search", size="2", weight="medium"),
                    rx.input(value=DashboardState.search_query, on_change=DashboardState.set_search_query, placeholder="title / dept / tender id"),
                    align="start",
                    width="100%",
                ),
                columns="5",
                spacing="3",
                width="100%",
            ),
            rx.hstack(
                rx.button("Apply Filters", on_click=DashboardState.apply_filters, color_scheme="blue"),
                rx.button("Reset", on_click=DashboardState.reset_filters, variant="soft"),
            ),
            width="100%",
            spacing="3",
            align="start",
        ),
        border="1px solid",
        border_color="gray.5",
        border_radius="12px",
        padding="1rem",
        background="linear-gradient(135deg, #f8fbff 0%, #f3f8ff 60%, #eef7ff 100%)",
        width="100%",
    )


def tender_row(row: TenderRow) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.badge(row.portal_name, color_scheme="violet"),
                rx.badge(row.tender_status, color_scheme="teal"),
                rx.text(f"Tender ID: {row.tender_id_extracted}", size="2"),
                width="100%",
                justify="between",
            ),
            rx.text(row.title_ref, weight="bold"),
            rx.hstack(
                rx.text(f"Dept: {row.department_name}"),
                rx.text(f"Published: {row.published_at}"),
                rx.text(f"Closing: {row.closing_at}"),
                rx.text(f"Est. Cost: {row.estimated_cost_value}"),
                wrap="wrap",
            ),
            rx.hstack(
                rx.text(f"State: {row.state_name}"),
                rx.text(f"District: {row.district}"),
                rx.text(f"City: {row.city}"),
                wrap="wrap",
            ),
            align="start",
            spacing="2",
        ),
        border="1px solid",
        border_color="gray.5",
        border_radius="12px",
        padding="0.75rem",
        width="100%",
        background="white",
    )


def content_section() -> rx.Component:
    return rx.vstack(
        rx.heading("Recommendations", size="6"),
        rx.grid(
            rx.foreach(
                DashboardState.recommendations,
                lambda item: rx.box(
                    rx.text(item.title, size="2", color="gray"),
                    rx.heading(item.value, size="4"),
                    border="1px solid",
                    border_color="gray.5",
                    border_radius="12px",
                    padding="0.85rem",
                    background="linear-gradient(135deg, #fff7ed 0%, #fffbeb 100%)",
                ),
            ),
            columns="4",
            spacing="2",
            width="100%",
        ),
        rx.divider(),
        rx.hstack(
            rx.heading("Tender Results", size="6"),
            rx.spacer(),
            rx.badge(f"Records: {DashboardState.total_count}", color_scheme="blue"),
            rx.badge(f"Page {DashboardState.page} / {DashboardState.total_pages}", color_scheme="purple"),
            width="100%",
        ),
        rx.cond(
            DashboardState.loading,
            rx.center(rx.spinner(size="3"), width="100%"),
            rx.vstack(
                rx.foreach(DashboardState.rows, tender_row),
                spacing="2",
                width="100%",
            ),
        ),
        rx.hstack(
            rx.button("Previous", on_click=DashboardState.prev_page, variant="soft"),
            rx.button("Next", on_click=DashboardState.next_page, color_scheme="blue"),
        ),
        width="100%",
        spacing="3",
        align="start",
    )


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Tender Data Analysis Dashboard", size="8"),
            rx.text("Separate Reflex app for tender filtering and view analytics"),
            rx.text(DashboardState.current_time),
            rx.cond(
                DashboardState.error_message != "",
                rx.callout(DashboardState.error_message, color_scheme="red"),
            ),
            rx.grid(
                stat_card("Live Tenders", DashboardState.live_tenders, "linear-gradient(135deg, #16a34a 0%, #22c55e 100%)"),
                stat_card("Expired Tenders", DashboardState.expired_tenders, "linear-gradient(135deg, #111827 0%, #374151 100%)"),
                stat_card("Total Tenders", DashboardState.total_tenders, "linear-gradient(135deg, #2563eb 0%, #3b82f6 100%)"),
                stat_card("Filtered Results", DashboardState.filtered_results, "linear-gradient(135deg, #0284c7 0%, #0ea5e9 100%)"),
                stat_card("Filter Match %", DashboardState.match_percent, "linear-gradient(135deg, #0f766e 0%, #14b8a6 100%)"),
                stat_card("Departments", DashboardState.departments, "linear-gradient(135deg, #f97316 0%, #fb923c 100%)"),
                stat_card("Due Today", DashboardState.due_today, "linear-gradient(135deg, #dc2626 0%, #ef4444 100%)"),
                stat_card("Due in 3 Days", DashboardState.due_3_days, "linear-gradient(135deg, #9333ea 0%, #a855f7 100%)"),
                stat_card("Due in 7 Days", DashboardState.due_7_days, "linear-gradient(135deg, #1d4ed8 0%, #2563eb 100%)"),
                stat_card("Data Sources", DashboardState.data_sources, "linear-gradient(135deg, #7e22ce 0%, #a855f7 100%)"),
                columns="5",
                spacing="2",
                width="100%",
            ),
            rx.divider(),
            rx.cond(
                DashboardState.selected_filter_position == "top",
                rx.vstack(
                    filter_panel(),
                    content_section(),
                    width="100%",
                    spacing="3",
                    align="start",
                ),
                rx.cond(
                    DashboardState.selected_filter_position == "left",
                    rx.hstack(
                        rx.box(filter_panel(), width="30%"),
                        rx.box(content_section(), width="70%"),
                        width="100%",
                        spacing="3",
                        align="start",
                    ),
                    rx.hstack(
                        rx.box(content_section(), width="70%"),
                        rx.box(filter_panel(), width="30%"),
                        width="100%",
                        spacing="3",
                        align="start",
                    ),
                ),
            ),
            width="100%",
            spacing="4",
            on_mount=DashboardState.load_initial_data,
        ),
        max_width="1600px",
    )


app = rx.App()
app.add_page(index, title="Tender Dashboard")
