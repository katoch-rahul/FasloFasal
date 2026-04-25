"""Automate PRI Claim Verification on fasalrin.gov.in.

Workflow:
  1. Navigate to claim-application-list
  2. Select "PRI" from Claim type dropdown
  3. Click PROCEED
  4. For each record: Click REVIEW -> Approve -> Confirm -> OK
"""

import csv
import sys
import time
import traceback
from datetime import datetime
from itertools import count

from playwright.sync_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

import config


def wait_for_login_and_table(page: Page) -> None:
    page.goto(config.LIST_URL, wait_until="domcontentloaded")
    print("\n" + "=" * 60)
    print("MANUAL STEPS (do these in the browser window):")
    print("  1. Log in if you are not logged in already.")
    print("  2. Select 'PRI' from the Claim type dropdown.")
    print("  3. Click the PROCEED button.")
    print("  4. Wait until the table of records is visible.")
    print("")
    print("The script will automatically take over once it sees the table.")
    print(f"Waiting up to {config.MANUAL_SETUP_TIMEOUT_SEC} seconds for the table to appear...")
    print("=" * 60)
    try:
        page.wait_for_selector(
            config.SELECTORS["review_button"],
            timeout=config.MANUAL_SETUP_TIMEOUT_SEC * 1000,
        )
        print("[OK] REVIEW buttons detected. Starting automation...")
        page.wait_for_timeout(1500)
    except PlaywrightTimeoutError:
        print("[ERROR] Timed out waiting for REVIEW buttons. Did you select PRI and click PROCEED?")
        raise


def _wait_for_review_or_paginate(page: Page) -> bool:
    """Return True if a REVIEW button is visible (possibly after going to next page).
    Return False if there are truly no more records to process."""
    try:
        page.wait_for_selector(
            config.SELECTORS["review_button"],
            timeout=config.LIST_REFRESH_TIMEOUT_MS,
            state="visible",
        )
        return True
    except PlaywrightTimeoutError:
        pass

    # Try clicking a "Next" pagination button if one exists.
    next_btn = page.locator(config.SELECTORS["next_page_button"])
    try:
        if next_btn.count() > 0 and next_btn.first.is_enabled():
            print("[INFO] No REVIEW on current page; clicking Next page...")
            next_btn.first.click(timeout=config.PER_RECORD_TIMEOUT_MS)
            page.wait_for_selector(
                config.SELECTORS["review_button"],
                timeout=config.LIST_REFRESH_TIMEOUT_MS,
                state="visible",
            )
            return True
    except Exception as e:
        print(f"[INFO] Pagination attempt failed: {e}")

    return False


def process_one_record(page: Page, log_writer, index: int) -> str:
    if not _wait_for_review_or_paginate(page):
        print("\n[DEBUG] No REVIEW buttons found and no Next page available.")
        html_file = config.LOGS_DIR / "page_dump.html"
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(page.content())
        print(f"[DEBUG] Full page HTML saved to: {html_file}")
        return "no_more_records"

    review_buttons = page.locator(config.SELECTORS["review_button"])
    count = review_buttons.count()
    print(f"[{index}] {count} REVIEW button(s) visible.")

    if index >= count:
        return "no_more_records"

    if config.DRY_RUN:
        print(f"[{index}] DRY_RUN: Clicking REVIEW button {index} (without actually approving)...")
        review_buttons.nth(index).click(timeout=config.PER_RECORD_TIMEOUT_MS)
        page.wait_for_timeout(800)
        page.go_back(wait_until="domcontentloaded")
        page.wait_for_timeout(800)
        _log(log_writer, index, "dry_run_review_clicked", "")
        return "ok"

    print(f"[{index}] Clicking REVIEW button {index}...")
    review_buttons.first.click(timeout=config.PER_RECORD_TIMEOUT_MS)

    page.locator(config.SELECTORS["approve_button"]).first.click(
        timeout=config.PER_RECORD_TIMEOUT_MS
    )
    page.locator(config.SELECTORS["confirm_button"]).first.click(
        timeout=config.PER_RECORD_TIMEOUT_MS
    )
    page.locator(config.SELECTORS["ok_button"]).first.click(
        timeout=config.PER_RECORD_TIMEOUT_MS
    )

    page.wait_for_url("**/claim-application-list*", timeout=config.PER_RECORD_TIMEOUT_MS)
    # Give the table a moment to re-render after the approval round-trip.
    page.wait_for_timeout(1500)
    _log(log_writer, index, "approved", "")
    return "ok"


