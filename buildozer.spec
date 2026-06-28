[app]

# App metadata
title = FasloFasal
package.name = faslofasal
package.domain = org.faslofasal

# Entry point — Kivy loads main.py
source.dir = .
source.include_exts = py,png,jpg,jpeg,ico,kv,atlas
source.include_patterns = assets/*
source.exclude_dirs = __pycache__, .git, browser-profile, logs, .venv, venv

# Version (keep in sync with config_android.py)
version = 1.2.0

# ── Python requirements ────────────────────────────────────────────────────────
# Do NOT add playwright, PySide6, or chromium — they have no Android recipes.
# Kivy and pyjnius are sufficient; android is the python-for-android helper package.
requirements = python3==3.11.6, kivy==2.3.0, pyjnius, android

# ── Android-specific settings ──────────────────────────────────────────────────
# Include our Java helper so Pyjnius can proxy WebViewClient / WebChromeClient
android.add_src = src

# Permissions required by the app
android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE

# API levels
# evaluateJavascript() requires API >= 19; minapi 21 (Lollipop) is safe
android.minapi = 21
android.api = 33
android.sdk = 33
android.ndk = 25b

# Build architectures (ARM64 for modern phones + ARM for older)
android.archs = arm64-v8a, armeabi-v7a

# Activity entry point (default for Kivy apps)
android.entrypoint = org.kivy.android.PythonActivity

# Enable hardware-accelerated WebView
android.meta_data = android.webkit.WebView.EnableSafeBrowsing=false

# App icon
icon.filename = %(source.dir)s/assets/faslofasal.png

# ── Buildozer settings ─────────────────────────────────────────────────────────
[buildozer]
log_level = 2
warn_on_root = 1
