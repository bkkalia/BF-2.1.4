# app_settings.py v2.2.1
# Handles loading/saving settings.json and reading base_urls.csv, using absolute paths.

import json
import csv
import os
import logging
from config import ( # Absolute imports from project root
    FALLBACK_BASE_URL, FALLBACK_URL_KEY,
    DEFAULT_THEME, USE_UNDETECTED_DRIVER_DEFAULT, HEADLESS_MODE_DEFAULT,
    DEEP_SCRAPE_DEPARTMENTS_DEFAULT, CONFIGURABLE_TIMEOUTS,
    PAGE_LOAD_TIMEOUT, ELEMENT_WAIT_TIMEOUT, STABILIZE_WAIT, POST_ACTION_WAIT,
    POST_CAPTCHA_WAIT, CAPTCHA_CHECK_TIMEOUT, DOWNLOAD_WAIT_TIMEOUT, POPUP_WAIT_TIMEOUT,
    POST_DOWNLOAD_CLICK_WAIT
)
from utils import get_website_keyword_from_url # Import utility
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

# Initialize timeout settings from config.py constants
_initial_timeout_settings = {
    key: globals().get(key, 0) for key in CONFIGURABLE_TIMEOUTS
}

# Default settings structure (download dir will be set by load_settings)
DEFAULT_SETTINGS_STRUCTURE = {
    "version": "1.1",
    "download_directory": None,
    "selected_url_name": None,
    "window_geometry": "1150x780",
    "dl_more_details": True,
    "dl_zip": True,
    "dl_notice_pdfs": True,
    "deep_scrape_departments": DEEP_SCRAPE_DEPARTMENTS_DEFAULT,
    "selected_theme": DEFAULT_THEME,
    "use_undetected_driver": USE_UNDETECTED_DRIVER_DEFAULT,
    "headless_mode": HEADLESS_MODE_DEFAULT,
    "department_parallel_workers": 1,
    "batch_delta_mode": "quick",
    "refresh_watch_enabled": False,
    "refresh_watch_loop_seconds": 30,
    "refresh_watch_portals": [],
    "refresh_watch_state": {},
    "refresh_watch_history": [],
    "central_sqlite_db_path": None,
    "sqlite_backup_directory": None,
    "sqlite_backup_retention_days": 30,
    "excel_export_policy": "on_demand",
    "excel_export_interval_days": 2,
    **_initial_timeout_settings  # Unpack all timeout settings
}

FALLBACK_URL_CONFIG = {
    "Name": "HP Tenders (Fallback)",
    "BaseURL": FALLBACK_BASE_URL,
    "OrgListURL": urljoin(FALLBACK_BASE_URL, "?page=FrontEndTendersByOrganisation&service=page"),
    "Keyword": FALLBACK_URL_KEY
}

def load_settings(settings_filepath, default_download_dir):
    """
    Loads settings from settings_filepath. Uses default_download_dir if needed.
    Ensures download path in settings is absolute.
    """
    settings = DEFAULT_SETTINGS_STRUCTURE.copy()
    settings["download_directory"] = default_download_dir # Set calculated default

    if os.path.exists(settings_filepath):
        try:
            with open(settings_filepath, 'r', encoding='utf-8') as f:
                loaded_settings = json.load(f)

            # Process loaded settings, keeping defaults for missing keys
            for key in DEFAULT_SETTINGS_STRUCTURE:
                if key in loaded_settings:
                    settings[key] = loaded_settings[key]

            # Special handling for download directory
            if settings["download_directory"] and not os.path.isabs(settings["download_directory"]):
                script_dir = os.path.dirname(settings_filepath)
                settings["download_directory"] = os.path.normpath(os.path.join(script_dir, settings["download_directory"]))

            logger.info(f"Settings loaded and merged with defaults from {settings_filepath}")

        except (json.JSONDecodeError, IOError, TypeError, KeyError) as e:
            logger.warning(f"Failed to load or parse settings from {settings_filepath}: {e}. Using defaults and saving.")
            # Set download dir back to default before saving
            settings["download_directory"] = default_download_dir
            save_settings(settings, settings_filepath)
    else:
        logger.info(f"{os.path.basename(settings_filepath)} not found. Creating with default settings at: {settings_filepath}")
        save_settings(settings, settings_filepath) # Save defaults

    # Ensure a selected URL name exists (fallback if needed after base_urls loaded)
    if not settings.get("selected_url_name"):
        settings["selected_url_name"] = FALLBACK_URL_CONFIG["Name"] # Default to fallback name initially

    return settings

