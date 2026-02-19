"""Excel/CSV Import page with smart column matching."""

from __future__ import annotations

import reflex as rx

from tender_dashboard_reflex.state import ExcelImportState, ColumnMapping


def upload_section() -> rx.Component:
    """File upload section."""
    return rx.vstack(
        rx.heading("📥 Import Tender Data", size="6", color="gray.12"),
        
        rx.callout(
            rx.vstack(
                rx.text(
                    "Import tender data from Excel or CSV files with smart column matching",
                    size="3",
                    weight="bold",
                ),
                rx.text(
                    "✅ Supports: .xlsx, .xls, .csv files",
                    size="2",
                ),
                rx.text(
                    "🔍 Smart matching: Automatically detects columns like 'Tender ID', 'tender_id_extracted', 'TenderID', etc.",
                    size="2",
                ),
                rx.text(
                    "🎯 Production ready: Import your existing hptenders_gov_in_tenders_*.xlsx files",
                    size="2",
                ),
                spacing="2",
                align="start",
            ),
            icon="info",
            size="1",
            color_scheme="blue",
        ),
        
        rx.divider(),
        
        # Upload area
        rx.upload(
            rx.vstack(
                rx.button(
                    rx.icon("upload"),
                    "Select Excel/CSV File",
                    color_scheme="blue",
                    size="3",
                ),
                rx.text(
                    "Drag and drop or click to select file",
                    size="2",
                    color="gray.11",
                ),
                rx.text(
                    f"Max file size: {ExcelImportState.max_file_size_mb} MB",
                    size="1",
                    color="gray.10",
                ),
                align="center",
                spacing="2",
            ),
            id="excel_upload",
            accept={
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
                "application/vnd.ms-excel": [".xls"],
                "text/csv": [".csv"],
            },
            max_files=1,
            disabled=ExcelImportState.uploading,
            on_drop=ExcelImportState.handle_upload(rx.upload_files(upload_id="excel_upload")),
            border="2px dashed",
            border_color="blue.7",
            border_radius="12px",
            padding="3rem",
            width="100%",
        ),
        
        # Upload progress
        rx.cond(
            ExcelImportState.uploading,
            rx.vstack(
                rx.spinner(size="3", color="blue"),
                rx.text("Analyzing file...", size="2", color="gray.11", weight="medium"),
                spacing="2",
                align="center",
            ),
        ),
        
        spacing="3",
        width="100%",
    )


def file_preview_section() -> rx.Component:
    """Preview uploaded file info and columns."""
    return rx.cond(
        ExcelImportState.file_uploaded,
        rx.vstack(
            rx.heading("📄 File Preview", size="5", color="gray.12"),
            
            # File info card
            rx.box(
                rx.vstack(
                    rx.hstack(
                        rx.icon("file-spreadsheet", size=24, color="green.9"),
                        rx.vstack(
                            rx.text("File Information", size="2", weight="bold"),
                            rx.text(f"{ExcelImportState.file_name}", size="3", weight="medium", color="blue.11"),
                            align="start",
                            spacing="0",
                        ),
                        align="center",
                        spacing="3",
                    ),
                    rx.grid(
                        rx.vstack(
                            rx.text("Rows", size="1", color="gray.10"),
                            rx.text(f"{ExcelImportState.file_rows:,}", size="3", weight="bold"),
                            spacing="0",
                        ),
                        rx.vstack(
                            rx.text("Columns", size="1", color="gray.10"),
                            rx.text(str(ExcelImportState.file_columns), size="3", weight="bold"),
                            spacing="0",
                        ),
                        rx.vstack(
                            rx.text("File Size", size="1", color="gray.10"),
                            rx.text(ExcelImportState.file_size_text, size="3", weight="bold"),
                            spacing="0",
                        ),
                        columns="3",
                        spacing="4",
                        width="100%",
                    ),
                    spacing="3",
                ),
                padding="1.5rem",
                border_radius="10px",
                border="1px solid",
                border_color="green.6",
                background="green.2",
                width="100%",
            ),
            
            spacing="3",
            width="100%",
        ),
    )


