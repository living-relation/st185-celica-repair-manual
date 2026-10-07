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
├── manuals\                repair-manual section PDFs + library.json (imported-section metadata)
├── manuals-electrical\     wiring-diagram PDFs + sources.json (edition registry)
├── tools\import_books.py   splits whole manuals from gt4.mwp.id.au into both libraries
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

**Editions.** 1993 is the primary edition; earlier years stay alongside it:

| Edition | Source | Notes |
|---|---|---|
| 1993 TIS | EWD160U — individual circuits pulled from Toyota TIS | Factory diagrams, partial (29 circuits); dial blower control; no convertible |
| 1993 Mitchell | 1993 Celica Service Manual (aftermarket, from gt4.mwp.id.au) | 40 systems: each system's diagnosis/testing/removal article plus its system wiring diagram and the matching overall grid diagrams. Fills the 1993 circuits TIS lacks (ABS, SRS, cruise control, heater, cooling fan, column switches, component locator, …) |
| 1992 | EWD132U (AT180 / ST184 / ST185) | Transition year: push-button **and** dial blower control; adds Convertible/Top Stack, Shift Lock, ECT, Electric Tension Reducer |
| 1990 | 1990 Celica All-Trac/4WD EWD (ST185 only) | A/C chapters: push-button blower control only |
| Ref | ECU pinouts, alternator guide, Toyota Wire Harness Repair Manual (RM1022E) | General references |

Each card opens the best match for your car: same year first, Toyota factory
diagrams before the aftermarket manual. The 1991 (EWD097U) and complete 1993
(EWD160U) Toyota books exist only in print as far as we could find — drop them
in via **+ Add manuals** if you get scans.

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

**Garage.** Both tabs share one list of saved cars. Each tab picks its own
car, so the repair tab can stay on a 1993 All-Trac while the electrical tab
looks at a 1990 car. The toolbar button turns that tab's filter on or off.
With the filter on, wiring circuits that do not fit the picked car are hidden,
and repair sections for a different engine or a different year are hidden when
the picked year already has that system. Add, edit, or delete cars under
**Garage** in either tab. A 1993 All-Trac can be filled in as an example, and
it is not selected until you save it. An older saved car from a previous
version is kept for the electrical tab only.

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

### Whole books from gt4.mwp.id.au

`tools/import_books.py` splits the whole manuals published at
<https://gt4.mwp.id.au/> into sections and keeps only what the library does
not already have (matched by Toyota page code):

| Book | Goes to | What is kept |
|---|---|---|
| 1993 ST185 Repair Manual vol. 1 (RM305U1) | Repair Manual | One section per chapter (page-header topic), skipping chapters already in the library and 4A-FE-only chapters |
| 1990 ST185 All-Trac Repair Manual (RM176U) | Repair Manual | Clutch, E150F transaxle, propeller shaft, suspension & axle, brakes, steering, body electrical, body — tagged 1990 so its page codes never link into 1993 pages |
| 1994 3S-GTE engine supplement (RM398E) and ST205 chassis and body supplement (RM399E) | Repair Manual | Whole books. Tagged 1994 so their page numbers never open a 1993 page. They still show when a 1993 All-Trac is selected, because a few procedures differ |
| 1993 Celica Service Manual (aftermarket) | Electrical + Repair Manual | Electrical articles and wiring diagrams become the *1993 Mitchell* edition; ST185-relevant mechanical articles (2.0L turbo engine, engine performance/diagnostics, A/C servicing, axles, brakes, steering, suspension, alignment, maintenance) become repair sections |
| Small references | either app | Specifications, chassis dimensions, E-series gearbox notes, ECU pinouts, alternator guide, Wire Harness Repair Manual, brake and suspension notes, CT26 rebuild guide, and the 1990 FWD wiring diagram |

```powershell
python tools\import_books.py C:\Users\<you>\Downloads    # folder with the MWP PDFs (original names)
python "celica-manual\build\build.py"
python "electrical\build\build_ewd.py"
```

Imported repair sections carry a source-book badge (e.g. *RM305U1 (1993)*);
their titles, systems and editions are recorded in `manuals\library.json`.
Re-running the importer replaces everything it imported before.

### Wiring-diagram editions and scanned manuals

The Electrical builder decides which edition a PDF belongs to from
`manuals-electrical\sources.json`, from the manual's foreword ("…electrical
system of the 1992 TOYOTA CELICA"), or by matching its printed page numbers
and circuit titles against an edition already in the library (so a single
circuit page pulled from TIS lands in the right year). Add an entry to
`sources.json` to name an edition or set its year.

Picture-only pages are read with Tesseract the first time a catalog is built,
and the words are stored invisibly on those pages so search and the PDF viewer
treat them like the other manuals. That needs Tesseract installed. If it is
missing, the build still finishes and those pages stay pictures.

Text-based PDFs are split automatically. A scanned PDF that still has no text
is shown
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

`pages` are PDF pages (or `page_list` for any set of pages), `printed_first`
is the page number printed on the first page, and feature `page` counts from
the start of the circuit. Titles are the circuit titles as printed in the
manual. Page maps also work for text PDFs that aren't laid out like a Toyota
EWD — the 1993 Mitchell edition is mapped this way.

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
  --hidden-import ocr_pages `
  --hidden-import fitz "celica-manual\build\app.py"
```

`Open Celica Manual.bat` (inside `celica-manual\`) is a legacy fallback that
serves the library with plain `python -m http.server` in your default browser —
the Add-manuals panels need the exe, everything else works.

## Copyright note

The PDFs in `manuals\` and `manuals-electrical\` are Toyota factory
service-manual material and are copyrighted by Toyota Motor Corporation.
**Keep this repository private.**
