import tkinter as tk
from tkinter import ttk, scrolledtext, Frame, Label, Button, filedialog, messagebox # Add filedialog, messagebox
import logging
import re
import os
from datetime import datetime
import pandas as pd
import pytesseract
from PIL import Image, ImageGrab

# --- Ensure project root in sys.path ---
import sys
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Update Tesseract path configuration
TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Tesseract-OCR\tesseract.exe",  # Common custom install location
    os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Tesseract-OCR', 'tesseract.exe'),
    os.path.join(os.environ.get('PROGRAMFILES', ''), 'Tesseract-OCR', 'tesseract.exe'),
    os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Tesseract-OCR', 'tesseract.exe'),
]

def _configure_tesseract():
    """Configure Tesseract OCR path."""
    try:
        # First try the default configuration
        test_text = pytesseract.image_to_string(Image.new('RGB', (1, 1)))
        logger.debug("Tesseract working with default configuration")
        return True
    except Exception:
        # If default fails, try each path
        for path in TESSERACT_PATHS:
            if os.path.isfile(path):
                try:
                    pytesseract.pytesseract.tesseract_cmd = path
                    test_text = pytesseract.image_to_string(Image.new('RGB', (1, 1)))
                    logger.info(f"Tesseract configured successfully at: {path}")
                    return True
                except Exception as e:
                    logger.debug(f"Path {path} exists but test failed: {e}")
                    continue
        return False

# --- PDF Library Import ---
# Add a try-except block for PyPDF2 import
# User might need to install it: pip install pypdf2
try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PyPDF2 = None # Set to None if import fails
    PYPDF2_AVAILABLE = False
    logging.warning("PyPDF2 library not found. PDF upload feature will be disabled.")
    # Optionally show a message to the user immediately, or wait until they click the button
# --- End PDF Library Import ---


# Absolute imports from project root
from scraper.logic import search_and_download_tenders
from gui import gui_utils # Absolute import

logger = logging.getLogger(__name__)