def column_mapping_section() -> rx.Component:
    """Smart column mapping interface."""
    return rx.cond(
        ExcelImportState.file_uploaded,
        rx.vstack(
            rx.heading("🔗 Column Mapping", size="5", color="gray.12"),
            
            rx.callout(
                rx.vstack(
                    rx.text("Smart matching detected the following column mappings:", size="2", weight="bold"),
                    rx.text(
                        f"✅ {ExcelImportState.auto_matched_columns} / {ExcelImportState.total_required_columns} required columns matched automatically",
                        size="2",
                    ),
                    rx.cond(
                        ~ExcelImportState.all_required_mapped,
                        rx.text(
                            "⚠️ Please map the remaining required columns manually below",
                            size="2",
                            color="orange.11",
                            weight="medium",
                        ),
                    ),
                    spacing="1",
                    align="start",
                ),
                icon=rx.cond(
                    ExcelImportState.all_required_mapped,
                    "circle-check",
                    "alert-circle",
                ),
                color_scheme=rx.cond(
                    ExcelImportState.all_required_mapped,
                    "green",
                    "orange",
                ),
                size="1",
            ),
            
            rx.divider(),
            
            # Column mapping table
            rx.box(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Database Column", background="blue.3"),
                            rx.table.column_header_cell("Excel/CSV Column", background="green.3"),
                            rx.table.column_header_cell("Required", background="gray.3"),
                            rx.table.column_header_cell("Preview", background="purple.3"),
                            rx.table.column_header_cell("Status", background="gray.3"),
                        )
                    ),
                    rx.table.body(
                        rx.foreach(
                            ExcelImportState.column_mappings,
                            lambda mapping: rx.table.row(
                                # Database column
                                rx.table.cell(
                                    rx.hstack(
                                        rx.icon(
                                            "database",
                                            size=16,
                                            color="blue.9",
                                        ),
                                        rx.text(mapping.db_column, size="2", weight="medium", font_family="monospace"),
                                        spacing="2",
                                    ),
                                    background="blue.2",
                                ),
                                # Excel column selector
                                rx.table.cell(
                                    rx.select(
                                        ExcelImportState.excel_columns_with_unmapped,
                                        value=mapping.excel_column,
                                        on_change=lambda val, db_col=mapping.db_column: ExcelImportState.update_column_mapping(db_col, val),
                                        placeholder="Select column",
                                        size="2",
                                        width="100%",
                                    ),
                                    background="green.2",
                                ),
                                # Required badge
                                rx.table.cell(
                                    rx.cond(
                                        mapping.is_required,
                                        rx.badge("Required", color_scheme="red", size="1"),
                                        rx.badge("Optional", color_scheme="gray", size="1", variant="soft"),
                                    ),
                                ),
                                # Sample data preview
                                rx.table.cell(
                                    rx.text(
                                        mapping.sample_data,
                                        size="1",
                                        color="gray.11",
                                        max_width="200px",
                                        truncate=True,
                                    ),
                                    background="purple.2",
                                ),
                                # Match status
                                rx.table.cell(
                                    rx.cond(
                                        mapping.is_mapped,
                                        rx.hstack(
                                            rx.icon("check", size=16, color="green.9"),
                                            rx.text("Matched", size="1", color="green.11", weight="medium"),
                                            spacing="1",
                                        ),
                                        rx.cond(
                                            mapping.is_required,
                                            rx.hstack(
                                                rx.icon("alert-circle", size=16, color="red.9"),
                                                rx.text("Required", size="1", color="red.11", weight="medium"),
                                                spacing="1",
                                            ),
                                            rx.text("—", size="1", color="gray.10"),
                                        ),
                                    ),
                                ),
                            )
                        )
                    ),
                    variant="surface",
                    size="2",
                    width="100%",
                ),
                overflow_x="auto",
                width="100%",
            ),
            
            spacing="3",
            width="100%",
        ),
    )


