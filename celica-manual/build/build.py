#!/usr/bin/env python3
"""
Celica ST185 GT-Four / All-Trac repair-manual catalog builder.

Reads every *.pdf in the manuals folder (<root>/manuals, sibling of the
celica-manual dir), extracts text with PyMuPDF, detects Toyota factory
section codes (EM, MX, FI...),
engine applicability (3S-GTE / 5S-FE), torque specs and cross-references, then
writes:
    data/index.json         machine-readable master index (no full text)
    data/data.js            window.CELICA_DATA = {...}  (full text, used by app)
    SECTION_INDEX.md        human-readable master section list
    TORQUE_SPECS.md         every torque value found, grouped by section
    CROSS_REFERENCES.md     cross-reference map (page code -> file)
Run:  python build.py
"""
from __future__ import annotations
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("PyMuPDF not installed. Run: python -m pip install pymupdf")

import ocr_pages

def _find_app_dir() -> Path:
    """celica-manual dir. When frozen inside CelicaManual.exe, __file__ points
    at the PyInstaller temp extraction dir, so anchor on the exe instead."""
    if getattr(sys, "frozen", False):
        here = Path(sys.executable).resolve().parent
        for cand in (here, here.parent, here.parent.parent):
            if (cand / "celica-manual" / "index.html").is_file():
                return cand / "celica-manual"
        raise SystemExit("Could not find celica-manual/ near the exe.")
    return Path(__file__).resolve().parents[1]

APP_DIR = _find_app_dir()                          # ...\celica-manual
MANUALS_DIR = APP_DIR.parent / "manuals"           # ...\<root>\manuals
LIBRARY_JSON = MANUALS_DIR / "library.json"
DATA_DIR = APP_DIR / "data"
THUMB_DIR = APP_DIR / "thumbs"
DATA_DIR.mkdir(parents=True, exist_ok=True)
THUMB_DIR.mkdir(parents=True, exist_ok=True)
THUMB_TARGET_W = 360        # target thumbnail width in px
FORCE_THUMBS = False        # re-render even if thumb exists (see run_build)

# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------
_TRANS = {
    0x2212: "-",  # minus sign
    0x2010: "-", 0x2011: "-", 0x2013: "-", 0x2014: "-", 0x2015: "-",
    0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"',
    0x00A0: " ", 0x2022: "-", 0x00B7: "-", 0x2027: "-",
    0x0060: "'",
}

def norm(s: str) -> str:
    return s.translate(_TRANS)

# ---------------------------------------------------------------------------
# Toyota factory section-code map  (code -> (system name, group))
# ---------------------------------------------------------------------------
CODE_MAP = {
    "IN": ("Introduction", "General"),
    "MA": ("Maintenance", "General"),
    "EM": ("Engine Mechanical", "Engine"),
    "TC": ("Turbocharger", "Engine"),
    "LU": ("Lubrication", "Engine"),
    "CO": ("Cooling", "Engine"),
    "FI": ("Fuel / EFI (MFI-SFI)", "Engine"),
    "EF": ("Fuel System", "Engine"),
    "SF": ("SFI System", "Engine"),
    "EC": ("Emission Control", "Engine"),
    "FU": ("Fuel", "Engine"),
    "EG": ("Engine Mechanical", "Engine"),
    "DI": ("Body Dimensions", "Body"),
    "IG": ("Ignition", "Engine Electrical"),
    "ST": ("Starting", "Engine Electrical"),
    "CH": ("Charging", "Engine Electrical"),
    "CL": ("Clutch", "Drivetrain"),
    "MX": ("Manual Transaxle S53 (FWD)", "Drivetrain"),
    "MT": ("Manual Transmission E150F (4WD)", "Drivetrain"),
    "AX": ("Automatic Transaxle", "Drivetrain"),
    "AT": ("Automatic Transaxle", "Drivetrain"),
    "PR": ("Propeller Shaft", "Drivetrain"),
    "TF": ("Transfer", "Drivetrain"),
    "SA": ("Suspension & Axle", "Chassis"),
    "BR": ("Brakes", "Brakes"),
    "AB": ("ABS", "Brakes"),
    "SR": ("Supplemental Restraint", "Body"),
    "BE": ("Body Electrical", "Electrical"),
    "BO": ("Body", "Body"),
    "AC": ("Air Conditioning", "HVAC"),
    "SS": ("Service Specifications", "General"),
    "MX ": ("Manual Transaxle", "Drivetrain"),
    "EX": ("Exhaust", "Engine"),
    "RE": ("Body Repair (panels)", "Body"),
    "CN": ("Body Construction", "Body"),
    "PP": ("Plastic Body Parts", "Body"),
    "AP": ("Appendix", "General"),
    "RS": ("Restraint / Seat Belt", "Body"),
}

