"""Data Visualization page - View all tender data and database schema."""

from __future__ import annotations

import reflex as rx

from tender_dashboard_reflex.state import DataVisualizationState, DataRow


def header_cell_listing(text: str) -> rx.Component:
    """Green header for fields from listing page (currently available)."""
    return rx.table.column_header_cell(
        rx.hstack(
            rx.text(text, size="2", weight="bold"),
            rx.badge("✓", size="1", color_scheme="green", variant="soft"),
            spacing="1",
        ),
        background="green.3",
    )


def header_cell_detail(text: str) -> rx.Component:
    """Yellow header for fields requiring deep scraping (future enhancement)."""
    return rx.table.column_header_cell(
        rx.hstack(
            rx.text(text, size="2", weight="bold"),
            rx.badge("⏳", size="1", color_scheme="yellow", variant="soft"),
            spacing="1",
        ),
        background="yellow.3",
    )


def header_cell_meta(text: str) -> rx.Component:
    """Gray header for metadata/system fields."""
    return rx.table.column_header_cell(
        rx.text(text, size="2", weight="bold"),
        background="gray.3",
    )


def data_table_header() -> rx.Component:
    """Table header with color-coded columns showing data source."""
    return rx.table.header(
        rx.table.row(
            # System metadata
            header_cell_meta("S.No"),
            
            # From listing page (currently populated)
            header_cell_listing("Portal"),
            header_cell_listing("Tender ID"),
            header_cell_detail("Serial No"),  # Legacy field
            header_cell_listing("Published"),
            header_cell_listing("Opening"),
            header_cell_listing("Closing"),
            header_cell_listing("Lifecycle"),
            header_cell_listing("Is Live"),
            
            # From detail page (requires deep scraping)
            header_cell_detail("Title"),
            header_cell_detail("Department"),
            header_cell_detail("Organization"),
            header_cell_detail("EMD Amount"),
            header_cell_detail("Est. Cost"),
            header_cell_detail("Tender Status"),
            header_cell_detail("State"),
            header_cell_detail("District"),
            header_cell_detail("City"),
            header_cell_detail("Pincode"),
            header_cell_detail("Location"),
            header_cell_detail("Type"),
            header_cell_detail("Work Type"),
            header_cell_detail("Payment"),
            
            # URLs (from listing page)
            header_cell_listing("Direct URL"),
            header_cell_listing("Status URL"),
            
            # System metadata
            header_cell_meta("Run ID"),
            header_cell_meta("First Seen"),
            header_cell_meta("Last Seen"),
            header_cell_meta("Actions"),
        )
    )


