#!/usr/bin/env python3
"""
Import whole manuals downloaded from https://gt4.mwp.id.au/ into the library.

Each book is split into section PDFs, and only what the library does not
already have is kept:

  RM305U1  1993 ST185 Repair Manual vol. 1 (engine)   -> manuals\\
           one PDF per chapter (running page-header topic). Chapters whose
           Toyota page codes are already in the library, and 4A-FE-only
           chapters (AT180 engine), are skipped.
  RM176U   1990 ST185 All-Trac Repair Manual           -> manuals\\
           the chassis / body sections the 1993 engine volume lacks
           (clutch, transaxle, transfer, propeller shaft, suspension & axle,
           brakes, restraints, body electrical). Tagged edition 1990 so its
           page codes never resolve into 1993 pages.
  1993 Celica Service Manual (Mitchell, aftermarket)   -> both apps
           electrical articles + system / overall wiring diagrams become a
           full 1993 edition in manuals-electrical\\ (with a page map);
           ST185-relevant mechanical articles go to manuals\\
  small reference documents                            -> either app

Writes manuals\\library.json (titles, systems and source book of every
imported repair section), adds the editions to manuals-electrical\\
sources.json and writes page maps to electrical\\build\\overrides\\.
Re-running replaces everything a previous run imported.

Usage:  python tools/import_books.py <folder with the downloaded PDFs>
Then rebuild both libraries (repair first: the electrical builder reads its
index for cross-links).
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("PyMuPDF not installed. Run: python -m pip install pymupdf")

BASE = Path(__file__).resolve().parents[1]
REPAIR_DIR = BASE / "manuals"
EWD_DIR = BASE / "manuals-electrical"
OVR_DIR = BASE / "electrical" / "build" / "overrides"
LIBRARY_JSON = REPAIR_DIR / "library.json"
SOURCES_JSON = EWD_DIR / "sources.json"
REPAIR_INDEX = BASE / "celica-manual" / "data" / "index.json"

RM305 = "Toyota - ST185 - 1993 - Repair Manual (RM305U1).pdf"
RM176 = "Toyota - ST185 - 1990 - Repair Manual (RM176U).pdf"
MITCHELL = "Toyota - ST185 - 1993 - Service Manual.pdf"
MITCHELL_EWD = "1993 Celica Service Manual (Mitchell) - Electrical.pdf"

BOOK_RM305 = "RM305U1 (1993)"
BOOK_RM176 = "RM176U (1990)"
BOOK_MITCHELL = "Mitchell 1993 (aftermarket)"
BOOK_MWP = "gt4.mwp.id.au"

_TR = {0x2212: "-", 0x2013: "-", 0x2014: "-", 0x2010: "-", 0x2011: "-",
       0x00A0: " ", 0x2019: "'", 0x2018: "'", 0x201C: '"', 0x201D: '"'}
CODE_LINE = re.compile(r"^([A-Z]{2})\s*-\s*(\d{1,3})\s*$", re.M)

SECTION_NAMES = {
    "IN": "Introduction", "MA": "Maintenance", "EM": "Engine Mechanical",
    "EX": "Exhaust System", "TC": "Turbocharger", "EC": "Emission Control",
    "FI": "MFI and SFI Systems", "CO": "Cooling System", "LU": "Lubrication",
    "IG": "Ignition", "ST": "Starting", "CH": "Charging", "CL": "Clutch",
    "MT": "Manual Transaxle E150F", "TF": "Transfer", "PR": "Propeller Shaft",
    "SA": "Suspension and Axle", "BR": "Brakes", "SR": "Steering",
    "BE": "Body Electrical", "BO": "Body", "AB": "ABS",
}
# (repair-app system, group); in these manuals SR is Steering, not restraints
RM176_KEEP = {
    "CL": ("Clutch", "Drivetrain"),
    "MT": ("Manual Transmission E150F (4WD)", "Drivetrain"),
    "TF": ("Transfer", "Drivetrain"),
    "PR": ("Propeller Shaft", "Drivetrain"),
    "SA": ("Suspension & Axle", "Chassis"),
    "BR": ("Brakes", "Brakes"),
    "SR": ("Steering", "Chassis"),
    "BE": ("Body Electrical", "Electrical"),
    "BO": ("Body", "Body"),
    "AB": ("ABS", "Brakes"),
}


def norm(s: str) -> str:
    return s.translate(_TR)


def safe(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|]+', "-", s)
    return re.sub(r"\s+", " ", s).strip(" .-")[:110]


def title_case(s: str) -> str:
    if s.upper() != s:
        return s
    small = {"OF", "AND", "FOR", "IN", "THE", "TO", "WITH", "ON", "OR"}
    keep = {"A/C", "ABS", "SRS", "SFI", "MFI", "EGR", "EVAP", "PCV", "TWC", "SAE",
            "M/T", "A/T", "VIN", "4WD", "2WD"}
    out = []
    for i, w in enumerate(s.split()):
        if w in keep or re.search(r"\d", w):
            out.append(w)
        elif w in small and i:
            out.append(w.lower())
        else:
            out.append(w[:1] + w[1:].lower())
    return " ".join(out)


def write_subset(doc, pages0, out_path: Path):
    sub = fitz.open()
    for p in pages0:
        sub.insert_pdf(doc, from_page=p, to_page=p)
    sub.save(str(out_path), garbage=3, deflate=True, no_new_id=True)
    sub.close()


def page_code(text):
    codes = CODE_LINE.findall(text)
    return f"{codes[-1][0]}-{codes[-1][1]}" if codes else None


def engines_in(s):
    return [e for e in ("4A-FE", "3S-GTE", "5S-FE") if e in s]


ENGINE_TAG = {("3S-GTE",): "3sgte", ("5S-FE",): "5sfe", ("3S-GTE", "5S-FE"): "both"}


# ---------------------------------------------------------------------------
# Library bookkeeping
# ---------------------------------------------------------------------------
def load_library():
    try:
        return json.loads(LIBRARY_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"files": {}}


def existing_codes():
    """Toyota page codes already in the repair library (its own sections, not
    earlier imports and not whole uncategorized books)."""
    try:
        recs = json.loads(REPAIR_INDEX.read_text(encoding="utf-8"))["records"]
    except (OSError, ValueError, KeyError):
        return set()
    have = set()
    for r in recs:
        if r.get("group") != "Other" and not r.get("book") and not r.get("edition"):
            have |= set(r["own_codes"])
    return have


def remove_previous_imports(library):
    removed = 0
    for name in list(library.get("files", {})):
        (REPAIR_DIR / name).unlink(missing_ok=True)
        removed += 1
    library["files"] = {}
    for src in load_sources():
        if src.get("imported"):
            for f in src.get("files", []):
                (EWD_DIR / f).unlink(missing_ok=True)
                (OVR_DIR / (Path(f).stem + ".json")).unlink(missing_ok=True)
    print(f"Removed {removed} previously imported repair sections")


def load_sources():
    try:
        return json.loads(SOURCES_JSON.read_text(encoding="utf-8")).get("sources", [])
    except (OSError, ValueError):
        return []


def save_sources(new_sources):
    data = json.loads(SOURCES_JSON.read_text(encoding="utf-8"))
    ids = {s["id"] for s in new_sources}
    data["sources"] = [s for s in data["sources"] if s["id"] not in ids] + new_sources
    SOURCES_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# RM305U1 (1993 repair manual, engine volume)
# ---------------------------------------------------------------------------
def rm305_chapters(doc):
    """[(section, topic, [page indexes], [codes])] from the running header
    ('-' / SECTION NAME / Topic) printed on every page."""
    raw = []
    for i in range(doc.page_count):
        text = norm(doc[i].get_text())
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        sec = topic = None
        for k in range(len(lines) - 2):
            if lines[k] == "-" and re.fullmatch(r"[A-Z][A-Z &/(),.\-]{3,}", lines[k + 1]):
                sec, topic = lines[k + 1], lines[k + 2]
                break
        raw.append((i, sec, topic, page_code(text), text))
    sec_count = Counter(s for _, s, _, _, _ in raw if s)
    chapters = []
    cur = None
    for i, sec, topic, code, text in raw:
        if sec is None and code is None:
            cur = None                      # section title / index page
            continue
        if sec and sec_count[sec] < 3 and cur:
            sec = cur["sec"]                # mis-read header, e.g. a table title
        if sec == "SERVICE SPECIFICATIONS":
            topic = "Service Specifications"
        bad = topic is None or len(topic) < 3 or re.fullmatch(r"[A-Z]{2}-\d+|\d+", topic or "")
        if cur and (bad or sec is None) and (sec in (None, cur["sec"])):
            topic = cur["topic"]
        sec = sec or (cur["sec"] if cur else "")
        topic = re.sub(r"\s+~\w*$|[,.]$", "", topic or "").strip()
        key = (sec, re.sub(r"[^a-z0-9]+", " ", topic.lower()).strip())
        if cur and cur["key"] == key:
            cur["pages"].append(i)
        else:
            cur = {"key": key, "sec": sec, "topic": topic, "pages": [i], "codes": [], "text": []}
            chapters.append(cur)
        if code:
            cur["codes"].append(code)
        cur["text"].append(text)
    return chapters


BOOK_ENGINE_ORDER = ["4A-FE", "3S-GTE", "5S-FE"]


def import_rm305(path, have, library):
    doc = fitz.open(path)
    kept = skipped_cov = skipped_4a = 0
    names = Counter()
    chapters = rm305_chapters(doc)
    # A section that repeats its chapters three times (Emission Control) has
    # one set per engine, in the book's engine order; the engine names are
    # only in the illustrations.
    seen = Counter()
    repeats = Counter((ch["sec"], ch["key"]) for ch in chapters)
    for ch in chapters:
        k = (ch["sec"], ch["key"])
        ch["engine_set"] = BOOK_ENGINE_ORDER[seen[k]] if repeats[k] == 3 else None
        seen[k] += 1
    for ch in chapters:
        topic, sec = ch["topic"], ch["sec"]
        if ch["engine_set"] and not engines_in(topic):
            topic = f"{topic} ({ch['engine_set']})"
        eng = engines_in(topic)
        if not eng:
            text = " ".join(ch["text"])
            counts = {e: text.count(e) for e in ("4A-FE", "3S-GTE", "5S-FE")}
            tot = sum(counts.values())
            top = max(counts, key=counts.get)
            if tot >= 3 and counts[top] >= 0.75 * tot and sec != "SERVICE SPECIFICATIONS":
                eng = [top]
                topic = f"{topic} ({top})"
        if eng == ["4A-FE"]:
            skipped_4a += 1
            continue
        codes = ch["codes"]
        if codes and sum(c in have for c in codes) >= 0.9 * len(codes):
            skipped_cov += 1
            continue
        sec_title = title_case(sec) if sec else "General"
        base = safe(f"RM305U1 - {sec_title} - {title_case(topic)}")
        names[base] += 1
        name = (base if names[base] == 1 else f"{base} ({names[base]})") + ".pdf"
        write_subset(doc, ch["pages"], REPAIR_DIR / name)
        meta = {"title": f"{title_case(topic)} — {sec_title}", "book": BOOK_RM305}
        tag = ENGINE_TAG.get(tuple(e for e in ("3S-GTE", "5S-FE") if e in eng))
        if tag:
            meta["engine"] = tag
        if sec == "SERVICE SPECIFICATIONS":
            meta.update(system="Service Specifications", group="General", engine="both")
        library["files"][name] = meta
        kept += 1
    doc.close()
    print(f"RM305U1: {kept} chapters added, {skipped_cov} already in the library, "
          f"{skipped_4a} 4A-FE-only skipped")


# ---------------------------------------------------------------------------
# RM176U (1990 All-Trac repair manual, scanned + OCR)
# ---------------------------------------------------------------------------
def import_rm176(path, library):
    doc = fitz.open(path)
    pref = []
    for i in range(doc.page_count):
        c = page_code(norm(doc[i].get_text()))
        p = c.split("-")[0] if c else None
        pref.append(p if p in SECTION_NAMES else None)
    # OCR noise: a lone code inside another section's run takes its neighbours'
    for i in range(1, len(pref) - 1):
        a = next((pref[j] for j in range(i - 1, -1, -1) if pref[j]), None)
        b = next((pref[j] for j in range(i + 1, len(pref)) if pref[j]), None)
        if pref[i] and a and a == b and pref[i] != a:
            pref[i] = a
    filled, last = [], None
    for p in pref:
        last = p or last
        filled.append(last)
    runs = []
    for i, p in enumerate(filled):
        if runs and runs[-1][0] == p:
            runs[-1][1].append(i)
        else:
            runs.append((p, [i]))
    by_prefix = defaultdict(list)
    for p, pages in runs:
        if p in RM176_KEEP and len(pages) >= 2:
            by_prefix[p] += pages
    for p, pages in sorted(by_prefix.items(), key=lambda kv: kv[1][0]):
        name = safe(f"RM176U 1990 - {SECTION_NAMES[p]}") + ".pdf"
        write_subset(doc, pages, REPAIR_DIR / name)
        system, group = RM176_KEEP[p]
        library["files"][name] = {"title": f"{SECTION_NAMES[p]} (1990 All-Trac)",
                                  "system": system, "group": group,
                                  "book": BOOK_RM176, "edition": "1990", "code": p}
        print(f"RM176U: {p} {SECTION_NAMES[p]} — {len(pages)} pages")
    doc.close()


# ---------------------------------------------------------------------------
# Mitchell 1993 Celica service manual (aftermarket)
# ---------------------------------------------------------------------------
AUTO_AC = "RADIATOR FAN AND AIR CONDITIONER (AUTOMATIC AIR CONDITIONER, FOR DIAL TYPE OF BLOWER CONTROL SW)"
MAN_AC = "RADIATOR FAN AND AIR CONDITIONER (MANUAL AIR CONDITIONER, FOR DIAL TYPE OF BLOWER CONTROL SW)"
# 1993 controls: the manual-A/C article says "A dial type switch is used to
# control fan speed"; the automatic-A/C article tests a single AUTO/LO/HI
# blower speed control switch.

ELECTRICAL_ARTICLES = {
    "A/C-HEATER SYSTEM - AUTOMATIC": AUTO_AC,
    "A/C-HEATER SYSTEM - MANUAL": MAN_AC,
    "HEATER SYSTEM": "HEATER",
    "ENGINE COOLING FAN": "ENGINE COOLING FAN",
    "AIR BAG RESTRAINT SYSTEM": "SRS AIRBAG",
    "ALTERNATOR & REGULATOR": "CHARGING",
    "STARTER": "STARTING AND IGNITION",
    "ANTI-LOCK BRAKE SYSTEM": "ABS (ANTI-LOCK BRAKE SYSTEM)",
    "ANTI-LOCK BRAKE SAFETY PRECAUTIONS": "ABS (ANTI-LOCK BRAKE SYSTEM)",
    "CRUISE CONTROL SYSTEM": "CRUISE CONTROL",
    "DEFOGGER - REAR WINDOW": "REAR WINDOW DEFOGGER",
    "DOOR LOCKS - POWER": "DOOR LOCK",
    "ELECTRICAL COMPONENT LOCATOR": "ELECTRICAL COMPONENT LOCATOR",
    "FUSES & CIRCUIT BREAKERS": "POWER SOURCE",
    "HOW TO USE SYSTEM WIRING DIAGRAMS": "HOW TO USE SYSTEM WIRING DIAGRAMS",
    "INSTRUMENT PANEL": "COMBINATION METER",
    "MIRRORS - POWER": "REMOTE CONTROL MIRROR",
    "J - PIN VOLTAGE CHARTS": "ENGINE CONTROL (3S-GTE)",
    "K - SENSOR RANGE CHARTS": "ENGINE CONTROL (3S-GTE)",
    "POWER WINDOWS": "POWER WINDOW",
    "SEATS - POWER": "POWER SEAT",
    "SHIFT LOCK SYSTEM": "SHIFT LOCK",
    "STEERING COLUMN SWITCHES": "STEERING COLUMN SWITCHES",
    "STEERING COLUMN - AUTOMATIC TILT WHEEL": "AUTO TILT AWAY STEERING",
    "SUN ROOF - POWER": "SUN ROOF",
    "WIPER/WASHER SYSTEM": "FRONT WIPER AND WASHER",
    "WIRING DIAGRAMS": "OVERALL WIRING DIAGRAM",
    "WIRING DIAGRAM SYMBOLS": "GLOSSARY OF TERMS AND SYMBOLS",
    "TROUBLE SHOOTING - BASIC PROCEDURES": "TROUBLESHOOTING",
}
# one diagram page per circuit in the SYSTEM WIRING DIAGRAMS article
SYSTEM_DIAGRAMS = [
    (r"Defogger Circuit", "REAR WINDOW DEFOGGER"),
    (r"Horn Circuit", "HORN"),
    (r"Power Antenna Circuit", "AUTO ANTENNA"),
    (r"Power Door Lock Circuit", "DOOR LOCK"),
    (r"Power Mirror Circuit", "REMOTE CONTROL MIRROR"),
    (r"Power Seat Circuit", "POWER SEAT"),
    (r"Power Window Circuit", "POWER WINDOW"),
    (r"Radio Circuits, W/ CD", "RADIO AND PLAYER (W/ CD PLAYER)"),
    (r"Radio Circuits, W/O CD", "RADIO AND PLAYER (W/O CD PLAYER)"),
    (r"Charging Circuit", "CHARGING"),
    (r"Starting Circuit", "STARTING AND IGNITION"),
    (r"1\.6L, Transmission Circuit", "ECT (4A-FE)"),
    (r"2\.2L, Transmission Circuit", "ECT (5S-FE)"),
    (r"Front Washer/Wiper Circuit", "FRONT WIPER AND WASHER"),
    (r"Rear Wiper/Washer Circuit", "REAR WIPER AND WASHER"),
]
# overall grid diagrams (WIRING DIAGRAMS) and engine diagrams (L - WIRING DIAGRAMS)
FIGURES = [
    (r"Engine Compartment, Headlights, Starter", ["HEADLIGHT (FOR USA)", "STARTING AND IGNITION"]),
    (r"Junction Block #2, Relay Block #5", ["POWER SOURCE"]),
    (r"1\.6L", ["ENGINE CONTROL (4A-FE)"]),
    (r"2\.0L Turbo", ["ENGINE CONTROL (3S-GTE)"]),
    (r"2\.2L A/T", ["ENGINE CONTROL (5S-FE A/T)"]),
    (r"2\.2L M/T", ["ENGINE CONTROL (5S-FE M/T)"]),
    (r"Junction Block #\s?1", ["POWER SOURCE"]),
    (r"Auto A/C & Heater", [AUTO_AC]),
    (r"Manual A/C & Heater", [MAN_AC]),
    (r"Fan Relays, Courtesy Lights, Heater Relay",
     [AUTO_AC, MAN_AC, "ENGINE COOLING FAN", "INTERIOR LIGHT"]),
    (r"Cruise Control System", ["CRUISE CONTROL"]),
    (r"ABS System", ["ABS (ANTI-LOCK BRAKE SYSTEM)"]),
    (r"Junction Block #3, A/T Control, Defogger",
     ["POWER SOURCE", "REAR WINDOW DEFOGGER", "SHIFT LOCK"]),
    (r"Instrument Cluster, Combination Switch", ["COMBINATION METER", "STEERING COLUMN SWITCHES"]),
    (r"Power Accessories, Taillights",
     ["POWER WINDOW", "DOOR LOCK", "REMOTE CONTROL MIRROR", "SUN ROOF", "TAILLIGHT"]),
]
_REPAIR = [
    ("2.0L 4-CYL TURBO - VIN [S]", "Engine Overhaul — 2.0L Turbo (3S-GTE)", "Engine Mechanical", "Engine", "3sgte"),
    ("2.2L 4-CYL - VIN [S]", "Engine Overhaul — 2.2L (5S-FE)", "Engine Mechanical", "Engine", "5sfe"),
    ("ENGINE OVERHAUL PROCEDURES - GENERAL INFORMATION", None, "Engine Mechanical", "Engine", None),
    ("A/C COMPRESSOR SERVICING", None, "Air Conditioning", "HVAC", None),
    ("A/C COMPRESSOR OIL CHECKING", None, "Air Conditioning", "HVAC", None),
    ("A/C SYSTEM GENERAL SERVICING", None, "Air Conditioning", "HVAC", None),
    ("A/C SYSTEM GENERAL DIAGNOSTIC PROCEDURES", None, "Air Conditioning", "HVAC", None),
    ("A - ENGINE/VIN ID", "Engine Performance A — Engine/VIN ID", "Engine Performance", "Engine", "both"),
    ("B - EMISSION APPLICATION", "Engine Performance B — Emission Application", "Engine Performance", "Engine", "both"),
    ("C - SPECIFICATIONS - 4-CYL", "Engine Performance C — Specifications", "Engine Performance", "Engine", "both"),
    ("D - ADJUSTMENTS - 4-CYL", "Engine Performance D — Adjustments", "Engine Performance", "Engine", "both"),
    ("E - THEORY/OPERATION", "Engine Performance E — Theory & Operation", "Engine Performance", "Engine", "both"),
    ("F - BASIC TESTING - 4-CYL", "Engine Performance F — Basic Testing", "Engine Performance", "Engine", "both"),
    ("G - TESTS W/CODES", "Engine Performance G — Tests With Trouble Codes", "Engine Performance", "Engine", "both"),
    ("H - TESTS W/O CODES", "Engine Performance H — Tests Without Codes", "Engine Performance", "Engine", "both"),
    ("I - SYSTEM/COMPONENT TESTS", "Engine Performance I — System & Component Tests", "Engine Performance", "Engine", "both"),
    ("J - PIN VOLTAGE CHARTS", "Engine Performance J — ECU Pin Voltage Charts", "Engine Performance", "Engine", "both"),
    ("K - SENSOR RANGE CHARTS", "Engine Performance K — Sensor Range Charts", "Engine Performance", "Engine", "both"),
    ("M - VACUUM DIAGRAMS", "Engine Performance M — Vacuum Diagrams", "Engine Performance", "Engine", "both"),
    ("N - REMOVE/INSTALL/OVERHAUL", "Engine Performance N — Remove/Install/Overhaul", "Engine Performance", "Engine", "both"),
    ("P - EGR FUNCTION TESTING", "Engine Performance P — EGR Function Testing", "Engine Performance", "Engine", "both"),
    ("GENERAL COOLING SYSTEM SERVICING", None, "Cooling", "Engine", None),
    ("AXLE SHAFTS - FRONT", None, "Drivetrain (4WD)", "Drivetrain", None),
    ("DRIVE AXLE - REAR", None, "Drivetrain (4WD)", "Drivetrain", None),
    ("DRIVE AXLE - INTEGRAL HOUSING", None, "Drivetrain (4WD)", "Drivetrain", None),
    ("CLUTCH", None, "Clutch", "Drivetrain", None),
    ("TRANSMISSION REMOVAL & INSTALLATION - M/T", None, "Manual Transaxle", "Drivetrain", None),
    ("TRANSMISSION SERVICING - M/T", None, "Manual Transaxle", "Drivetrain", None),
    ("BRAKE SYSTEM", None, "Brakes", "Brakes", None),
    ("STEERING COLUMN - TILT", None, "Steering", "Chassis", None),
    ("STEERING COLUMN - STANDARD", None, "Steering", "Chassis", None),
    ("STEERING SYSTEM - POWER RACK & PINION", None, "Steering", "Chassis", None),
    ("SUSPENSION - FRONT", None, "Suspension & Axle", "Chassis", None),
    ("SUSPENSION - REAR", None, "Suspension & Axle", "Chassis", None),
    ("PRE-ALIGNMENT CHECKS", None, "Wheel Alignment", "Chassis", None),
    ("RIDING HEIGHT ADJUSTMENT", None, "Wheel Alignment", "Chassis", None),
    ("WHEEL ALIGNMENT THEORY/OPERATION", None, "Wheel Alignment", "Chassis", None),
    ("WHEEL ALIGNMENT SPECIFICATIONS & PROCEDURES", None, "Wheel Alignment", "Chassis", None),
    ("JACKING & HOISTING", None, "General Info", "General", None),
    ("COMPUTER RELEARN PROCEDURES", None, "General Info", "General", None),
    ("MAINTENANCE INFORMATION", None, "Maintenance", "General", None),
    ("SCHEDULED SERVICES - TURBO", None, "Maintenance", "General", "3sgte"),
]
REPAIR_ARTICLES = {a: (t, s, g, e) for a, t, s, g, e in _REPAIR}
_HEADING = re.compile(r"[A-Z][A-Z0-9 &/,()'.\-]{4,70}")


def mitchell_articles(doc):
    """[(name, first page, last page)]: an article starts on a page whose
    header reads '<ARTICLE NAME> / 1993 Toyota Celica / <CATEGORY>'."""
    starts = []
    for i in range(doc.page_count):
        lines = [l.strip() for l in doc[i].get_text().splitlines() if l.strip()]
        for j in range(1, min(4, len(lines))):
            if re.fullmatch(r"199\d Toyota Celica", lines[j]):
                starts.append((lines[j - 1].strip("* ").strip(), i))
                break
    return [(name, a, (starts[k + 1][1] - 1) if k + 1 < len(starts) else doc.page_count - 1)
            for k, (name, a) in enumerate(starts)]


def article_features(doc, pages, name):
    """Section headings (DESCRIPTION, OPERATION, ... TESTS) as feature anchors."""
    feats, seen = [], {name.upper(), "1993 TOYOTA CELICA"}
    for k, p in enumerate(pages):
        for line in norm(doc[p].get_text()).splitlines():
            t = line.strip()
            if not _HEADING.fullmatch(t) or t in seen or "TABLE" in t or ".." in t \
                    or t.startswith("1993 ") or len(t.split()) > 9 or t.endswith(")") and "(" not in t:
                continue
            seen.add(t)
            feats.append({"title": t, "page": k + 1})
    return feats[:40]


def import_mitchell(path, library):
    doc = fitz.open(path)
    circuits = defaultdict(lambda: {"pages": [], "features": []})
    order = []

    def add(title, pages, features=()):
        if title not in circuits:
            order.append(title)
        c = circuits[title]
        offset = len(c["pages"])
        c["pages"] += pages
        c["features"] += [dict(f, page=f["page"] + offset) for f in features]

    repair_kept = 0
    for name, a, b in mitchell_articles(doc):
        pages = list(range(a, b + 1))
        if name in ELECTRICAL_ARTICLES:
            add(ELECTRICAL_ARTICLES[name], pages, article_features(doc, pages, name))
        if name in REPAIR_ARTICLES:
            title, system, group, engine = REPAIR_ARTICLES[name]
            title = title or title_case(name)
            fname = safe(f"Mitchell 1993 - {title}") + ".pdf"
            write_subset(doc, pages, REPAIR_DIR / fname)
            meta = {"title": title, "system": system, "group": group, "book": BOOK_MITCHELL}
            if engine:
                meta["engine"] = engine
            library["files"][fname] = meta
            repair_kept += 1
        if name == "SYSTEM WIRING DIAGRAMS":
            for p in pages:
                head = " ".join(l.strip() for l in doc[p].get_text().splitlines()[:3])
                hit = next(((t, m.group(0)) for rx, t in SYSTEM_DIAGRAMS
                            if (m := re.search(rx, head))), None)
                if hit:
                    add(hit[0], [p], [{"title": "WIRING DIAGRAM - " + hit[1].upper(), "page": 1}])
                else:
                    add("OVERALL WIRING DIAGRAM", [p])
        if name in ("WIRING DIAGRAMS", "L - WIRING DIAGRAMS"):
            for p in pages:
                m = re.search(r"Fig\.\s*\d+:\s*([^\n]+)", doc[p].get_text())
                if not m:
                    continue
                cap = m.group(1).strip()
                for rx, titles in FIGURES:
                    if re.search(rx, cap):
                        for t in titles:
                            add(t, [p], [{"title": "WIRING DIAGRAM - " + cap.upper(), "page": 1}])
                        break

    # electrical subset PDF + page map
    used = sorted({p for c in circuits.values() for p in c["pages"]})
    pos = {p: k + 1 for k, p in enumerate(used)}
    write_subset(doc, used, EWD_DIR / MITCHELL_EWD)
    ov = {"circuits": []}
    for title in order:
        c = circuits[title]
        ov["circuits"].append({
            "title": title,
            "page_list": [pos[p] for p in c["pages"]],
            "features": [{"n": k + 1, "title": f["title"], "page": f["page"]}
                         for k, f in enumerate(c["features"])],
        })
    OVR_DIR.mkdir(parents=True, exist_ok=True)
    (OVR_DIR / (Path(MITCHELL_EWD).stem + ".json")).write_text(
        json.dumps(ov, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    doc.close()
    print(f"Mitchell 1993: {len(order)} electrical circuits ({len(used)} pages), "
          f"{repair_kept} mechanical articles")
    return {
        "id": "mitchell1993", "year": 1993, "pub": "Mitchell 1993",
        "title": "1993 Celica Service Manual — electrical articles and wiring diagrams (aftermarket)",
        "models": ["AT180", "ST184", "ST185"], "engines": ["4A-FE", "5S-FE", "3S-GTE"],
        "kind": "book", "aftermarket": True, "imported": True, "files": [MITCHELL_EWD],
        "note": "Mitchell-style aftermarket manual for all 1993 Celicas: diagnosis, testing and "
                "removal for each electrical system plus system and overall wiring diagrams. "
                "Fills the circuits missing from the 1993 TIS pulls.",
    }


# ---------------------------------------------------------------------------
# Small reference documents
# ---------------------------------------------------------------------------
REPAIR_DOCS = {
    "Toyota Celica ST185 Specifications.pdf": ("ST185 Specifications (Toyota brochure)", "Specifications", "General"),
    "Haynes ST185 Info.pdf": ("ST185 Data Sheet (Haynes)", "Specifications", "General"),
    "Toyota ST185 Chassis Dimensions.pdf": ("ST185 Chassis Dimensions", "Body Dimensions", "Body"),
    "E Gearbox Identification.pdf": ("E-Series Gearbox Identification", "Manual Transmission E150F (4WD)", "Drivetrain"),
    "E Gearbox Information.pdf": ("E-Series Gearbox Information", "Manual Transmission E150F (4WD)", "Drivetrain"),
    "Brake Upgrade Guide.pdf": ("Brake Upgrades (5x100 Celica)", "Brakes", "Brakes"),
    "Toyota DBA Rotors Catalouge.pdf": ("DBA Brake Rotor Catalogue", "Brakes", "Brakes"),
    "Whiteline ST185 Catalogue.pdf": ("Whiteline ST185 Catalogue", "Suspension", "Chassis"),
    "Hot4s-ST185-Handling-Guide.pdf": ("ST185 Handling Guide (Hot 4's)", "Suspension", "Chassis"),
    "CT26 Turbo Rebuild Guide.pdf": ("CT26 Turbo Rebuild Guide", "Turbocharger", "Engine"),
}
EWD_DOCS = {
    "3SGTE ECU Pinouts.pdf": "ENGINE CONTROL (3S-GTE, ECU PINOUTS)",
    "Alternator Guide.pdf": "CHARGING (ALTERNATOR GUIDE)",
    "Toyota - Wire Harness Repair Manual (RM1022E).pdf": "WIRE HARNESS REPAIR MANUAL (RM1022E)",
}


def import_small_docs(folder, library):
    for fname, (title, system, group) in REPAIR_DOCS.items():
        if (folder / fname).is_file():
            shutil.copyfile(folder / fname, REPAIR_DIR / fname)
            meta = {"title": title, "system": system, "group": group, "book": BOOK_MWP}
            if fname in ("CT26 Turbo Rebuild Guide.pdf",
                         "Whiteline ST185 Catalogue.pdf",
                         "Hot4s-ST185-Handling-Guide.pdf"):
                meta["engine"] = "3sgte"
            library["files"][fname] = meta
    files = []
    for fname, title in EWD_DOCS.items():
        if not (folder / fname).is_file():
            continue
        shutil.copyfile(folder / fname, EWD_DIR / fname)
        n = fitz.open(folder / fname).page_count
        (OVR_DIR / (Path(fname).stem + ".json")).write_text(
            json.dumps({"circuits": [{"title": title, "pages": [1, n]}]}, indent=1) + "\n",
            encoding="utf-8", newline="\n")
        files.append(fname)
    return {
        "id": "refdocs", "year": None, "pub": "Reference",
        "title": "Reference documents (gt4.mwp.id.au)", "models": ["ST185"],
        "engines": [], "kind": "refs", "reference": True, "imported": True, "files": files,
        "note": "Enthusiast and Toyota general references: 3S-GTE ECU pinouts, alternator theory, "
                "and Toyota's Wire Harness Repair Manual (connector and terminal repair).",
    }


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    folder = Path(sys.argv[1])
    library = load_library()
    have = existing_codes()
    remove_previous_imports(library)
    new_sources = []
    if (folder / RM305).is_file():
        import_rm305(folder / RM305, have, library)
    if (folder / RM176).is_file():
        import_rm176(folder / RM176, library)
    if (folder / MITCHELL).is_file():
        new_sources.append(import_mitchell(folder / MITCHELL, library))
    new_sources.append(import_small_docs(folder, library))
    library["_comment"] = ("Sections split out of whole manuals by tools/import_books.py: "
                           "title, system/group, engine, source book and edition per file.")
    library["files"] = dict(sorted(library["files"].items()))
    LIBRARY_JSON.write_text(json.dumps(library, indent=1, ensure_ascii=False) + "\n",
                            encoding="utf-8", newline="\n")
    save_sources(new_sources)
    print(f"library.json: {len(library['files'])} imported repair sections")


if __name__ == "__main__":
    main()
