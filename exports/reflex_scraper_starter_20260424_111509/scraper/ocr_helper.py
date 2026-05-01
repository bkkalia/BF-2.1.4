import io
import logging
import re
from PIL import Image, ImageGrab
import pytesseract

logger = logging.getLogger(__name__)

def get_clipboard_image():
    """Get image from clipboard if available."""
    try:
        clipboard_image = ImageGrab.grabclipboard()
        if isinstance(clipboard_image, Image.Image):
            return clipboard_image
        return None
    except Exception as e:
        logger.error(f"Error getting clipboard image: {e}")
        return None

def extract_tender_ids(image, pattern=r'\b(20\d{2}_[A-Z0-9_]+_\d+(_\d+)?)\b'):
    """Extract tender IDs from image using OCR."""
    try:
        # Convert image to text using OCR
        text = pytesseract.image_to_string(image)
        
        # Find all matches
        matches = re.finditer(pattern, text)
        ids = [match.group(1) for match in matches]
        
        # Return unique IDs while preserving order
        seen = set()
        return [x for x in ids if not (x in seen or seen.add(x))]
        
    except Exception as e:
        logger.error(f"Error extracting tender IDs from image: {e}")
        return []