def _log(writer, index: int, status: str, error: str) -> None:
    writer.writerow(
        {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "index": index,
            "status": status,
            "error": error,
        }
    )


def _recover_to_list(page: Page) -> None:
    """Try to get back to a state where REVIEW buttons are clickable, without
    destroying the PRI/PROCEED filter state. We try Escape (close any modal)
    then browser back, and only as a last resort fall back to the bare list URL
    (which will require manual PRI+PROCEED again)."""
    for attempt in ("escape", "back"):
        try:
            if attempt == "escape":
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)
            elif attempt == "back":
                page.go_back(wait_until="domcontentloaded")
                page.wait_for_timeout(1000)
            if page.locator(config.SELECTORS["review_button"]).count() > 0:
                return
        except Exception:
            continue
    print("[WARN] Could not recover table state automatically. You may need to re-select PRI + PROCEED.")


def _screenshot(page: Page, label: str) -> str:
    path = config.LOGS_DIR / f"error_{label}_{int(time.time())}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
        return str(path)
    except Exception:
        return ""


def main() -> int:
    config.LOGS_DIR.mkdir(exist_ok=True)
    config.BROWSER_PROFILE_DIR.mkdir(exist_ok=True)

    log_path = config.LOGS_DIR / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    print(f"Log file: {log_path}")
    if config.DRY_RUN:
        print("DRY_RUN is ON -- Approve will NOT be clicked. Set DRY_RUN=False in config.py for real runs.")
    print("Script will run continuously until all records are processed or you press Ctrl+C.")

    approved = 0
    failed = 0

    with open(log_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "index", "status", "error"])
        writer.writeheader()
        f.flush()

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                str(config.BROWSER_PROFILE_DIR),
                headless=False,
                viewport={"width": 1400, "height": 900},
            )
            page = context.pages[0] if context.pages else context.new_page()

            try:
                wait_for_login_and_table(page)

                for i in count():
                    try:
                        result = process_one_record(page, writer, i)
                        f.flush()
                        if result == "no_more_records":
                            print(f"[{i}] No more REVIEW buttons found. Stopping.")
                            break
                        approved += 1
                        print(f"[{i}] OK")
                    except PlaywrightTimeoutError as e:
                        failed += 1
                        shot = _screenshot(page, f"timeout_{i}")
                        _log(writer, i, "failed_timeout", f"{e} | screenshot={shot}")
                        f.flush()
                        print(f"[{i}] TIMEOUT - screenshot saved to {shot}")
                        _recover_to_list(page)
                    except Exception as e:
                        failed += 1
                        shot = _screenshot(page, f"err_{i}")
                        _log(writer, i, "failed", f"{e} | screenshot={shot}")
                        f.flush()
                        print(f"[{i}] ERROR: {e} - screenshot saved to {shot}")
                        _recover_to_list(page)

                    time.sleep(config.DELAY_BETWEEN_RECORDS_SEC)

            except KeyboardInterrupt:
                print("\nInterrupted by user (Ctrl+C). Closing.")
            except Exception:
                traceback.print_exc()
            finally:
                print(f"\nDone. Approved: {approved}, Failed: {failed}")
                print(f"Log: {log_path}")
                try:
                    input("Press Enter to close the browser...")
                except EOFError:
                    pass
                context.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