def import_settings_section() -> rx.Component:
    """Import settings and options."""
    return rx.cond(
        ExcelImportState.file_uploaded,
        rx.vstack(
            rx.heading("⚙️ Import Settings", size="5", color="gray.12"),
            
            rx.grid(
                # Portal name
                rx.vstack(
                    rx.text("Portal Name", size="2", weight="bold"),
                    rx.input(
                        value=ExcelImportState.portal_name,
                        on_change=ExcelImportState.set_portal_name,
                        placeholder="e.g., HP Tenders",
                        size="2",
                        width="100%",
                    ),
                    rx.text("Name of the portal these tenders belong to", size="1", color="gray.10"),
                    align="start",
                    spacing="1",
                ),
                
                # Base URL
                rx.vstack(
                    rx.text("Base URL", size="2", weight="bold"),
                    rx.input(
                        value=ExcelImportState.base_url,
                        on_change=ExcelImportState.set_base_url,
                        placeholder="https://hptenders.gov.in",
                        size="2",
                        width="100%",
                    ),
                    rx.text("Portal website URL", size="1", color="gray.10"),
                    align="start",
                    spacing="1",
                ),
                
                columns="2",
                spacing="4",
                width="100%",
            ),
            
            rx.divider(),
            
            # Import options
            rx.vstack(
                rx.text("Import Options", size="3", weight="bold"),
                
                rx.hstack(
                    rx.switch(
                        checked=ExcelImportState.skip_duplicates,
                        on_change=ExcelImportState.toggle_skip_duplicates,
                        size="2",
                    ),
                    rx.vstack(
                        rx.text("Skip duplicate tenders", size="2", weight="medium"),
                        rx.text(
                            "Check for existing tender IDs and skip duplicates",
                            size="1",
                            color="gray.10",
                        ),
                        spacing="0",
                        align="start",
                    ),
                    align="center",
                    spacing="2",
                ),
                
                rx.hstack(
                    rx.switch(
                        checked=ExcelImportState.validate_data,
                        on_change=ExcelImportState.toggle_validate_data,
                        size="2",
                    ),
                    rx.vstack(
                        rx.text("Validate data before import", size="2", weight="medium"),
                        rx.text(
                            "Check for required fields and data format",
                            size="1",
                            color="gray.10",
                        ),
                        spacing="0",
                        align="start",
                    ),
                    align="center",
                    spacing="2",
                ),
                
                align="start",
                spacing="3",
            ),
            
            spacing="3",
            width="100%",
        ),
    )


