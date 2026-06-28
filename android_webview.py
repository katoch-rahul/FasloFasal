"""Android WebView wrapper with JavaScript-based portal automation.

Replaces approve_claims.py + Playwright on Android.
Creates a native Android WebView via Pyjnius, drives fasalrin.gov.in by
injecting JavaScript, and exposes a simple automation API.

Threading model
───────────────
  Kivy/Python main thread (= Android UI thread):
    • AndroidWebView.create() / destroy()
    • @run_on_ui_thread callbacks
    • Kivy Clock callbacks (on_page_started, on_page_finished)

  Background automation thread (threading.Thread):
    • _automation_loop()
    • _js_eval() — posts JS to UI thread, blocks on Event for result
    • _wait_for_review_or_paginate(), _process_one(), etc.

  Android WebView JS thread (internal):
    • WebChromeClient.onConsoleMessage → _handle_console (thread-safe queue)

NEVER call _exec_js_wait() from the UI thread — use _exec_js_fire() instead.
"""

import csv
import json
import os
import threading
import time
import uuid
from datetime import datetime
from typing import Callable, Optional

from kivy.clock import Clock
from kivy.utils import platform

import config_android as cfg

# ── JavaScript helpers injected after every page load ─────────────────────────
_JS_HELPERS = r"""
(function () {
    if (window.__fasloInstalled) return;
    window.__fasloInstalled = true;

    window.__fasloSend = function (payload) {
        console.log('PYBRIDGE:' + payload);
    };

    /* First visible element whose trimmed text matches one of `texts`. */
    window.__fasloFind = function (texts) {
        var els = document.querySelectorAll(
            'a, button, input[type=submit], input[type=button]'
        );
        for (var i = 0; i < els.length; i++) {
            var el  = els[i];
            var txt = (el.textContent || el.value || '').trim();
            for (var j = 0; j < texts.length; j++) {
                if (txt.toLowerCase() === texts[j].toLowerCase() &&
                        el.offsetParent !== null) {
                    return el;
                }
            }
        }
        return null;
    };

    window.__fasloCountReview = function () {
        var els = document.querySelectorAll('a, button');
        var n = 0;
        for (var i = 0; i < els.length; i++) {
            if ((els[i].textContent || '').trim().toUpperCase() === 'REVIEW' &&
                    els[i].offsetParent !== null) n++;
        }
        return n;
    };

    window.__fasloClick = function (texts) {
        var el = window.__fasloFind(texts);
        if (el) { el.click(); return true; }
        return false;
    };

    window.__fasloModule = function () {
        var url = window.location.href;
        if (url.indexOf('loan-application-list') !== -1)
            return 'LOAN APPLICATION VERIFICATION';
        if (url.indexOf('claim-application-list') !== -1)
            return 'CLAIM VERIFICATION';
        return 'UNKNOWN';
    };

    window.__fasloHasNext = function () {
        return !!window.__fasloFind(['Next', '»']);
    };

    window.__fasloSend('helpers_installed');
})();
"""

# ── Android-only: Pyjnius classes + PythonJavaClass implementations ───────────

if platform == 'android':
    from jnius import autoclass, PythonJavaClass, java_method  # type: ignore
    from android.runnable import run_on_ui_thread               # type: ignore

    _WebView        = autoclass('android.webkit.WebView')
    _WebSettings    = autoclass('android.webkit.WebSettings')
    _FrameLayoutLP  = autoclass('android.widget.FrameLayout$LayoutParams')
    _Gravity        = autoclass('android.view.Gravity')
    _CookieManager  = autoclass('android.webkit.CookieManager')
    _PythonActivity = autoclass('org.kivy.android.PythonActivity')
    _WVCallbacks    = autoclass('org.faslofasal.WebViewCallbacks')
    _FILL           = autoclass('android.view.ViewGroup$LayoutParams').FILL_PARENT

    class _PyPageListener(PythonJavaClass):
        __javainterfaces__ = ['org/faslofasal/WebViewCallbacks$PageListener']

        def __init__(self, on_started: Callable, on_finished: Callable):
            super().__init__()
            self._on_started  = on_started
            self._on_finished = on_finished

        @java_method('(Ljava/lang/String;)V')
        def onPageStarted(self, url: str):
            Clock.schedule_once(lambda dt: self._on_started(url))

        @java_method('(Ljava/lang/String;)V')
        def onPageFinished(self, url: str):
            Clock.schedule_once(lambda dt: self._on_finished(url))

    class _PyConsoleListener(PythonJavaClass):
        __javainterfaces__ = ['org/faslofasal/WebViewCallbacks$ConsoleListener']

        def __init__(self, handler: Callable):
            super().__init__()
            self._handler = handler

        @java_method('(Ljava/lang/String;ILjava/lang/String;)Z')
        def onConsoleMessage(self, message: str, line: int, source: str) -> bool:
            if message.startswith('PYBRIDGE:'):
                self._handler(message[9:])   # thread-safe enqueue
                return True
            return False