# Filename-keyword fallback -> (system name, group).  First match wins.
KEYWORD_RULES = [
    (("turbocharg", "turbo"), ("Turbocharger", "Engine")),
    (("timing_belt",), ("Engine Mechanical", "Engine")),
    (("cylinder_head", "cylinder_block", "compression", "oil_nozzle"),
     ("Engine Mechanical", "Engine")),
    (("water_pump", "cooling", "radiator_support", "radiator_upper"),
     ("Cooling", "Engine")),
    (("oil_pump", "oil_cooler", "oil_pressure", "lubrication",
      "removal_and_installation_of_oil"), ("Lubrication", "Engine")),
    (("throttle_body", "fuel_pump", "fuel_tank", "fuel_cut", "cold_start_injector",
      "mfi", "sfi", "circuit_opening_relay", "control_relay"),
     ("Fuel / EFI", "Engine")),
    (("positive_crankcase", "emission", "egr", "evap"),
     ("Emission Control", "Engine")),
    (("tvis", "ac_idleup", "idle_air_control", "turbocharging_pressure",
      "intake_air_temperature", "engine_coolant_temperature"),
     ("Engine Management", "Engine")),
    (("onvehicle_inspection", "engine_tuneup", "engine_mechanical",
      "description_3sgte", "description_5sfe", "eng3s", "compression_check"),
     ("Engine Mechanical", "Engine")),
    (("distributor", "ignition", "integrated_ignition"),
     ("Ignition", "Engine Electrical")),
    (("charging", "generator"), ("Charging", "Engine Electrical")),
    (("starting", "startall"), ("Starting", "Engine Electrical")),
    (("clutch", "bleeding_of_clutch"), ("Clutch", "Drivetrain")),
    (("differential", "front_drive_shaft", "rear_drive_shaft", "propeller",
      "transfer", "front_axle_hub", "rear_axle_hub"),
     ("Drivetrain (4WD)", "Drivetrain")),
    (("input_shaft", "output_shaft", "gear_housing", "shift_and_select",
      "shift_lever", "removal_and_installation_of_tra", "transaxle",
      "installation_of_component_parts", "component_parts_installation",
      "component_parts_removal", "removal_of_component_parts",
      "assembly_removal"), ("Manual Transaxle", "Drivetrain")),
    (("antilock", "abs", "speed_sensor", "deceleration"), ("ABS", "Brakes")),
    (("brake", "master_cylinder", "proportioning", "disc_brake",
      "brake_booster", "front_speed_sensor"), ("Brakes", "Brakes")),
    (("seat_belt", "seatbelt", "rcm", "restraint"),
     ("Supplemental Restraint", "Body")),
    (("electronic_control_module", "ecm", "location_of_electronic",
      "diagnosis_system"), ("Engine Control (ECM)", "Engine")),
    (("power_source", "powrsource", "pwrsource", "relay_location",
      "ground_point", "connector", "electrical_wire", "wire_routing",
      "component_layout", "component_location"),
     ("Electrical / Wiring", "Electrical")),
    (("powrwind", "pwrseat", "doorlock", "radiow", "usbw", "horn",
      "illumination", "combmeter", "interiorlight", "taillight", "stoplight",
      "hdlit", "headlight", "sunroof", "auto_tilt", "tilt_steering",
      "gear_housing_steering"), ("Body Electrical", "Electrical")),
    (("body_dimension", "body_lower", "body_opening", "front_body",
      "front_fender", "front_side_member", "front_crossmember", "cowl",
      "quarter", "rocker", "roof_panel", "rear_floor", "under_body",
      "location_of_plastic", "high-strength", "rust-resistant",
      "standard_body", "front_door", "doorg", "quartert",
      "luggage_compartment"), ("Body / Collision", "Body")),
    (("radair", "radiator_and_air"), ("Radiator / A/C Fan", "HVAC")),
    (("exhaust",), ("Exhaust", "Engine")),
    (("electric", "tshwl", "usbw", "fww"), ("Electrical / Wiring", "Electrical")),
    (("removalo", "remov"), ("Removal / Installation", "Body")),
    (("fit_standard", "rwd", "atas", "theoryof", "operation",
      "system_purpose", "description"), ("Reference", "General")),
    (("foreword", "how_to_use", "abbreviation", "symbol", "identification",
      "precaution", "preparation", "general_", "maintenance_operation",
      "part_number", "male_waterproof"), ("General Info", "General")),
]

