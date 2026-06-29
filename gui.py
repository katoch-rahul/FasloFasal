"""GUI wrapper for PRI Claim Verification automation — compact redesign."""

import csv
import re
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime
from itertools import count
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QCheckBox,
    QSpinBox,
    QDoubleSpinBox,
    QTextEdit,
    QTabWidget,
    QFrame,
    QFormLayout,
    QDialog,
    QScrollArea,
    QFileDialog,
)
from playwright.sync_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

import config


# ── Stylesheet (compact, modern) ──────────────────────────────────────────────
APP_STYLE = """
* { font-family: 'Segoe UI', Arial, sans-serif; }
QMainWindow, QWidget { background-color: #1e1e2e; color: #cdd6f4; font-size: 10pt; }

QLabel#title { font-size: 14pt; font-weight: bold; color: #cba6f7; }
QLabel#subtitle { font-size: 8pt; color: #6c7086; }

QFrame#statusCard {
    background-color: #313244;
    border-radius: 8px;
    padding: 8px;
}
QLabel#statusDot { font-size: 16pt; }
QLabel#statusText { font-size: 10pt; font-weight: bold; }
QLabel#statusHint { font-size: 8pt; color: #a6adc8; }

QTabWidget::pane {
    border: 1px solid #45475a;
    border-radius: 6px;
    background-color: #313244;
    top: -1px;
}
QTabBar::tab {
    background-color: #1e1e2e;
    color: #a6adc8;
    padding: 6px 14px;
    border: 1px solid #45475a;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    font-size: 9pt;
}
QTabBar::tab:selected {
    background-color: #313244;
    color: #cba6f7;
    font-weight: bold;
}
QTabBar::tab:hover:!selected { background-color: #2a2a3a; }

QPushButton {
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 10pt;
    font-weight: bold;
    border: none;
    color: white;
}
QPushButton#startBtn   { background-color: #a6e3a1; color: #1e1e2e; }
QPushButton#startBtn:hover { background-color: #94e2d5; }
QPushButton#startBtn:disabled { background-color: #45475a; color: #6c7086; }

QPushButton#pauseBtn   { background-color: #f9e2af; color: #1e1e2e; }
QPushButton#pauseBtn:hover { background-color: #fab387; }
QPushButton#pauseBtn:disabled { background-color: #45475a; color: #6c7086; }

QPushButton#stopBtn    { background-color: #f38ba8; color: #1e1e2e; }
QPushButton#stopBtn:hover { background-color: #eba0ac; }
QPushButton#stopBtn:disabled { background-color: #45475a; color: #6c7086; }

QPushButton#linkBtn {
    background-color: transparent;
    color: #89b4fa;
    padding: 2px 6px;
    font-weight: normal;
    font-size: 8pt;
    text-decoration: underline;
}
QPushButton#linkBtn:hover { color: #b4befe; }

QPushButton#uploadBtn {
    background-color: #89b4fa;
    color: #11111b;
    font-size: 11pt;
    font-weight: bold;
    border-radius: 8px;
    padding: 16px;
}
QPushButton#uploadBtn:hover { background-color: #b4befe; }
QPushButton#uploadBtn:disabled { background-color: #45475a; color: #6c7086; }
QPushButton#uploadBtnLoaded {
    background-color: #a6e3a1;
    color: #11111b;
    font-size: 11pt;
    font-weight: bold;
    border-radius: 8px;
    padding: 16px;
}
QPushButton#uploadBtnLoaded:hover { background-color: #94e2d5; }

QCheckBox { spacing: 6px; padding: 2px; }
QCheckBox::indicator { width: 14px; height: 14px; border-radius: 3px; border: 1px solid #6c7086; background: #1e1e2e; }
QCheckBox::indicator:checked { background-color: #a6e3a1; border: 1px solid #a6e3a1; }

QSpinBox, QDoubleSpinBox {
    padding: 3px 6px;
    border: 1px solid #45475a;
    border-radius: 4px;
    background-color: #1e1e2e;
    color: #cdd6f4;
    min-width: 90px;
    min-height: 24px;
}
QSpinBox:focus, QDoubleSpinBox:focus { border: 1px solid #cba6f7; }
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    border-left: 1px solid #45475a;
    border-bottom: 1px solid #45475a;
    border-top-right-radius: 4px;
    background-color: #313244;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover { background-color: #45475a; }
QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed { background-color: #585b70; }
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    border-left: 1px solid #45475a;
    border-bottom-right-radius: 4px;
    background-color: #313244;
}
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover { background-color: #45475a; }
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed { background-color: #585b70; }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    width: 0; height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #cdd6f4;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    width: 0; height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #cdd6f4;
}


QTextEdit {
    background-color: #11111b;
    color: #cdd6f4;
    font-family: 'Cascadia Code', 'Consolas', monospace;
    font-size: 8pt;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px;
}

QFrame#liveWarn {
    background-color: #45132a;
    border: 1px solid #f38ba8;
    border-radius: 4px;
    padding: 4px;
}
QLabel#liveWarnText { color: #f38ba8; font-weight: bold; font-size: 9pt; }

QScrollBar:vertical { background: #1e1e2e; width: 6px; }
QScrollBar::handle:vertical { background: #45475a; border-radius: 3px; min-height: 20px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { background: none; }
"""

PHASES = {
    "idle":    ("●", "#f9e2af", "Ready",       "Click ▶ Start to begin"),
    "waiting": ("●", "#89b4fa", "Waiting for you…", "Open the page and click PROCEED on the website"),
    "running": ("●", "#a6e3a1", "Working…",    "Tool is approving records — please don't touch"),
    "paused":  ("●", "#f9e2af", "Paused",      "Click Resume when you're ready"),
    "done":    ("✓", "#a6e3a1", "Finished!",   "All done. Check the Log tab for details"),
    "error":   ("✕", "#f38ba8", "Something went wrong", "Open the Log tab to see what happened"),
}


