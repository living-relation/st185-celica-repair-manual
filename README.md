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

Requirements: Windows 10/11 with the Microsoft Edge WebView2 runtime
(preinstalled on any up-to-date Windows).

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