# Forced filename overrides (take precedence over page-code detection)
FORCE_RULES = [
    ("general_information", ("General Information", "General")),
    ("diagnosis_system", ("Engine Diagnostics", "Engine")),
]

# Collision / TSB filename prefixes -> Body group
def tsb_group(stem: str):
    s = stem.lower()
    if re.match(r"^t-|^ts-|^tsb|^tss", s):
        # crude bucket by 2nd token
        if re.search(r"br|brake", s):
            return ("Brake Bulletin", "Body")
        if re.search(r"eg|engine", s):
            return ("Engine Bulletin", "Engine")
        if re.search(r"bo|body|qtg|crib", s):
            return ("Collision / Body Bulletin", "Body")
        if re.search(r"ac", s):
            return ("A/C Bulletin", "HVAC")
        if re.search(r"pg|paint", s):
            return ("Paint / Prep Bulletin", "Body")
        if re.search(r"ss|structure", s):
            return ("Structure Bulletin", "Body")
        if re.search(r"ax|dl|st|su|pa|pd|tc|ai|cp", s):
            return ("Service Bulletin", "Body")
        return ("Service Bulletin", "Body")
    return None

# ---------------------------------------------------------------------------
# Regexes
# ---------------------------------------------------------------------------
CODE_LINE = re.compile(r"^([A-Z]{2})\s*-\s*(\d{1,3}[A-Za-z]?)$")
REF_CODE = re.compile(r"pages?\s+([A-Z]{2})\s*-\s*(\d{1,3})")
TORQUE_INLINE = re.compile(r"Torque\s*:?\s*(.*)", re.IGNORECASE)
TORQUE_UNIT = re.compile(
    r"(N\s*-?\s*m|kgf|kg\s*-?\s*cm|ft\s*-?\s*lb|in\.?\s*-?\s*lb)", re.IGNORECASE)


def prettify(stem: str) -> str:
    s = re.sub(r"\s*\(\d+\)$", "", stem)          # drop trailing (1)/(2)
    s = re.sub(r"_\d+$", "", s)                    # drop trailing _1
    s = s.replace("_", " ").strip()
    return s[:1].upper() + s[1:] if s else stem


def _engine_hits(blob: str) -> list[str]:
    """Engines named in a filename or page text. Longer names are checked
    first so 3S-GTE is never mistaken for 3S-GE."""
    low = blob.lower()
    found = []
    checks = (
        ("3sgte", ("3sgte", "3s-gte", "3s gte")),
        ("3sge", ("3sge", "3s-ge", "3s ge")),
        ("5sfe", ("5sfe", "5s-fe", "5s fe")),
        ("4afe", ("4afe", "4a-fe", "4a fe")),
    )
    for key, names in checks:
        if any(name in low for name in names):
            found.append(key)
    return found


def detect_engine(stem: str, text: str):
    """Prefer the engine in the file name. A long book that mentions a
    second engine in passing stays with the engine the file is about."""
    named = _engine_hits(stem)
    if len(named) == 1:
        return named[0]
    if len(named) > 1:
        return "both"
    found = _engine_hits(text)
    if len(found) == 1:
        return found[0]
    if len(found) > 1:
        return "both"
    return "na"


