"""Configuration for PRI Claim Verification automation.

Tweak selectors and timing here without touching approve_claims.py.
"""

from pathlib import Path

PROJECT_DIR = Path(__file__).parent
BROWSER_PROFILE_DIR = PROJECT_DIR / "browser-profile"
LOGS_DIR = PROJECT_DIR / "logs"

PORTAL_BASE = "https://fasalrin.gov.in"
LIST_URL = f"{PORTAL_BASE}/claim-application-list"

DRY_RUN = False
MAX_RECORDS_PER_RUN = 10
PER_RECORD_TIMEOUT_MS = 30_000
DELAY_BETWEEN_RECORDS_SEC = 2.0
MANUAL_SETUP_TIMEOUT_SEC = 180
LIST_REFRESH_TIMEOUT_MS = 15_000

SELECTORS = {
    "review_button": 'a:has-text("REVIEW"), button:has-text("REVIEW")',
    "approve_button": 'button:has-text("Approve"), button:has-text("APPROVE")',
    "confirm_button": 'button:has-text("Confirm"), button:has-text("CONFIRM"), button:has-text("Yes")',
    "ok_button": 'button:has-text("OK"), button:has-text("Ok")',
    "table_row": "table tbody tr",
    "next_page_button": 'button:has-text("Next"), a:has-text("Next"), button[aria-label="Next"], li.next:not(.disabled) a',
}
