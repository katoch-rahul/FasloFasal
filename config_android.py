"""Configuration for FasloFasal Android.

Mirrors config.py but uses os.path (not pathlib) and Android-aware
storage paths so it works both on Android and desktop for testing.
"""

import os

VERSION = "1.2.0-android"

# Storage: use the app's writable private directory on Android,
# fall back to the script's directory on desktop.
try:
    from android.storage import app_storage_path  # type: ignore[import]
    _BASE_DIR = app_storage_path()
except ImportError:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LOGS_DIR = os.path.join(_BASE_DIR, "logs")

PORTAL_BASE = "https://fasalrin.gov.in"
DASHBOARD_URL = f"{PORTAL_BASE}/dashboard"
CLAIM_LIST_URL = f"{PORTAL_BASE}/claim-application-list"
LOAN_LIST_URL = f"{PORTAL_BASE}/loan-application-list"
LIST_URL = DASHBOARD_URL

DRY_RUN = True
MAX_RECORDS_PER_RUN = 50
DELAY_BETWEEN_RECORDS_SEC = 1.0
MANUAL_SETUP_TIMEOUT_SEC = 300

# Button text lists used by the JavaScript automation helper.
BUTTON_TEXTS = {
    "review":  ["REVIEW"],
    "approve": ["Approve", "APPROVE"],
    "confirm": ["Confirm", "CONFIRM", "Yes"],
    "ok":      ["OK", "Ok"],
    "next":    ["Next", "»"],
}