def detect_edition(stem: str, meta: dict) -> str:
    """Year stamped on an imported book. Blank means the main 1993 shelf."""
    edition = str(meta.get("edition") or "")
    if edition:
        return edition
    match = re.search(r"(1990|1991|1992|1993)", stem)
    return match.group(1) if match else ""


def extract_pdf(path: Path, thumb_path: Path):
    doc = fitz.open(path)
    pages = [norm(pg.get_text("text")) for pg in doc]
    if doc.page_count and (FORCE_THUMBS or not thumb_path.exists()):
        try:
            p0 = doc.load_page(0)
            pw = p0.rect.width or 612
            zoom = max(0.4, min(1.3, THUMB_TARGET_W / pw))
            pix = p0.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            pix.save(thumb_path)
        except Exception as e:
            print(f"  thumb fail {path.name}: {e}")
    doc.close()
    return pages


def load_library() -> dict:
    """Per-file metadata for sections split out of whole books
    (manuals/library.json, written by tools/import_books.py):
    title, system, group, engine, code, book (source manual), edition
    (year of a manual whose page codes differ from the main library)."""
    try:
        return json.loads(LIBRARY_JSON.read_text(encoding="utf-8")).get("files", {})
    except (OSError, ValueError):
        return {}


def build():
    ocr_pages.convert_tree(MANUALS_DIR)
    pdfs = sorted(MANUALS_DIR.glob("*.pdf"), key=lambda p: p.name.lower())
    print(f"Found {len(pdfs)} PDFs in {MANUALS_DIR}")
    library = load_library()

    records = []
    page_index = {}            # "EM-46" -> file id   (main library)
    ed_index = defaultdict(dict)   # other editions: edition -> code -> file id
    unmapped = []

    for path in pdfs:
        stem = path.stem
        meta = library.get(path.name, {})
        thumb_name = stem + ".png"
        pages = [ocr_pages.strip_sentinel(pg)
                 for pg in extract_pdf(path, THUMB_DIR / thumb_name)]
        n = len(pages)
        full = "\n".join(
            f"\n===== PAGE {i} of {n} =====\n{pg}" for i, pg in enumerate(pages, 1)
        )

        # --- per-page: own footer code + torque-page detection ---
        code_by_page = []
        torque_pages = []        # pages that merely mention a torque value
        torque_table_pages = []  # pages with a TORQUE SPECIFICATIONS table heading
        for pno, ptext in enumerate(pages, 1):
            last = None
            for ln in ptext.splitlines():
                ln = ln.strip()
                m = CODE_LINE.match(ln)
                if m:
                    last = f"{m.group(1)}-{m.group(2)}"
            code_by_page.append(last)
            up = ptext.upper()
            # "TORQUE SPECIFICATIONS" heading, or a continuation page of the
            # same columnar table (Toyota tables repeat "Part tightened")
            if "TORQUE SPECIFICATION" in up or "PART TIGHTENED" in up:
                torque_table_pages.append(pno)
            elif TORQUE_UNIT.search(ptext):
                torque_pages.append(pno)
        own_codes = [c for c in code_by_page if c]
        code_pages = {}                       # Toyota code -> 1-based page in THIS pdf
        for idx, c in enumerate(code_by_page):
            if c and c not in code_pages:
                code_pages[c] = idx + 1

        prefixes = Counter(c.split("-")[0] for c in own_codes)
        code = prefixes.most_common(1)[0][0] if prefixes else meta.get("code")

        # --- classification (library metadata, then forced filename overrides) ---
        system, group = meta.get("system"), meta.get("group")
        low0 = stem.lower()
        for key, (sysn, grp) in ([] if system else FORCE_RULES):
            if key in low0:
                system, group = sysn, grp
                break
        if system is None and code and code in CODE_MAP:
            system, group = CODE_MAP[code]
        if system is None:
            low = stem.lower()
            for keys, (sysn, grp) in KEYWORD_RULES:
                if any(k in low for k in keys):
                    system, group = sysn, grp
                    break
        if system is None:
            tg = tsb_group(stem)
            if tg:
                system, group = tg
        if system is None:
            system, group = ("Uncategorized", "Other")
            unmapped.append(stem)

        engine = meta.get("engine") or detect_engine(stem, full)
        real_chars = sum(len("".join(pg.split())) for pg in pages)
        image_only = real_chars < 40 * max(1, n)
        # "ref" keeps other-engine books out of the All-Trac wiring links.
        # The My car filter uses the engine tag, not this flag.
        relevance = "ref" if engine in ("5sfe", "3sge", "4afe") else "car"

        # --- first heading (title) from page 1, ignoring markers ---
        first_heading = ""
        for ln in (pages[0].splitlines() if pages else []):
            t = ln.strip()
            if len(t) >= 4 and not CODE_LINE.match(t) \
               and not t.startswith("--") and not t.startswith("====="):
                first_heading = t
                break
        title = meta.get("title") or prettify(stem)
        edition = detect_edition(stem, meta)

        # --- torque specs ---
        torques = []
        lines = [l.strip() for l in full.splitlines()]
        for i, ln in enumerate(lines):
            m = TORQUE_INLINE.match(ln)
            if m:
                val = m.group(1).strip()
                if not TORQUE_UNIT.search(val) and i + 1 < len(lines):
                    val = lines[i + 1].strip()
                if not val or not TORQUE_UNIT.search(val):
                    continue
                # nearest preceding descriptive line as context
                ctx = ""
                for j in range(i - 1, max(-1, i - 6), -1):
                    c = lines[j]
                    if c and not TORQUE_INLINE.match(c) and not CODE_LINE.match(c) \
                       and not c.startswith("--") and not c.startswith("=====") \
                       and len(c) > 3:
                        ctx = c
                        break
                torques.append({"context": ctx[:120], "value": val[:120]})

        # --- cross references ---
        refs = []
        seen = set()
        for m in REF_CODE.finditer(full):
            rc = f"{m.group(1)}-{m.group(2)}"
            if rc in seen:
                continue
            seen.add(rc)
            refs.append(rc)

        rec = {
            "id": stem,
            "file": path.name,
            "thumb": thumb_name,
            "title": title,
            "heading": first_heading[:140],
            "code": code or "",
            "system": system,
            "group": group,
            "engine": engine,
            "relevance": relevance,
            "image_only": image_only,
            "pages": len(pages),
            "own_codes": own_codes,
            "code_pages": code_pages,
            "torque_pages": torque_pages,
            "torque_table_pages": torque_table_pages,
            "torques": torques,
            "has_torque_table": bool(torque_table_pages),
            "refs": refs,
            "book": meta.get("book", ""),
            "edition": edition,
            "text": full,
        }
        records.append(rec)
        index = ed_index[edition] if edition else page_index
        for c, pno in code_pages.items():
            index.setdefault(c, {"file": stem, "page": pno})

    # --- resolve cross references to target file + page ---
    # Toyota page codes are sequential within a file, so a code whose footer
    # was never detected can still be estimated from the nearest detected
    # code sharing its prefix (nearest-page fallback, max jump NEAR_MAX).
    NEAR_MAX = 6

    def resolve_near(rc, edition):
        """Estimate (file id, pdf page) for an undetected code, or None.
        Only searches sections of the same edition: page codes are
        renumbered between model years."""
        m = re.match(r"^([A-Z]{2})-(\d+)$", rc)
        if not m:
            return None
        prefix, nn = m.group(1), int(m.group(2))
        best = None                      # (sort key, file id, est page)
        for rec in records:
            if rec["edition"] != edition:
                continue
            nums = []                    # (code number, pdf page) with prefix
            for c, pno in rec["code_pages"].items():
                cm = re.match(r"^" + prefix + r"-(\d+)", c)
                if cm:
                    nums.append((int(cm.group(1)), pno))
            if not nums:
                continue
            kk, pk = min(nums, key=lambda t: abs(nn - t[0]))
            dist = abs(nn - kk)
            if dist > NEAR_MAX:
                continue
            lo, hi = min(k for k, _ in nums), max(k for k, _ in nums)
            key = (not (lo <= nn <= hi), dist)   # prefer containment, then proximity
            if best is None or key < best[0]:
                est = max(1, min(rec["pages"], pk + (nn - kk)))
                best = (key, rec["id"], est)
        return (best[1], best[2]) if best else None

    for rec in records:
        resolved = []
        own = ed_index[rec["edition"]] if rec["edition"] else page_index
        for rc in rec["refs"]:
            tgt = own.get(rc)
            if tgt and tgt["file"] != rec["id"]:
                resolved.append({"code": rc, "target": tgt["file"],
                                 "page": tgt["page"]})
            elif not tgt:
                near = resolve_near(rc, rec["edition"])
                if near and near[0] != rec["id"]:
                    resolved.append({"code": rc, "target": near[0],
                                     "page": near[1], "approx": True})
                elif near:
                    pass    # nearest page is inside this same PDF -> skip,
                            # matching how exact self-references are dropped
                else:
                    sysname = CODE_MAP.get(rc.split("-")[0], ("", ""))[0]
                    resolved.append({"code": rc, "target": None, "page": None,
                                     "system": sysname})
        rec["refs_resolved"] = resolved

    compute_master_torque(records)
    n_prev, n_pairs = render_page_previews(records)
    print(f"Page previews: {n_pairs} link-target pages, {n_prev} newly rendered")
    print(f"Stale thumbnails removed: {prune_thumbs(records)}")

    write_outputs(records, page_index, unmapped)
    return records, unmapped