def data_table_row(row: DataRow) -> rx.Component:
    """Table row displaying ALL database columns - raw data (reordered to match headers)."""
    return rx.table.row(
        # System metadata
        rx.table.cell(rx.text(row.row_num, size="1", color="gray.11")),
        
        # From listing page (green background)
        rx.table.cell(rx.text(row.portal_name, size="1", weight="medium"), background="green.2"),
        rx.table.cell(rx.text(row.tender_id_extracted, size="1", font_family="monospace"), background="green.2"),
        rx.table.cell(rx.text(row.serial_no, size="1"), background="yellow.2"),
        rx.table.cell(rx.text(row.published_date, size="1"), background="green.2"),
        rx.table.cell(rx.text(row.opening_date, size="1"), background="green.2"),
        rx.table.cell(rx.text(row.closing_date, size="1"), background="green.2"),
        rx.table.cell(
            rx.badge(
                row.lifecycle_status,
                color_scheme=rx.cond(row.lifecycle_status == "Live", "green", "gray"),
                size="1",
            ),
            background="green.2",
        ),
        rx.table.cell(
            rx.badge(
                row.is_live,
                color_scheme=rx.cond(row.is_live == "1", "green", "gray"),
                size="1",
            ),
            background="green.2",
        ),
        
        # From detail page (yellow background - mostly empty)
        rx.table.cell(rx.text(row.title_ref, size="1", max_width="300px"), background="yellow.2"),
        rx.table.cell(rx.text(row.department_name, size="1", max_width="200px"), background="yellow.2"),
        rx.table.cell(rx.text(row.organisation_chain, size="1", max_width="200px"), background="yellow.2"),
        rx.table.cell(rx.text(row.emd_amount, size="1"), background="yellow.2"),
        rx.table.cell(rx.text(row.estimated_cost, size="1"), background="yellow.2"),
        rx.table.cell(rx.text(row.tender_status, size="1"), background="yellow.2"),
        rx.table.cell(rx.text(row.state_name, size="1"), background="yellow.2"),
        rx.table.cell(rx.text(row.district, size="1"), background="yellow.2"),
        rx.table.cell(rx.text(row.city, size="1"), background="yellow.2"),
        rx.table.cell(rx.text(row.pincode, size="1"), background="yellow.2"),
        rx.table.cell(rx.text(row.location_text, size="1", max_width="200px"), background="yellow.2"),
        rx.table.cell(rx.text(row.tender_type, size="1"), background="yellow.2"),
        rx.table.cell(rx.text(row.work_type, size="1"), background="yellow.2"),
        rx.table.cell(rx.text(row.payment_type, size="1"), background="yellow.2"),
        
        # URLs (from listing page - green background)
        rx.table.cell(rx.text(row.direct_url, size="1", max_width="200px"), background="green.2"),
        rx.table.cell(rx.text(row.status_url, size="1", max_width="200px"), background="green.2"),
        
        # System metadata (gray background)
        rx.table.cell(rx.text(row.run_id, size="1"), background="gray.2"),
        rx.table.cell(rx.text(row.first_seen_at, size="1"), background="gray.2"),
        rx.table.cell(rx.text(row.last_seen_at, size="1"), background="gray.2"),
        rx.table.cell(
            rx.hstack(
                rx.cond(
                    row.direct_url != "",
                    rx.link(
                        rx.icon_button(
                            rx.icon("external-link"),
                            size="1",
                            variant="soft",
                            color_scheme="blue"
                        ),
                        href=row.direct_url,
                        is_external=True,
                    ),
                    rx.box()
                ),
                rx.cond(
                    row.status_url != "",
                    rx.link(
                        rx.icon_button(
                            rx.icon("file-text"),
                            size="1",
                            variant="soft",
                            color_scheme="purple"
                        ),
                        href=row.status_url,
                        is_external=True,
                    ),
                    rx.box()
                ),
                spacing="1",
            )
        ),
        align="center",
    )


