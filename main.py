"""FasloFasal Android — Kivy entry point.

The desktop version still lives in gui.py (PySide6 + Playwright).
This file is the Android entry point: Kivy UI + native WebView automation.

Screens
───────
  control  — status card, log viewer, settings, control buttons (pure Kivy)
  browser  — shows the native Android WebView; Kivy is a thin bottom bar only
"""

import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import FadeTransition, Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.switch import Switch
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex, platform

import config_android as cfg

if platform == 'android':
    from android_webview import AndroidWebView  # type: ignore
    from jnius import autoclass                 # type: ignore
    _PythonActivity = autoclass('org.kivy.android.PythonActivity')

# ── Colour palette (matches desktop dark theme) ───────────────────────────────
BG      = get_color_from_hex('#1e1e2e')
SURFACE = get_color_from_hex('#313244')
PURPLE  = get_color_from_hex('#cba6f7')
GREEN   = get_color_from_hex('#a6e3a1')
YELLOW  = get_color_from_hex('#f9e2af')
RED     = get_color_from_hex('#f38ba8')
TEXT    = get_color_from_hex('#cdd6f4')
MUTED   = get_color_from_hex('#a6adc8')
BLUE    = get_color_from_hex('#89b4fa')

# Note: keep glyphs to font-safe characters. Kivy's default Roboto font does
# not include media-control / symbol glyphs (e.g. U+25B6, U+23F8), which render
# as empty "tofu" boxes on device. A plain bullet renders everywhere.
PHASES = {
    'idle':    ('•', YELLOW, 'Ready',             'Tap Start to begin'),
    'waiting': ('•', BLUE,   'Waiting for you...', 'Log in and click PROCEED on the portal'),
    'running': ('•', GREEN,  'Working...',         'Approving records - do not touch the browser'),
    'paused':  ('•', YELLOW, 'Paused',            'Tap Resume when ready'),
    'done':    ('•', GREEN,  'Finished!',          'Check Log tab for details'),
    'error':   ('•', RED,    'Something went wrong', 'Check Log tab'),
}

Builder.load_string("""
#:import dp kivy.metrics.dp
#:import gch kivy.utils.get_color_from_hex

<FlatBtn@Button>:
    background_normal: ''
    background_color: gch('#313244')
    color: gch('#cdd6f4')
    font_size: dp(13)
    bold: True
    size_hint_y: None
    height: dp(44)

<GreenBtn@FlatBtn>:
    background_color: gch('#a6e3a1')
    color: gch('#1e1e2e')
    font_size: dp(15)
    height: dp(48)

<YellowBtn@FlatBtn>:
    background_color: gch('#f9e2af')
    color: gch('#1e1e2e')

<RedBtn@FlatBtn>:
    background_color: gch('#f38ba8')
    color: gch('#1e1e2e')
""")


# ── Control Screen ────────────────────────────────────────────────────────────