# Groups whose sections get a master torque-table link
MASTER_GROUPS = {"Engine", "Engine Electrical", "Drivetrain"}

# Known factory spec files -> the Toyota code prefix their torque table covers.
# (Some spec files have no detectable footer code, so map them explicitly.)
SPEC_PREFIX_OVERRIDES = {
    "Engine_Mechanical_3sgte": "EM",
    "Engine_Mechanical_5sfe": "EM",
    "Cylinder_Head_3sgte": "EM",
    "Service_Specifications": "MX",
    "Turbocharger_System": "TC",
    "Mfi_And_Sfi_Systems_3sgte": "FI",
    "Cooling_System": "CO",
    "Lubrication_System": "LU",
    "Ignition_System": "IG",
}

# For sections with no footer code, infer their prefix from the system name
SYSTEM_PREFIX = {
    "Engine Mechanical": "EM",
    "Turbocharger": "TC",
    "Cooling": "CO",
    "Lubrication": "LU",
    "Fuel / EFI (MFI-SFI)": "FI",
    "Fuel / EFI": "FI",
    "Engine Management": "FI",
    "Ignition": "IG",
    "Manual Transaxle": "MX",
}

def compute_master_torque(records):
    """For every Engine/Drivetrain section, link the torque-TABLE pages of the
    spec file(s) covering its Toyota code prefix (e.g. EM section -> the
    Engine Mechanical service-spec file's TORQUE SPECIFICATIONS pages)."""
    by_id = {r["id"]: r for r in records}
    specs_by_prefix = defaultdict(list)
    for r in records:
        if not r["torque_table_pages"]:
            continue
        prefix = SPEC_PREFIX_OVERRIDES.get(r["id"]) or r["code"]
        if prefix:
            specs_by_prefix[prefix].append(r["id"])
    for r in records:
        masters = []
        prefix = r["code"] or SYSTEM_PREFIX.get(r["system"], "")
        if r["group"] in MASTER_GROUPS and prefix:
            for sid in specs_by_prefix.get(prefix, []):
                if sid == r["id"]:
                    continue
                s = by_id[sid]
                if s["edition"] != r["edition"]:
                    continue
                # don't offer the wrong engine's spec table
                if (r["engine"] == "3sgte" and s["engine"] == "5sfe") or \
                   (r["engine"] == "5sfe" and s["engine"] == "3sgte"):
                    continue
                masters.append({"target": sid,
                                "pages": s["torque_table_pages"]})
        r["master_torque"] = masters