def save_settings(settings, settings_filepath):
    """Saves the provided settings dictionary to settings_filepath."""
    try:
        os.makedirs(os.path.dirname(settings_filepath), exist_ok=True)
        
        # Ensure download path is absolute
        dl_dir = settings.get("download_directory")
        if dl_dir and not os.path.isabs(dl_dir):
            script_dir = os.path.dirname(settings_filepath)
            settings["download_directory"] = os.path.normpath(os.path.join(script_dir, dl_dir))

        # Write settings with proper encoding and flush
        with open(settings_filepath, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())  # Force write to disk
            
        logger.info(f"Settings saved successfully to {settings_filepath}")
        return True
    except Exception as e:
        logger.error(f"Failed to save settings to {settings_filepath}: {e}", exc_info=True)
        return False

def load_base_urls(csv_filepath):
    """Loads base URL configurations from a CSV file."""
    urls_data = []
    org_list_suffix = "?page=FrontEndTendersByOrganisation&service=page" # Define suffix
    try:
        with open(csv_filepath, mode='r', newline='', encoding='utf-8') as csvfile:
            # Expecting columns: Name, BaseURL, Keyword (OrgListURL removed)
            reader = csv.DictReader(csvfile)
            if not all(col in reader.fieldnames for col in ['Name', 'BaseURL', 'Keyword']):
                 logger.error(f"CSV '{os.path.basename(csv_filepath)}' missing required columns: Name, BaseURL, Keyword.")
                 return [] # Return empty if columns missing

            for row in reader:
                base_url = row.get('BaseURL', '').strip()
                if base_url:
                    # Generate OrgListURL dynamically
                    org_list_url = urljoin(base_url, org_list_suffix)
                    urls_data.append({
                        'Name': row.get('Name', '').strip(),
                        'BaseURL': base_url,
                        'OrgListURL': org_list_url, # Add the generated URL
                        'Keyword': row.get('Keyword', '').strip()
                    })
                else:
                    logger.warning(f"Skipping row in {os.path.basename(csv_filepath)} due to missing BaseURL: {row}")
        logger.info(f"Loaded {len(urls_data)} base URL configurations from {os.path.basename(csv_filepath)}.")
        # Sort by Name for consistent dropdown order
        urls_data.sort(key=lambda x: x.get('Name', '').lower())
        return urls_data
    except FileNotFoundError:
        logger.warning(f"Base URLs file not found: {csv_filepath}. Using fallback or defaults.")
        return []
    except Exception as e:
        logger.error(f"Error reading base URLs file '{csv_filepath}': {e}", exc_info=True)
        return []

def append_base_url(csv_filepath, name, base_url):
    """Appends a new base URL configuration to the CSV file."""
    if not name or not base_url or not base_url.startswith(('http://', 'https://')):
        logger.error(f"Invalid data provided for appending to CSV: Name='{name}', BaseURL='{base_url}'")
        return False, "Invalid name or URL provided."

    keyword = get_website_keyword_from_url(base_url)
    new_row = {'Name': name, 'BaseURL': base_url, 'Keyword': keyword}
    file_exists = os.path.isfile(csv_filepath)

    try:
        # Check if URL already exists
        existing_urls = load_base_urls(csv_filepath) # Use existing loader
        for existing in existing_urls:
            if existing.get('BaseURL') == base_url:
                logger.warning(f"URL '{base_url}' already exists in {os.path.basename(csv_filepath)}. Not appending.")
                return False, f"URL already exists: {base_url}"

        # Append the new row
        with open(csv_filepath, mode='a', newline='', encoding='utf-8') as csvfile:
            # Define fieldnames - ensure consistency
            fieldnames = ['Name', 'BaseURL', 'Keyword']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            # Write header only if file didn't exist or was empty before opening in 'a' mode
            if not file_exists or os.path.getsize(csv_filepath) == 0:
                writer.writeheader()
            writer.writerow(new_row)
        logger.info(f"Appended new URL to {os.path.basename(csv_filepath)}: Name='{name}', BaseURL='{base_url}'")
        return True, f"Successfully added '{name}'."
    except Exception as e:
        logger.error(f"Error appending to base URLs file '{csv_filepath}': {e}", exc_info=True)
        return False, f"Error saving to CSV: {e}"

def get_url_config(url_name, base_urls_data):
    """Retrieves the URL configuration dictionary for the given name."""
    config = base_urls_data.get(url_name)
    if not config:
        logger.warning(f"URL configuration name '{url_name}' not found. Returning fallback.")
        # Try finding the fallback name in the loaded data first
        fallback_config = base_urls_data.get(FALLBACK_URL_CONFIG["Name"])
        if (fallback_config):
             return fallback_config.copy()
        # If even the fallback isn't there (e.g., empty csv), return the hardcoded one
        return FALLBACK_URL_CONFIG.copy()
    return config.copy() # Return a copy