def data_grid_tab() -> rx.Component:
    """Tab 1: All tender data in Excel-like grid with filters."""
    return rx.vstack(
        # Info callout - NIC portal architecture explanation
        rx.callout(
            rx.vstack(
                rx.text(
                    "📊 NIC Portal Two-Tier Data Architecture",
                    size="3",
                    weight="bold",
                ),
                rx.text(
                    "Green columns (✓): Available from listing page scraping (FrontEndTendersByOrganisation) - currently implemented",
                    size="2",
                ),
                rx.text(
                    "Yellow columns (⏳): Require deep scraping from detail pages (FrontEndViewTender) - future enhancement",
                    size="2",
                ),
                rx.text(
                    "💡 Why yellow columns are mostly empty: Scraper currently extracts only listing page data. Deep scraping will populate Title, Department, Organization, EMD, Costs, Location, etc.",
                    size="2",
                ),
                rx.link(
                    "📖 Read full architecture documentation",
                    href="../docs/NIC_PORTAL_ARCHITECTURE.md",
                    size="2",
                    weight="medium",
                    color="blue",
                ),
                spacing="2",
                align="start",
            ),
            icon="info",
            size="1",
            color_scheme="blue",
        ),
        
        # Filters
        rx.hstack(
            rx.hstack(
                rx.text("Portal:", size="2", weight="medium"),
                rx.select(
                    DataVisualizationState.portal_options,
                    value=DataVisualizationState.selected_portal,
                    on_change=DataVisualizationState.set_selected_portal,
                    placeholder="Select portal",
                    size="2",
                    width="200px",
                ),
                spacing="2",
            ),
            rx.hstack(
                rx.text("Status:", size="2", weight="medium"),
                rx.select(
                    ["All", "Live", "Expired"],
                    value=DataVisualizationState.lifecycle_filter,
                    on_change=DataVisualizationState.set_lifecycle_filter,
                    size="2",
                    width="120px",
                ),
                spacing="2",
            ),
            rx.spacer(),
            rx.text(
                f"Showing {DataVisualizationState.showing_from}-{DataVisualizationState.showing_to} of {DataVisualizationState.total_records} records",
                size="2",
                color="gray.11",
            ),
            rx.button(
                rx.icon("refresh-cw"),
                "Refresh",
                on_click=DataVisualizationState.load_data,
                variant="soft",
                size="2",
            ),
            width="100%",
            align="center",
        ),
        
        rx.divider(),
        
        # Color legend
        rx.hstack(
            rx.box(
                rx.hstack(
                    rx.box(width="20px", height="20px", background="green.3", border_radius="4px"),
                    rx.text("Listing Page Fields (FrontEndTendersByOrganisation)", size="2", weight="medium"),
                    rx.badge("✓ Currently Available", color_scheme="green", size="1"),
                    spacing="2",
                ),
                padding="0.5rem 1rem",
                border="1px solid",
                border_color="green.6",
                border_radius="8px",
                background="green.2",
            ),
            rx.box(
                rx.hstack(
                    rx.box(width="20px", height="20px", background="yellow.3", border_radius="4px"),
                    rx.text("Detail Page Fields (FrontEndViewTender)", size="2", weight="medium"),
                    rx.badge("⏳ Requires Deep Scraping", color_scheme="yellow", size="1"),
                    spacing="2",
                ),
                padding="0.5rem 1rem",
                border="1px solid",
                border_color="yellow.6",
                border_radius="8px",
                background="yellow.2",
            ),
            rx.box(
                rx.hstack(
                    rx.box(width="20px", height="20px", background="gray.3", border_radius="4px"),
                    rx.text("System Metadata", size="2", weight="medium"),
                    spacing="2",
                ),
                padding="0.5rem 1rem",
                border="1px solid",
                border_color="gray.6",
                border_radius="8px",
                background="gray.2",
            ),
            spacing="3",
            width="100%",
            wrap="wrap",
        ),
        
        rx.divider(),
        
        # Data table
        rx.cond(
            DataVisualizationState.loading,
            rx.center(
                rx.vstack(
                    rx.spinner(size="3", color="blue"),
                    rx.text("Loading tender data...", size="2", color="gray.11"),
                    spacing="2",
                ),
                padding="3rem",
            ),
            rx.box(
                rx.table.root(
                    data_table_header(),
                    rx.table.body(
                        rx.foreach(DataVisualizationState.data_rows, data_table_row)
                    ),
                    variant="surface",
                    size="1",
                    width="100%",
                ),
                width="100%",
                overflow_x="auto",
                max_height="calc(100vh - 350px)",
                overflow_y="auto",
            ),
        ),
        
        # Pagination
        rx.hstack(
            rx.button(
                rx.icon("chevrons-left"),
                "First",
                on_click=DataVisualizationState.first_page,
                disabled=DataVisualizationState.page == 1,
                variant="soft",
                size="2",
            ),
            rx.button(
                rx.icon("chevron-left"),
                "Previous",
                on_click=DataVisualizationState.prev_page,
                disabled=DataVisualizationState.page == 1,
                variant="soft",
                size="2",
            ),
            rx.text(
                f"Page {DataVisualizationState.page} of {DataVisualizationState.total_pages}",
                size="2",
                weight="medium",
            ),
            rx.button(
                "Next",
                rx.icon("chevron-right"),
                on_click=DataVisualizationState.next_page,
                disabled=DataVisualizationState.page >= DataVisualizationState.total_pages,
                color_scheme="blue",
                size="2",
            ),
            rx.button(
                "Last",
                rx.icon("chevrons-right"),
                on_click=DataVisualizationState.last_page,
                disabled=DataVisualizationState.page >= DataVisualizationState.total_pages,
                color_scheme="blue",
                size="2",
            ),
            spacing="2",
            justify="center",
            width="100%",
        ),
        
        spacing="3",
        width="100%",
    )