# ── Module Confirmation Dialog ────────────────────────────────────────────────
class ModuleConfirmationDialog(QDialog):
    def __init__(self, module_name: str, record_count: int = 0,
                 require_excel: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm Before Starting")
        self.setMinimumWidth(440)
        self.setStyleSheet(APP_STYLE)
        # Force this dialog to appear on top of all windows (including the browser)
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowStaysOnTopHint
            | Qt.CustomizeWindowHint
            | Qt.WindowTitleHint
            | Qt.WindowCloseButtonHint
        )
        self.setModal(True)
        self.require_excel = require_excel
        self.excel_path = None          # set once a valid workbook is chosen
        self.lookup = None              # ISClaimLookup, set after a successful load
        self.confirm_btn = None
        self._build_ui(module_name, record_count)
        self.confirmed = False

    def showEvent(self, event):
        super().showEvent(event)
        # Bring to front and grab focus when shown
        self.raise_()
        self.activateWindow()
        QApplication.alert(self, 0)            # flash taskbar to grab attention

    def _build_ui(self, module_name: str, record_count: int):
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 18, 18, 18)
        v.setSpacing(12)

        # Title
        title = QLabel("Please check before starting")
        title.setStyleSheet("font-size:13pt; font-weight:bold; color:#cba6f7;")
        v.addWidget(title)

        # Friendly explainer — different wording for the two workflows
        if self.require_excel:
            explainer = QLabel(
                "This is the <b>IS Claim — Add from Excel</b> page. For each claim "
                "below I will open it, read its <b>Account No.</b>, find that account "
                "in your Excel file, fill in the dates and amounts, then Save &amp; "
                "Submit.<br/><br/>"
                "First choose your Excel file below, then press Yes."
            )
        else:
            explainer = QLabel(
                "I am about to start clicking <b>REVIEW → Approve → Confirm → OK</b> "
                "on every record below.<br/><br/>"
                "Please make sure you opened the right page before saying Yes."
            )
        explainer.setTextFormat(Qt.RichText)
        explainer.setWordWrap(True)
        explainer.setStyleSheet("color:#cdd6f4; font-size:10pt;")
        v.addWidget(explainer)

        # Module info — large and clear
        info = QLabel(
            f"<div style='font-size:9pt; color:#a6adc8;'>You are on this page:</div>"
            f"<div style='color:#a6e3a1; font-size:13pt; font-weight:bold;'>{module_name}</div>"
        )
        info.setTextFormat(Qt.RichText)
        info.setWordWrap(True)
        info.setStyleSheet("padding:12px; background:#2a1f3d; border-radius:6px; border-left:4px solid #a6e3a1;")
        v.addWidget(info)

        if record_count > 0:
            count_lbl = QLabel(
                f"<div style='font-size:9pt; color:#a6adc8;'>Records visible on screen:</div>"
                f"<div style='color:#89b4fa; font-size:12pt; font-weight:bold;'>{record_count}</div>"
            )
            count_lbl.setTextFormat(Qt.RichText)
            count_lbl.setStyleSheet("padding:8px; background:#1e1e2e; border-radius:6px;")
            v.addWidget(count_lbl)

        # Excel upload — only for the IS-Claim fill flow
        if self.require_excel:
            v.addWidget(self._build_excel_section())

        # Warning
        warn = QLabel("⚠  If this is the wrong page, click <b>NO, GO BACK</b> and start again.")
        warn.setTextFormat(Qt.RichText)
        warn.setWordWrap(True)
        warn.setStyleSheet("color:#f9e2af; font-size:10pt; font-weight:bold; padding:6px;")
        v.addWidget(warn)

        v.addSpacing(8)

        # Buttons — large and clear
        h = QHBoxLayout()
        cancel = QPushButton("✕  NO, GO BACK")
        cancel.setObjectName("stopBtn")
        cancel.setFixedHeight(44)
        cancel.clicked.connect(self.reject)
        self.confirm_btn = QPushButton("✓  YES, START")
        self.confirm_btn.setObjectName("startBtn")
        self.confirm_btn.setFixedHeight(44)
        self.confirm_btn.setDefault(True)
        self.confirm_btn.clicked.connect(self._on_confirm)
        # For the IS-Claim flow, can't start until a valid Excel is loaded.
        if self.require_excel:
            self.confirm_btn.setEnabled(False)
        h.addWidget(cancel)
        h.addWidget(self.confirm_btn)
        v.addLayout(h)

    def _build_excel_section(self) -> QFrame:
        # Prominent "drop-zone" style card so this required step can't be missed.
        box = QFrame()
        box.setStyleSheet(
            "QFrame { background:#11192b; border:2px dashed #89b4fa; "
            "border-radius:10px; }"
        )
        bv = QVBoxLayout(box)
        bv.setContentsMargins(16, 16, 16, 16)
        bv.setSpacing(8)

        head = QLabel("📄  Required — your IS-claim Excel file")
        head.setStyleSheet(
            "color:#89b4fa; font-size:11pt; font-weight:bold; border:none;"
        )
        bv.addWidget(head)

        why = QLabel(
            "The tool reads each claim's <b>Account No.</b> from the website and "
            "looks up the dates and amounts to enter from this file. Pick the "
            "workbook for this financial year to continue."
        )
        why.setTextFormat(Qt.RichText)
        why.setWordWrap(True)
        why.setStyleSheet("color:#cdd6f4; font-size:9pt; border:none;")
        bv.addWidget(why)

        self.upload_btn = QPushButton("📁   Choose Excel file…")
        self.upload_btn.setObjectName("uploadBtn")
        self.upload_btn.setMinimumHeight(56)
        self.upload_btn.setCursor(Qt.PointingHandCursor)
        self.upload_btn.clicked.connect(self._choose_excel)
        bv.addWidget(self.upload_btn)

        self.excel_status = QLabel("No file chosen yet — choose your .xlsx file above.")
        self.excel_status.setWordWrap(True)
        self.excel_status.setAlignment(Qt.AlignCenter)
        self.excel_status.setStyleSheet(
            "color:#a6adc8; font-size:9pt; border:none;"
        )
        bv.addWidget(self.excel_status)
        return box

    def _choose_excel(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select your IS-claim Excel", "", "Excel files (*.xlsx *.xls)"
        )
        if not path:
            return
        self.upload_btn.setText("⏳   Loading…")
        self.upload_btn.setEnabled(False)
        self.excel_status.setText("Reading workbook, please wait…")
        self.excel_status.setStyleSheet("color:#a6adc8; font-size:9pt; border:none;")
        QApplication.processEvents()
        try:
            # imported lazily so launching the GUI doesn't pull in pandas
            from is_claim_data import ISClaimLookup
            lookup = ISClaimLookup.load(path)
        except Exception as e:
            self.excel_path = None
            self.lookup = None
            self.excel_status.setText(f"✕  Could not read this file:\n{e}")
            self.excel_status.setStyleSheet("color:#f38ba8; font-size:9pt; font-weight:bold; border:none;")
            self._set_upload_btn_style("uploadBtn")
            self.upload_btn.setText("📁   Choose Excel file…")
            self.upload_btn.setEnabled(True)
            self.confirm_btn.setEnabled(False)
            return

        self.excel_path = path
        self.lookup = lookup
        name = Path(path).name
        dup = f" ({len(lookup.duplicates)} duplicate accounts ignored)" if lookup.duplicates else ""
        self.excel_status.setText(f"✓  {name}\n{lookup.count} accounts loaded{dup}")
        self.excel_status.setStyleSheet("color:#a6e3a1; font-size:9pt; font-weight:bold; border:none;")
        self._set_upload_btn_style("uploadBtnLoaded")
        self.upload_btn.setText("✓   File loaded — change file…")
        self.upload_btn.setEnabled(True)
        self.confirm_btn.setEnabled(True)

    def _set_upload_btn_style(self, object_name: str):
        """Swap the upload button's object name and re-polish so the matching
        stylesheet rule (blue 'choose' vs green 'loaded') takes effect."""
        self.upload_btn.setObjectName(object_name)
        self.upload_btn.style().unpolish(self.upload_btn)
        self.upload_btn.style().polish(self.upload_btn)

    def _on_confirm(self):
        # Defensive: never allow confirming the IS flow without a loaded workbook.
        if self.require_excel and self.lookup is None:
            return
        self.confirmed = True
        self.accept()


