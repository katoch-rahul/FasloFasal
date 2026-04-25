"""GUI wrapper for PRI Claim Verification automation — compact redesign."""

import csv
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
    "idle":    ("●", "#f9e2af", "Ready",       "Configure below, then press Start"),
    "waiting": ("●", "#89b4fa", "Waiting…",    "Log in → select claim type → click PROCEED"),
    "running": ("●", "#a6e3a1", "Running",     "Processing claims automatically"),
    "paused":  ("●", "#f9e2af", "Paused",      "Click Resume to continue"),
    "done":    ("✓", "#a6e3a1", "Finished",    "See log for summary"),
    "error":   ("✕", "#f38ba8", "Error",       "Check log for details"),
}


# ── Worker thread ─────────────────────────────────────────────────────────────
class AutomationWorker(QThread):
    log_signal      = Signal(str)
    phase_signal    = Signal(str)
    progress_signal = Signal(int, int)        # approved, failed
    finished_signal = Signal(int, int)

    def __init__(self, settings: dict):
        super().__init__()
        self.settings    = settings
        self.is_running  = True
        self._pause_evt  = threading.Event()
        self._pause_evt.set()                  # set = run, clear = paused
        self.approved    = 0
        self.failed      = 0

    def stop(self):
        self.is_running = False
        self._pause_evt.set()                  # release if paused

    def pause(self):
        self._pause_evt.clear()

    def resume(self):
        self._pause_evt.set()

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

    # ── helpers ────────────────────────────────────────────────────────────
    def _log(self, msg: str):
        self.log_signal.emit(msg)

    def _wait_for_login_and_table(self, page: Page) -> None:
        page.goto(config.LIST_URL, wait_until="domcontentloaded")
        self.phase_signal.emit("waiting")
        self._log("[INFO] Browser opened. Complete steps 2–4 in the browser.")
        try:
            page.wait_for_selector(
                config.SELECTORS["review_button"],
                timeout=self.settings["manual_timeout"] * 1000,
            )
            self._log("[OK] Table detected — starting.")
            self.phase_signal.emit("running")
            page.wait_for_timeout(1500)
        except PlaywrightTimeoutError:
            ct = self.settings.get("claim_type", "PRI/IS")
            self._log(f"[ERROR] Timed out — did you select {ct} and click PROCEED?")
            raise

    def _wait_for_review_or_paginate(self, page: Page) -> bool:
        try:
            page.wait_for_selector(
                config.SELECTORS["review_button"],
                timeout=self.settings["list_refresh_timeout"],
                state="visible",
            )
            return True
        except PlaywrightTimeoutError:
            pass

        next_btn = page.locator(config.SELECTORS["next_page_button"])
        try:
            if next_btn.count() > 0:
                btn_first = next_btn.first
                is_visible = btn_first.is_visible()
                self._log(f"[DEBUG] Next button: visible={is_visible}, enabled={btn_first.is_enabled()}")
                if is_visible:
                    self._log("[INFO] Next page…")
                    btn_first.click(timeout=self.settings["per_record_timeout"])
                    page.wait_for_timeout(2000)
                    page.wait_for_selector(
                        config.SELECTORS["review_button"],
                        timeout=self.settings["list_refresh_timeout"],
                        state="visible",
                    )
                    return True
        except Exception as e:
            self._log(f"[INFO] Pagination failed: {e}")
            try:
                btns = page.locator("button, a").all()
                texts = [b.inner_text().strip() for b in btns if b.inner_text().strip()]
                self._log(f"[DEBUG] Buttons/links on page: {texts}")
            except Exception:
                pass
            html_file = config.LOGS_DIR / "page_dump_pagination_failed.html"
            try:
                with open(html_file, "w", encoding="utf-8") as f:
                    f.write(page.content())
                self._log(f"[DEBUG] Page HTML saved: {html_file}")
            except Exception:
                pass
        return False

    def _screenshot(self, page: Page, label: str) -> str:
        path = config.LOGS_DIR / f"error_{label}_{int(time.time())}.png"
        try:
            page.screenshot(path=str(path), full_page=True)
            return str(path)
        except Exception:
            return ""

    def _log_record(self, writer, index: int, status: str, error: str) -> None:
        writer.writerow({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "index":     index,
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
        self._log(f"[{index}] {n} REVIEW button(s) visible.")

        if self.settings["dry_run"]:
            self._log(f"[{index}] DRY RUN — REVIEW only…")
            btns.nth(index).click(timeout=self.settings["per_record_timeout"])
            page.wait_for_timeout(800)
            page.go_back(wait_until="domcontentloaded")
            page.wait_for_timeout(800)
            self._log_record(writer, index, "dry_run_review_clicked", "")
            return "ok"

        self._log(f"[{index}] REVIEW…")
        btns.first.click(timeout=self.settings["per_record_timeout"])
        page.locator(config.SELECTORS["approve_button"]).first.click(timeout=self.settings["per_record_timeout"])
        page.locator(config.SELECTORS["confirm_button"]).first.click(timeout=self.settings["per_record_timeout"])
        page.locator(config.SELECTORS["ok_button"]).first.click(timeout=self.settings["per_record_timeout"])
        page.wait_for_url("**/claim-application-list*", timeout=self.settings["per_record_timeout"])
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

        max_rec = self.settings["max_records"]

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
                    self._wait_for_login_and_table(page)

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
                            self.progress_signal.emit(self.approved, self.failed)
                            self._log(f"[OK] Record {i} done. (Total: {self.approved})")
                        except PlaywrightTimeoutError as e:
                            self.failed += 1
                            shot = self._screenshot(page, f"timeout_{i}")
                            self._log_record(writer, i, "failed_timeout", f"{e} | screenshot={shot}")
                            f.flush()
                            self.progress_signal.emit(self.approved, self.failed)
                            self._log(f"[ERROR] Timeout on {i}. {shot}")
                            self._recover(page)
                        except Exception as e:
                            self.failed += 1
                            shot = self._screenshot(page, f"err_{i}")
                            self._log_record(writer, i, "failed", f"{e} | screenshot={shot}")
                            f.flush()
                            self.progress_signal.emit(self.approved, self.failed)
                            self._log(f"[ERROR] Record {i}: {e}")
                            self._recover(page)

                        time.sleep(self.settings["delay_between_records"])

                except KeyboardInterrupt:
                    self._log("[INFO] Interrupted.")
                finally:
                    try:
                        context.close()
                    except Exception:
                        pass

        self._log(f"[DONE] ✓{self.approved} ✕{self.failed}")
        self.phase_signal.emit("done")
        self.finished_signal.emit(self.approved, self.failed)


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
        self.setMinimumSize(420, 560)
        self.resize(440, 600)

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
        sub = QLabel("Claim Verifier")
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
        lbl = QLabel("⚠  LIVE MODE — claims will be approved")
        lbl.setObjectName("liveWarnText")
        h.addWidget(lbl)
        f.setVisible(False)
        return f

    def _build_guide_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)

        # Capability banner
        banner = QLabel("Works with both <b>IS</b> and <b>PRI</b> claim verifications.")
        banner.setTextFormat(Qt.RichText)
        banner.setWordWrap(True)
        banner.setStyleSheet(
            "color:#cba6f7; font-size:9pt; font-weight:bold;"
            "padding:6px 8px; background:#2a1f3d; border-radius:4px;"
            "border-left:3px solid #cba6f7;"
        )
        v.addWidget(banner)

        steps = [
            ("1", "Press <b>Start</b> — a browser window opens at the portal."),
            ("2", "Log in to <b>fasalrin.gov.in</b> if prompted."),
            ("3", "Select <b>IS</b> or <b>PRI</b> from the Claim Type dropdown."),
            ("4", "Set Financial Year, Claim Status, Branch/PACS as needed."),
            ("5", "Click <b>PROCEED</b> — wait for the claims table to appear."),
            ("6", "The tool auto-processes every row: REVIEW → Approve → Confirm → OK."),
            ("7", "To verify the other claim type, press <b>Start</b> again and repeat."),
        ]
        for num, txt in steps:
            row = QHBoxLayout()
            n = QLabel(num)
            n.setStyleSheet("color:#cba6f7; font-weight:bold; min-width:18px; font-size:11pt;")
            n.setAlignment(Qt.AlignTop)
            t = QLabel(txt)
            t.setWordWrap(True)
            t.setTextFormat(Qt.RichText)
            t.setStyleSheet("color:#cdd6f4; font-size:9pt;")
            row.addWidget(n)
            row.addWidget(t, stretch=1)
            v.addLayout(row)

        v.addStretch()
        tip = QLabel("💡 Keep <b>Dry Run</b> on for your first run — it clicks REVIEW only, makes no approvals.")
        tip.setTextFormat(Qt.RichText)
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#a6adc8; font-size:8pt; padding:6px; background:#1e1e2e; border-radius:4px;")
        v.addWidget(tip)
        return w

    def _build_settings_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(6)

        self.dry_run_cb = QCheckBox("Dry Run (safe — no actual approvals)")
        self.dry_run_cb.setChecked(True)
        self.dry_run_cb.toggled.connect(self._on_dry_run_toggled)
        v.addWidget(self.dry_run_cb)

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

        form.addRow(self._lbl("Max records:"),    self._max_records_sb)
        form.addRow(self._lbl("Action timeout (s):"), self._timeout_sec_sb)
        form.addRow(self._lbl("Delay (s):"),      self._delay_sb)
        form.addRow(self._lbl("Login wait (s):"), self._manual_timeout_sb)
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
