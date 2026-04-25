"""GUI wrapper for PRI Claim Verification automation."""

import csv
import sys
import time
import traceback
from datetime import datetime
from itertools import count
from pathlib import Path
from threading import Thread

from PySide6.QtCore import Qt, QThread, Signal as pyqtSignal, QTimer
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
    QGroupBox,
    QTextEdit,
    QFileDialog,
    QMessageBox,
)
from playwright.sync_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

import config


class AutomationWorker(QThread):
    """Worker thread to run automation without blocking UI."""

    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int, int)
    error_signal = pyqtSignal(str)

    def __init__(self, settings: dict):
        super().__init__()
        self.settings = settings
        self.is_running = True
        self.approved = 0
        self.failed = 0

    def log(self, msg: str):
        self.log_signal.emit(msg)

    def update_status(self, msg: str):
        self.status_signal.emit(msg)

    def stop(self):
        self.is_running = False

    def run(self):
        try:
            self._run_automation()
        except Exception as e:
            self.error_signal.emit(f"Fatal error: {e}\n{traceback.format_exc()}")

    def _wait_for_login_and_table(self, page: Page) -> None:
        page.goto(config.LIST_URL, wait_until="domcontentloaded")
        self.log("\n" + "=" * 60)
        self.log("MANUAL STEPS (do these in the browser window):")
        self.log("  1. Log in if you are not logged in already.")
        self.log("  2. Select 'PRI' from the Claim type dropdown.")
        self.log("  3. Click the PROCEED button.")
        self.log("  4. Wait until the table of records is visible.")
        self.log("")
        self.log("The script will automatically take over once it sees the table.")
        self.log(f"Waiting up to {self.settings['manual_timeout']} seconds for the table to appear...")
        self.log("=" * 60)
        try:
            page.wait_for_selector(
                config.SELECTORS["review_button"],
                timeout=self.settings['manual_timeout'] * 1000,
            )
            self.log("[OK] REVIEW buttons detected. Starting automation...")
            page.wait_for_timeout(1500)
        except PlaywrightTimeoutError:
            self.log("[ERROR] Timed out waiting for REVIEW buttons. Did you select PRI and click PROCEED?")
            raise

    def _wait_for_review_or_paginate(self, page: Page) -> bool:
        try:
            page.wait_for_selector(
                config.SELECTORS["review_button"],
                timeout=self.settings['list_refresh_timeout'],
                state="visible",
            )
            return True
        except PlaywrightTimeoutError:
            pass

        next_btn = page.locator(config.SELECTORS["next_page_button"])
        try:
            if next_btn.count() > 0 and next_btn.first.is_enabled():
                self.log("[INFO] No REVIEW on current page; clicking Next page...")
                next_btn.first.click(timeout=self.settings['per_record_timeout'])
                page.wait_for_selector(
                    config.SELECTORS["review_button"],
                    timeout=self.settings['list_refresh_timeout'],
                    state="visible",
                )
                return True
        except Exception as e:
            self.log(f"[INFO] Pagination attempt failed: {e}")

        return False

    def _screenshot(self, page: Page, label: str) -> str:
        path = config.LOGS_DIR / f"error_{label}_{int(time.time())}.png"
        try:
            page.screenshot(path=str(path), full_page=True)
            return str(path)
        except Exception:
            return ""

    def _log_record(self, writer, index: int, status: str, error: str) -> None:
        writer.writerow(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "index": index,
                "status": status,
                "error": error,
            }
        )

    def _recover_to_list(self, page: Page) -> None:
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
        self.log("[WARN] Could not recover table state automatically. You may need to re-select PRI + PROCEED.")

    def _process_one_record(self, page: Page, log_writer, index: int) -> str:
        if not self.is_running:
            return "stopped"

        if not self._wait_for_review_or_paginate(page):
            self.log("\n[DEBUG] No REVIEW buttons found and no Next page available.")
            html_file = config.LOGS_DIR / "page_dump.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(page.content())
            self.log(f"[DEBUG] Full page HTML saved to: {html_file}")
            return "no_more_records"

        review_buttons = page.locator(config.SELECTORS["review_button"])
        count_buttons = review_buttons.count()
        self.log(f"[{index}] {count_buttons} REVIEW button(s) visible.")

        if index >= count_buttons:
            return "no_more_records"

        if self.settings['dry_run']:
            self.log(f"[{index}] DRY_RUN: Clicking REVIEW button {index} (without actually approving)...")
            review_buttons.nth(index).click(timeout=self.settings['per_record_timeout'])
            page.wait_for_timeout(800)
            page.go_back(wait_until="domcontentloaded")
            page.wait_for_timeout(800)
            self._log_record(log_writer, index, "dry_run_review_clicked", "")
            return "ok"

        self.log(f"[{index}] Clicking REVIEW button {index}...")
        review_buttons.first.click(timeout=self.settings['per_record_timeout'])

        page.locator(config.SELECTORS["approve_button"]).first.click(
            timeout=self.settings['per_record_timeout']
        )
        page.locator(config.SELECTORS["confirm_button"]).first.click(
            timeout=self.settings['per_record_timeout']
        )
        page.locator(config.SELECTORS["ok_button"]).first.click(
            timeout=self.settings['per_record_timeout']
        )

        page.wait_for_url("**/claim-application-list*", timeout=self.settings['per_record_timeout'])
        page.wait_for_timeout(1500)
        self._log_record(log_writer, index, "approved", "")
        return "ok"

    def _run_automation(self):
        config.LOGS_DIR.mkdir(exist_ok=True)
        config.BROWSER_PROFILE_DIR.mkdir(exist_ok=True)

        log_path = config.LOGS_DIR / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self.log(f"Log file: {log_path}")
        if self.settings['dry_run']:
            self.log("DRY_RUN is ON -- Approve will NOT be clicked.")

        self.approved = 0
        self.failed = 0

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
                            self.log("[INFO] Stopping automation...")
                            break

                        try:
                            result = self._process_one_record(page, writer, i)
                            f.flush()
                            if result == "no_more_records":
                                self.log(f"[{i}] No more REVIEW buttons found. Stopping.")
                                break
                            if result == "stopped":
                                break
                            self.approved += 1
                            self.log(f"[{i}] OK")
                        except PlaywrightTimeoutError as e:
                            self.failed += 1
                            shot = self._screenshot(page, f"timeout_{i}")
                            self._log_record(log_writer, i, "failed_timeout", f"{e} | screenshot={shot}")
                            f.flush()
                            self.log(f"[{i}] TIMEOUT - screenshot saved to {shot}")
                            self._recover_to_list(page)
                        except Exception as e:
                            self.failed += 1
                            shot = self._screenshot(page, f"err_{i}")
                            self._log_record(log_writer, i, "failed", f"{e} | screenshot={shot}")
                            f.flush()
                            self.log(f"[{i}] ERROR: {e} - screenshot saved to {shot}")
                            self._recover_to_list(page)

                        time.sleep(self.settings['delay_between_records'])

                except Exception as e:
                    self.log(f"\nException: {e}\n{traceback.format_exc()}")
                finally:
                    try:
                        context.close()
                    except:
                        pass

        self.log(f"\nDone. Approved: {self.approved}, Failed: {self.failed}")
        self.finished_signal.emit(self.approved, self.failed)


class ClaimApproverGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("FasloFasal - Claim Approver")
        self.setGeometry(100, 100, 900, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # Settings Group
        settings_group = QGroupBox("Settings")
        settings_layout = QVBoxLayout()

        # Dry Run
        self.dry_run_checkbox = QCheckBox("Dry Run (REVIEW only, no Approve)")
        self.dry_run_checkbox.setChecked(config.DRY_RUN)
        settings_layout.addWidget(self.dry_run_checkbox)

        # Max Records
        max_records_layout = QHBoxLayout()
        max_records_layout.addWidget(QLabel("Max Records per Run:"))
        self.max_records_spinbox = QSpinBox()
        self.max_records_spinbox.setMinimum(1)
        self.max_records_spinbox.setMaximum(1000)
        self.max_records_spinbox.setValue(config.MAX_RECORDS_PER_RUN)
        max_records_layout.addWidget(self.max_records_spinbox)
        max_records_layout.addStretch()
        settings_layout.addLayout(max_records_layout)

        # Per Record Timeout
        timeout_layout = QHBoxLayout()
        timeout_layout.addWidget(QLabel("Per Record Timeout (ms):"))
        self.timeout_spinbox = QSpinBox()
        self.timeout_spinbox.setMinimum(5000)
        self.timeout_spinbox.setMaximum(120000)
        self.timeout_spinbox.setValue(config.PER_RECORD_TIMEOUT_MS)
        self.timeout_spinbox.setSingleStep(1000)
        timeout_layout.addWidget(self.timeout_spinbox)
        timeout_layout.addStretch()
        settings_layout.addLayout(timeout_layout)

        # Delay Between Records
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Delay Between Records (sec):"))
        self.delay_spinbox = QDoubleSpinBox()
        self.delay_spinbox.setMinimum(0.5)
        self.delay_spinbox.setMaximum(10.0)
        self.delay_spinbox.setValue(config.DELAY_BETWEEN_RECORDS_SEC)
        self.delay_spinbox.setSingleStep(0.5)
        delay_layout.addWidget(self.delay_spinbox)
        delay_layout.addStretch()
        settings_layout.addLayout(delay_layout)

        # Manual Setup Timeout
        manual_timeout_layout = QHBoxLayout()
        manual_timeout_layout.addWidget(QLabel("Manual Setup Timeout (sec):"))
        self.manual_timeout_spinbox = QSpinBox()
        self.manual_timeout_spinbox.setMinimum(30)
        self.manual_timeout_spinbox.setMaximum(600)
        self.manual_timeout_spinbox.setValue(config.MANUAL_SETUP_TIMEOUT_SEC)
        manual_timeout_layout.addWidget(self.manual_timeout_spinbox)
        manual_timeout_layout.addStretch()
        settings_layout.addLayout(manual_timeout_layout)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Control Buttons
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Automation")
        self.start_button.clicked.connect(self.start_automation)
        button_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Automation")
        self.stop_button.clicked.connect(self.stop_automation)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)

        layout.addLayout(button_layout)

        # Log Display
        log_group = QGroupBox("Activity Log")
        log_layout = QVBoxLayout()
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: Courier;")
        log_layout.addWidget(self.log_display)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        # Status Bar
        self.statusBar().showMessage("Ready")

    def start_automation(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Already Running", "Automation is already running!")
            return

        settings = {
            'dry_run': self.dry_run_checkbox.isChecked(),
            'max_records': self.max_records_spinbox.value(),
            'per_record_timeout': self.timeout_spinbox.value(),
            'delay_between_records': self.delay_spinbox.value(),
            'manual_timeout': self.manual_timeout_spinbox.value(),
            'list_refresh_timeout': config.LIST_REFRESH_TIMEOUT_MS,
        }

        self.worker = AutomationWorker(settings)
        self.worker.log_signal.connect(self.append_log)
        self.worker.status_signal.connect(self.update_status)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.error_signal.connect(self.on_error)
        self.worker.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.statusBar().showMessage("Running...")

    def stop_automation(self):
        if self.worker:
            self.worker.stop()
            self.stop_button.setEnabled(False)
            self.statusBar().showMessage("Stopping...")

    def append_log(self, msg: str):
        self.log_display.append(msg)
        # Auto-scroll to bottom
        self.log_display.verticalScrollBar().setValue(
            self.log_display.verticalScrollBar().maximum()
        )

    def update_status(self, msg: str):
        self.statusBar().showMessage(msg)

    def on_finished(self, approved: int, failed: int):
        self.append_log(f"\n✓ Automation finished. Approved: {approved}, Failed: {failed}")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.statusBar().showMessage(f"Finished - Approved: {approved}, Failed: {failed}")

    def on_error(self, error_msg: str):
        self.append_log(f"\n✗ ERROR: {error_msg}")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.statusBar().showMessage("Error occurred")
        QMessageBox.critical(self, "Error", error_msg)


def main():
    app = QApplication(sys.argv)
    window = ClaimApproverGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
