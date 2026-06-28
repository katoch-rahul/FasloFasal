"""Capture helper — opens the portal with your saved session and dumps the
current page's HTML + a full-page screenshot whenever you press Enter.

Use this to capture:
  • one row of the claim-application-list table (account number column + Add button)
  • the "Add" form that opens after clicking Add on a row

Run from the FasloFasal folder:
    ..\.venv\Scripts\python tools\dump_page.py

IMPORTANT: close any other FasloFasal browser window first — the saved
profile can only be opened by one Chromium at a time.
"""

import sys
import time
from pathlib import Path

# Allow "import config" when run from the FasloFasal folder or from tools/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def main() -> int:
    config.LOGS_DIR.mkdir(exist_ok=True)
    print("=" * 64)
    print("PAGE DUMP HELPER")
    print("  1. A browser opens with your saved fasalrin.gov.in session.")
    print("  2. Navigate to the page you want me to see (table row OR Add form).")
    print("  3. Come back here and press Enter — I'll save the HTML + screenshot.")
    print("  4. Repeat for as many pages as you like. Type 'q' + Enter to quit.")
    print("=" * 64)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(config.BROWSER_PROFILE_DIR),
            headless=False,
            viewport={"width": 1400, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(config.CLAIM_LIST_URL, wait_until="domcontentloaded")

        try:
            while True:
                cmd = input("\nPress Enter to capture this page (or 'q' to quit): ").strip().lower()
                if cmd == "q":
                    break
                ts = time.strftime("%Y%m%d_%H%M%S")
                html_path = config.LOGS_DIR / f"capture_{ts}.html"
                png_path = config.LOGS_DIR / f"capture_{ts}.png"
                try:
                    html_path.write_text(page.content(), encoding="utf-8")
                    page.screenshot(path=str(png_path), full_page=True)
                    print(f"  [OK] HTML       -> {html_path}")
                    print(f"  [OK] screenshot -> {png_path}")
                    print(f"  [INFO] current URL: {page.url}")
                except Exception as e:
                    print(f"  [ERROR] capture failed: {e}")
        except (EOFError, KeyboardInterrupt):
            pass
        finally:
            context.close()

    print("\nDone. Send me the capture_*.html / capture_*.png files in logs/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