class ControlScreen(Screen):
    """Full-screen Kivy control panel."""

    def __init__(self, app_ref: 'FasloFasalApp', **kw):
        super().__init__(**kw)
        self._app = app_ref
        self._build()

    def _build(self):
        root = BoxLayout(
            orientation='vertical',
            padding=dp(12),
            spacing=dp(8),
        )
        root.canvas.before.clear()
        with root.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(*BG)
            self._bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(
            pos=lambda w, v: setattr(self._bg, 'pos', v),
            size=lambda w, v: setattr(self._bg, 'size', v),
        )

        # ── Header ────────────────────────────────────────────────────────────
        hdr = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        hdr.add_widget(Label(
            text='FasloFasal',
            font_size=dp(20), bold=True, color=PURPLE,
            size_hint_x=0.55, halign='left', valign='center',
        ))
        self._subtitle = Label(
            text='Claim & Loan Verifier',
            font_size=dp(11), color=MUTED,
            size_hint_x=0.45, halign='right', valign='center',
        )
        hdr.add_widget(self._subtitle)
        root.add_widget(hdr)

        # ── Status card ───────────────────────────────────────────────────────
        status_card = BoxLayout(
            size_hint_y=None, height=dp(68), spacing=dp(10), padding=dp(10),
        )
        with status_card.canvas.before:
            from kivy.graphics import Color, RoundedRectangle
            Color(*SURFACE)
            self._card_bg = RoundedRectangle(
                pos=status_card.pos, size=status_card.size, radius=[dp(8)]
            )
        status_card.bind(
            pos=lambda w, v: setattr(self._card_bg, 'pos', v),
            size=lambda w, v: setattr(self._card_bg, 'size', v),
        )
        self._dot  = Label(text='•', font_size=dp(20), color=YELLOW,
                           size_hint_x=None, width=dp(28))
        col = BoxLayout(orientation='vertical', spacing=dp(2))
        self._status_text = Label(
            text='Ready', font_size=dp(14), bold=True, color=YELLOW,
            halign='left', valign='center',
        )
        self._status_hint = Label(
            text='Tap Start to begin', font_size=dp(11), color=MUTED,
            halign='left', valign='center',
        )
        col.add_widget(self._status_text)
        col.add_widget(self._status_hint)
        self._progress_lbl = Label(
            text='OK 0  Err 0', markup=True, font_size=dp(12), color=MUTED,
            size_hint_x=None, width=dp(96), halign='right', valign='center',
        )
        status_card.add_widget(self._dot)
        status_card.add_widget(col)
        status_card.add_widget(self._progress_lbl)
        root.add_widget(status_card)

        # ── Log display ───────────────────────────────────────────────────────
        scroll = ScrollView()
        self._log_lbl = Label(
            text='',
            markup=True,
            font_size=dp(11),
            size_hint_y=None,
            halign='left', valign='top',
            text_size=(None, None),
        )
        self._log_lbl.bind(
            texture_size=self._log_lbl.setter('size'),
            width=lambda w, v: setattr(w, 'text_size', (v, None)),
        )
        scroll.add_widget(self._log_lbl)
        root.add_widget(scroll)

        # ── Settings row ──────────────────────────────────────────────────────
        srow = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        self._dry_toggle = ToggleButton(
            text='Dry Run  ON', state='down',
            background_color=YELLOW[:3] + [1],
            color=BG,
            size_hint_x=0.55,
            font_size=dp(13),
        )
        self._dry_toggle.bind(on_press=self._on_dry_toggle)
        srow.add_widget(self._dry_toggle)
        clear_btn = Button(
            text='Clear Log',
            background_color=SURFACE,
            color=MUTED,
            font_size=dp(12),
            size_hint_x=0.45,
        )
        clear_btn.bind(on_press=lambda _: setattr(self._log_lbl, 'text', ''))
        srow.add_widget(clear_btn)
        root.add_widget(srow)

        # ── Control buttons ───────────────────────────────────────────────────
        brow = GridLayout(cols=3, size_hint_y=None, height=dp(52), spacing=dp(8))
        self._start_btn = Button(
            text='Start',
            background_color=GREEN, color=BG,
            font_size=dp(15), bold=True,
        )
        self._pause_btn = Button(
            text='Pause',
            background_color=SURFACE, color=MUTED,
            font_size=dp(13), disabled=True,
        )
        self._stop_btn = Button(
            text='Stop',
            background_color=SURFACE, color=MUTED,
            font_size=dp(13), disabled=True,
        )
        self._start_btn.bind(on_press=self._on_start)
        self._pause_btn.bind(on_press=self._on_pause)
        self._stop_btn.bind(on_press=self._on_stop)
        brow.add_widget(self._start_btn)
        brow.add_widget(self._pause_btn)
        brow.add_widget(self._stop_btn)
        root.add_widget(brow)

        # ── Browser toggle ────────────────────────────────────────────────────
        browser_btn = Button(
            text='Show Browser',
            background_color=SURFACE, color=BLUE,
            font_size=dp(13),
            size_hint_y=None, height=dp(40),
        )
        browser_btn.bind(on_press=lambda _: self._app.show_browser())
        root.add_widget(browser_btn)

        self.add_widget(root)

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_dry_toggle(self, btn: ToggleButton):
        if btn.state == 'down':
            btn.text = 'Dry Run  ON'
            btn.background_color = YELLOW[:3] + [1]
        else:
            btn.text = 'Dry Run  OFF (!)'
            btn.background_color = RED[:3] + [1]

    def _on_start(self, _):
        dry = self._dry_toggle.state == 'down'
        self._app.start_automation(dry_run=dry)

    def _on_pause(self, _):
        self._app.toggle_pause()

    def _on_stop(self, _):
        self._app.stop_automation()

    # ── Public API called by the App ──────────────────────────────────────────

    def set_phase(self, phase: str):
        dot, color, text, hint = PHASES.get(phase, ('•', MUTED, phase, ''))
        self._dot.text         = dot
        self._dot.color        = color
        self._status_text.text  = text
        self._status_text.color = color
        self._status_hint.text  = hint

        running = phase in ('waiting', 'running', 'paused')
        self._start_btn.disabled  = running
        self._start_btn.background_color = SURFACE if running else GREEN
        self._pause_btn.disabled  = not running
        self._pause_btn.background_color = YELLOW if running else SURFACE
        self._pause_btn.color    = BG if running else MUTED
        self._stop_btn.disabled  = not running
        self._stop_btn.background_color = RED if running else SURFACE
        self._stop_btn.color     = BG if running else MUTED

    def set_pause_label(self, label: str):
        self._pause_btn.text = label

    def update_progress(self, approved: int, failed: int):
        self._progress_lbl.text = (
            f'[color=#a6e3a1]OK {approved}[/color]  '
            f'[color=#f38ba8]Err {failed}[/color]'
        )

    def append_log(self, msg: str):
        color = '#cdd6f4'
        if   msg.startswith('[OK]'):    color = '#a6e3a1'
        elif msg.startswith('[ERROR]'): color = '#f38ba8'
        elif msg.startswith('[WARN]'):  color = '#f9e2af'
        elif msg.startswith('[INFO]'):  color = '#89b4fa'
        elif msg.startswith('[DEBUG]'): color = '#6c7086'
        elif msg.startswith('[DONE]'):  color = '#cba6f7'
        escaped = msg.replace('[', '[[').replace(']', ']]')
        self._log_lbl.text += f'[color={color}]{escaped}[/color]\n'