def render_page_previews(records):
    """Render a preview PNG for every page the app links to (cross-ref targets,
    torque-table pages, master torque pages) so links show what they open."""
    pages_dir = THUMB_DIR / "pages"
    pages_dir.mkdir(exist_ok=True)
    by_id = {r["id"]: r for r in records}
    pairs = set()
    for r in records:
        for p in r["torque_table_pages"]:
            pairs.add((r["id"], p))
        for x in r["refs_resolved"]:
            if x["target"] and x["page"]:
                pairs.add((x["target"], x["page"]))
        for m in r.get("master_torque", []):
            for p in m["pages"]:
                pairs.add((m["target"], p))
    byfile = defaultdict(list)
    for fid, p in pairs:
        byfile[fid].append(p)
    rendered = 0
    for fid, plist in byfile.items():
        rec = by_id.get(fid)
        if not rec:
            continue
        need = [p for p in sorted(set(plist))
                if FORCE_THUMBS or not (pages_dir / f"{fid}_p{p}.png").exists()]
        if not need:
            continue
        try:
            doc = fitz.open(MANUALS_DIR / rec["file"])
        except Exception as e:
            print(f"  preview open fail {rec['file']}: {e}")
            continue
        for p in need:
            if p < 1 or p > doc.page_count:
                continue
            try:
                pg = doc.load_page(p - 1)
                zoom = max(0.4, min(1.3, THUMB_TARGET_W / (pg.rect.width or 612)))
                pix = pg.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                pix.save(pages_dir / f"{fid}_p{p}.png")
                rendered += 1
            except Exception as e:
                print(f"  preview fail {fid} p{p}: {e}")
        doc.close()
    return rendered, len(pairs)


