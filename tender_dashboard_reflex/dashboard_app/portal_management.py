"""Portal Management page - View and export portal statistics."""

from __future__ import annotations

import reflex as rx

from tender_dashboard_reflex.state import PortalManagementState, PortalRow


def portal_stats_card(title: str, value: rx.Var | str, color: str, icon: str) -> rx.Component:
    """Portal statistics card."""
    return rx.box(
        rx.hstack(
            rx.icon(icon, size=28, color=color),
            rx.vstack(
                rx.text(title, size="2", color="gray.10", weight="medium"),
                rx.heading(value, size="5", color="gray.12", weight="bold"),
                align="start",
                spacing="0",
            ),
            align="center",
            spacing="3",
        ),
        padding="1rem",
        border_radius="10px",
        border="1px solid",
        border_color="gray.6",
        background="white",
        width="100%",
    )


def export_settings_dialog() -> rx.Component:
    """Export settings dialog."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("📤 Export Portal Data"),
            rx.vstack(
                rx.text(
                    f"Selected {PortalManagementState.selected_count} portal(s) for export",
                    size="2",
                    color="gray.11",
                    weight="medium",
                ),
                rx.divider(),
                
                # Export options
                rx.vstack(
                    rx.text("Export Settings", size="3", weight="bold"),
                    
                    # Live only toggle
                    rx.hstack(
                        rx.switch(
                            checked=PortalManagementState.export_live_only,
                            on_change=PortalManagementState.toggle_export_live_only,
                            size="2",
                        ),
                        rx.text("Export Live Tenders Only", size="2", weight="medium"),
                        align="center",
                    ),
                    
                    # Expired days (only if not live_only)
                    rx.cond(
                        ~PortalManagementState.export_live_only,
                        rx.hstack(
                            rx.text("Include expired tenders from last", size="2"),
                            rx.input(
                                value=str(PortalManagementState.export_expired_days),
                                on_change=PortalManagementState.set_export_expired_days,
                                type="number",
                                width="80px",
                                size="2",
                            ),
                            rx.text("days", size="2"),
                            align="center",
                            spacing="2",
                        ),
                    ),
                    
                    align="start",
                    spacing="3",
                    width="100%",
                ),
                
                rx.divider(),
                
                rx.callout(
                    "Files will be named: {portal_domain}_tenders_YYYYMMDD_HHMMSS.xlsx",
                    icon="info",
                    size="1",
                    color_scheme="blue",
                ),
                
                rx.hstack(
                    rx.dialog.close(rx.button("Cancel", size="2", variant="soft")),
                    rx.button(
                        rx.icon("download"),
                        "Export Selected",
                        on_click=PortalManagementState.export_selected_portals_to_excel,
                        color_scheme="green",
                        size="2",
                        loading=PortalManagementState.exporting,
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
        open=PortalManagementState.show_export_dialog,
        on_open_change=PortalManagementState.toggle_export_dialog,
    )


def export_history_dialog() -> rx.Component:
    """Export history dialog showing past exports."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("📊 Export History"),
            rx.vstack(
                rx.text("Recent portal exports", size="2", color="gray.11"),
                rx.divider(),
                
                rx.box(
                    rx.cond(
                        PortalManagementState.export_history,
                        rx.vstack(
                            rx.foreach(
                                PortalManagementState.export_history,
                                lambda entry: rx.box(
                                    rx.vstack(
                                        rx.hstack(
                                            rx.badge(entry.export_type, size="1", color_scheme="blue"),
                                            rx.text(entry.timestamp[:19], size="1", color="gray.10"),
                                            spacing="2",
                                        ),
                                        rx.text(
                                            f"{entry.file_count} files, {entry.total_tenders} tenders",
                                            size="2",
                                            weight="medium",
                                        ),
                                        rx.text(
                                            f"Directory: {entry.export_dir}",
                                            size="1",
                                            color="gray.11",
                                        ),
                                        align="start",
                                        spacing="1",
                                    ),
                                    padding="0.75rem",
                                    border_radius="6px",
                                    border="1px solid",
                                    border_color="gray.6",
                                    width="100%",
                                )
                            ),
                            spacing="2",
                            width="100%",
                        ),
                        rx.text("No export history available", size="2", color="gray.10"),
                    ),
                    max_height="400px",
                    overflow_y="auto",
                    width="100%",
                ),
                
                rx.divider(),
                
                rx.hstack(
                    rx.dialog.close(rx.button("Close", size="2", variant="soft")),
                    justify="end",
                    width="100%",
                ),
                
                align="start",
                spacing="3",
                width="100%",
            ),
            max_width="600px",
        ),
        open=PortalManagementState.show_export_history,
        on_open_change=PortalManagementState.close_export_history,
    )