def import_action_section() -> rx.Component:
    """Import action buttons and results."""
    return rx.cond(
        ExcelImportState.file_uploaded,
        rx.vstack(
            rx.divider(),
            
            # Action buttons
            rx.hstack(
                rx.button(
                    rx.icon("trash-2"),
                    "Clear",
                    on_click=ExcelImportState.clear_upload,
                    variant="soft",
                    color_scheme="gray",
                    size="3",
                ),
                rx.spacer(),
                rx.button(
                    rx.icon("database"),
                    "Import to Database",
                    on_click=ExcelImportState.start_import,
                    color_scheme="green",
                    size="3",
                    disabled=~ExcelImportState.all_required_mapped | ExcelImportState.importing,
                    loading=ExcelImportState.importing,
                ),
                width="100%",
                align="center",
            ),
            
            # Import progress
            rx.cond(
                ExcelImportState.importing,
                rx.box(
                    rx.vstack(
                        rx.heading("Importing...", size="4", color="blue.11"),
                        rx.progress(
                            value=ExcelImportState.import_progress,
                            max=100,
                            width="100%",
                        ),
                        rx.text(
                            ExcelImportState.import_status,
                            size="2",
                            color="gray.11",
                        ),
                        rx.grid(
                            rx.vstack(
                                rx.text("Processed", size="1", color="gray.10"),
                                rx.text(f"{ExcelImportState.import_processed:,}", size="3", weight="bold", color="blue.11"),
                                spacing="0",
                            ),
                            rx.vstack(
                                rx.text("Imported", size="1", color="gray.10"),
                                rx.text(f"{ExcelImportState.import_success:,}", size="3", weight="bold", color="green.11"),
                                spacing="0",
                            ),
                            rx.vstack(
                                rx.text("Skipped", size="1", color="gray.10"),
                                rx.text(f"{ExcelImportState.import_skipped:,}", size="3", weight="bold", color="yellow.11"),
                                spacing="0",
                            ),
                            rx.vstack(
                                rx.text("Errors", size="1", color="gray.10"),
                                rx.text(f"{ExcelImportState.import_errors:,}", size="3", weight="bold", color="red.11"),
                                spacing="0",
                            ),
                            columns="4",
                            spacing="4",
                            width="100%",
                        ),
                        spacing="3",
                        align="start",
                    ),
                    padding="1.5rem",
                    border_radius="10px",
                    border="1px solid",
                    border_color="blue.6",
                    background="blue.2",
                    width="100%",
                ),
            ),
            
            # Import results
            rx.cond(
                ExcelImportState.import_completed,
                rx.box(
                    rx.vstack(
                        rx.hstack(
                            rx.icon("circle-check", size=28, color="green.9"),
                            rx.heading("Import Completed!", size="4", color="green.11"),
                            spacing="3",
                        ),
                        rx.divider(),
                        rx.grid(
                            rx.vstack(
                                rx.text("Total Rows", size="1", color="gray.10"),
                                rx.text(f"{ExcelImportState.file_rows:,}", size="4", weight="bold"),
                                spacing="0",
                            ),
                            rx.vstack(
                                rx.text("Successfully Imported", size="1", color="gray.10"),
                                rx.text(f"{ExcelImportState.import_success:,}", size="4", weight="bold", color="green.11"),
                                spacing="0",
                            ),
                            rx.vstack(
                                rx.text("Skipped (Duplicates)", size="1", color="gray.10"),
                                rx.text(f"{ExcelImportState.import_skipped:,}", size="4", weight="bold", color="yellow.11"),
                                spacing="0",
                            ),
                            rx.vstack(
                                rx.text("Errors", size="1", color="gray.10"),
                                rx.text(f"{ExcelImportState.import_errors:,}", size="4", weight="bold", color="red.11"),
                                spacing="0",
                            ),
                            columns="4",
                            spacing="4",
                            width="100%",
                        ),
                        rx.text(
                            f"Import time: {ExcelImportState.import_duration}",
                            size="2",
                            color="gray.11",
                        ),
                        rx.hstack(
                            rx.button(
                                rx.icon("database"),
                                "View Data",
                                on_click=rx.redirect("/data"),
                                color_scheme="blue",
                                size="2",
                            ),
                            rx.button(
                                rx.icon("upload"),
                                "Import Another File",
                                on_click=ExcelImportState.clear_upload,
                                variant="soft",
                                size="2",
                            ),
                            spacing="2",
                        ),
                        spacing="3",
                        align="start",
                    ),
                    padding="1.5rem",
                    border_radius="10px",
                    border="1px solid",
                    border_color="green.6",
                    background="green.2",
                    width="100%",
                ),
            ),
            
            # Error messages
            rx.cond(
                ExcelImportState.has_errors,
                rx.callout(
                    rx.vstack(
                        rx.text("Import Errors", size="2", weight="bold"),
                        rx.foreach(
                            ExcelImportState.error_messages,
                            lambda error: rx.text(f"• {error}", size="2"),
                        ),
                        spacing="1",
                        align="start",
                    ),
                    icon="alert-circle",
                    color_scheme="red",
                    size="1",
                ),
            ),
            
            spacing="3",
            width="100%",
        ),
    )


def excel_import_page() -> rx.Component:
    """Main Excel/CSV import page."""
    return rx.box(
        rx.vstack(
            upload_section(),
            file_preview_section(),
            column_mapping_section(),
            import_settings_section(),
            import_action_section(),
            spacing="4",
            width="100%",
        ),
        padding="2rem",
        max_width="1400px",
        margin="0 auto",
        width="100%",
    )
