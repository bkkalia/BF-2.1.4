# AI ASSISTANT GUIDELINES FOR CLOUD84 TENDER SCRAPER

## PROJECT IDENTITY
**ALWAYS REMEMBER**: This is a Python desktop application for scraping government tender data. NOT a web application, NOT a game, NOT a React app.

## TECHNOLOGY CONSTRAINTS
### ✅ ALLOWED TECHNOLOGIES
- Python 3.7+ code only
- Tkinter for GUI components
- pandas for data manipulation
- Selenium for web scraping
- openpyxl for Excel operations
- Standard Python libraries

### ❌ FORBIDDEN TECHNOLOGIES
- JavaScript, HTML, CSS files
- React, Angular, Vue.js components
- Node.js, Express, web servers
- Game development libraries
- Brain training or cognitive games
- Web-based dashboards or SPAs

## ERROR PREVENTION RULES
1. **Always check attribute existence** with `hasattr()` before accessing
2. **Use None-safe operations** for potentially None values
3. **Remove duplicate method definitions** - check for existing methods
4. **Validate DataFrame existence** before operations
5. **Handle string/None type issues** with proper type checking

## WHEN USER REQUESTS UPDATES

### Dashboard/UI Improvements → `gui/tab_search.py`
- Enhance Tkinter widgets (Treeview, Frame, Button)
- Improve pandas DataFrame filtering
- Add new search/filter capabilities
- Optimize data display and sorting
- **Always validate widget attributes exist**

### Data Processing → pandas operations
- DataFrame filtering and manipulation
- Date parsing and filtering
- Search across multiple columns
- Data aggregation and statistics
- **Check for None DataFrames before operations**

### Scraping Features → `scraper/logic.py`
- Selenium WebDriver enhancements
- New portal support
- Error handling improvements
- Data extraction optimization

### Settings/Config → `app_settings.py`, `config.py`
- User preference management
- Configuration file handling
- Default value management

## COMMON REQUEST MAPPINGS
| User Request | Target File | Technology |
|--------------|-------------|------------|
| "Improve dashboard" | `gui/tab_search.py` | Tkinter widgets |
| "Better filtering" | `gui/tab_search.py` | pandas operations |
| "Add date picker" | `gui/tab_search.py` | Tkinter DateEntry |
| "Export features" | `gui/tab_search.py` | openpyxl, pandas |
| "URL management" | `gui/tab_url_process.py` | Tkinter forms |
| "Search functionality" | `gui/tab_search.py` | pandas string operations |
| "Data sorting" | `gui/tab_search.py` | pandas sort_values |

## CODE STYLE GUIDELINES
1. Use proper Python file headers with filepath comments
2. Import statements at the top following Python conventions
3. Class methods with docstrings
4. Error handling with try/except blocks
5. Logging for debugging and user feedback
6. Tkinter event binding for user interactions
7. **Type checking and None validation**
8. **Attribute existence validation**

## CRITICAL ERROR PATTERNS TO AVOID
- ❌ Accessing attributes without `hasattr()` check
- ❌ Operating on None DataFrames without validation
- ❌ Duplicate method definitions
- ❌ String operations on potentially None values
- ❌ Creating web files (.js, .html, .css)

## RED FLAGS - NEVER SUGGEST
- Creating .js, .html, .css files
- React components or JSX syntax
- Web framework installations
- Browser-based solutions
- Game mechanics or scoring systems
- Client-server architectures

## VALIDATION CHECKLIST
Before providing any code solution, verify:
- [ ] Is this Python code for a desktop application?
- [ ] Am I working with Tkinter widgets, not web components?
- [ ] Is the solution related to data scraping/filtering?
- [ ] Am I enhancing the search dashboard functionality?
- [ ] No web technologies mentioned?
- [ ] Are all attribute accesses safe with hasattr()?
- [ ] Are DataFrame operations checking for None?
- [ ] No duplicate methods being created?

## FILE MODIFICATION PRIORITIES
1. **High Priority**: `gui/tab_search.py` (main user interface)
2. **Medium Priority**: `main.py`, `app_settings.py` (core functionality)
3. **Low Priority**: `config.py`, `scraper/logic.py` (infrastructure)
4. **Never Create**: Any .js, .html, .css files

## EXAMPLE PROPER RESPONSES
✅ "I'll update the search filtering in `gui/tab_search.py` using pandas DataFrame operations with None checking..."
✅ "Let me enhance the Tkinter Treeview widget with hasattr() validation..."
✅ "I'll add a date range picker using Tkinter widgets with proper error handling..."

❌ "Let me create a React component for the dashboard..."
❌ "I'll add JavaScript for dynamic filtering..."
❌ "Let's build a web API for the data..."