def portal_table_row(portal: PortalRow) -> rx.Component:
    """Portal statistics table row with health status colors."""

    # Health status color based on days since update
    # 🟢 Green (0 days/today), 🟡 Yellow (1-7 days), 🟠 Orange (8-30 days), 🔴 Red (>30 days)
    status_color = rx.cond(
        portal.days_since_update == 0,
        "green.9",
        rx.cond(
            portal.days_since_update <= 7,
            "yellow.9",
            rx.cond(
                portal.days_since_update <= 30,
                "orange.9",
                "red.9"
            )
        )
    )
    
    status_icon = rx.cond(
        portal.days_since_update == 0,
        "check-circle",
        rx.cond(
            portal.days_since_update <= 7,
            "clock",
            rx.cond(
                portal.days_since_update <= 30,
                "alert-circle",
                "alert-triangle"
            )
        )
    )
    
    return rx.table.row(
        rx.table.cell(
            rx.checkbox(
                checked=PortalManagementState.export_selected_portals.contains(portal.portal_slug),
                on_change=PortalManagementState.toggle_portal_selection(portal.portal_slug),
            )
        ),
        rx.table.cell(
                rx.vstack(
                    rx.hstack(
                        rx.text(portal.portal_name, size="2", weight="bold", color="blue.11"),
                        rx.badge(portal.category, size="1", color_scheme="gray"),
                        align="center",
                        spacing="2",
                    ),
                    rx.text(portal.portal_slug, size="1", color="gray.10", font_family="monospace"),
                    align="start",
                    spacing="0",
                ),
            _hover={"background": "gray.2", "cursor": "pointer"},
        ),
        rx.table.cell(
            rx.badge(portal.total_tenders, color_scheme="blue", size="2")
        ),
        rx.table.cell(
            rx.badge(portal.live_tenders, color_scheme="green", size="2")
        ),
        rx.table.cell(
            rx.badge(portal.expired_tenders, color_scheme="gray", size="2")
        ),
        rx.table.cell(
            rx.cond(
                portal.last_updated,
                rx.hstack(
                    rx.icon(status_icon, size=16, color=status_color),
                    rx.text(portal.last_updated[:16], size="2", color="gray.11"),
                    rx.cond(
                        portal.days_since_update >= 0,
                        rx.text(f"({portal.days_since_update}d)", size="1", color="gray.10"),
                        rx.fragment(),
                    ),
                    align="center",
                    spacing="1",
                ),
                rx.hstack(
                    rx.icon("circle-help", size=16, color="gray.7"),
                    rx.text("N/A", size="2", color="gray.10"),
                    align="center",
                    spacing="1",
                )
            )
        ),
        align="center",
    )