# ── Worker thread ─────────────────────────────────────────────────────────────
class AutomationWorker(QThread):
    log_signal           = Signal(str)
    phase_signal         = Signal(str)
    progress_signal      = Signal(int, int)        # approved, failed
    finished_signal      = Signal(int, int)
    module_detected      = Signal(str, int, bool)  # module_name, record_count, needs_excel

    def __init__(self, settings: dict):
        super().__init__()
        self.settings    = settings
        self.is_running  = True
        self._pause_evt  = threading.Event()
        self._pause_evt.set()                  # set = run, clear = paused
        self._confirm_evt = threading.Event()
        self._confirm_evt.clear()              # clear = waiting for confirmation
        self.approved    = 0
        self.failed      = 0
        self.module_name = ""
        self.flow        = "approval"   # "approval" (REVIEW) or "is_fill" (Add)
        self.lookup      = None         # ISClaimLookup, set for the is_fill flow
        self._is_form_dumped = False    # dump the IS form DOM once per run for tuning
        self.consecutive_failures = 0   # reliability: trip the breaker on a streak
        self.skipped_accounts = set()   # IS-fill (live): rows we couldn't process
        self._dry_cursor = 0            # per-page row index for dry-run walks
        self._aborted = False           # True if the run stopped on an error
        self.anomalies = []             # IS-fill: rows where Applicable IS was capped

    def set_lookup(self, lookup):
        """Called by the GUI after the user uploads the IS-claim Excel."""
        self.lookup = lookup

    def stop(self):
        self.is_running = False
        self._pause_evt.set()                  # release if paused
        self._confirm_evt.set()                # release if waiting for confirmation

    def pause(self):
        self._pause_evt.clear()

    def resume(self):
        self._pause_evt.set()

    def confirm_module(self):
        self._confirm_evt.set()

    def reject_module(self):
        self.is_running = False
        self._confirm_evt.set()

    def is_paused(self) -> bool:
        return not self._pause_evt.is_set()

    def _wait_if_paused(self):
        if not self._pause_evt.is_set():
            self.phase_signal.emit("paused")
            self.log_signal.emit("[INFO] Paused — waiting for Resume…")
            self._pause_evt.wait()
            if self.is_running:
                self.phase_signal.emit("running")
                self.log_signal.emit("[INFO] Resumed.")

    def _wait_for_module_confirmation(self):
        self.log_signal.emit("[INFO] Waiting for user to confirm module…")
        self._confirm_evt.wait()
        if not self.is_running:
            self._log("[INFO] Module verification cancelled by user.")
            raise RuntimeError("Module verification cancelled")

    # ── helpers ────────────────────────────────────────────────────────────
    def _log(self, msg: str):
        self.log_signal.emit(msg)

    def _detect_flow(self, page: Page) -> tuple[str, str]:
        """Decide which workflow the visible table belongs to.

        IS-Claim fill flow → rows carry "Add" buttons (data entry).
        Approval flow      → rows carry "REVIEW" buttons.
        Returns (flow, human_module_name)."""
        url = page.url
        try:
            add_n = page.locator(config.IS_CLAIM_SELECTORS["add_button"]).count()
        except Exception:
            add_n = 0
        try:
            review_n = page.locator(config.SELECTORS["review_button"]).count()
        except Exception:
            review_n = 0

        if "claim-application-list" in url and add_n > 0 and review_n == 0:
            return "is_fill", "IS CLAIM — FILL FROM EXCEL"
        if "loan-application-list" in url:
            return "approval", "LOAN APPLICATION VERIFICATION"
        return "approval", "CLAIM VERIFICATION"

    def _get_record_count(self, page: Page, flow: str = "approval") -> int:
        """Number of actionable rows visible for the given flow."""
        sel = (config.IS_CLAIM_SELECTORS["add_button"] if flow == "is_fill"
               else config.SELECTORS["review_button"])
        try:
            return page.locator(sel).count()
        except Exception:
            return 0

    def _wait_for_login_and_table(self, page: Page) -> None:
        page.goto(config.LIST_URL, wait_until="domcontentloaded")
        self.phase_signal.emit("waiting")
        self._log("[INFO] Browser opened. Select a module and click PROCEED.")
        # Wait for either an approval table (REVIEW) or an IS-fill table (Add).
        combined = f'{config.SELECTORS["review_button"]}, {config.IS_CLAIM_SELECTORS["add_button"]}'
        try:
            page.wait_for_selector(combined, timeout=self.settings["manual_timeout"] * 1000)
            self._log("[OK] Table detected. Waiting for confirmation…")
            page.wait_for_timeout(1500)

            # Detect flow + module and get record count
            flow, module = self._detect_flow(page)
            self.flow = flow
            self.module_name = module
            count = self._get_record_count(page, flow)
            self._log(f"[INFO] Detected: {module} (flow={flow}, rows={count})")
            self.module_detected.emit(module, count, flow == "is_fill")

            # Wait for user confirmation (and, for is_fill, an uploaded Excel)
            self._wait_for_module_confirmation()
            if flow == "is_fill" and self.lookup is None:
                raise RuntimeError("No IS-claim Excel was loaded — cannot start the fill run.")

            self._log("[OK] Starting automation…")
            self.phase_signal.emit("running")
        except PlaywrightTimeoutError:
            self._log("[ERROR] Timed out — did you select a module and click PROCEED?")
            raise

    # ── reliability helpers ──────────────────────────────────────────────────
    def _session_alive(self, page: Page) -> bool:
        """True while we're still on a work list (i.e. logged in). When the
        actionable buttons vanish, this tells 'finished' apart from 'session
        dropped / logged out'."""
        try:
            return config.SESSION_LIST_URL_HINT in (page.url or "")
        except Exception:
            return False

    def _too_many_failures(self) -> bool:
        """Count one more failure; return True (and log) once the run has failed
        too many times back-to-back — our guard against spinning forever."""
        self.consecutive_failures += 1
        cap = config.MAX_CONSECUTIVE_FAILURES
        if self.consecutive_failures >= cap:
            self._log(f"[ERROR] {self.consecutive_failures} failures in a row — "
                      "stopping. Check the browser (session/login/portal), then "
                      "Start again.")
            self._aborted = True
            return True
        self._log(f"[WARN] Failure {self.consecutive_failures}/{cap} in a row — "
                  "retrying…")
        return False

    def _try_next_page(self, page: Page, action_sel: str) -> bool:
        """Advance to the next page of results. True if a next page loaded with
        actionable rows; False if there is no enabled next page."""
        next_btn = page.locator(config.SELECTORS["next_page_button"])
        try:
            if (next_btn.count() > 0 and next_btn.first.is_visible()
                    and next_btn.first.is_enabled()):
                self._log("[INFO] Next page…")
                next_btn.first.click(timeout=self.settings["per_record_timeout"])
                page.wait_for_timeout(2000)
                page.wait_for_selector(
                    action_sel,
                    timeout=self.settings["list_refresh_timeout"],
                    state="visible",
                )
                return True
        except Exception as e:
            self._log(f"[INFO] No more pages ({e}).")
        return False

    def _actionable_or_paginate(self, page: Page, action_sel: str) -> bool:
        """True if actionable rows are present now, or after turning the page."""
        try:
            page.wait_for_selector(
                action_sel,
                timeout=self.settings["list_refresh_timeout"],
                state="visible",
            )
            return True
        except PlaywrightTimeoutError:
            pass
        return self._try_next_page(page, action_sel)

    def _wait_for_relogin(self, page: Page, action_sel: str) -> bool:
        """The session looks dropped (buttons gone, no longer on a work list).
        Wait for the user to log back in and click PROCEED again, then resume.
        True if the table came back; False on timeout or if the user stopped."""
        self._log("[WARN] You appear to be logged out or the session expired.")
        self._log("[INFO] Log back in and click PROCEED again — I'll wait and "
                  "carry on automatically.")
        self.phase_signal.emit("waiting")
        try:
            page.wait_for_selector(
                action_sel,
                timeout=self.settings["manual_timeout"] * 1000,
                state="visible",
            )
        except PlaywrightTimeoutError:
            self._log("[ERROR] Session did not come back in time — stopping.")
            self._aborted = True
            return False
        if not self.is_running:
            return False
        page.wait_for_timeout(1000)
        self.phase_signal.emit("running")
        self._log("[OK] Back online — continuing where we left off.")
        return True

    def _wait_actionable(self, page: Page, action_sel: str) -> bool:
        """Ensure actionable rows are available, transparently handling
        pagination and a dropped session. False only when the work is genuinely
        finished (or the run was stopped)."""
        if self._actionable_or_paginate(page, action_sel):
            return True
        # No rows and no next page: truly done, or did the session drop?
        if self._session_alive(page):
            return False
        return self._wait_for_relogin(page, action_sel)

    def _wait_for_review_or_paginate(self, page: Page) -> bool:
        return self._wait_actionable(page, config.SELECTORS["review_button"])

    def _screenshot(self, page: Page, label: str) -> str:
        path = config.LOGS_DIR / f"error_{label}_{int(time.time())}.png"
        try:
            page.screenshot(path=str(path), full_page=True)
            return str(path)
        except Exception:
            return ""

    def _log_record(self, writer, index: int, status: str, error: str,
                    account: str = "") -> None:
        writer.writerow({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "index":     index,
            "account":   account,
            "status":    status,
            "error":     error,
        })

    def _recover(self, page: Page) -> None:
        for attempt in ("escape", "back"):
            try:
                if attempt == "escape":
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(500)
                else:
                    page.go_back(wait_until="domcontentloaded")
                    page.wait_for_timeout(1000)
                if page.locator(config.SELECTORS["review_button"]).count() > 0:
                    return
            except Exception:
                continue
        self._log("[WARN] Could not auto-recover — may need to redo PRI + PROCEED.")

    def _process_one(self, page: Page, writer, index: int) -> str:
        if not self.is_running:
            return "stopped"

        if not self._wait_for_review_or_paginate(page):
            html_file = config.LOGS_DIR / "page_dump.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(page.content())
            self._log(f"[DEBUG] No REVIEW buttons. Dump: {html_file}")
            return "no_more_records"

        btns = page.locator(config.SELECTORS["review_button"])
        n = btns.count()
        if n == 0:
            return "no_more_records"
        self._log(f"[{index}] {n} REVIEW button(s) visible.")

        if self.settings["dry_run"]:
            # Dry run approves nothing, so rows never disappear — walk them by a
            # per-page cursor and turn the page once this one is exhausted.
            if self._dry_cursor >= n:
                if not self._try_next_page(page, config.SELECTORS["review_button"]):
                    return "no_more_records"
                self._dry_cursor = 0
                btns = page.locator(config.SELECTORS["review_button"])
                n = btns.count()
                if n == 0:
                    return "no_more_records"
            self._log(f"[{index}] DRY RUN — REVIEW only (row {self._dry_cursor + 1}/{n})…")
            btns.nth(self._dry_cursor).click(timeout=self.settings["per_record_timeout"])
            page.wait_for_timeout(800)
            page.go_back(wait_until="domcontentloaded")
            page.wait_for_timeout(800)
            self._log_record(writer, index, "dry_run_review_clicked", "")
            self._dry_cursor += 1
            return "ok"

        self._log(f"[{index}] REVIEW…")
        btns.first.click(timeout=self.settings["per_record_timeout"])
        page.locator(config.SELECTORS["approve_button"]).first.click(timeout=self.settings["per_record_timeout"])
        page.locator(config.SELECTORS["confirm_button"]).first.click(timeout=self.settings["per_record_timeout"])
        page.locator(config.SELECTORS["ok_button"]).first.click(timeout=self.settings["per_record_timeout"])
        # Wait for either claim or loan application list URL
        page.wait_for_url("**/*application-list*", timeout=self.settings["per_record_timeout"])
        page.wait_for_timeout(2500)
        self._log_record(writer, index, "approved", "")
        return "ok"

    # ── main ───────────────────────────────────────────────────────────────
    def run(self):
        try:
            self._run_automation()
        except Exception as e:
            self._log(f"[ERROR] {e}\n{traceback.format_exc()}")
            self.phase_signal.emit("error")
            self.finished_signal.emit(self.approved, self.failed)

    def _run_automation(self):
        config.LOGS_DIR.mkdir(exist_ok=True)
        config.BROWSER_PROFILE_DIR.mkdir(exist_ok=True)

        log_path = config.LOGS_DIR / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self._log(f"[INFO] Log: {log_path.name}")
        if self.settings["dry_run"]:
            self._log("[INFO] DRY RUN — no real approvals.")

        with open(log_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["timestamp", "index", "account", "status", "error"]
            )
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
                    self._wait_for_login_and_table(page)
                    if self.flow == "is_fill":
                        self._run_is_fill(page, writer, f)
                    else:
                        self._run_approval(page, writer, f)
                except KeyboardInterrupt:
                    self._log("[INFO] Interrupted.")
                finally:
                    try:
                        context.close()
                    except Exception:
                        pass

        self._write_anomalies()
        self._log(f"[DONE] ✓{self.approved} ✕{self.failed}")
        self.phase_signal.emit("error" if self._aborted else "done")
        self.finished_signal.emit(self.approved, self.failed)

    # ── approval flow (REVIEW → Approve → Confirm → OK) ──────────────────────
    def _run_approval(self, page: Page, writer, f) -> None:
        max_rec = self.settings["max_records"]
        for i in count():
            if not self.is_running:
                self._log("[INFO] Stopped by user.")
                break
            self._wait_if_paused()
            if not self.is_running:
                break
            if self.approved >= max_rec:
                self._log(f"[INFO] Reached limit ({max_rec}). Stopping.")
                break
            try:
                result = self._process_one(page, writer, i)
                f.flush()
                if result in ("no_more_records", "stopped"):
                    if result == "no_more_records":
                        self._log("[INFO] No more records.")
                    break
                self.approved += 1
                self.consecutive_failures = 0
                self.progress_signal.emit(self.approved, self.failed)
                self._log(f"[OK] Record {i} done. (Total: {self.approved})")
            except PlaywrightTimeoutError as e:
                self.failed += 1
                shot = self._screenshot(page, f"timeout_{i}")
                self._log_record(writer, i, "failed_timeout", f"{e} | screenshot={shot}")
                f.flush()
                self.progress_signal.emit(self.approved, self.failed)
                self._log(f"[ERROR] Timeout on {i}. {shot}")
                if self._too_many_failures():
                    break
                self._recover(page)
            except Exception as e:
                self.failed += 1
                shot = self._screenshot(page, f"err_{i}")
                self._log_record(writer, i, "failed", f"{e} | screenshot={shot}")
                f.flush()
                self.progress_signal.emit(self.approved, self.failed)
                self._log(f"[ERROR] Record {i}: {e}")
                if self._too_many_failures():
                    break
                self._recover(page)

            time.sleep(self.settings["delay_between_records"])

    # ── IS-Claim fill flow (Add → fill from Excel → Save & Continue → Submit) ─
    @staticmethod
    def _mask(account: str) -> str:
        a = str(account or "")
        return ("•" * max(0, len(a) - 4)) + a[-4:] if a else "?"

    def _run_is_fill(self, page: Page, writer, f) -> None:
        max_rec = self.settings["max_records"]
        dry = self.settings["dry_run"]
        if dry:
            self._log("[INFO] DRY RUN — fields will be filled but NOT Saved/Submitted.")
        else:
            self._log("[WARN] LIVE — each matched record will be Saved & Submitted.")
        for i in count():
            if not self.is_running:
                self._log("[INFO] Stopped by user.")
                break
            self._wait_if_paused()
            if not self.is_running:
                break
            if self.approved >= max_rec:
                self._log(f"[INFO] Reached limit ({max_rec}). Stopping.")
                break
            try:
                result = self._fill_one_is_claim(page, writer, i, dry)
                f.flush()
                if result == "no_more":
                    self._log("[INFO] No more rows to process.")
                    break
                if result == "blocked":
                    self._log("[ERROR] A row that can't be auto-filled is blocking "
                              "the queue. Add that account to your Excel or process "
                              "it by hand on the portal, then Start again.")
                    self._aborted = True
                    break
                if result in ("filled", "dry"):
                    self.approved += 1
                    self.consecutive_failures = 0
                    self.progress_signal.emit(self.approved, self.failed)
                    self._log(f"[OK] Row {i} done. (Total: {self.approved})")
                elif result == "skip":
                    self.failed += 1
                    self.progress_signal.emit(self.approved, self.failed)
                    # In live mode a skipped row stays at the top of the queue;
                    # a streak of skips means we're stuck. Dry-run skips are
                    # genuine progress (the cursor advanced), so don't count them.
                    if not dry and self._too_many_failures():
                        break
            except PlaywrightTimeoutError as e:
                self.failed += 1
                shot = self._screenshot(page, f"is_timeout_{i}")
                self._log_record(writer, i, "failed_timeout", f"{e} | screenshot={shot}")
                f.flush()
                self.progress_signal.emit(self.approved, self.failed)
                self._log(f"[ERROR] Timeout on row {i}. {shot}")
                if self._too_many_failures():
                    break
                self._is_recover(page)
            except Exception as e:
                self.failed += 1
                shot = self._screenshot(page, f"is_err_{i}")
                self._log_record(writer, i, "failed", f"{e} | screenshot={shot}")
                f.flush()
                self.progress_signal.emit(self.approved, self.failed)
                self._log(f"[ERROR] Row {i}: {e}")
                if self._too_many_failures():
                    break
                self._is_recover(page)

            time.sleep(self.settings["delay_between_records"])

    def _wait_for_add_or_paginate(self, page: Page) -> bool:
        return self._wait_actionable(page, config.IS_CLAIM_SELECTORS["add_button"])

    def _fill_one_is_claim(self, page: Page, writer, index: int, dry: bool) -> str:
        if not self._wait_for_add_or_paginate(page):
            return "no_more"
        add_btns = page.locator(config.IS_CLAIM_SELECTORS["add_button"])
        n = add_btns.count()
        if n == 0:
            return "no_more"
        if dry:
            # Dry run submits nothing, so rows never disappear — walk them by a
            # per-page cursor and turn the page once this one is exhausted.
            if self._dry_cursor >= n:
                if not self._try_next_page(page, config.IS_CLAIM_SELECTORS["add_button"]):
                    return "no_more"
                self._dry_cursor = 0
                add_btns = page.locator(config.IS_CLAIM_SELECTORS["add_button"])
                n = add_btns.count()
                if n == 0:
                    return "no_more"
            target = add_btns.nth(self._dry_cursor)
        else:
            # Live runs always take the first remaining row (processed rows drop
            # off the list after submit).
            target = add_btns.first
        self._log(f"[{index}] {n} Add button(s) visible.")
        target.click(timeout=self.settings["per_record_timeout"])
        page.wait_for_timeout(1200)

        account = self._read_account_from_form(page)
        if not account:
            self._log(f"[{index}] [WARN] Couldn't read Account No. from the form.")
            self._log_record(writer, index, "no_account", "account header not found")
            self._is_back_to_list(page)
            if dry:
                self._dry_cursor += 1
            return "skip"

        # Live: a row we already gave up on is still sitting at the top of the
        # queue (the portal gives us no way to remove it). Re-skipping it forever
        # would stall the whole run — recognise the repeat and stop cleanly.
        if not dry and account in self.skipped_accounts:
            self._log(f"[{index}] [ERROR] Account {self._mask(account)} can't be "
                      "processed and is blocking the queue.")
            self._is_back_to_list(page)
            return "blocked"

        rec = self.lookup.get(account)
        if rec is None:
            self._log(f"[{index}] [WARN] Account {self._mask(account)} not in Excel — skipping.")
            self._log_record(writer, index, "not_in_excel", "", account=account)
            self._is_back_to_list(page)
            if dry:
                self._dry_cursor += 1
            else:
                self.skipped_accounts.add(account)
            return "skip"

        self._log(f"[{index}] Account {self._mask(account)} matched — filling…")
        self._dump_form_html(page)
        self._fill_is_form(page, rec, account)

        if dry:
            self._log(f"[{index}] DRY RUN — filled, not saving. Returning to list.")
            self._log_record(writer, index, "dry_run_filled", "", account=account)
            self._is_back_to_list(page)
            self._dry_cursor += 1
            return "dry"

        # LIVE: Save & Continue → [OK] → review → Submit → CONFIRM → [OK].
        # The portal pops a dialog after each step; auto-click straight through.
        page.locator(config.IS_CLAIM_SELECTORS["save_button"]).first.click(
            timeout=self.settings["per_record_timeout"])
        # "Claim application saved successfully." → OK
        self._click_dialog(page, config.IS_CLAIM_SELECTORS["ok_button"], "OK (saved)")
        page.wait_for_timeout(800)
        # Review screen → Submit
        page.locator(config.IS_CLAIM_SELECTORS["submit_button"]).first.click(
            timeout=self.settings["per_record_timeout"])
        # "Are you sure you want to submit this claim application?" → CONFIRM
        self._click_dialog(page, config.IS_CLAIM_SELECTORS["confirm_button"], "Confirm (submit)")
        page.wait_for_timeout(800)
        # "Claim application No. … has been submitted successfully." → OK
        self._click_dialog(page, config.IS_CLAIM_SELECTORS["ok_button"], "OK (submitted)")
        page.wait_for_timeout(1800)
        self._log_record(writer, index, "submitted", "", account=account)
        return "filled"

    def _click_dialog(self, page: Page, selector: str, label: str,
                      timeout_ms: int = 12000) -> bool:
        """Best-effort click of a pop-up dialog button (e.g. the OK on
        'saved successfully', or CONFIRM on the submit prompt). Waits briefly
        for it to appear; a missing dialog is logged but never raises so one
        absent pop-up can't abort an otherwise-good submission."""
        try:
            btn = page.locator(selector).first
            btn.wait_for(state="visible", timeout=timeout_ms)
            btn.click(timeout=self.settings["per_record_timeout"])
            self._log(f"     · clicked {label}")
            page.wait_for_timeout(400)
            return True
        except Exception:
            self._log(f"     · no {label} dialog appeared (skipped)")
            return False

    def _dump_form_html(self, page: Page) -> None:
        """Save the IS form DOM once per run so selectors can be tuned to the
        real markup. Written to logs/ (git-ignored) — local only."""
        if self._is_form_dumped:
            return
        try:
            path = config.LOGS_DIR / "is_form_dump.html"
            path.write_text(page.content(), encoding="utf-8")
            self._is_form_dumped = True
            self._log(f"[DEBUG] Saved form HTML for selector tuning: {path.name}")
        except Exception as e:
            self._log(f"[DEBUG] Could not save form HTML: {e}")

    def _read_account_from_form(self, page: Page) -> str:
        """Read the Account No. shown in the form header. Best-effort text scrape;
        tighten against real HTML if it ever misreads."""
        text = ""
        try:
            loc = page.locator(config.IS_CLAIM_SELECTORS["account_no_label"]).first
            loc.wait_for(timeout=self.settings["per_record_timeout"], state="visible")
            text = loc.locator("xpath=..").inner_text(timeout=5000)
        except Exception:
            try:
                text = page.inner_text("body", timeout=5000)
            except Exception:
                return ""
        m = re.search(r"Account\s*No\.?\D*(\d{10,18})", text)
        if m:
            return m.group(1)
        m = re.search(r"\b(\d{12,18})\b", text)
        return m.group(1) if m else ""

    def _read_eligible_amount(self, page: Page) -> str:
        """Read 'Eligible Loan Amount for IS' from the Activities table — the
        value to type into Max Withdrawal Amount (per SOP). Takes the last
        non-empty cell, i.e. the Total row. Returns whole rupees as digits."""
        cells = page.locator("td.eligibleLoanAmount")
        best = ""
        try:
            for i in range(cells.count()):
                raw = cells.nth(i).inner_text(timeout=2000)
                digits = re.sub(r"\D", "", raw.split(".")[0])   # drop paise, ₹ and commas
                if digits:
                    best = digits
        except Exception:
            pass
        return best

    def _fill_is_form(self, page: Page, rec, account: str = "") -> None:
        for field in config.IS_CLAIM_FIELDS:
            src = field["source"]
            if src == "constant":
                value = field.get("value", "")
            elif src == "excel":
                value = getattr(rec, field["key"], "")
            elif src == "portal":      # read Eligible Loan Amount for IS off the form
                value = self._read_eligible_amount(page)
            else:
                value = None
            # The portal rejects an Applicable IS above the Maximum Allowed Claim.
            # Cap it to the max, submit anyway, and log the anomaly for review.
            if field["key"] == "applicable_is":
                value = self._cap_applicable_is(page, account, value)
            try:
                self._set_field(page, field, value)
            except Exception as e:
                self._log(f"     · [WARN] couldn't set {field['label']}: {e}")
            # Selecting the submission type enables the downstream fields — give
            # the React form a moment to re-render before filling dates/amounts.
            if field["key"] == "is_submission_type":
                page.wait_for_timeout(700)
        self._tick_declaration(page)

    @staticmethod
    def _to_rupees(value) -> int | None:
        """Parse a money-ish value ('₹2,325.00', '2496', 2496.0, '1,55,000') to
        whole rupees (paise dropped). Returns None if it can't be parsed."""
        if value is None:
            return None
        s = re.sub(r"[^\d.]", "", str(value))     # strip ₹, commas, spaces
        if not s:
            return None
        try:
            return int(float(s))                  # floor positive → drops paise
        except ValueError:
            return None

    def _read_max_allowed_claim(self, page: Page) -> str:
        """Read 'Maximum Allowed Claim' off the form — the cap the portal
        enforces on Applicable IS. Returns the raw cell text (e.g. '₹2,325.00')
        or '' if it can't be read."""
        try:
            cell = page.locator(config.IS_CLAIM_SELECTORS["max_allowed_claim"]).first
            cell.wait_for(state="visible", timeout=5000)
            return cell.inner_text(timeout=4000).strip()
        except Exception:
            return ""

    def _cap_applicable_is(self, page: Page, account: str, excel_value) -> str:
        """If the Excel Applicable IS exceeds the form's Maximum Allowed Claim,
        return the max (so the portal accepts it) and record the anomaly.
        Otherwise return the Excel value unchanged."""
        # Let the form settle so the system-computed max is current before we read.
        page.wait_for_timeout(400)
        excel_n = self._to_rupees(excel_value)
        max_n = self._to_rupees(self._read_max_allowed_claim(page))
        if excel_n is None or max_n is None or max_n <= 0:
            # Can't compare reliably — leave the Excel value as-is.
            return excel_value
        if excel_n > max_n:
            self._log(f"     · [WARN] Applicable IS {excel_n} exceeds Maximum Allowed "
                      f"Claim {max_n} — capping to {max_n} (anomaly logged).")
            self.anomalies.append({
                "account_no":   account,
                "actual_claim": excel_n,
                "added_claim":  max_n,
            })
            return str(max_n)
        return excel_value

    def _write_anomalies(self) -> None:
        """Write the capped-record anomalies (account, actual claim, added claim)
        to an Excel file in logs/ for later review. Falls back to CSV if the
        Excel engine isn't available so the data is never lost."""
        if not self.anomalies:
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        cols = ["account_no", "actual_claim", "added_claim"]
        xlsx = config.LOGS_DIR / f"is_claim_anomalies_{stamp}.xlsx"
        try:
            import pandas as pd
            pd.DataFrame(self.anomalies, columns=cols).to_excel(xlsx, index=False)
            self._log(f"[INFO] {len(self.anomalies)} capped record(s) saved to "
                      f"anomalies file: {xlsx.name}")
        except Exception as e:
            csv_path = config.LOGS_DIR / f"is_claim_anomalies_{stamp}.csv"
            try:
                with open(csv_path, "w", newline="", encoding="utf-8") as fh:
                    w = csv.DictWriter(fh, fieldnames=cols)
                    w.writeheader()
                    w.writerows(self.anomalies)
                self._log(f"[WARN] Could not write Excel ({e}); saved anomalies as "
                          f"CSV: {csv_path.name}")
            except Exception as e2:
                self._log(f"[ERROR] Could not write anomalies file: {e2}")

    def _set_field(self, page: Page, field: dict, value) -> None:
        sel = field["selector"]
        loc = page.locator(sel).first
        try:
            loc.wait_for(state="visible", timeout=self.settings["per_record_timeout"])
        except Exception:
            self._log(f"     · [WARN] {field['label']} not found ({sel})")
            return

        if field["type"] == "dropdown":
            loc.select_option(label=str(value), timeout=self.settings["per_record_timeout"])
            self._log(f"     · {field['label']} = {value}")
            return

        if value in ("", None):
            return
        if not self._wait_editable(page, loc, 6000):
            self._log(f"     · [WARN] {field['label']} stayed disabled — skipped")
            return

        if field["type"] == "date":
            self._type_date(page, loc, str(value))
        else:
            loc.click(timeout=self.settings["per_record_timeout"])
            loc.fill(str(value), timeout=self.settings["per_record_timeout"])
        self._log(f"     · {field['label']} = {value}  (got: {self._safe_value(loc)})")

    MONTHS = ["january", "february", "march", "april", "may", "june", "july",
              "august", "september", "october", "november", "december"]

    def _type_date(self, page: Page, loc, value: str) -> None:
        """Set an rmdp date by driving its calendar. The input ignores typed and
        programmatic values, so we open the popup, step to the target month/year
        with the arrows, then click the day cell."""
        try:
            dt = datetime.strptime(value, config.IS_CLAIM_DATE_FORMAT)
        except Exception:
            self._log(f"     · [WARN] bad date value {value!r}")
            return
        self._close_calendar(page)
        try:
            loc.scroll_into_view_if_needed(timeout=4000)
        except Exception:
            pass
        loc.click(timeout=self.settings["per_record_timeout"])
        cal = page.locator(".rmdp-calendar, .rmdp-wrapper").first
        try:
            cal.wait_for(state="visible", timeout=8000)
        except Exception:
            self._log("     · [WARN] calendar did not open")
            return
        if not self._navigate_calendar_to(page, dt.month, dt.year):
            self._log(f"     · [WARN] could not reach {dt.month:02d}/{dt.year} in calendar")
            self._close_calendar(page)
            return
        self._click_calendar_day(page, dt.day)
        page.wait_for_timeout(150)
        self._close_calendar(page)

    def _month_index(self, name: str):
        key = name.strip().lower()[:3]
        for i, mn in enumerate(self.MONTHS):
            if mn.startswith(key):
                return i + 1
        return None

    def _navigate_calendar_to(self, page: Page, month: int, year: int) -> bool:
        for _ in range(80):                      # cap: plenty for any FY span
            try:
                txt = page.locator(".rmdp-header-values").first.inner_text(timeout=3000).strip()
            except Exception:
                return False
            m = re.search(r"([A-Za-z]+)\D+(\d{4})", txt)
            if not m:
                return False
            cur_month = self._month_index(m.group(1))
            cur_year = int(m.group(2))
            if cur_month == month and cur_year == year:
                return True
            go_next = (cur_year, cur_month) < (year, month)
            arrow = (".rmdp-arrow-container.rmdp-right" if go_next
                     else ".rmdp-arrow-container.rmdp-left")
            try:
                page.locator(arrow).first.click(timeout=3000)
            except Exception:
                return False
            page.wait_for_timeout(110)
        return False

    def _click_calendar_day(self, page: Page, day: int) -> None:
        # Exclude days bleeding in from adjacent months (hidden/deactivated).
        days = page.locator(
            ".rmdp-day:not(.rmdp-day-hidden):not(.rmdp-deactive)")
        target = str(int(day))
        for i in range(days.count()):
            d = days.nth(i)
            try:
                if d.inner_text(timeout=1500).strip() == target:
                    d.click(timeout=self.settings["per_record_timeout"])
                    return
            except Exception:
                continue
        self._log(f"     · [WARN] day {day} not found in calendar grid")

    def _close_calendar(self, page: Page) -> None:
        """Dismiss any open rmdp calendar popup so it can't intercept clicks."""
        try:
            cal = page.locator(".rmdp-wrapper, .rmdp-calendar")
            if cal.count() == 0 or not cal.first.is_visible():
                return
            page.keyboard.press("Escape")
            page.wait_for_timeout(120)
            if cal.count() > 0 and cal.first.is_visible():
                page.mouse.click(4, 4)           # neutral click to dismiss
                page.wait_for_timeout(120)
        except Exception:
            pass

    def _tick_declaration(self, page: Page) -> None:
        try:
            cb = page.locator(config.IS_CLAIM_SELECTORS["declaration_checkbox"]).first
            if not cb.is_checked():
                cb.check(timeout=self.settings["per_record_timeout"])
            self._log("     · Declaration ticked")
        except Exception as e:
            self._log(f"     · [WARN] couldn't tick declaration: {e}")

    def _wait_editable(self, page: Page, loc, timeout_ms: int) -> bool:
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            try:
                if loc.is_editable():
                    return True
            except Exception:
                pass
            page.wait_for_timeout(150)
        return False

    @staticmethod
    def _safe_value(loc) -> str:
        try:
            return (loc.input_value() or "").strip()
        except Exception:
            return ""

    def _is_back_to_list(self, page: Page) -> None:
        back = page.locator(config.IS_CLAIM_SELECTORS["back_button"])
        try:
            if back.count() > 0 and back.first.is_visible():
                back.first.click(timeout=self.settings["per_record_timeout"])
                page.wait_for_timeout(1200)
                if page.locator(config.IS_CLAIM_SELECTORS["add_button"]).count() > 0:
                    return
        except Exception:
            pass
        try:
            page.go_back(wait_until="domcontentloaded")
            page.wait_for_timeout(1000)
        except Exception:
            pass

    def _is_recover(self, page: Page) -> None:
        for attempt in ("escape", "back"):
            try:
                if attempt == "escape":
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(500)
                else:
                    page.go_back(wait_until="domcontentloaded")
                    page.wait_for_timeout(1000)
                if page.locator(config.IS_CLAIM_SELECTORS["add_button"]).count() > 0:
                    return
            except Exception:
                continue
        self._log("[WARN] Could not auto-recover the IS list — may need to redo PROCEED.")


