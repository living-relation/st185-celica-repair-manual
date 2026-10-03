# ST185 Celica GT-Four / All-Trac — Workshop Library

Offline desktop workshop library for the **1993 Toyota Celica GT-Four / All-Trac (ST185)**.
One window, two separate apps in tabs:

- **Repair Manual** — turns a folder of factory-manual PDF sections into a
  searchable, cross-linked workshop reference: thumbnail grid by system,
  full-text search with title-first ranking, factory torque-table links with
  page previews, "see page XX-nn" jump links.
- **Electrical** — the factory electrical wiring diagrams (EWD), split into
  one card per electrical system, with every edition from 1990 to 1993 side by
  side, variants (e.g. Automatic vs Manual A/C, push-button vs dial blower
  control), component and connector locations, fuses and relays, and jump
  links between circuits.

Both use an embedded PDF viewer (PDF.js) — no browser plugins, no Adobe, no
internet connection needed. Each app keeps its own place when you switch tabs
(**Ctrl+1** / **Ctrl+2**), and related sections link across apps (e.g. the
repair manual's *Generator* section links to the *Charging* wiring diagram and
back).

## Quickstart

Double-click **`CelicaManual.exe`**. That's it — it starts a private local
server and opens the library in a native window.

## Prerequisites

**To use the app (typical user):**

- Windows 10 or 11 (64-bit)
- Microsoft Edge WebView2 Runtime — preinstalled on Windows 11 and any
  Windows 10 with Edge; otherwise free from Microsoft:
  <https://developer.microsoft.com/microsoft-edge/webview2/>
- ~750 MB free disk space
- No Python, no internet connection, no Adobe, no browser configuration
  required — everything is bundled in `CelicaManual.exe`, including adding
  new PDFs and rebuilding either library via the in-app **+ Add manuals** panel

**Getting the app:**