def portal_management_page() -> rx.Component:
    """Portal management page with statistics and export functionality."""
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
                        color_scheme="blue",
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
                    rx.heading("🌐 Portal Management", size="8", color="gray.12"),
                    rx.text("View statistics and export data for all portals", size="3", color="gray.10"),
                    align="start",
                    spacing="1",
                ),
                rx.spacer(),
                rx.button(
                    rx.icon("refresh-cw"),
                    "Refresh",
                    on_click=PortalManagementState.load_portal_statistics,
                    variant="soft",
                    size="2",
                ),
                width="100%",
                align="center",
            ),
            
            rx.divider(),
            
            # Summary cards
            rx.grid(
                portal_stats_card(
                    "Total Portals",
                    PortalManagementState.total_portals,
                    "blue.9",
                    "globe"
                ),
                portal_stats_card(
                    "Total Tenders",
                    PortalManagementState.total_all_tenders,
                    "violet.9",
                    "file-text"
                ),
                portal_stats_card(
                    "Live Tenders",
                    PortalManagementState.total_live_tenders,
                    "green.9",
                    "check"
                ),
                portal_stats_card(
                    "Expired Tenders",
                    PortalManagementState.total_expired_tenders,
                    "gray.9",
                    "x"
                ),
                columns="4",
                spacing="3",
                width="100%",
            ),
            
            rx.divider(),
            
            # Filters and actions
            rx.vstack(
                # First row: Days filter and category filter
                rx.hstack(
                    rx.hstack(
                        rx.text("Updated in last:", size="2", weight="medium"),
                        rx.select(
                            ["0 (All)", "1", "7", "30", "90"],
                            value=str(PortalManagementState.days_filter),
                            on_change=PortalManagementState.set_days_filter,
                            size="2",
                            width="120px",
                        ),
                        rx.text("days", size="2"),
                        align="center",
                        spacing="2",
                    ),
                    rx.hstack(
                        rx.text("Category:", size="2", weight="medium"),
                        rx.select(
                            ["All", "Central", "State", "PSU"],
                            value=PortalManagementState.category_filter,
                            on_change=PortalManagementState.set_category_filter,
                            size="2",
                            width="120px",
                        ),
                        align="center",
                        spacing="2",
                    ),
                    rx.spacer(),
                    rx.button(
                        rx.icon("history"),
                        "Export History",
                        on_click=PortalManagementState.load_export_history,
                        variant="soft",
                        size="2",
                    ),
                    width="100%",
                    align="center",
                ),
                
                # Second row: Export by category buttons
                rx.hstack(
                    rx.text("Quick Export:", size="2", weight="medium"),
                    rx.button(
                        rx.icon("download"),
                        "Central Portals",
                        on_click=PortalManagementState.export_category_portals("Central"),
                        color_scheme="blue",
                        variant="soft",
                        size="2",
                        loading=PortalManagementState.exporting,
                    ),
                    rx.button(
                        rx.icon("download"),
                        "State Portals",
                        on_click=PortalManagementState.export_category_portals("State"),
                        color_scheme="green",
                        variant="soft",
                        size="2",
                        loading=PortalManagementState.exporting,
                    ),
                    rx.button(
                        rx.icon("download"),
                        "PSU Portals",
                        on_click=PortalManagementState.export_category_portals("PSU"),
                        color_scheme="purple",
                        variant="soft",
                        size="2",
                        loading=PortalManagementState.exporting,
                    ),
                    rx.spacer(),
                    rx.button(
                        "Select All",
                        on_click=PortalManagementState.select_all_portals,
                        variant="soft",
                        size="2",
                    ),
                    rx.button(
                        "Deselect All",
                        on_click=PortalManagementState.deselect_all_portals,
                        variant="soft",
                        size="2",
                    ),
                    rx.button(
                        rx.icon("download"),
                        f"Export Selected ({PortalManagementState.selected_count})",
                        on_click=PortalManagementState.toggle_export_dialog,
                        color_scheme="green",
                        size="2",
                        disabled=PortalManagementState.selected_count == 0,
                    ),
                    width="100%",
                    align="center",
                ),
                spacing="2",
                width="100%",
            ),
            
            rx.divider(),
            
            # Portal table
            rx.cond(
                PortalManagementState.loading,
                rx.center(
                    rx.vstack(
                        rx.spinner(size="3", color="blue"),
                        rx.text("Loading portal statistics...", size="2", color="gray.11"),
                        spacing="2",
                    ),
                    padding="3rem",
                ),
                rx.box(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell(
                                    rx.text("Select")
                                ),
                                rx.table.column_header_cell("Portal Name"),
                                rx.table.column_header_cell("Total"),
                                rx.table.column_header_cell("Live"),
                                rx.table.column_header_cell("Expired"),
                                rx.table.column_header_cell("Last Updated"),
                            )
                        ),
                        rx.table.body(
                            rx.foreach(PortalManagementState.portal_rows, portal_table_row)
                        ),
                        variant="surface",
                        size="2",
                    ),
                    width="100%",
                    overflow_x="auto",
                ),
            ),
            
            # Export dialog
            export_settings_dialog(),
            
            # Export history dialog
            export_history_dialog(),
            
            # Toast notification
            rx.cond(
                PortalManagementState.show_toast,
                rx.box(
                    rx.hstack(
                        rx.cond(
                            PortalManagementState.toast_type == "success",
                            rx.icon("check", size=20, color="white"),
                            rx.cond(
                                PortalManagementState.toast_type == "error",
                                rx.icon("x", size=20, color="white"),
                                rx.icon("info", size=20, color="white"),
                            ),
                        ),
                        rx.text(PortalManagementState.toast_message, size="2", weight="medium", color="white"),
                        rx.icon_button(
                            rx.icon("x", size=16),
                            on_click=PortalManagementState.hide_toast,
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
                    border_radius="10px",
                    background=rx.cond(
                        PortalManagementState.toast_type == "success",
                        "green.9",
                        rx.cond(
                            PortalManagementState.toast_type == "error",
                            "red.9",
                            "blue.9",
                        ),
                    ),
                    box_shadow="xl",
                    z_index="9999",
                    min_width="350px",
                    max_width="500px",
                ),
            ),
            
            spacing="4",
            width="100%",
            on_mount=PortalManagementState.load_portal_statistics,
        ),
        width="100%",
        max_width="100%",
        padding="1.5rem",
    )