# ── Main Window ───────────────────────────────────────────────────────────────
class ClaimApproverGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self._build_ui()
        self._set_phase("idle")
        self._update_progress(0, 0)

    # ── UI ─────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.setWindowTitle("FasloFasal")
        self.setMinimumSize(460, 620)
        self.resize(500, 720)

        # Set icon
        icon_path = Path(__file__).parent / "assets" / "faslofasal.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._center()

        root = QWidget()
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)

        # Header
        header = QHBoxLayout()
        title = QLabel("FasloFasal")
        title.setObjectName("title")
        sub = QLabel("Claim & Loan Verifier")
        sub.setObjectName("subtitle")
        sub.setAlignment(Qt.AlignBottom)
        header.addWidget(title)
        header.addWidget(sub)
        header.addStretch()
        self.progress_lbl = QLabel("✓0  ✕0")
        self.progress_lbl.setStyleSheet("color:#a6adc8; font-size:9pt;")
        header.addWidget(self.progress_lbl)
        v.addLayout(header)

        # Status card
        v.addWidget(self._build_status_card())

        # Live mode warning (hidden by default)
        self.live_warn = self._build_live_warn()
        v.addWidget(self.live_warn)

        # Tabs (Guide / Settings / Log)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_guide_tab(),    "Guide")
        self.tabs.addTab(self._build_settings_tab(), "Settings")
        self.tabs.addTab(self._build_log_tab(),      "Log")
        self.tabs.setCurrentIndex(0)
        v.addWidget(self.tabs, stretch=1)

        # Buttons
        v.addLayout(self._build_buttons())

    def _build_status_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("statusCard")
        h = QHBoxLayout(card)
        h.setContentsMargins(10, 8, 10, 8)
        h.setSpacing(10)

        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("statusDot")
        h.addWidget(self.status_dot)

        col = QVBoxLayout()
        col.setSpacing(0)
        self.status_text = QLabel()
        self.status_text.setObjectName("statusText")
        self.status_hint = QLabel()
        self.status_hint.setObjectName("statusHint")
        col.addWidget(self.status_text)
        col.addWidget(self.status_hint)
        h.addLayout(col, stretch=1)
        return card

    def _build_live_warn(self) -> QFrame:
        f = QFrame()
        f.setObjectName("liveWarn")
        h = QHBoxLayout(f)
        h.setContentsMargins(8, 4, 8, 4)
        lbl = QLabel("⚠  LIVE MODE — records will be approved for real!")
        lbl.setObjectName("liveWarnText")
        h.addWidget(lbl)
        f.setVisible(False)
        return f

    def _build_guide_tab(self) -> QWidget:
        # Wrap in a scroll area — guide is long and readable text matters more than fitting on screen
        outer = QWidget()
        outer_v = QVBoxLayout(outer)
        outer_v.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(12)

        # ── What this tool does ────────────────────────────────────────
        what = QLabel(
            "<div style='font-size:13pt; font-weight:bold; color:#cba6f7;'>"
            "What does this tool do?</div>"
            "<div style='font-size:10pt; color:#cdd6f4; margin-top:6px;'>"
            "It does your repetitive clicking for you, one record at a time, "
            "until the whole list is finished. It can do <b>two jobs</b>:"
            "<br/><br/>"
            "<b>1. Approve / Verify</b> — clicks <b>REVIEW → Approve → "
            "Confirm → OK</b> on every record.<br/><br/>"
            "<b>2. Add IS Claims from Excel</b> — opens each claim, reads its "
            "account number, finds that account in <b>your Excel file</b>, fills "
            "in the dates and amounts, ticks the declaration, and submits it."
            "</div>"
        )
        what.setTextFormat(Qt.RichText)
        what.setWordWrap(True)
        what.setStyleSheet("padding:12px; background:#2a1f3d; border-radius:6px; border-left:4px solid #cba6f7;")
        v.addWidget(what)

        # ── Works with ────────────────────────────────────────────────
        works = QLabel(
            "<div style='font-size:11pt; font-weight:bold; color:#a6e3a1;'>"
            "✓ Works on these pages:</div>"
            "<div style='font-size:10pt; color:#cdd6f4; margin-top:4px; line-height:1.5;'>"
            "<b>Approve / Verify</b><br/>"
            "&nbsp;&nbsp;• Loan Application Verification<br/>"
            "&nbsp;&nbsp;• PRI Claim Verification<br/>"
            "&nbsp;&nbsp;• IS Claim Verification<br/><br/>"
            "<b>Add from Excel</b><br/>"
            "&nbsp;&nbsp;• IS Claim list (rows with an <b>Add</b> button)"
            "</div>"
        )
        works.setTextFormat(Qt.RichText)
        works.setWordWrap(True)
        works.setStyleSheet("padding:12px; background:#1e1e2e; border-radius:6px;")
        v.addWidget(works)

        # ── New: Add IS Claims from Excel ─────────────────────────────
        is_excel = QLabel(
            "<div style='font-size:11pt; font-weight:bold; color:#89b4fa;'>"
            "🆕 Adding IS Claims from Excel</div>"
            "<div style='font-size:10pt; color:#cdd6f4; margin-top:4px; line-height:1.5;'>"
            "When you open the <b>IS Claim</b> list where each row has an "
            "<b>Add</b> button, the tool switches to data-entry mode:"
            "<br/><br/>"
            "&nbsp;&nbsp;1. The pop-up asks you to <b>choose your IS-claim "
            "Excel file</b>.<br/>"
            "&nbsp;&nbsp;2. For each claim it reads the <b>Account No.</b> and "
            "finds that row in your file.<br/>"
            "&nbsp;&nbsp;3. It fills the dates and amounts, ticks the "
            "declaration, and submits.<br/>"
            "&nbsp;&nbsp;4. Accounts not found in your file are skipped and "
            "noted in the Log.<br/>"
            "&nbsp;&nbsp;5. If a claim's Applicable IS is higher than the "
            "portal's Maximum Allowed Claim, it fills the <b>maximum</b> instead "
            "and saves those to an anomalies Excel file in the logs folder."
            "<br/><br/>"
            "<span style='color:#a6adc8; font-size:9pt;'>Your Excel file stays "
            "on your computer — it is never uploaded or saved by this tool.</span>"
            "</div>"
        )
        is_excel.setTextFormat(Qt.RichText)
        is_excel.setWordWrap(True)
        is_excel.setStyleSheet(
            "padding:12px; background:#11192b; border-radius:6px; "
            "border-left:4px solid #89b4fa;"
        )
        v.addWidget(is_excel)

        # ── How to use it ─────────────────────────────────────────────
        how_title = QLabel("<b style='font-size:13pt; color:#cba6f7;'>How to use it — step by step</b>")
        how_title.setTextFormat(Qt.RichText)
        v.addWidget(how_title)

        steps = [
            ("1", "Click the green <b>▶ Start</b> button at the bottom of this window.",
                  "A new browser window will open by itself."),
            ("2", "Log in to the website if it asks you to.",
                  "Use your usual username and password for fasalrin.gov.in."),
            ("3", "On the website, go to the page you want to verify.",
                  "Either <b>Claim Verification</b> or <b>Loan Application</b> — whichever you need today."),
            ("4", "Fill the dropdowns at the top — Financial Year, Status, Branch.",
                  "Same as you do every day. For claims, also pick <b>PRI</b> or <b>IS</b>."),
            ("5", "Click the green <b>PROCEED</b> button on the website.",
                  "Wait a few seconds — the list of records will appear."),
            ("6", "A small box will pop up asking <b>“Yes, Start”</b> or <b>“No, Go Back”</b>.",
                  "It tells you which page you are on. On the <b>IS Claim Add</b> page it also asks you to <b>choose your Excel file</b> first. Read it carefully, then click <b>YES, START</b> if everything looks correct."),
            ("7", "Sit back. The tool will do the rest by itself.",
                  "You will see green ticks (✓) for every record done. Don't touch the browser while it is working."),
            ("8", "When you see <b>“Finished”</b> at the top, the work is done.",
                  "If you want to do another page, click <b>▶ Start</b> again and repeat."),
        ]
        for num, headline, detail in steps:
            row = QFrame()
            row.setStyleSheet("background:#1e1e2e; border-radius:6px;")
            rh = QHBoxLayout(row)
            rh.setContentsMargins(10, 10, 10, 10)
            rh.setSpacing(12)

            n = QLabel(num)
            n.setStyleSheet(
                "color:#1e1e2e; background:#cba6f7; "
                "font-weight:bold; font-size:14pt; "
                "min-width:32px; max-width:32px; min-height:32px; max-height:32px; "
                "border-radius:16px;"
            )
            n.setAlignment(Qt.AlignCenter)
            rh.addWidget(n, alignment=Qt.AlignTop)

            text_col = QVBoxLayout()
            text_col.setSpacing(2)
            head = QLabel(headline)
            head.setTextFormat(Qt.RichText)
            head.setWordWrap(True)
            head.setStyleSheet("color:#cdd6f4; font-size:10pt; font-weight:bold;")
            det = QLabel(detail)
            det.setTextFormat(Qt.RichText)
            det.setWordWrap(True)
            det.setStyleSheet("color:#a6adc8; font-size:9pt;")
            text_col.addWidget(head)
            text_col.addWidget(det)
            rh.addLayout(text_col, stretch=1)
            v.addLayout(self._wrap_in_layout(row))

        # ── Buttons explained ─────────────────────────────────────────
        btn_title = QLabel("<b style='font-size:13pt; color:#cba6f7;'>What the buttons do</b>")
        btn_title.setTextFormat(Qt.RichText)
        v.addWidget(btn_title)

        button_help = [
            ("▶ Start",  "#a6e3a1", "Opens the browser and starts everything."),
            ("⏸ Pause",  "#f9e2af", "Takes a break. The tool will wait until you click Resume."),
            ("■ Stop",   "#f38ba8", "Stops the tool completely."),
        ]
        for name, color, desc in button_help:
            row = QHBoxLayout()
            tag = QLabel(name)
            tag.setStyleSheet(
                f"color:#1e1e2e; background:{color}; "
                f"padding:4px 10px; border-radius:4px; "
                f"font-weight:bold; font-size:10pt; min-width:80px;"
            )
            tag.setAlignment(Qt.AlignCenter)
            d = QLabel(desc)
            d.setWordWrap(True)
            d.setStyleSheet("color:#cdd6f4; font-size:10pt;")
            row.addWidget(tag, alignment=Qt.AlignTop)
            row.addSpacing(8)
            row.addWidget(d, stretch=1)
            v.addLayout(row)

        # ── Big tip ───────────────────────────────────────────────────
        tip = QLabel(
            "<div style='font-size:11pt; font-weight:bold; color:#f9e2af;'>"
            "💡 First time using it?</div>"
            "<div style='font-size:10pt; color:#cdd6f4; margin-top:4px;'>"
            "Go to <b>Settings</b> tab and turn ON <b>“Dry Run”</b>. "
            "This makes the tool only LOOK at records without approving anything. "
            "Once you are happy it is working, turn Dry Run OFF and start for real."
            "</div>"
        )
        tip.setTextFormat(Qt.RichText)
        tip.setWordWrap(True)
        tip.setStyleSheet("padding:12px; background:#3d2f1f; border-radius:6px; border-left:4px solid #f9e2af;")
        v.addWidget(tip)

        # ── Safety note ───────────────────────────────────────────────
        safety = QLabel(
            "<div style='font-size:11pt; font-weight:bold; color:#f38ba8;'>"
            "⚠ Important safety tips</div>"
            "<div style='font-size:10pt; color:#cdd6f4; margin-top:4px; line-height:1.5;'>"
            "• Always read the popup carefully before clicking <b>YES, START</b>.<br/>"
            "• Do not move your mouse or use the browser while the tool is working.<br/>"
            "• If something looks wrong, click <b>■ Stop</b> immediately.<br/>"
            "• If you get logged out mid-run, just log back in and click "
            "<b>PROCEED</b> again — the tool waits and carries on by itself."
            "</div>"
        )
        safety.setTextFormat(Qt.RichText)
        safety.setWordWrap(True)
        safety.setStyleSheet("padding:12px; background:#45132a; border-radius:6px; border-left:4px solid #f38ba8;")
        v.addWidget(safety)

        v.addStretch()
        scroll.setWidget(w)
        outer_v.addWidget(scroll)
        return outer

    def _wrap_in_layout(self, widget):
        """Helper to put a single QFrame inside a QVBoxLayout for cleaner spacing."""
        l = QVBoxLayout()
        l.setContentsMargins(0, 0, 0, 0)
        l.addWidget(widget)
        return l

    def _build_settings_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(6)

        self.dry_run_cb = QCheckBox("Dry Run — practice mode (does NOT approve anything)")
        self.dry_run_cb.setChecked(True)
        self.dry_run_cb.toggled.connect(self._on_dry_run_toggled)
        v.addWidget(self.dry_run_cb)

        dry_help = QLabel(
            "Turn this ON the first time. It only opens each record without approving — "
            "so you can safely check that everything is working."
        )
        dry_help.setWordWrap(True)
        dry_help.setStyleSheet("color:#a6adc8; font-size:8pt; padding-left:22px; padding-bottom:4px;")
        v.addWidget(dry_help)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#45475a;")
        v.addWidget(line)

        form = QFormLayout()
        form.setSpacing(6)
        form.setLabelAlignment(Qt.AlignLeft)

        self._max_records_sb   = self._make_sb(1, 1000, config.MAX_RECORDS_PER_RUN)
        self._timeout_sec_sb   = self._make_sb(5, 120, config.PER_RECORD_TIMEOUT_MS // 1000)
        self._delay_sb         = self._make_dsb(0.1, 10.0, config.DELAY_BETWEEN_RECORDS_SEC)
        self._manual_timeout_sb = self._make_sb(30, 600, config.MANUAL_SETUP_TIMEOUT_SEC)

        form.addRow(self._lbl("Max records to do:"),       self._max_records_sb)
        form.addRow(self._lbl("Wait per click (sec):"),    self._timeout_sec_sb)
        form.addRow(self._lbl("Pause between records (sec):"), self._delay_sb)
        form.addRow(self._lbl("Time to log in (sec):"),    self._manual_timeout_sb)
        v.addLayout(form)
        v.addStretch()

        # Bottom actions
        row = QHBoxLayout()
        row.setSpacing(4)
        clear = QPushButton("Clear Log")
        clear.setObjectName("linkBtn")
        clear.clicked.connect(lambda: self.log_display.clear())
        logs = QPushButton("Open Logs Folder")
        logs.setObjectName("linkBtn")
        logs.clicked.connect(self._open_logs_folder)
        row.addWidget(clear)
        row.addWidget(logs)
        row.addStretch()
        v.addLayout(row)
        return w

    def _build_log_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(4)
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        v.addWidget(self.log_display)
        return w

    def _build_buttons(self) -> QHBoxLayout:
        h = QHBoxLayout()
        h.setSpacing(6)

        self.start_btn = QPushButton("▶ Start")
        self.start_btn.setObjectName("startBtn")
        self.start_btn.setFixedHeight(36)
        self.start_btn.clicked.connect(self.start_automation)
        h.addWidget(self.start_btn, stretch=2)

        self.pause_btn = QPushButton("⏸ Pause")
        self.pause_btn.setObjectName("pauseBtn")
        self.pause_btn.setFixedHeight(36)
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self.toggle_pause)
        h.addWidget(self.pause_btn, stretch=1)

        self.stop_btn = QPushButton("■ Stop")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setFixedHeight(36)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_automation)
        h.addWidget(self.stop_btn, stretch=1)
        return h

    # ── small builders ─────────────────────────────────────────────────────
    def _make_sb(self, lo, hi, val):
        sb = QSpinBox(); sb.setRange(lo, hi); sb.setValue(val); return sb

    def _make_dsb(self, lo, hi, val):
        sb = QDoubleSpinBox(); sb.setRange(lo, hi); sb.setValue(val); sb.setSingleStep(0.1); sb.setDecimals(2); return sb

    def _lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#a6adc8; font-size:9pt;")
        return lbl

    # ── helpers ────────────────────────────────────────────────────────────
    def _center(self):
        scr = QApplication.primaryScreen().availableGeometry()
        self.move((scr.width() - self.width()) // 2, (scr.height() - self.height()) // 2)

    def _set_phase(self, phase: str):
        dot, color, text, hint = PHASES[phase]
        self.status_dot.setText(dot)
        self.status_dot.setStyleSheet(f"color:{color}; font-size:16pt;")
        self.status_text.setText(text)
        self.status_text.setStyleSheet(f"color:{color}; font-weight:bold; font-size:10pt;")
        self.status_hint.setText(hint)

    def _update_progress(self, approved: int, failed: int):
        self.progress_lbl.setText(f"<span style='color:#a6e3a1'>✓{approved}</span>  "
                                  f"<span style='color:#f38ba8'>✕{failed}</span>")

    def _on_dry_run_toggled(self, checked: bool):
        self.live_warn.setVisible(not checked)

    def _open_logs_folder(self):
        config.LOGS_DIR.mkdir(exist_ok=True)
        subprocess.Popen(["explorer", str(config.LOGS_DIR)])

    def _collect_settings(self) -> dict:
        return {
            "dry_run":               self.dry_run_cb.isChecked(),
            "max_records":           self._max_records_sb.value(),
            "per_record_timeout":    self._timeout_sec_sb.value() * 1000,
            "delay_between_records": self._delay_sb.value(),
            "manual_timeout":        self._manual_timeout_sb.value(),
            "list_refresh_timeout":  config.LIST_REFRESH_TIMEOUT_MS,
        }

    # ── slots ──────────────────────────────────────────────────────────────
    def start_automation(self):
        if self.worker and self.worker.isRunning():
            return

        self.log_display.clear()
        self.worker = AutomationWorker(self._collect_settings())
        self.worker.log_signal.connect(self._append_log)
        self.worker.phase_signal.connect(self._set_phase)
        self.worker.progress_signal.connect(self._update_progress)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.module_detected.connect(self._on_module_detected)
        self.worker.start()

        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.pause_btn.setText("⏸ Pause")
        self.stop_btn.setEnabled(True)
        self.tabs.setCurrentIndex(2)         # show log
        self._set_phase("waiting")

    def toggle_pause(self):
        if not self.worker:
            return
        if self.worker.is_paused():
            self.worker.resume()
            self.pause_btn.setText("⏸ Pause")
        else:
            self.worker.pause()
            self.pause_btn.setText("▶ Resume")

    def stop_automation(self):
        if self.worker:
            self.worker.stop()
        self.stop_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)

    def _append_log(self, msg: str):
        m = msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if m.startswith("[OK]"):       color = "#a6e3a1"
        elif m.startswith("[ERROR]"):  color = "#f38ba8"
        elif m.startswith("[WARN]"):   color = "#f9e2af"
        elif m.startswith("[INFO]"):   color = "#89b4fa"
        elif m.startswith("[DEBUG]"):  color = "#6c7086"
        elif m.startswith("[DONE]"):   color = "#cba6f7"
        else:                          color = "#cdd6f4"
        self.log_display.append(f'<span style="color:{color};">{m}</span>')
        sb = self.log_display.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_module_detected(self, module_name: str, record_count: int, needs_excel: bool):
        """Show confirmation dialog when a module is detected. For the IS-Claim
        fill flow the same dialog also collects the Excel file."""
        # Bring main window to front first so the dialog has a focused parent
        self.raise_()
        self.activateWindow()
        self.showNormal()                      # restore if minimised

        dialog = ModuleConfirmationDialog(module_name, record_count, needs_excel, self)
        if dialog.exec() == QDialog.Accepted and dialog.confirmed:
            if needs_excel and dialog.lookup is not None:
                self.worker.set_lookup(dialog.lookup)
            self.worker.confirm_module()
        else:
            self.worker.reject_module()

    def _on_finished(self, approved: int, failed: int):
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("⏸ Pause")
        self.stop_btn.setEnabled(False)


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE)
    window = ClaimApproverGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