def prune_thumbs(records):
    """Delete thumbnails / page previews of sections no longer in manuals\\."""
    ids = {r["id"] for r in records}
    removed = 0
    for f in THUMB_DIR.glob("*.png"):
        if f.stem not in ids:
            f.unlink()
            removed += 1
    pages_dir = THUMB_DIR / "pages"
    if pages_dir.is_dir():
        for f in pages_dir.glob("*.png"):
            if f.stem.rpartition("_p")[0] not in ids:
                f.unlink()
                removed += 1
    return removed


def write_outputs(records, page_index, unmapped):
    # index.json (metadata, no full text)
    slim = []
    for r in records:
        s = {k: v for k, v in r.items() if k != "text"}
        s["torque_count"] = len(r["torques"])
        slim.append(s)
    (DATA_DIR / "index.json").write_text(
        json.dumps({"records": slim, "page_index": page_index},
                   indent=2, ensure_ascii=False), encoding="utf-8")

    # data.js (full payload for the offline app)
    payload = {"records": records, "page_index": page_index,
               "generated_files": len(records)}
    (DATA_DIR / "data.js").write_text(
        "window.CELICA_DATA = " +
        json.dumps(payload, ensure_ascii=False) + ";",
        encoding="utf-8")

    # SECTION_INDEX.md
    by_group = defaultdict(list)
    for r in records:
        by_group[r["group"]].append(r)
    eng_label = {"3sgte": "3S-GTE", "5sfe": "5S-FE", "both": "3S-GTE + 5S-FE",
                 "na": "-"}
    lines = ["# ST185 Celica GT-Four / All-Trac - Master Section Index",
             "",
             f"Total section files: **{len(records)}**  |  "
             "Vehicle: **1993 ST185 (3S-GTE turbo, All-Trac AWD)**", ""]
    for grp in sorted(by_group):
        recs = sorted(by_group[grp], key=lambda x: (x["system"], x["title"]))
        lines.append(f"## {grp}  ({len(recs)})")
        lines.append("")
        lines.append("| Title | System | Code | Engine | Pages | Torques |")
        lines.append("|---|---|---|---|---|---|")
        for r in recs:
            lines.append(f"| {r['title']} | {r['system']} | {r['code'] or '-'} "
                         f"| {eng_label[r['engine']]} | {r['pages']} "
                         f"| {len(r['torques'])} |")
        lines.append("")
    (APP_DIR / "SECTION_INDEX.md").write_text("\n".join(lines), encoding="utf-8")

    # TORQUE_SPECS.md  (torque TABLE page references only)
    tlines = ["# ST185 Torque Table References",
              "",
              "Sections containing a factory TORQUE SPECIFICATIONS table, with "
              "the PDF page(s) of the table. Open the PDF at that page and "
              "scroll for full surrounding context.",
              ""]
    by_group = defaultdict(list)
    for r in records:
        if r["torque_table_pages"]:
            by_group[r["group"]].append(r)
    for grp in sorted(by_group):
        tlines.append(f"## {grp}")
        tlines.append("")
        for r in sorted(by_group[grp], key=lambda x: x["title"]):
            pages = ", ".join("p." + str(p) for p in r["torque_table_pages"])
            tlines.append(f"- **{r['title']}** [{r['system']}] — "
                          f"torque table page(s): {pages} — `{r['file']}`")
        tlines.append("")
    (APP_DIR / "TORQUE_SPECS.md").write_text("\n".join(tlines), encoding="utf-8")

    # CROSS_REFERENCES.md
    clines = ["# ST185 Cross-Reference Map",
              "",
              "Where each 'See page XX-nn' reference resolves to a file in this "
              "set. Unresolved codes are pages not present as separate PDFs.", ""]
    for r in sorted(records, key=lambda x: x["title"]):
        rr = r.get("refs_resolved", [])
        if not rr:
            continue
        clines.append(f"## {r['title']}  (`{r['file']}`)")
        for ref in rr:
            tgt = ref["target"]
            if tgt:
                trec = next((x for x in records if x["id"] == tgt), None)
                tname = trec["file"] if trec else tgt
                mark = "  (nearest page)" if ref.get("approx") else ""
                clines.append(f"- {ref['code']}  ->  {tname}{mark}")
            else:
                clines.append(f"- {ref['code']}  ->  (not in set)")
        clines.append("")
    (APP_DIR / "CROSS_REFERENCES.md").write_text("\n".join(clines),
                                                 encoding="utf-8")