def schema_visualization_tab() -> rx.Component:
    """Tab 2: Database schema and data flow visualization."""
    return rx.vstack(
        rx.heading("📊 Database Schema & Data Flow", size="6", color="gray.12"),
        
        rx.divider(),
        
        # Tables overview
        rx.grid(
            # Runs table
            rx.box(
                rx.vstack(
                    rx.hstack(
                        rx.icon("database", size=20, color="blue.9"),
                        rx.heading("runs", size="4", color="blue.11"),
                        spacing="2",
                    ),
                    rx.divider(),
                    rx.vstack(
                        rx.text("📌 Primary Key: id", size="1", weight="bold"),
                        rx.text("Portal run metadata:", size="1", color="gray.11"),
                        rx.vstack(
                            rx.text("• portal_name", size="1", font_family="monospace"),
                            rx.text("• base_url", size="1", font_family="monospace"),
                            rx.text("• scope_mode (Full/Quick)", size="1", font_family="monospace"),
                            rx.text("• started_at, completed_at", size="1", font_family="monospace"),
                            rx.text("• status", size="1", font_family="monospace"),
                            rx.text("• extracted_total_tenders", size="1", font_family="monospace"),
                            spacing="1",
                            align="start",
                        ),
                        spacing="2",
                        align="start",
                    ),
                    spacing="2",
                    align="start",
                ),
                padding="1rem",
                border_radius="10px",
                border="2px solid",
                border_color="blue.6",
                background="blue.2",
            ),
            
            # Tenders table
            rx.box(
                rx.vstack(
                    rx.hstack(
                        rx.icon("file-text", size=20, color="green.9"),
                        rx.heading("tenders", size="4", color="green.11"),
                        spacing="2",
                    ),
                    rx.divider(),
                    rx.vstack(
                        rx.text("📌 Primary Key: id", size="1", weight="bold"),
                        rx.text("🔗 Foreign Key: run_id → runs(id)", size="1", weight="bold", color="orange.9"),
                        rx.text("Tender records:", size="1", color="gray.11"),
                        rx.vstack(
                            rx.text("• tender_id_extracted", size="1", font_family="monospace"),
                            rx.text("• portal_name, department_name", size="1", font_family="monospace"),
                            rx.text("• title_ref, organisation_chain", size="1", font_family="monospace"),
                            rx.text("• published_date, closing_date", size="1", font_family="monospace"),
                            rx.text("• lifecycle_status (active/expired)", size="1", font_family="monospace"),
                            rx.text("• direct_url, status_url", size="1", font_family="monospace"),
                            spacing="1",
                            align="start",
                        ),
                        spacing="2",
                        align="start",
                    ),
                    spacing="2",
                    align="start",
                ),
                padding="1rem",
                border_radius="10px",
                border="2px solid",
                border_color="green.6",
                background="green.2",
            ),
            
            # V3 Schema (if exists)
            rx.box(
                rx.vstack(
                    rx.hstack(
                        rx.icon("layers", size=20, color="purple.9"),
                        rx.heading("V3 Schema (New)", size="4", color="purple.11"),
                        spacing="2",
                    ),
                    rx.divider(),
                    rx.vstack(
                        rx.text("Modern schema with enhanced features:", size="1", color="gray.11"),
                        rx.vstack(
                            rx.text("📊 portals - Portal metadata", size="1", weight="medium"),
                            rx.text("📄 tender_items - Enhanced tender data", size="1", weight="medium"),
                            rx.text("  + state_name, district, city", size="1", font_family="monospace"),
                            rx.text("  + tender_type, work_type", size="1", font_family="monospace"),
                            rx.text("  + estimated_cost_value (numeric)", size="1", font_family="monospace"),
                            rx.text("  + is_live (boolean flag)", size="1", font_family="monospace"),
                            spacing="1",
                            align="start",
                        ),
                        spacing="2",
                        align="start",
                    ),
                    spacing="2",
                    align="start",
                ),
                padding="1rem",
                border_radius="10px",
                border="2px solid",
                border_color="purple.6",
                background="purple.2",
            ),
            
            columns="3",
            spacing="3",
            width="100%",
        ),
        
        rx.divider(),
        
        # Data flow diagram
        rx.box(
            rx.vstack(
                rx.heading("🔄 Data Flow", size="5", color="gray.12"),
                rx.divider(),
                
                rx.hstack(
                    # Step 1
                    rx.box(
                        rx.vstack(
                            rx.icon("play", size=32, color="blue.9"),
                            rx.text("1. Scraper Run", size="2", weight="bold"),
                            rx.text("Creates run record", size="1", color="gray.11"),
                            spacing="1",
                        ),
                        padding="1rem",
                        border_radius="8px",
                        background="blue.3",
                        width="150px",
                        text_align="center",
                    ),
                    
                    rx.icon("arrow-right", size=24, color="gray.9"),
                    
                    # Step 2
                    rx.box(
                        rx.vstack(
                            rx.icon("download", size=32, color="green.9"),
                            rx.text("2. Extract Data", size="2", weight="bold"),
                            rx.text("Portal scraping", size="1", color="gray.11"),
                            spacing="1",
                        ),
                        padding="1rem",
                        border_radius="8px",
                        background="green.3",
                        width="150px",
                        text_align="center",
                    ),
                    
                    rx.icon("arrow-right", size=24, color="gray.9"),
                    
                    # Step 3
                    rx.box(
                        rx.vstack(
                            rx.icon("database", size=32, color="orange.9"),
                            rx.text("3. Store Tenders", size="2", weight="bold"),
                            rx.text("Insert into DB", size="1", color="gray.11"),
                            spacing="1",
                        ),
                        padding="1rem",
                        border_radius="8px",
                        background="orange.3",
                        width="150px",
                        text_align="center",
                    ),
                    
                    rx.icon("arrow-right", size=24, color="gray.9"),
                    
                    # Step 4
                    rx.box(
                        rx.vstack(
                            rx.icon("eye", size=32, color="purple.9"),
                            rx.text("4. Dashboard", size="2", weight="bold"),
                            rx.text("View & Export", size="1", color="gray.11"),
                            spacing="1",
                        ),
                        padding="1rem",
                        border_radius="8px",
                        background="purple.3",
                        width="150px",
                        text_align="center",
                    ),
                    
                    spacing="2",
                    justify="center",
                    align="center",
                ),
                
                rx.divider(),
                
                # Relationships
                rx.vstack(
                    rx.text("🔗 Table Relationships:", size="3", weight="bold"),
                    rx.vstack(
                        rx.hstack(
                            rx.badge("runs", color_scheme="blue"),
                            rx.icon("arrow-right", size=16),
                            rx.badge("tenders", color_scheme="green"),
                            rx.text(": One run can have many tenders (1:N)", size="2", color="gray.11"),
                            spacing="2",
                            align="center",
                        ),
                        rx.hstack(
                            rx.badge("Foreign Key", color_scheme="orange"),
                            rx.text(": tenders.run_id references runs.id", size="2", color="gray.11"),
                            spacing="2",
                            align="center",
                        ),
                        rx.hstack(
                            rx.badge("CASCADE DELETE", color_scheme="red"),
                            rx.text(": Deleting a run deletes all its tenders", size="2", color="gray.11"),
                            spacing="2",
                            align="center",
                        ),
                        spacing="2",
                        align="start",
                    ),
                    spacing="2",
                    align="start",
                ),
                
                spacing="3",
                align="start",
            ),
            padding="1.5rem",
            border_radius="10px",
            border="1px solid",
            border_color="gray.6",
            background="white",
            width="100%",
        ),
        
        rx.divider(),
        
        # Statistics
        rx.grid(
            rx.box(
                rx.vstack(
                    rx.hstack(
                        rx.icon("bar-chart", size=20, color="blue.9"),
                        rx.text("Total Records", size="2", weight="bold"),
                        spacing="2",
                    ),
                    rx.heading(DataVisualizationState.db_total_records, size="6", color="blue.11"),
                    spacing="1",
                ),
                padding="1rem",
                border_radius="8px",
                border="1px solid",
                border_color="blue.6",
                background="blue.2",
            ),
            rx.box(
                rx.vstack(
                    rx.hstack(
                        rx.icon("check-circle", size=20, color="green.9"),
                        rx.text("Active Tenders", size="2", weight="bold"),
                        spacing="2",
                    ),
                    rx.heading(DataVisualizationState.db_active_records, size="6", color="green.11"),
                    spacing="1",
                ),
                padding="1rem",
                border_radius="8px",
                border="1px solid",
                border_color="green.6",
                background="green.2",
            ),
            rx.box(
                rx.vstack(
                    rx.hstack(
                        rx.icon("globe", size=20, color="purple.9"),
                        rx.text("Portals Tracked", size="2", weight="bold"),
                        spacing="2",
                    ),
                    rx.heading(DataVisualizationState.db_portal_count, size="6", color="purple.11"),
                    spacing="1",
                ),
                padding="1rem",
                border_radius="8px",
                border="1px solid",
                border_color="purple.6",
                background="purple.2",
            ),
            columns="3",
            spacing="3",
            width="100%",
        ),
        
        spacing="4",
        width="100%",
    )