class IdSearchTab(ttk.Frame):
    """Frame containing widgets and logic for searching by Tender ID."""

    def __init__(self, parent, main_app_ref, **kwargs):
        super().__init__(parent, **kwargs)
        self.main_app = main_app_ref
        self.log_callback = self.main_app.update_log
        self.portal_var = tk.StringVar(value=self.main_app.base_urls_data[0]['Name'])
        self._create_widgets()

    def _create_widgets(self):
        section = ttk.Labelframe(self, text="Process by Tender ID", style="Section.TLabelframe")
        section.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        # Create frame for text area and line numbers
        text_frame = ttk.Frame(section)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(5, 10))

        # Line numbers text widget
        self.line_numbers = tk.Text(
            text_frame,
            width=4,
            padx=3,
            takefocus=0,
            border=0,
            background='lightgray',
            state='disabled',
            wrap=tk.NONE,
            font=self.main_app.log_font
        )
        self.line_numbers.pack(side=tk.LEFT, fill=tk.Y)

        # Main text area with scrollbar
        self.tender_id_text = scrolledtext.ScrolledText(
            text_frame,
            height=20,
            width=40,
            wrap=tk.WORD,
            font=self.main_app.log_font,
            borderwidth=1,
            relief="solid"
        )
        self.tender_id_text.pack(fill=tk.BOTH, expand=True)

        # Bind events for line numbers
        self.tender_id_text.bind('<KeyPress>', self._on_text_change)
        self.tender_id_text.bind('<KeyRelease>', self._on_text_change)
        self.tender_id_text.bind('<MouseWheel>', self._on_text_scroll)

        # Initial line numbers
        self._update_line_numbers()

        # Main Button Frame
        main_button_frame = ttk.Frame(section)
        main_button_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        self.start_search_id_button = ttk.Button(
            main_button_frame,
            text="Start Search by ID",
            command=self.start_search_ids,
            style="Accent.TButton",
            width=22
        )
        self.start_search_id_button.pack(side=tk.LEFT, padx=(0, 10))

        self.save_button = ttk.Button(
            main_button_frame,
            text="Save IDs",
            command=self.save_ids_to_file,
            width=12
        )
        self.save_button.pack(side=tk.LEFT, padx=(0, 10))

        self.clear_button = ttk.Button(
            main_button_frame,
            text="Clear Input",
            command=lambda: self.tender_id_text.delete("1.0", tk.END),
            width=12
        )
        self.clear_button.pack(side=tk.LEFT)

        # Extraction Buttons Frame
        extract_frame = ttk.LabelFrame(section, text="Import IDs from:")
        extract_frame.pack(fill=tk.X, padx=5, pady=(0, 10))

        # Add extraction buttons
        btn_width = 15
        btn_padding = 5

        self.image_button = ttk.Button(
            extract_frame,
            text="Image",
            command=self.extract_ids_from_image,
            width=btn_width
        )
        self.image_button.pack(side=tk.LEFT, padx=(btn_padding, btn_padding), pady=5)

        self.excel_button = ttk.Button(
            extract_frame,
            text="Excel File",
            command=self.extract_ids_from_excel,
            width=btn_width
        )
        self.excel_button.pack(side=tk.LEFT, padx=btn_padding, pady=5)

        self.text_button = ttk.Button(
            extract_frame,
            text="Text File",
            command=self.extract_ids_from_textfile,
            width=btn_width
        )
        self.text_button.pack(side=tk.LEFT, padx=btn_padding, pady=5)

        if PYPDF2_AVAILABLE:
            self.pdf_button = ttk.Button(
                extract_frame,
                text="PDF File",
                command=self.upload_and_extract_ids,
                width=btn_width
            )
            self.pdf_button.pack(side=tk.LEFT, padx=btn_padding, pady=5)

        section.columnconfigure(0, weight=1)
        section.rowconfigure(1, weight=1)

    def _on_text_change(self, event=None):
        """Update line numbers when text changes."""
        self._update_line_numbers()

    def _on_text_scroll(self, event=None):
        """Sync line numbers with main text scroll."""
        self.line_numbers.yview_moveto(self.tender_id_text.yview()[0])
        return "break"

    def _update_line_numbers(self):
        """Update the line numbers display."""
        if not hasattr(self, 'line_numbers'):
            return

        # Get the total lines of text
        final_index = self.tender_id_text.index("end-1c")
        num_of_lines = int(final_index.split('.')[0])

        # Generate line numbers
        line_numbers_text = '\n'.join(str(i).rjust(3) for i in range(1, num_of_lines + 1))

        # Update line numbers widget
        self.line_numbers.configure(state='normal')
        self.line_numbers.delete(1.0, tk.END)
        self.line_numbers.insert(1.0, line_numbers_text)
        self.line_numbers.configure(state='disabled')

        # Sync scroll position
        self.line_numbers.yview_moveto(self.tender_id_text.yview()[0])

    def _enable_text_scrolling(self, widget):
        def _on_mousewheel(event):
            if event.delta:
                widget.yview_scroll(int(-1*(event.delta/120)), "units")
            elif event.num == 4:
                widget.yview_scroll(-1, "units")
            elif event.num == 5:
                widget.yview_scroll(1, "units")
            return "break"
        widget.bind("<MouseWheel>", _on_mousewheel)
        widget.bind("<Button-4>", _on_mousewheel)
        widget.bind("<Button-5>", _on_mousewheel)

    def extract_ids_from_image(self):
        """Extract tender IDs from clipboard first, then from image file if needed."""
        try:
            # First try clipboard
            try:
                clipboard_image = ImageGrab.grabclipboard()
                if isinstance(clipboard_image, Image.Image):
                    self.log_callback("Found image in clipboard, processing...")
                    return self._process_image(clipboard_image, "clipboard")
                elif isinstance(clipboard_image, list) and clipboard_image:  # List of file paths
                    if any(path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')) 
                           for path in clipboard_image):
                        img_path = next(path for path in clipboard_image 
                                      if path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')))
                        self.log_callback(f"Found image path in clipboard: {img_path}")
                        return self._process_image(Image.open(img_path), "clipboard file")
            except Exception as clip_err:
                self.log_callback(f"No valid image in clipboard: {clip_err}")

            # If clipboard fails, show file dialog
            filepath = filedialog.askopenfilename(
                title="Select Image File",
                filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.tiff")],
                parent=self.main_app.root
            )
            if not filepath:
                self.log_callback("Image file selection cancelled.")
                return

            return self._process_image(Image.open(filepath), os.path.basename(filepath))

        except Exception as e:
            self.log_callback(f"Error in image extraction: {e}")
            messagebox.showerror("Image Error", str(e), parent=self.main_app.root)

    def _process_image(self, image, source="unknown"):
        """Process image and extract tender IDs with enhanced detection."""
        if not _configure_tesseract():
            error_msg = (
                "Tesseract OCR not found or not working.\n\n"
                "1. Download Tesseract installer from:\n"
                "   https://github.com/UB-Mannheim/tesseract/wiki\n\n"
                "2. Install with default settings (important!)"
            )
            self.log_callback("Tesseract OCR configuration failed")
            messagebox.showerror("Tesseract Not Found", error_msg, parent=self.main_app.root)
            return False

        try:
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Try different OCR configurations to improve accuracy
            configs = [
                '--psm 6 --oem 3 -c preserve_interword_spaces=1',  # Uniform block with preserved spacing
                '--psm 4 --oem 3 -c preserve_interword_spaces=1',  # Single column with preserved spacing
                '--psm 3 --oem 3 -c preserve_interword_spaces=1',  # Auto with preserved spacing
                '--psm 11 --oem 3 -c preserve_interword_spaces=1', # Sparse text with preserved spacing
                '--psm 13 --oem 3 -c preserve_interword_spaces=1'  # Raw line with preserved spacing
            ]
            
            texts = []
            for config in configs:
                text = pytesseract.image_to_string(image, config=config)
                if text.strip():
                    # Clean OCR artifacts and standardize separators
                    text = re.sub(r'[,|]', ' ', text)  # Replace commas and vertical bars with spaces
                    text = re.sub(r'\s+', ' ', text)   # Standardize spaces
                    texts.append(text)

            # Combine all extracted texts
            full_text = '\n'.join(texts)

            # Enhanced pattern matching for numeric department codes and IDs
            patterns = [
                # Handle both with and without version numbers
                r'\b(20\d{2})[_\s]([A-Z0-9]{2,})[_\s](\d{5,6})(?:[_\s](\d+))?\b',
                # Handle variations in separators
                r'\b(20\d{2})[_\s.-]([A-Z0-9]{2,})[_\s.-](\d{5,6})(?:[_\s.-](\d+))?\b'
            ]
            
            matches_with_pos = []
            for pattern in patterns:
                for match in re.finditer(pattern, full_text):
                    year, dept, num, ver = match.groups()
                    # Construct standardized ID
                    tender_id = f"{year}_{dept}_{num}"
                    if ver:  # Add version if present
                        tender_id += f"_{ver}"
                    
                    # Get line number for position tracking
                    line_num = full_text.count('\n', 0, match.start())
                    matches_with_pos.append((line_num, tender_id))

            # Remove duplicates while preserving order and line position
            seen = set()
            matches_with_pos = [(pos, id) for pos, id in matches_with_pos 
                              if not (id in seen or seen.add(id))]

            # Sort by line number to maintain top-to-bottom order
            matches_with_pos.sort(key=lambda x: x[0])
            found_ids = [id for _, id in matches_with_pos]

            if not found_ids:
                self.log_callback(f"No tender IDs found in {source}")
                messagebox.showinfo("No IDs Found", 
                                  "No text matching the Tender ID pattern was found.", 
                                  parent=self.main_app.root)
                return False

            # Get existing IDs to avoid duplicates
            existing_ids = self.get_tender_ids_from_input()
            existing_ids_set = set(existing_ids)
            
            # Filter out duplicates while maintaining order
            new_ids = [id for id in found_ids if id not in existing_ids_set]
            
            if not new_ids:
                self.log_callback(f"No new Tender IDs found in {source} (all IDs already exist)")
                messagebox.showinfo("No New IDs", 
                                  "All found IDs already exist in the list.", 
                                  parent=self.main_app.root)
                return False

            # Add new IDs to text area
            current_text = self.tender_id_text.get("1.0", tk.END).strip()
            next_line_num = len(current_text.splitlines()) + 1 if current_text else 1
            
            separator = "\n" if current_text else ""
            new_ids_text = separator + "\n".join(new_ids)
            self.tender_id_text.insert(tk.END, new_ids_text + "\n")
            
            self.log_callback(f"Added {len(new_ids)} new Tender IDs from {source}")
            self.main_app.update_status(f"Added {len(new_ids)} new IDs from {source}")
            
            # Show success message
            success_msg = f"Successfully extracted and added {len(new_ids)} new unique Tender IDs from {source}."
            messagebox.showinfo("IDs Added", success_msg, parent=self.main_app.root)
            
            # Update line numbers
            self._update_line_numbers()
            
            return True

        except Exception as e:
            self.log_callback(f"Error processing image: {e}")
            messagebox.showerror("Processing Error", str(e), parent=self.main_app.root)
            return False

    def extract_ids_from_excel(self):
        """Extract tender IDs from Excel or CSV files."""
        try:
            filepath = filedialog.askopenfilename(
                title="Select Excel/CSV File",
                filetypes=[
                    ("Excel Files", "*.xlsx *.xls"),
                    ("CSV Files", "*.csv"),
                    ("All Supported", "*.xlsx *.xls *.csv")
                ],
                parent=self.main_app.root
            )
            if not filepath:
                self.log_callback("File selection cancelled.")
                return

            # Read file based on extension
            if filepath.lower().endswith('.csv'):
                # Try different encodings and delimiters for CSV
                encodings = ['utf-8', 'cp1252', 'iso-8859-1']
                delimiters = [',', ';', '\t']
                df = None
                
                for enc in encodings:
                    for delim in delimiters:
                        try:
                            df = pd.read_csv(filepath, encoding=enc, sep=delim)
                            if not df.empty:
                                break
                        except Exception:
                            continue
                    if df is not None and not df.empty:
                        break
                
                if df is None or df.empty:
                    raise ValueError("Could not read CSV file with any encoding/delimiter combination")
            else:
                df = pd.read_excel(filepath)

            # Enhanced ID extraction from dataframe
            pattern = r'\b(20\d{2}_[A-Z0-9_]+_\d+(_\d+)?)\b'
            found_ids = set()

            # Process each cell in the dataframe
            for column in df.columns:
                # Convert column to string and search for IDs
                df[column] = df[column].astype(str)
                # Extract IDs from each cell
                ids = df[column].str.extractall(pattern)
                if not ids.empty:
                    found_ids.update(ids[0].tolist())

            if not found_ids:
                self.log_callback("No tender IDs found in the file.")
                messagebox.showinfo("No IDs Found", 
                                  "No text matching the Tender ID pattern was found.", 
                                  parent=self.main_app.root)
                return

            # Add to text area
            current_text = self.tender_id_text.get("1.0", tk.END).strip()
            separator = "\n" if current_text else ""
            new_ids = "\n".join(sorted(found_ids))
            self.tender_id_text.insert(tk.END, separator + new_ids + "\n")
            
            # Show success message
            success_msg = f"Successfully extracted and added {len(found_ids)} unique Tender IDs from {os.path.basename(filepath)}."
            messagebox.showinfo("IDs Added", success_msg, parent=self.main_app.root)
            
            self.log_callback(f"Added {len(found_ids)} unique Tender IDs from {os.path.basename(filepath)}")
            self.main_app.update_status(f"Added {len(found_ids)} IDs from file")
            self._update_line_numbers()

        except Exception as e:
            self.log_callback(f"Error processing file: {e}")
            messagebox.showerror("File Error", str(e), parent=self.main_app.root)

    def extract_ids_from_textfile(self):
        """Extract tender IDs from a text file."""
        filepath = filedialog.askopenfilename(
            title="Select Text File",
            filetypes=[("Text Files", "*.txt")],
            parent=self.main_app.root
        )
        if not filepath:
            self.log_callback("Text file selection cancelled.")
            return

        try:
            with open(filepath, 'r') as file:
                content = file.read()
                num_lines = len([line for line in content.splitlines() if line.strip()])
                current_text = self.tender_id_text.get("1.0", tk.END).strip()
                separator = "\n" if current_text else ""
                self.tender_id_text.insert(tk.END, separator + content + "\n")
                
                # Show success message
                success_msg = f"Successfully added {num_lines} lines from {os.path.basename(filepath)}."
                messagebox.showinfo("Content Added", success_msg, parent=self.main_app.root)
                
                self.log_callback(f"Content from {os.path.basename(filepath)} added to the list.")
                self._update_line_numbers()

        except Exception as e:
            self.log_callback(f"Error reading text file: {e}")
            messagebox.showerror("File Error", f"Could not read the text file.\n\nError: {e}", parent=self.main_app.root)

    def get_tender_ids_from_input(self):
        """Extracts and cleans tender IDs from the text area."""
        ids_text = self.tender_id_text.get("1.0", tk.END).strip()
        if not ids_text: return []
        tender_ids = []
        # Split by lines first, then by comma or whitespace within each line
        for line in ids_text.splitlines():
            line_ids = re.split(r'[,\s]+', line.strip())
            tender_ids.extend([tid for tid in line_ids if tid]) # Filter out empty strings
        if not tender_ids: logger.warning("No valid Tender IDs found after parsing input.")
        else: logger.info(f"Parsed {len(tender_ids)} potential Tender IDs from input.")
        # Return unique IDs while preserving order as much as possible
        seen = set()
        unique_ids = [x for x in tender_ids if not (x in seen or seen.add(x))]
        return unique_ids

    def upload_and_extract_ids(self):
        """Handles PDF upload, text extraction, and ID identification."""
        if not PYPDF2_AVAILABLE:
            messagebox.showerror("Missing Library", "The PDF processing library (PyPDF2) is not installed.\nPlease install it using 'pip install pypdf2' to enable this feature.", parent=self.main_app.root)
            return

        filepath = filedialog.askopenfilename(
            title="Select PDF File",
            filetypes=[("PDF Files", "*.pdf")],
            parent=self.main_app.root
        )
        if not filepath:
            self.log_callback("PDF selection cancelled.")
            return

        self.log_callback(f"Processing PDF: {os.path.basename(filepath)}")
        self.main_app.update_status(f"Extracting IDs from {os.path.basename(filepath)}...")

        extracted_text = ""
        try:
            if not PyPDF2:
                raise ImportError("PyPDF2 library is not available")
            with open(filepath, 'rb') as pdf_file:
                reader = PyPDF2.PdfReader(pdf_file)
                num_pages = len(reader.pages)
                self.log_callback(f"  PDF has {num_pages} pages.")
                for page_num in range(num_pages):
                    page = reader.pages[page_num]
                    extracted_text += page.extract_text() + "\n" # Add newline between pages
            self.log_callback("  Finished text extraction from PDF.")
        except Exception as e:
            logger.error(f"Error reading PDF file '{filepath}': {e}", exc_info=True)
            messagebox.showerror("PDF Error", f"Could not read or process the PDF file.\n\nError: {e}", parent=self.main_app.root)
            self.main_app.update_status("Error reading PDF.")
            return

        if not extracted_text:
            self.log_callback("  No text could be extracted from the PDF.")
            messagebox.showwarning("Extraction Warning", "No text could be extracted from the selected PDF.\nIt might be image-based or protected.", parent=self.main_app.root)
            self.main_app.update_status("No text extracted from PDF.")
            return

        # Regex to find Tender IDs (YYYY_DEPT_NUM_VER)
        # \b ensures word boundaries
        # (20\d{2}) captures the year (starting with 20)
        # _ matches literal underscore
        # ([A-Z0-9_]+) captures department/org code (alphanumeric and underscore)
        # _ matches literal underscore
        # (\d+) captures the main number part
        # (_\d+)? optionally captures the version part (_ followed by digits)
        tender_id_pattern = re.compile(r'\b(20\d{2}_[A-Z0-9_]+_\d+(_\d+)?)\b')
        found_ids = tender_id_pattern.findall(extracted_text)

        # findall returns tuples if groups are used, extract the full match (group 0 implicitly, or group 1 if using outer parens)
        # Adjusting to get the full matched string
        full_matches = [match[0] for match in found_ids if match[0]] # Get the first element of the tuple which is the full match

        if not full_matches:
            self.log_callback("  No potential Tender IDs matching the pattern found in the PDF text.")
            messagebox.showinfo("No IDs Found", "No text matching the Tender ID pattern (e.g., 2025_ABC_12345_1) was found in the PDF.", parent=self.main_app.root)
            self.main_app.update_status("No matching IDs found in PDF.")
            return

        # Get existing IDs from the text area to avoid duplicates
        existing_ids_list = self.get_tender_ids_from_input()
        existing_ids_set = set(existing_ids_list)

        new_ids_found = []
        unique_found_ids = set(full_matches) # Get unique IDs from the PDF

        for tid in unique_found_ids:
            if tid not in existing_ids_set:
                new_ids_found.append(tid)

        if not new_ids_found:
            self.log_callback(f"  Found {len(unique_found_ids)} unique potential IDs, but all were already present.")
            messagebox.showinfo("IDs Already Present", f"Found {len(unique_found_ids)} potential IDs, but they are already in the input list.", parent=self.main_app.root)
            self.main_app.update_status("IDs from PDF already listed.")
            return

        # Append new unique IDs to the text area
        current_text = self.tender_id_text.get("1.0", tk.END).strip()
        separator = "\n" if current_text else "" # Add newline only if text area isn't empty
        ids_to_add_str = "\n".join(new_ids_found)

        self.tender_id_text.insert(tk.END, separator + ids_to_add_str + "\n")
        self.log_callback(f"  Added {len(new_ids_found)} new unique Tender IDs from PDF to the list.")
        self.main_app.update_status(f"Added {len(new_ids_found)} IDs from PDF.")
        messagebox.showinfo("IDs Added", f"Successfully extracted and added {len(new_ids_found)} new unique Tender IDs to the list.", parent=self.main_app.root)

    def start_search_ids(self):
        """Start the search process for entered tender IDs."""
        try:
            tender_ids = self.get_tender_ids_from_input()
            if not tender_ids:
                return

            # Use selected portal's URL config
            selected_portal = self.portal_var.get()
            url_config = next(
                (url for url in self.main_app.base_urls_data if url['Name'] == selected_portal),
                self.main_app.base_urls_data[0]
            )

            logger.info(f"Starting Search & Download for {len(tender_ids)} ID(s). Base download dir: {self.main_app.download_dir_var.get()}")
            
            # Get current URL config and download directory
            download_dir = self.main_app.download_dir_var.get()
            
            # Validate download directory before starting
            if not self.main_app.validate_download_dir(download_dir):
                return

            # Start background task with only the required positional arguments
            self.main_app.start_background_task(
                self._search_worker,
                args=(tender_ids, url_config, download_dir),
                task_name="Tender ID Search"
            )
            
        except Exception as e:
            logger.error(f"Error starting ID search: {e}", exc_info=True)
            self.main_app.update_log(f"Error starting search: {e}")

    def _search_worker(self, tender_ids, base_url_config, download_dir, **kwargs):
        """Worker function to process tender ID search."""
        try:
            from scraper.logic import search_and_download_tenders
            return search_and_download_tenders(
                tender_ids=tender_ids,
                base_url_config=base_url_config,
                download_dir=download_dir,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Error in tender ID search worker: {e}", exc_info=True)
            raise

    def save_ids_to_file(self):
        """Save the current IDs to a text file."""
        try:
            # Get all IDs from text area
            ids_text = self.tender_id_text.get("1.0", tk.END).strip()
            if not ids_text:
                messagebox.showwarning("No Content", "No IDs to save.", parent=self.main_app.root)
                return

            # Show save file dialog
            filename = datetime.now().strftime("Tender_IDs_%Y%m%d_%H%M%S.txt")
            filepath = filedialog.asksaveasfilename(
                defaultextension=".txt",
                initialfile=filename,
                filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
                parent=self.main_app.root
            )
            
            if not filepath:
                return  # User cancelled

            # Save to file
            with open(filepath, 'w') as f:
                f.write(ids_text)

            self.log_callback(f"IDs saved to: {filepath}")
            messagebox.showinfo(
                "Save Complete", 
                f"IDs saved successfully to:\n{filepath}", 
                parent=self.main_app.root
            )

        except Exception as e:
            self.log_callback(f"Error saving IDs: {e}")
            messagebox.showerror(
                "Save Error",
                f"Could not save IDs.\nError: {e}",
                parent=self.main_app.root
            )

def search_and_download_tenders(tender_ids, base_url_config, download_dir, driver,
                              log_callback=None, progress_callback=None, timer_callback=None, 
                              status_callback=None, stop_event=None, deep_scrape=False,
                              dl_more_details=True, dl_zip=True, dl_notice_pdfs=True):
    """Search and download tender details for given IDs."""
    if not driver:
        raise ValueError("WebDriver instance must be provided")

    try:
        total_tenders = len(tender_ids)
        processed_tenders = 0
        start_time = datetime.now()

        if log_callback:
            log_callback(f"Starting tender search for {total_tenders} IDs...")

        # Pass our driver instance to navigation functions
        for tender_id in tender_ids:
            if stop_event and stop_event.is_set():
                break

            try:
                # Use existing driver instance
                driver.get(base_url_config['BaseURL'])
                # ...rest of existing search logic...
            except Exception as e:
                if log_callback:
                    log_callback(f"Error processing tender ID {tender_id}: {e}")
                continue

    except Exception as e:
        if log_callback:
            log_callback(f"Error during tender ID search: {e}")
        raise
    finally:
        logger.debug("Tender ID search worker finished")