# ── AndroidWebView ────────────────────────────────────────────────────────────

class AndroidWebView:
    """Creates and drives an Android WebView for portal automation."""

    def __init__(
        self,
        on_log:             Callable[[str], None]       = None,
        on_phase:           Callable[[str], None]       = None,
        on_progress:        Callable[[int, int], None]  = None,
        on_module_detected: Callable[[str, int], None]  = None,
    ):
        self._on_log             = on_log             or (lambda m: None)
        self._on_phase           = on_phase           or (lambda p: None)
        self._on_progress        = on_progress        or (lambda a, f: None)
        self._on_module_detected = on_module_detected or (lambda m, c: None)

        self._webview: Optional[object] = None

        # Page-load synchronisation (automation thread blocks on this)
        self._page_loaded = threading.Event()

        # Console bridge: messages arrive from Java thread, read by automation thread
        self._console_lock:     threading.Lock       = threading.Lock()
        self._console_messages: list[str]            = []

        # Automation state
        self._is_running  = False
        self._is_paused   = False
        self._module_evt  = threading.Event()
        self._module_ok   = False
        self._settings: dict = {}

        self.approved = 0
        self.failed   = 0

        # Keep Pyjnius objects alive (GC guard)
        self._page_listener:    Optional[object] = None
        self._console_listener: Optional[object] = None

    # ── WebView lifecycle (must be called from Kivy/UI thread) ───────────────

    def create(self, settings: dict):
        """Create WebView and attach to Activity. Call from UI thread."""
        if platform != 'android':
            self._log('[WARN] create() called on non-Android platform — skipped.')
            return
        self._settings = settings
        self._do_create()

    def destroy(self):
        """Detach and destroy WebView. Call from UI thread."""
        if platform == 'android':
            self._do_destroy()

    # ── Private UI-thread methods ─────────────────────────────────────────────

    def _do_create(self):
        activity = _PythonActivity.mActivity
        self._webview = _WebView(activity)

        ws = self._webview.getSettings()
        ws.setJavaScriptEnabled(True)
        ws.setDomStorageEnabled(True)
        ws.setSavePassword(True)
        ws.setLoadWithOverviewMode(True)
        ws.setUseWideViewPort(True)
        ws.setBuiltInZoomControls(True)
        ws.setDisplayZoomControls(False)
        ws.setUserAgentString(
            'Mozilla/5.0 (Linux; Android 11; Mobile) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Mobile Safari/537.36'
        )

        cm = _CookieManager.getInstance()
        cm.setAcceptCookie(True)
        cm.setAcceptThirdPartyCookies(self._webview, True)

        self._page_listener = _PyPageListener(
            self._handle_page_started,
            self._handle_page_finished,
        )
        self._console_listener = _PyConsoleListener(self._handle_console)

        self._webview.setWebViewClient(
            _WVCallbacks.buildWebViewClient(self._page_listener)
        )
        self._webview.setWebChromeClient(
            _WVCallbacks.buildWebChromeClient(self._console_listener)
        )

        params = _FrameLayoutLP(_FILL, _FILL)
        params.gravity = _Gravity.TOP
        activity.addContentView(self._webview, params)

        self._webview.loadUrl(cfg.LIST_URL)
        self._log('[INFO] Browser opened. Log in and click PROCEED on the portal.')
        self._emit_phase('waiting')

    def _do_destroy(self):
        if self._webview:
            try:
                parent = self._webview.getParent()
                if parent:
                    parent.removeView(self._webview)
                self._webview.destroy()
            except Exception:
                pass
            self._webview = None

    # ── JS execution ─────────────────────────────────────────────────────────

    def _exec_js_fire(self, code: str):
        """Fire-and-forget JS. Safe to call from UI thread or background thread."""
        if not self._webview or platform != 'android':
            return
        if threading.current_thread() is threading.main_thread():
            # Already on UI thread — execute directly
            self._webview.evaluateJavascript(code, None)
        else:
            done = threading.Event()

            def _run():
                self._webview.evaluateJavascript(code, None)
                done.set()

            run_on_ui_thread(_run)()
            done.wait(timeout=5.0)

    def _js_eval(self, expr: str, timeout: float = 8.0) -> Optional[str]:
        """Evaluate JS expression and return result (background thread only).

        Uses the console bridge: JS logs 'PYBRIDGE:r:<key>:<JSON result>'.
        """
        key  = uuid.uuid4().hex[:8]
        code = (
            f"console.log('PYBRIDGE:r:{key}:' + "
            f"JSON.stringify({expr}));"
        )
        self._exec_js_fire(code)
        raw = self._wait_for_console(f'r:{key}:', timeout)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    # ── Event callbacks (called via Clock → Kivy/UI thread) ──────────────────

    def _handle_page_started(self, url: str):
        self._page_loaded.clear()

    def _handle_page_finished(self, url: str):
        # Inject helpers — fire-and-forget, we're on UI thread
        if self._webview and platform == 'android':
            self._webview.evaluateJavascript(_JS_HELPERS, None)
        self._page_loaded.set()

    def _handle_console(self, payload: str):
        """Store PYBRIDGE payload. Called from Java thread — must be thread-safe."""
        with self._console_lock:
            self._console_messages.append(payload)

    # ── Console queue helpers ─────────────────────────────────────────────────

    def _wait_for_console(self, prefix: str, timeout: float = 8.0) -> Optional[str]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._console_lock:
                for i, msg in enumerate(self._console_messages):
                    if msg.startswith(prefix):
                        del self._console_messages[i]
                        return msg[len(prefix):]
            time.sleep(0.15)
        return None

    def _wait_page_load(self, timeout: float = 20.0):
        self._page_loaded.wait(timeout=timeout)
        time.sleep(0.4)

    # ── Portal automation helpers (background thread) ─────────────────────────

    def _count_review(self) -> int:
        v = self._js_eval(
            'window.__fasloCountReview ? window.__fasloCountReview() : 0'
        )
        try:
            return int(v or 0)
        except (TypeError, ValueError):
            return 0

    def _detect_module(self) -> str:
        return (
            self._js_eval(
                "window.__fasloModule ? window.__fasloModule() : 'UNKNOWN'"
            )
            or 'UNKNOWN'
        )

    def _click(self, texts: list[str]) -> bool:
        result = self._js_eval(
            f'window.__fasloClick ? window.__fasloClick({json.dumps(texts)}) : false'
        )
        return bool(result)

    def _has_next(self) -> bool:
        return bool(
            self._js_eval(
                'window.__fasloHasNext ? window.__fasloHasNext() : false'
            )
        )

    def _wait_for_review_or_paginate(self, timeout: float = 15.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self._is_running:
                return False
            if self._count_review() > 0:
                return True
            time.sleep(0.5)

        if self._has_next():
            self._log('[INFO] No REVIEW on this page — clicking Next…')
            self._click(cfg.BUTTON_TEXTS['next'])
            self._wait_page_load(10.0)
            deadline2 = time.monotonic() + timeout
            while time.monotonic() < deadline2:
                if self._count_review() > 0:
                    return True
                time.sleep(0.5)
        return False

    def _process_one(self, index: int) -> str:
        """Process one record. Returns 'ok', 'no_more_records', 'stopped', or 'error'."""
        if not self._is_running:
            return 'stopped'
        if not self._wait_for_review_or_paginate():
            return 'no_more_records'

        n = self._count_review()
        self._log(f'[{index}] {n} REVIEW button(s) visible.')

        dry = self._settings.get('dry_run', True)
        if dry:
            self._log(f'[{index}] DRY RUN — clicking REVIEW (no approval)…')
            self._click(cfg.BUTTON_TEXTS['review'])
            time.sleep(1.5)
            self._exec_js_fire('history.back();')
            self._wait_page_load(8.0)
            return 'ok'

        self._log(f'[{index}] REVIEW → Approve → Confirm → OK…')
        if not self._click(cfg.BUTTON_TEXTS['review']):
            self._log(f'[{index}] Could not click REVIEW.')
            return 'error'
        self._wait_page_load(15.0)
        time.sleep(0.3)

        if not self._click(cfg.BUTTON_TEXTS['approve']):
            self._log(f'[{index}] Could not click Approve — recovering…')
            self._exec_js_fire('history.back();')
            self._wait_page_load(8.0)
            return 'error'
        time.sleep(0.4)

        self._click(cfg.BUTTON_TEXTS['confirm'])
        time.sleep(0.4)
        self._click(cfg.BUTTON_TEXTS['ok'])
        self._wait_page_load(15.0)
        time.sleep(1.0)
        return 'ok'

    # ── Public automation control ─────────────────────────────────────────────

    def start_automation(self, settings: dict):
        if self._is_running:
            return
        self._settings   = settings
        self._is_running = True
        self._is_paused  = False
        self.approved    = 0
        self.failed      = 0
        self._module_evt.clear()
        self._module_ok  = False
        threading.Thread(target=self._automation_loop, daemon=True).start()

    def stop_automation(self):
        self._is_running = False
        self._module_evt.set()

    def pause_automation(self):
        self._is_paused = True

    def resume_automation(self):
        self._is_paused = False

    def confirm_module(self):
        self._module_ok = True
        self._module_evt.set()

    def reject_module(self):
        self._module_ok = False
        self._module_evt.set()

    # ── Automation loop (background thread) ───────────────────────────────────

    def _log(self, msg: str):
        Clock.schedule_once(lambda dt: self._on_log(msg))

    def _emit_phase(self, phase: str):
        Clock.schedule_once(lambda dt: self._on_phase(phase))

    def _automation_loop(self):
        os.makedirs(cfg.LOGS_DIR, exist_ok=True)
        log_path = os.path.join(
            cfg.LOGS_DIR,
            f'run_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
        )
        self._log(f'[INFO] Log: {os.path.basename(log_path)}')
        if self._settings.get('dry_run', True):
            self._log('[INFO] DRY RUN — no real approvals will be made.')

        # Wait for user to navigate to the portal and select a module
        self._log('[INFO] Waiting for you to log in and click PROCEED…')
        manual_timeout = self._settings.get('manual_timeout', cfg.MANUAL_SETUP_TIMEOUT_SEC)
        deadline = time.monotonic() + manual_timeout

        while time.monotonic() < deadline:
            if not self._is_running:
                return
            if self._count_review() > 0:
                break
            time.sleep(1.0)
        else:
            self._log('[ERROR] Timed out waiting for REVIEW buttons.')
            self._emit_phase('error')
            return

        # Detect module and ask the user to confirm
        module = self._detect_module()
        count  = self._count_review()
        self._log(f'[INFO] Detected: {module} ({count} records)')
        self._module_evt.clear()
        Clock.schedule_once(
            lambda dt: self._on_module_detected(module, count)
        )
        self._module_evt.wait()

        if not self._module_ok or not self._is_running:
            self._log('[INFO] Cancelled.')
            self._emit_phase('idle')
            return

        self._log('[OK] Starting automation…')
        self._emit_phase('running')

        max_rec = self._settings.get('max_records', cfg.MAX_RECORDS_PER_RUN)
        delay   = self._settings.get('delay_between_records', cfg.DELAY_BETWEEN_RECORDS_SEC)

        with open(log_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(
                f, fieldnames=['timestamp', 'index', 'status', 'error']
            )
            writer.writeheader()

            for i in range(max_rec * 20):
                if not self._is_running:
                    self._log('[INFO] Stopped by user.')
                    break

                if self._is_paused:
                    self._emit_phase('paused')
                    while self._is_paused and self._is_running:
                        time.sleep(0.4)
                    if self._is_running:
                        self._emit_phase('running')

                if self.approved >= max_rec:
                    self._log(f'[INFO] Reached limit ({max_rec}). Stopping.')
                    break

                ts = datetime.now().isoformat(timespec='seconds')
                try:
                    result = self._process_one(i)
                    if result == 'no_more_records':
                        self._log('[INFO] No more records. All done!')
                        break
                    elif result == 'stopped':
                        break
                    elif result == 'ok':
                        self.approved += 1
                        writer.writerow({'timestamp': ts, 'index': i,
                                        'status': 'approved', 'error': ''})
                        a, fa = self.approved, self.failed
                        Clock.schedule_once(lambda dt: self._on_progress(a, fa))
                        self._log(f'[OK] Record {i} done. Total approved: {self.approved}')
                    else:  # error
                        self.failed += 1
                        writer.writerow({'timestamp': ts, 'index': i,
                                        'status': 'failed', 'error': 'click_failed'})
                        a, fa = self.approved, self.failed
                        Clock.schedule_once(lambda dt: self._on_progress(a, fa))
                        self._log(f'[WARN] Record {i} failed — continuing.')
                except Exception as exc:
                    self.failed += 1
                    writer.writerow({'timestamp': ts, 'index': i,
                                    'status': 'failed', 'error': str(exc)})
                    a, fa = self.approved, self.failed
                    Clock.schedule_once(lambda dt: self._on_progress(a, fa))
                    self._log(f'[ERROR] Record {i}: {exc}')
                finally:
                    f.flush()

                time.sleep(delay)

        self._log(f'[DONE] Approved: {self.approved}  Failed: {self.failed}')
        self._is_running = False
        self._emit_phase('done')
