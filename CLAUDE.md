# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Certificate/award printing application (감사장/상장 인쇄 시스템) for Korean organizations. A Tkinter GUI manages settings and runs a Flask web server that generates PDFs with a background image template and overlaid name text, then prints them via SumatraPDF on Windows.

## Architecture

- **`gui.py`** — Main entry point. Tkinter GUI for settings management (background, font, text position, SumatraPDF path, port). Runs Flask server in a daemon thread. Supports system tray minimization via pystray.
- **`config.py`** — Configuration module. Loads/saves `config.json`, provides defaults, auto-detects SumatraPDF path.
- **`config.json`** — Runtime settings (background, font, font_size, name position, SumatraPDF path, port). Auto-created with defaults on first run. Not committed to git.
- **`app.py`** — Flask app with three routes. Reads all settings from `config.json` via `config.py`:
  - `GET /preview` — HTML preview of certificate with name via Jinja2 template
  - `GET /test` — Generates and returns a PDF directly in browser
  - `POST /print` — Generates PDF and sends to default printer via SumatraPDF
- **`generate_pdf()`** — Uses PyMuPDF (fitz) to compose A4 PDF: background image + optional photo (with border) + name text
- **`print_pdf()`** — Calls SumatraPDF CLI (`-print-to-default -silent`) to print
- **`templates/template.html`** — Jinja2 template for HTML preview (A4-sized, background image + name overlay)
- **`static/images/background_*.png`** — Organization-specific background templates (selected via GUI/config)
- **`static/fonts/`** — Korean fonts: NanumSquare (`nanum.ttf`), MaruBuri (multiple weights)

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run with GUI (recommended)
python gui.py

# Run server only (no GUI)
python app.py
# Server starts at http://0.0.0.0:5000

# Preview a certificate in browser
# GET http://localhost:5000/preview?name=홍길동

# Generate test PDF
# GET http://localhost:5000/test?name=홍길동
```

## Key Details

- Target platform is Windows (SumatraPDF for printing)
- SumatraPDF path is auto-detected or configurable via GUI/config.json
- The `output/` directory is auto-created at startup for generated PDFs
- Background template is selected via GUI dropdown (no manual symlink needed)
- Photo images in `/print` accept URLs, base64 data URIs, or local file paths
- PDF dimensions: A4 (595×842 points), name text position configurable via GUI
- All settings persist in `config.json`