# ── Browser Screen ────────────────────────────────────────────────────────────

class BrowserScreen(Screen):
    """Thin overlay screen while the native Android WebView is visible.

    The WebView is shown/hidden by the App when this screen is entered/left.
    Only a small "Back" button is drawn by Kivy on top of the WebView.
    """

    def __init__(self, app_ref: 'FasloFasalApp', **kw):
        super().__init__(**kw)
        self._app = app_ref

        back = Button(
            text='< Control Panel',
            size_hint=(None, None),
            size=(dp(160), dp(44)),
            pos_hint={'right': 1, 'top': 1},
            background_color=(0.25, 0.25, 0.35, 0.90),
            color=BLUE,
            font_size=dp(12),
        )
        back.bind(on_press=lambda _: self._app.show_control())
        self.add_widget(back)

    def on_enter(self):
        if platform == 'android' and self._app.webview:
            Clock.schedule_once(lambda dt: self._app.webview._exec_js_fire(''), 0)
            # The WebView was created at app start; toggling visibility is done
            # by the App by adding/removing it from the layout. Here we simply
            # make the Kivy surface transparent so the WebView shows through.
            from kivy.core.window import Window
            Window.clearcolor = (0, 0, 0, 0)

    def on_leave(self):
        from kivy.core.window import Window
        Window.clearcolor = BG


# ── Application ───────────────────────────────────────────────────────────────

