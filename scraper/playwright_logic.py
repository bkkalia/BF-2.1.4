import os
import re
from urllib.parse import urljoin


def _sanitize_direct_url(url_value: str) -> str:
    direct_url = str(url_value or "").strip()
    if not direct_url:
        return ""
    direct_url = re.sub(r'([?&])session=T(&)?', lambda m: m.group(1) if not m.group(2) else m.group(1), direct_url)
    direct_url = direct_url.replace("&&", "&").rstrip("?&")
    return direct_url


def fetch_department_list_from_site_playwright(target_url, log_callback=None):
    """Fetch department rows using Playwright (JS-capable alternative for discovery stage)."""
    log_callback = log_callback or (lambda _msg: None)

    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    except Exception as import_err:
        log_callback(f"Playwright import failed: {import_err}")
        return None, 0

    departments = []
    total_tenders = 0

    log_callback(f"Playwright: Fetching departments from base URL: {target_url}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()
            page.set_default_timeout(45000)

            log_callback("Playwright: Navigating to target page...")
            page.goto(target_url, wait_until="domcontentloaded")

            org_link = page.locator("a[href*='FrontEndTendersByOrganisation']").first
            if org_link.count() > 0:
                log_callback("Playwright: Opening 'Tenders by Organisation' link...")
                org_link.click()
                page.wait_for_load_state("domcontentloaded")

            try:
                page.wait_for_selector("#table", timeout=30000)
            except PlaywrightTimeoutError:
                log_callback("Playwright: Department table '#table' not found")
                browser.close()
                return None, 0

            rows = page.locator("#table tbody tr")
            if rows.count() == 0:
                rows = page.locator("#table tr")

            row_count = rows.count()
            log_callback(f"Playwright: Found {row_count} department table rows")

            for i in range(row_count):
                row = rows.nth(i)
                cells = row.locator("td")
                cell_count = cells.count()
                if cell_count < 3:
                    continue

                s_no = (cells.nth(0).inner_text() or "").strip()
                dept_name = (cells.nth(1).inner_text() or "").strip()
                count_text = (cells.nth(2).inner_text() or "").strip()

                if s_no.lower() in {"s.no", "sr.no", "serial", "#"}:
                    continue
                if dept_name.lower() in {"organisation name", "department name", "organization", "organization name"}:
                    continue

                link = cells.nth(2).locator("a").first
                has_link = link.count() > 0
                direct_url = ""
                if has_link:
                    try:
                        href = link.get_attribute("href")
                        if href:
                            direct_url = _sanitize_direct_url(urljoin(target_url, href))
                    except Exception:
                        direct_url = ""

                if count_text.isdigit():
                    total_tenders += int(count_text)

                departments.append(
                    {
                        "s_no": s_no,
                        "name": dept_name,
                        "count_text": count_text,
                        "has_link": bool(has_link),
                        "processed": False,
                        "tenders_found": 0,
                        "direct_url": direct_url,
                    }
                )

            browser.close()

        log_callback(f"Playwright: Processed {len(departments)} departments. Estimated tenders: {total_tenders}")
        return departments, total_tenders

    except Exception as err:
        log_callback(f"Playwright: Critical fetch error: {err}")
        return None, 0
