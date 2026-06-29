"""Configuration for PRI Claim Verification automation.

Tweak selectors and timing here without touching approve_claims.py.
"""

from pathlib import Path

VERSION = "2.1.0"

PROJECT_DIR = Path(__file__).parent
BROWSER_PROFILE_DIR = PROJECT_DIR / "browser-profile"
LOGS_DIR = PROJECT_DIR / "logs"

PORTAL_BASE = "https://fasalrin.gov.in"
DASHBOARD_URL = f"{PORTAL_BASE}/dashboard"
CLAIM_LIST_URL = f"{PORTAL_BASE}/claim-application-list"
LOAN_LIST_URL = f"{PORTAL_BASE}/loan-application-list"
LIST_URL = DASHBOARD_URL  # Default entry point

DRY_RUN = False
MAX_RECORDS_PER_RUN = 50
PER_RECORD_TIMEOUT_MS = 30_000
DELAY_BETWEEN_RECORDS_SEC = 0.5
MANUAL_SETUP_TIMEOUT_SEC = 180
LIST_REFRESH_TIMEOUT_MS = 15_000

# ── Reliability / resilience ──────────────────────────────────────────────────
# A single bad row shouldn't stop the whole run, but a long failure *streak*
# means something is genuinely wrong (session dropped, portal changed) — better
# to stop cleanly than to spin forever. High enough to ride out transient blips,
# low enough not to hammer the portal.
MAX_CONSECUTIVE_FAILURES = 6
# Substring marking a "logged in, on the work list" URL. If the actionable
# buttons disappear AND the URL no longer contains this, we treat it as a
# dropped session and wait for the user to log back in — instead of wrongly
# reporting the run as finished.
SESSION_LIST_URL_HINT = "application-list"

SELECTORS = {
    "review_button": 'a:has-text("REVIEW"), button:has-text("REVIEW")',
    "approve_button": 'button:has-text("Approve"), button:has-text("APPROVE")',
    "confirm_button": 'button:has-text("Confirm"), button:has-text("CONFIRM"), button:has-text("Yes")',
    "ok_button": 'button:has-text("OK"), button:has-text("Ok")',
    "table_row": "table tbody tr",
    "next_page_button": 'button:has-text("Next"), a:has-text("Next"), button[aria-label="Next"], li.next:not(.disabled) a',
}

# ── IS Claim Against Loan Application — fill-from-Excel module ─────────────────
# A different workflow from the approve flow above. Per the FY2025-26 SOP:
#   1. claim-application-list, Claim Type = IS, FY 2025-26, Proceed
#   2. for each pending row: click Add  ->  the "IS Claim Against Loan
#      Application" form opens
#   3. read Account No. from the form header, look it up in the Excel "Main" sheet
#   4. IS Submission Type = "Complete" (constant)
#      First Loan Disbursal/Int Cycle Start date  <- Excel
#      Interest cycle end/Rollover date           <- Excel
#      Max Withdrawal Amount = Eligible Loan Amount for IS (read from the form's
#                              Activities table, NOT from Excel)
#      Applicable IS                              <- Excel
#   5. tick Declaration, Save & Continue, review, Submit
#
# The user uploads/selects their IS-claim Excel at RUNTIME (file picker in the
# GUI). We never bundle or commit customer data — the repo may be public. The
# chosen path is passed to ISClaimLookup.load() when a run starts; the default
# here is intentionally None.
IS_CLAIM_EXCEL = None
IS_CLAIM_EXCEL_SHEET = "Main"
# Excel column whose value equals the portal's "Account No." (match key).
IS_CLAIM_MATCH_COLUMN = "Account"

# Fixed value for the IS Submission Type dropdown (per SOP). Matches the
# <option> label exactly (the portal shows it upper-case).
IS_CLAIM_SUBMISSION_TYPE = "COMPLETE"

# Editable fields on the Add form, filled in this order. For each:
#   key          – internal id used in logs
#   label        – human label for logs
#   type         – dropdown | date | number
#   source       – constant | excel | portal
#                    constant -> use "value"
#                    excel    -> read "excel_column" from the matched row
#                    portal   -> read a value off the form (Eligible Loan Amount
#                                for IS, Total row) and type it in
#   selector     – exact Playwright selector for the input (from captured DOM)
#
# IMPORTANT: at form load the date/amount fields are DISABLED; they enable only
# after IS Submission Type is chosen — hence the dropdown is filled first.
IS_CLAIM_FIELDS = [
    {"key": "is_submission_type", "label": "IS Submission Type",
     "type": "dropdown", "source": "constant", "value": IS_CLAIM_SUBMISSION_TYPE,
     "selector": 'select[name="priSubmissionType"]'},
    {"key": "disbursal_date", "label": "First Loan Disbursal/Int Cycle Start Date",
     "type": "date", "source": "excel",
     "excel_column": "First Loan Disbursal/Int Cycle Start date",
     "selector": 'td.disbursalDate input.rmdp-input'},
    {"key": "cycle_end_date", "label": "Interest Cycle End/Rollover Date",
     "type": "date", "source": "excel",
     "excel_column": "Interest cycle end/Rollover date",
     "selector": 'td.rePaymentDate input.rmdp-input'},
    {"key": "max_withdrawal", "label": "Max Withdrawal Amount (INR)",
     "type": "number", "source": "portal",   # = Eligible Loan Amount for IS (Total row)
     "selector": 'input[name="maxWithdrawalAmount"]'},
    {"key": "applicable_is", "label": "Applicable IS (INR)",
     "type": "number", "source": "excel", "excel_column": "Applicable IS",
     "selector": 'input[name="applicableISAmount"]'},
]

# Read-only / system-computed on the form — never written to (for reference):
#   Eligible for IS, Maximum Allowed Claim, Intrest Days
IS_CLAIM_DATE_FORMAT = "%d/%m/%Y"   # how dates are typed into the rmdp inputs

# Exact selectors from the captured IS form DOM.
IS_CLAIM_SELECTORS = {
    "add_button": 'a:has-text("Add"), button:has-text("Add")',   # on each list row
    "account_no_label": 'text=/Account No\\.?/',                 # header anchor to read account #
    "is_submission_type": 'select[name="priSubmissionType"]',
    # Read-only cell showing the system's Maximum Allowed Claim — the cap the
    # portal enforces on Applicable IS (it rejects anything higher on Save with
    # "Please enter valid Applicable IS amount").
    "max_allowed_claim": 'td.maxAllowedClaimTD',
    "declaration_checkbox": 'input[name="declarationText"][type="checkbox"]',
    "save_button": 'button:has-text("SAVE & CONTINUE")',
    "submit_button": 'button:has-text("Submit"), button:has-text("SUBMIT")',
    "back_button": 'button:has-text("BACK")',
    # Pop-up dialogs (SweetAlert-style) auto-clicked to finish a live submit:
    #   Save & Continue -> "saved successfully"      -> OK
    #   Submit          -> "are you sure ... submit" -> CONFIRM (NOT Cancel)
    #                   -> "submitted successfully"  -> OK
    # "Confirm" matching never hits the CANCEL button beside it.
    "confirm_button": 'button:has-text("CONFIRM"), button:has-text("Confirm"), button:has-text("Yes")',
    "ok_button": 'button:has-text("OK"), button:has-text("Ok")',
}