- Clone or download this repo and keep the folder structure intact
  (`CelicaManual.exe` and `index.html` at the root, plus the `manuals\`,
  `manuals-electrical\`, `celica-manual\`, `electrical\` and `shared\`
  folders), then double-click `CelicaManual.exe`
- First launch may show Windows SmartScreen — click **More info** then
  **Run anyway** (the exe is unsigned)

**Only for developers modifying the app:**

- Python 3.12+ with `pymupdf`, `pywebview`, `pyinstaller`
- Git + GitHub CLI

## Folder layout

```
Celica Repair Manuals\
├── CelicaManual.exe        the app — double-click to run
├── index.html              shared shell: header + [Repair Manual | Electrical] tabs
├── shared\                 PDF.js viewer, theme, Add-manuals panel, tab messaging
├── manuals\                repair-manual section PDFs
├── manuals-electrical\     wiring-diagram PDFs + sources.json (edition registry)
├── celica-manual\          Repair Manual app
│   ├── index.html          app UI
│   ├── data\               generated search index (data.js, index.json)
│   ├── thumbs\             generated page thumbnails and link previews
│   ├── build\              builder + desktop app source (build.py, app.py)
│   ├── SECTION_INDEX.md    generated master section list
│   ├── TORQUE_SPECS.md     generated torque-table catalog
│   └── CROSS_REFERENCES.md generated cross-reference map
└── electrical\             Electrical app
    ├── index.html          app UI
    ├── build\              builder (build_ewd.py, taxonomy.py, validate_ewd.py)
    ├── data\               generated data (data.js, index.json, repair_links.js)
    ├── circuits\           generated one-PDF-per-circuit files the viewer opens
    ├── thumbs\             generated thumbnails and link previews
    └── SYSTEM_INDEX.md     generated system list per edition
```

## The Electrical app

**Editions.** The library currently holds three wiring-diagram editions:

| Edition | Source | Notes |
|---|---|---|
| 1990 | 1990 Celica All-Trac/4WD EWD (ST185 only) | A/C chapters: push-button blower control only |
| 1992 | EWD132U (AT180 / ST184 / ST185) | Transition year: push-button **and** dial blower control; adds Convertible/Top Stack, Shift Lock, ECT, Electric Tension Reducer |
| 1993 | EWD160U — individual circuits pulled from Toyota TIS | Partial (29 circuits); dial blower control; no convertible |

The 1991 (EWD097U) and complete 1993 (EWD160U) books exist only in print as far
as we could find — drop them in via **+ Add manuals** if you get scans.

**Systems and variants.** Books are split automatically into one circuit per
system using the title printed at the top of every EWD page. Each system card
(Charging, Power Window, Cruise Control, …) holds every edition of that
system; inside, **Edition** and **Variant** chips switch between them (e.g.
Starting & Ignition *All-Trac/4WD* vs *2WD*, Cruise Control *Motor* vs
*Vacuum* type, Radio *w/* vs *w/o CD player*).

**A/C.** The radiator-fan-and-A/C chapter is split into *Automatic A/C* and
*Manual A/C* systems, each tagged by blower control type (five push buttons in
1990–91, a single dial in 1992–93). The A/C card shows a coverage table of
which edition covers each combination, and the system-outline features
(cooling fan, blower motor, recirc/fresh, air-vent mode and air-mix servos, A/C
operation) as jump links. Other circuits whose wiring changes with the blower
control (e.g. 1992 engine control) are listed too.

**My car.** Set your year, model, transmission, body, A/C type, blower control
and options once; the **My car** toggle then hides circuits that don't apply,
and every card opens the edition that best matches your car.

**Locations index.** Every part code (A34 *Auto A/C Amplifier*), harness joint
(IE1), junction block and relay block from each edition's routing pages, with
links to the page that shows where it is. The main search box also finds part
codes, connector codes and fuse names (e.g. `HAZ-HORN`).

## Adding more manuals

No Python needed. In the running app, in either tab:

1. Click **+ Add manuals** in the left rail (under Tools).
2. Drag PDF files into the drop zone (or click to browse), then
   **Upload & check**.
3. Resolve any conflicts (see below), click **Rebuild library** —
   takes ~10–30 seconds; progress is shown live.
4. Click **Reload app** when it finishes.

Uploads in the **Repair Manual** tab go to `manuals\`; uploads in the
**Electrical** tab go to `manuals-electrical\`. New sections get full
functionality automatically. You can also copy PDFs into those folders by
hand and rebuild from the app.

### Wiring-diagram editions and scanned manuals

The Electrical builder decides which edition a PDF belongs to from
`manuals-electrical\sources.json`, from the manual's foreword ("…electrical
system of the 1992 TOYOTA CELICA"), or by matching its printed page numbers
and circuit titles against an edition already in the library (so a single
circuit page pulled from TIS lands in the right year). Add an entry to
`sources.json` to name an edition or set its year.

Text-based PDFs are split automatically. A scanned (image-only) PDF is shown
unsplit until you add a page map `electrical\build\overrides\<file name>.json`:

```json
{"source": {"id": "ewd1991", "year": 1991, "pub": "EWD097U",
            "title": "1991 Celica Electrical Wiring Diagram"},
 "circuits": [
   {"title": "RADIATOR FAN AND AIR CONDITIONER (AUTOMATIC AIR CONDITIONER)",
    "pages": [210, 220], "printed_first": 148,
    "features": [{"n": 1, "title": "Cooling fan operation", "page": 7}]}
 ]}
```

`pages` are PDF pages, `printed_first` is the page number printed on the first
page, and feature `page` counts from the start of the circuit. Titles are the
circuit titles as printed in the manual.

### Duplicate / conflict protection

Every upload is checked against the current library before it is added —
by filename and by content: for the repair manual, the Toyota page codes
printed on each page (e.g. EM-46); for wiring diagrams, the edition plus the
circuit pages it contains. So a section that overlaps an existing one is
caught even under a different name. For each conflict the app shows both
files' page counts plus a verdict, e.g. *"Existing: 21 pages (EM-46–EM-66) ·
Your upload: 24 pages → MORE complete (+3 pages)"* or *"Your upload has
3 pages; 18 existing pages would be LOST"*. You then choose:

- **Abort** — discard the upload, library untouched.
- **Overwrite** — replace the existing file (the button shows exactly how
  many pages you would lose, if any).
- **Keep both** — add the upload under an auto-numbered name
  (`Name_v2.pdf`).

### Replace a single page

Fix one bad scan without re-uploading the whole section: in the
**Add manuals** panel, search for the manual by title or filename, enter
the page number, pick a one-page replacement PDF and click
**Replace page**. The page is swapped in place (page count is preserved;
multi-page PDFs are rejected) — then rebuild the library to refresh
search and previews.

## Rebuilding from the command line (developers)

```powershell
python -m pip install pymupdf
python "celica-manual\build\build.py"            # repair manual: index + thumbnails
python "celica-manual\build\build.py" --thumbs   # force re-render thumbnails
python "electrical\build\build_ewd.py"           # electrical: split circuits, data, previews
python "electrical\build\build_ewd.py" --thumbs  # force re-render circuit PDFs + previews
python "electrical\build\validate_ewd.py"        # sanity-check the electrical library
python "celica-manual\build\validate.py"         # sanity-check the repair library
```

Build the repair manual first when both change — the electrical builder reads
its index to create the cross-app links.

Run the server without a window (for testing in a browser):

```powershell
python "celica-manual\build\app.py" --server-only --port 8765
# then open http://127.0.0.1:8765/index.html
```

Rebuild the exe (needs `pywebview` and `pyinstaller` too):

```powershell
python -m PyInstaller --noconfirm --onefile --windowed --name CelicaManual `
  --workpath "$env:TEMP\cm-build" --specpath "$env:TEMP\cm-build" --distpath . `
  --paths "celica-manual\build" --paths "electrical\build" `
  --hidden-import build --hidden-import build_ewd --hidden-import taxonomy `
  --hidden-import fitz "celica-manual\build\app.py"
```

`Open Celica Manual.bat` (inside `celica-manual\`) is a legacy fallback that
serves the library with plain `python -m http.server` in your default browser —
the Add-manuals panels need the exe, everything else works.

## Copyright note

The PDFs in `manuals\` and `manuals-electrical\` are Toyota factory
service-manual material and are copyrighted by Toyota Motor Corporation.
**Keep this repository private.**