def data_visualization_page() -> rx.Component:
    """Main data visualization page with tabs."""
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
                rx.link(
                    rx.button(
                        rx.icon("database"),
                        "Data Visualization",
                        variant="soft",
                        size="2",
                        color_scheme="blue",
                    ),
                    href="/data",
                ),
                rx.link(
                    rx.button(
                        rx.icon("zap"),
                        "Scraping Control",
                        variant="soft",
                        size="2",
                        color_scheme="green",
                    ),
                    href="/scraping",
                ),
                rx.link(
                    rx.button(
                        rx.icon("upload"),
                        "Import Data",
                        variant="soft",
                        size="2",
                        color_scheme="orange",
                    ),
                    href="/import",
                ),
                spacing="2",
                padding="0.5rem 0",
            ),
            
            rx.divider(),
            
            # Header
            rx.hstack(
                rx.vstack(
                    rx.heading("💾 Data Flow Visualization", size="8", color="gray.12"),
                    rx.text("Explore tender data and understand database structure", size="3", color="gray.10"),
                    align="start",
                    spacing="1",
                ),
                width="100%",
            ),
            
            rx.divider(),
            
            # Tabs
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger("📋 Data Grid", value="grid"),
                    rx.tabs.trigger("🗄️ Database Schema", value="schema"),
                ),
                rx.tabs.content(
                    data_grid_tab(),
                    value="grid",
                ),
                rx.tabs.content(
                    schema_visualization_tab(),
                    value="schema",
                ),
                default_value="grid",
                width="100%",
            ),
            
            spacing="4",
            width="100%",
            on_mount=DataVisualizationState.load_data,
        ),
        width="100%",
        max_width="100%",
        padding="1.5rem",
    )