def report(records, unmapped):
    print("\n=== BUILD REPORT ===")
    grp = Counter(r["group"] for r in records)
    print("Groups:", dict(grp))
    codes = Counter(r["code"] or "(none)" for r in records)
    print("Codes:", dict(codes))
    eng = Counter(r["engine"] for r in records)
    print("Engine tags:", dict(eng))
    total_t = sum(len(r["torques"]) for r in records)
    print(f"Total torque callouts: {total_t}")
    tbl = [r for r in records if r["torque_table_pages"]]
    print(f"Sections with torque TABLES: {len(tbl)}")
    masters = sum(1 for r in records if r.get("master_torque"))
    print(f"Sections with a master torque link: {masters}")
    tot_refs = sum(len(r.get("refs_resolved", [])) for r in records)
    print(f"Total cross-refs: {tot_refs}")
    all_refs = [x for r in records for x in r.get("refs_resolved", [])]
    n_exact = sum(1 for x in all_refs if x["target"] and not x.get("approx"))
    n_approx = sum(1 for x in all_refs if x.get("approx"))
    n_dead = sum(1 for x in all_refs if not x["target"])
    print(f"Cross-ref resolution: {n_exact} exact, {n_approx} approx "
          f"(nearest page), {n_dead} unresolved")
    if unmapped:
        print(f"\nUNMAPPED ({len(unmapped)}):")
        for u in unmapped:
            print("  -", u)
    djs = (DATA_DIR / "data.js").stat().st_size
    print(f"\ndata.js size: {djs/1024/1024:.2f} MB")
    thumbs = list(THUMB_DIR.glob("*.png"))
    tsize = sum(t.stat().st_size for t in thumbs)
    print(f"thumbnails: {len(thumbs)} files, {tsize/1024/1024:.2f} MB total")


def run_build(force_thumbs: bool = False) -> dict:
    """Run the full catalog build. Importable entry point (used by the app's
    /api/rebuild endpoint); prints progress the same way the CLI does."""
    global FORCE_THUMBS
    FORCE_THUMBS = force_thumbs
    MANUALS_DIR.mkdir(parents=True, exist_ok=True)
    recs, unmapped = build()
    report(recs, unmapped)
    print("\nDone. Outputs in:", APP_DIR)
    return {"files": len(recs), "unmapped": len(unmapped)}


if __name__ == "__main__":
    run_build(force_thumbs="--thumbs" in sys.argv)