class FasloFasalApp(App):
    title = 'FasloFasal'

    def build(self):
        from kivy.core.window import Window
        Window.clearcolor = BG

        self.webview: Optional['AndroidWebView'] = None
        self._paused = False

        sm = ScreenManager(transition=FadeTransition())
        self._ctrl = ControlScreen(self, name='control')
        self._brow = BrowserScreen(self, name='browser')
        sm.add_widget(self._ctrl)
        sm.add_widget(self._brow)
        return sm

    def on_start(self):
        if platform == 'android':
            self.webview = AndroidWebView(
                on_log=self._on_log,
                on_phase=self._on_phase,
                on_progress=self._on_progress,
                on_module_detected=self._on_module_detected,
            )
            # Create WebView on the UI thread
            activity = _PythonActivity.mActivity
            self.webview.create({})

    # ── Navigation ────────────────────────────────────────────────────────────

    def show_browser(self):
        if self.webview:
            self.webview.show()
        self.root.current = 'browser'

    def show_control(self):
        self.root.current = 'control'
        if self.webview:
            self.webview.hide()

    # ── Automation control ────────────────────────────────────────────────────

    def start_automation(self, dry_run: bool = True):
        if not self.webview:
            self._on_log('[WARN] Android WebView not available on this platform.')
            return
        settings = {
            'dry_run':               dry_run,
            'max_records':           cfg.MAX_RECORDS_PER_RUN,
            'delay_between_records': cfg.DELAY_BETWEEN_RECORDS_SEC,
            'manual_timeout':        cfg.MANUAL_SETUP_TIMEOUT_SEC,
        }
        # Switch to browser screen so user can interact with portal
        self.show_browser()
        self.webview.start_automation(settings)

    def toggle_pause(self):
        if not self.webview:
            return
        if self._paused:
            self.webview.resume_automation()
            self._paused = False
            self._ctrl.set_pause_label('Pause')
        else:
            self.webview.pause_automation()
            self._paused = True
            self._ctrl.set_pause_label('Resume')

    def stop_automation(self):
        if self.webview:
            self.webview.stop_automation()
        self._paused = False
        self._ctrl.set_pause_label('Pause')

    # ── Callbacks from AndroidWebView (always arrive on Kivy main thread) ─────

    def _on_log(self, msg: str):
        self._ctrl.append_log(msg)

    def _on_phase(self, phase: str):
        self._ctrl.set_phase(phase)
        if phase == 'done':
            # Auto-return to control panel
            Clock.schedule_once(lambda dt: self.show_control(), 1.5)

    def _on_progress(self, approved: int, failed: int):
        self._ctrl.update_progress(approved, failed)

    def _on_module_detected(self, module_name: str, record_count: int):
        """Show a confirmation dialog before automation starts."""
        content = BoxLayout(
            orientation='vertical', spacing=dp(12), padding=dp(14),
        )
        content.add_widget(Label(
            text='[b]Please check before starting[/b]',
            markup=True, font_size=dp(15), color=PURPLE,
            size_hint_y=None, height=dp(30),
        ))
        content.add_widget(Label(
            text=(
                'I am about to click\n'
                '[b]REVIEW -> Approve -> Confirm -> OK[/b]\n'
                'on every record visible on screen.\n'
                'Make sure you opened the right page first.'
            ),
            markup=True, font_size=dp(12), color=TEXT,
            halign='center', valign='center',
            size_hint_y=None, height=dp(80),
        ))
        mod_lbl = Label(
            text=f'[b]{module_name}[/b]\n{record_count} record(s) visible',
            markup=True, font_size=dp(13), color=GREEN,
            halign='center', valign='center',
            size_hint_y=None, height=dp(52),
        )
        content.add_widget(mod_lbl)

        popup = Popup(
            title='Confirm Before Starting',
            content=content,
            size_hint=(0.88, 0.62),
            auto_dismiss=False,
            title_color=PURPLE,
            background_color=SURFACE,
        )

        btns = GridLayout(cols=2, size_hint_y=None, height=dp(50), spacing=dp(8))

        def _yes(_):
            popup.dismiss()
            if self.webview:
                self.webview.confirm_module()

        def _no(_):
            popup.dismiss()
            if self.webview:
                self.webview.reject_module()
            self.show_control()

        yes_btn = Button(
            text='YES, START',
            background_color=GREEN, color=BG, bold=True,
        )
        no_btn = Button(
            text='NO, GO BACK',
            background_color=RED, color=BG,
        )
        yes_btn.bind(on_press=_yes)
        no_btn.bind(on_press=_no)
        btns.add_widget(no_btn)
        btns.add_widget(yes_btn)
        content.add_widget(btns)

        popup.open()

    # ── Android back button ───────────────────────────────────────────────────

    def on_back_pressed(self):
        if self.root.current == 'browser':
            self.show_control()
            return True
        return False


# Allow `Optional` type hint without importing typing at top level on Android
try:
    from typing import Optional
except ImportError:
    pass


def main():
    FasloFasalApp().run()


if __name__ == '__main__':
    main()
