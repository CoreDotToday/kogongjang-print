# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Certificate/award printing system (감사장/상장 인쇄 시스템) for Korean organizations. A customtkinter GUI manages settings and runs an embedded Flask server in a daemon thread. The server composes A4 PDFs (background image + optional bordered photo + name text) with **fpdf2** and prints them silently via SumatraPDF on Windows. An optional Chrome kiosk window can be auto-opened against the `/preview` page so the box behaves like a turnkey appliance.

## Run / Build

```bash
# Install runtime deps
pip install -r requirements.txt

# Run with GUI (recommended — also starts the Flask server in a thread)
python gui.py

# Run server only (no GUI; binds 0.0.0.0:<port from config.json>)
python app.py

# Build a single-file Windows exe (Nuitka, onefile, console hidden).
# Use a dedicated venv — see `command` file. Anaconda/system Python pulls
# in scipy/numpy/etc. that bloat the binary; build_venv keeps it lean.
python -m venv build_venv
.\build_venv\Scripts\activate
pip install -r requirements.txt
python build.py        # outputs dist\감사장인쇄.exe
```

There is no test suite or linter configured.

## Architecture

### Module layout
- **`gui.py`** — entry point. customtkinter UI for all settings; runs Flask via `werkzeug.make_server` in a daemon thread so the server can be cleanly stopped from the UI. Also handles: Windows Registry autostart toggle (HKCU `...\Run`), pystray system-tray hide on minimize, socket-based duplicate-instance check (refuses to start if the configured port is already in use), Chrome kiosk launch.
- **`app.py`** — Flask app. Stateless apart from `kiosk_process_holder` (a dict shared with `gui.py` so the `/close-kiosk` route can terminate the Chrome process the GUI launched).
- **`config.py`** — `config.json` loader/saver with `DEFAULT_CONFIG` merge, SumatraPDF auto-detection, and `find_background()` lookup (external folder first, then bundled).
- **`build.py`** — Nuitka invocation. Includes `flask`, `werkzeug`, `jinja2`, `markupsafe`, `flask_cors`, `fpdf`, `PIL`, `requests`, `pystray`, `customtkinter` (with package data); explicitly **excludes** `fitz`/`pymupdf`/`scipy`/`numpy`/`pandas`/`torch`/etc. via `--nofollow-import-to`.

### HTTP routes (all in `app.py`)
- `GET /preview?name=...` — renders `templates/template.html` (HTML A4 preview, used as the kiosk page).
- `GET /test?name=...` — generates a PDF and returns it inline in the browser.
- `POST /print` `{name, img?}` — generates a PDF and silently prints to the default printer via SumatraPDF (`-print-to-default -silent`). `img` may be an http(s) URL, a `data:image/...;base64,...` URI, or a local path; it is fitted to 556×604, given a 3px black border, then placed.
- `POST /close-kiosk` — terminates the kiosk Chrome process tree via `taskkill /F /T` (if the GUI launched one).
- `POST /quit` — graceful app shutdown (Flask server + GUI + kiosk Chrome). Routed through `shutdown_callback_holder["callback"]` which the GUI registers in `_start_server`; the callback re-schedules `_on_close` onto the Tk main thread via `root.after(0, ...)`. Used by `check_duplicate` to politely terminate a running instance.
- `POST /shutdown` — Windows `shutdown /s /t 0` (powers off the host). **Not** the same as `/quit`.
- `GET /backgrounds/<filename>` — serves images from the **external** `backgrounds/` folder.

### PDF generation
`generate_pdf()` uses **fpdf2** in `mm`/A4 mode. Coordinates in `config.json` (`name_x`, `name_y`, `name_width`, `name_height`) are stored in **points (pt)** for historical reasons and converted to mm via `pt_to_mm()` before drawing. The photo box uses hard-coded pt rect `(69, 186, 208, 337)` — also pt→mm converted.

### Path resolution (important for Nuitka onefile)
- `config.py` derives `APP_DIR` from `sys.argv[0]` and centralizes all user/runtime files under `APP_DIR/data/`:
  ```
  data/
    ├── config.json     (atomic save: tmp + fsync + os.replace)
    ├── backgrounds/    (user PNG templates)
    ├── fonts/          (user TTF/OTF)
    ├── output/         (generated PDFs)
    └── error.log
  ```
  `data/` lives **next to the exe**, not inside Nuitka's temp extract dir. The first time `data/` is created, `_migrate_legacy_layout()` moves any pre-existing `config.json` / `backgrounds/` / `output/` from `APP_DIR` into it (so existing installs upgrade transparently).
- `app.py`/`gui.py` derive `BASE_DIR` from `__file__` for **bundled** static assets (`static/images/`, `static/fonts/`, `templates/`) which Nuitka packs into the binary via `--include-data-dir`.
- `find_background()` and `find_font()` check the **user** folder (`data/backgrounds/`, `data/fonts/`) first, then fall back to the bundled assets. The GUI dropdowns (`_get_backgrounds`, `_get_fonts`) union both. PDF generation in `app.py` uses the same lookup so user-added fonts/backgrounds are reflected on print.
- `gui.py` inlines the `data/` path computation at the top (before any third-party imports) so `error.log` redirect and `show_startup_error()` work even if the import chain blows up.
- `_toggle_autostart()` must use `__nuitka_binary_dir` (not `sys.argv[0]`) when `__compiled__` is defined, because onefile sets `argv[0]` to the temp extract path which disappears between runs.

### GUI ↔ server communication
- The GUI imports `app.app` lazily inside `_start_server()` to avoid Flask import cost at UI launch.
- Werkzeug logs are routed to a `queue.Queue` via `QueueLogHandler` and pumped into the CTkTextbox every 100ms, so the in-app log pane shows live request traffic without thread-unsafe Tk calls.
- Chrome kiosk is launched with `--kiosk --user-data-dir=%LOCALAPPDATA%\KogongjangKiosk\ChromeData` and `--force-device-scale-factor=<kiosk_zoom/100>`. The `Popen` handle is stashed in `app.kiosk_process_holder` so `/close-kiosk` can terminate it.

## config.json

Auto-created on first run by merging `DEFAULT_CONFIG` over the saved file (so adding new keys in `config.py` is backward-compatible). Not committed. Keys: `background`, `font`, `font_size`, `name_x/y/width/height` (pt), `sumatra_path` (`"auto"` triggers `find_sumatra()`), `port`, `kiosk_url`, `kiosk_auto_open`, `kiosk_zoom`.

## Platform notes

- **Windows-only** at runtime: `winreg` (autostart), SumatraPDF CLI (printing), `shutdown.exe` (`/shutdown` route), Chrome paths under `%PROGRAMFILES%`.
- `static/fonts/` ships Korean TTFs (NanumSquare, MaruBuri weights). fpdf2 needs `add_font(..., uni=True)` for Unicode — already wired.
- `output/` is auto-created and used as a scratch dir for generated PDFs.
- `docs/frontend-api-guide.md` documents the HTTP API for frontend consumers — keep it in sync if you change routes.
