# utils.py v2.1.4
# General utility functions

import os
import re
import logging
from urllib.parse import urlparse, urljoin

logger = logging.getLogger(__name__)

def sanitise_filename(name):
    """Removes or replaces characters unsuitable for filenames."""
    if not name:
        return "default_filename"
    name = str(name)
    # Replace common invalid chars with underscore
    name = re.sub(r'[\\/*?:"<>|]', '_', name)
    # Replace sequences of whitespace with a single underscore
    name = re.sub(r'\s+', '_', name)
    # Remove leading/trailing underscores, spaces, periods
    name = name.strip('_ .')
    # Limit length to avoid issues on some filesystems
    name = name[:150]
    if not name:
        return "sanitized_filename"
    return name

def get_website_keyword_from_url(url):
    """
    Extracts a usable website keyword from a URL for filenames or keys.
    Generates one from the hostname.
    """
    try:
        if not url:
            return "unknown_site"
        parsed_url = urlparse(url)
        hostname = parsed_url.netloc
        if not hostname:
            path_part = parsed_url.path.split('/')[-1]
            if path_part:
                hostname = path_part

        if not hostname:
             return "unknown_site"

        name = hostname.replace('www.', '').replace('.', '_')
        name = re.sub(r'[^\w_]+', '', name) # Keep only word chars and underscore
        name = re.sub(r'_+', '_', name).strip('_') # Consolidate/strip underscores

        return name.lower() if name else "unknown_site"
    except Exception as e:
        logger.warning(f"Could not parse website keyword from URL '{url}': {e}")
        return "unknown_site"


def generate_tender_urls(original_url, base_url):
    """
    Generates Direct URL and Status URL from the original tender detail link found on list pages.
    Ensures URLs are absolute using the provided base_url context.
    """
    if not original_url or not isinstance(original_url, str):
        logger.warning("generate_tender_urls received invalid input.")
        return {'direct_url': None, 'status_url': None}

    try:
        # Resolve the original URL against the base URL to ensure it's absolute
        abs_original_url = urljoin(base_url, original_url)

        # Generate Direct URL (usually just remove session parameter)
        direct_url = re.sub(r'&session=T', '', abs_original_url)

        # Generate Status URL by replacing the component/page part
        search_patterns = [
            'component=%24DirectLink&page=FrontEndViewTender&service=direct&sp=',
            'component=%24DirectLink_0&page=FrontEndAdvancedSearchResult&service=direct&sp=',
            'component=%24DirectLink&page=FrontEndListTendersbyDate&service=direct&sp=',
            'component=%24DirectLink&page=FrontEndTendersByClassification&service=direct&sp=',
        ]
        replacement = 'component=view&page=WebTenderStatusLists&service=direct&sp='

        status_url = direct_url
        found_pattern = False
        for pattern in search_patterns:
            if pattern in status_url:
                status_url = status_url.replace(pattern, replacement)
                found_pattern = True
                logger.debug(f"Generated status URL using pattern: {pattern}")
                break

        if not found_pattern:
            logger.warning(f"Could not identify a known pattern for generating status URL from: {original_url}")
            status_url = None # Status URL couldn't be generated reliably

        return {'direct_url': direct_url, 'status_url': status_url}

    except Exception as e:
        logger.error(f"Error generating URLs from '{original_url}' relative to '{base_url}': {e}", exc_info=True)
        return {'direct_url': None, 'status_url': None}
