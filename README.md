# ST185 Celica GT-Four / All-Trac — Repair Manual App

Offline repair-manual desktop app for the **1993 Toyota Celica GT-Four / All-Trac (ST185)**.
It turns a folder of factory-manual PDF sections into a searchable, cross-linked
workshop reference: thumbnail grid by system, full-text search with title-first
ranking, factory torque-table links with page previews, "see page XX-nn" jump
links, and an embedded PDF viewer (PDF.js) — no browser plugins, no Adobe, no
internet connection needed.

## Quickstart

Double-click **`CelicaManual.exe`**. That's it — it starts a private local
server and opens the app in a native window.

## Prerequisites

**To use the app (typical user):**

- Windows 10 or 11 (64-bit)
- Microsoft Edge WebView2 Runtime — preinstalled on Windows 11 and any
  Windows 10 with Edge; otherwise free from Microsoft:
  <https://developer.microsoft.com/microsoft-edge/webview2/>
- ~700 MB free disk space
- No Python, no internet connection, no Adobe, no browser configuration
  required — everything is bundled in `CelicaManual.exe`, including adding
  new PDFs and rebuilding the index via the in-app **+ Add manuals** panel

**Getting the app:**

- Clone or download this repo and keep the folder structure intact
  (`CelicaManual.exe` at the root, `manuals\` subfolder), then double-click
  `CelicaManual.exe`
- First launch may show Windows SmartScreen — click **More info** then
  **Run anyway** (the exe is unsigned)

**Only for developers modifying the app:**

- Python 3.12+ with `pymupdf`, `pywebview`, `pyinstaller`
- Git + GitHub CLI

## Folder layout

```
Celica Repair Manuals\
├── CelicaManual.exe        the app — double-click to run
├── manuals\                all manual-section PDFs (283 files)
└── celica-manual\
    ├── index.html          the single-file app UI
    ├── data\               generated search index (data.js, index.json)
    ├── thumbs\             generated page thumbnails and link previews
    ├── pdfjs\              vendored PDF.js viewer
    ├── build\              builder + app source (build.py, app.py)
    ├── SECTION_INDEX.md    generated master section list
    ├── TORQUE_SPECS.md     generated torque-table catalog
    └── CROSS_REFERENCES.md generated cross-reference map
```

## Adding more manuals

No Python needed. In the running app:

1. Click **+ Add manuals** in the left rail (under Tools).
2. Drag PDF files into the drop zone (or click to browse), then **Upload**.
3. Click **Rebuild library** — takes ~10–30 seconds; progress is shown live.
4. Click **Reload app** when it finishes.

New sections get full functionality automatically: search, thumbnails,
torque-table links and cross-references.

You can also just copy PDFs into `manuals\` by hand and rebuild from the app.

## Rebuilding from the command line (developers)

```powershell
python -m pip install pymupdf
python "celica-manual\build\build.py"           # rebuild index + thumbnails
python "celica-manual\build\build.py" --thumbs  # force re-render thumbnails
```

Rebuild the exe (needs `pywebview` and `pyinstaller` too):

```powershell
python -m PyInstaller --noconfirm --onefile --windowed --name CelicaManual `
  --workpath "$env:TEMP\cm-build" --specpath "$env:TEMP\cm-build" --distpath . `
  --paths "celica-manual\build" --hidden-import build --hidden-import fitz `
  "celica-manual\build\app.py"
```

`Open Celica Manual.bat` (inside `celica-manual\`) is a legacy fallback that
serves the app with plain `python -m http.server` in your default browser —
the Add-manuals panel needs the exe, everything else works.

## Copyright note

The PDFs in `manuals\` are Toyota factory service-manual material and are
copyrighted by Toyota Motor Corporation. **Keep this repository private.**
