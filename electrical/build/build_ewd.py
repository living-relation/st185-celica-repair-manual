#!/usr/bin/env python3
"""
Electrical wiring diagram (EWD) catalog builder for the Electrical app.

Reads every *.pdf in <root>/manuals-electrical (whole EWD books and single-
circuit pulls), assigns each file to an edition (manuals-electrical/
sources.json, foreword detection, or printed-page matching), splits books into
system circuits using the bold circuit title printed at the top of each page,
and extracts per circuit:
    variant / applicability   engine, drive, market, A/T-M/T, A/C type,
                              blower-control type (push / dial), options
    features                  numbered SYSTEM OUTLINE headings + page anchors
    components                PARTS LOCATION codes resolved to part names and
                              their wiring-routing location page
    relay / junction blocks, harness joints, fuses
    refs                      "SEE PAGE nn" resolved to circuit + page
then writes:
    circuits/<id>.pdf         one PDF per circuit (what the viewer opens)
    thumbs/<id>.png           first-page thumbnail
    thumbs/pages/<id>_p<n>.png  previews of every page the app links to
    data/data.js              window.EWD_DATA = {...}   (full text, used by app)
    data/index.json           same without text (+ page maps for edition matching)
    data/repair_links.js      window.EWD_LINKS = {...}  (read by the repair app)
    SYSTEM_INDEX.md           human-readable system list per edition

Scanned (image-only) PDFs are split from build/overrides/<file stem>.json:
    {"source": {"id": "...", "year": 1993, "pub": "...", "title": "..."},
     "circuits": [{"title": "<printed circuit title>", "pages": [first, last],
                   "printed_first": 210,
                   "features": [{"n": 1, "title": "...", "page": 3}]}]}
(pages are 1-based PDF pages; "page_list": [..] instead of "pages" takes any
pages in any order; "page" in features is 1-based within the circuit)
Page maps also work for text PDFs that are not laid out like a Toyota EWD.

Run:  python build_ewd.py [--thumbs]     (--thumbs forces re-rendering)
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("PyMuPDF not installed. Run: python -m pip install pymupdf")

import taxonomy as tx

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "celica-manual" / "build"))
import ocr_pages


def _find_app_dir() -> Path:
    """electrical/ dir. When frozen inside CelicaManual.exe, __file__ points
    at the PyInstaller temp extraction dir, so anchor on the exe instead."""
    if getattr(sys, "frozen", False):
        here = Path(sys.executable).resolve().parent
        for cand in (here, here.parent, here.parent.parent):
            if (cand / "electrical" / "index.html").is_file():
                return cand / "electrical"
        raise SystemExit("Could not find electrical/ near the exe.")
    return Path(__file__).resolve().parents[1]


APP_DIR = _find_app_dir()                       # ...\electrical
BASE = APP_DIR.parent
SRC_DIR = BASE / "manuals-electrical"
SOURCES_JSON = SRC_DIR / "sources.json"
DATA_DIR = APP_DIR / "data"
THUMB_DIR = APP_DIR / "thumbs"
PAGES_DIR = THUMB_DIR / "pages"
CIRCUIT_DIR = APP_DIR / "circuits"
OVERRIDE_DIR = APP_DIR / "build" / "overrides"
STATE_JSON = DATA_DIR / "build_state.json"
REPAIR_INDEX = BASE / "celica-manual" / "data" / "index.json"
THUMB_TARGET_W = 360
FORCE_THUMBS = False

# ---------------------------------------------------------------------------
# Page analysis
# ---------------------------------------------------------------------------
_NUM_ONLY = re.compile(r"^[\d.]+$")
_FEATURE_NUM = re.compile(r"^(\d{1,2})\.$")


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", tx.norm_text(s)).strip()


def analyze_page(page) -> dict:
    """Printed page number, circuit title, numbered feature headings, text."""
    h = page.rect.height or 792
    printed = None
    title_spans = []
    rows = defaultdict(list)            # 9pt bold spans by row -> features
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for s in line["spans"]:
                t = _clean(s["text"])
                if not t:
                    continue
                x0, y0 = s["bbox"][0], s["bbox"][1]
                bold = "Bold" in s["font"]
                if not bold and s["size"] >= 13 and y0 > h - 75 \
                   and re.fullmatch(r"\d{1,3}", t):
                    printed = int(t)
                elif bold and s["size"] >= 8.5 and y0 < h * 0.06 \
                        and not _NUM_ONLY.match(t):
                    title_spans.append((round(y0 / 4), x0, t))
                elif bold and 8.5 <= s["size"] < 10.5:
                    rows[round(y0 / 3)].append((x0, t))
    title_spans.sort()
    title = _clean(" ".join(t for _, _, t in title_spans))
    features = []
    for _, spans in sorted(rows.items()):
        spans.sort()
        m = _FEATURE_NUM.match(spans[0][1])
        if m and len(spans) > 1:
            head = _clean(" ".join(t for _, t in spans[1:]))
            if len(head) >= 4:
                features.append((int(m.group(1)), head))
    text = ocr_pages.strip_sentinel(tx.norm_text(page.get_text("text")))
    return {"printed": printed, "title": title, "features": features, "text": text}


def analyze_pdf(path: Path):
    doc = fitz.open(path)
    pages = [analyze_page(p) for p in doc]
    doc.close()
    return pages


def is_image_only(pages) -> bool:
    if not pages:
        return False
    blank = sum(1 for p in pages if len(p["text"].strip()) < 25)
    return blank >= 0.8 * len(pages)


# ---------------------------------------------------------------------------
# Editions (sources)
# ---------------------------------------------------------------------------
def load_sources():
    if not SOURCES_JSON.is_file():
        return []
    return json.loads(SOURCES_JSON.read_text(encoding="utf-8")).get("sources", [])


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def foreword_edition(pages):
    """Year / publication number / models from a book's foreword."""
    head = " ".join(p["text"] for p in pages[:3])
    head = re.sub(r"\s+", " ", head)
    m = re.search(r"electrical system of the (\d{4}) TOYOTA CELICA", head, re.I)
    if not m:
        return None
    pub = re.search(r"\b(EWD\d{3}[A-Z]?)\b", head)
    models = re.findall(r"\b(AT180|ST18[45])\b", head)
    if re.search(r"ST184,\s*185", head):
        models += ["ST184", "ST185"]
    return {"year": int(m.group(1)), "pub": pub.group(1) if pub else "",
            "models": sorted(set(models)) or ["ST185"]}


def match_page_map(pages, page_maps):
    """Edition whose printed page -> circuit title map agrees with these pages."""
    best = None
    for sid, pmap in page_maps.items():
        hits = misses = 0
        for p in pages:
            if p["printed"] is None or not p["title"] or p["title"].startswith("("):
                continue
            want = pmap.get(str(p["printed"]))
            if want is None:
                continue
            if want == tx.group_key(tx.classify(p["title"])):
                hits += 1
            else:
                misses += 1
        if hits and not misses and (best is None or hits > best[1]):
            best = (sid, hits)
    return best[0] if best else None


def load_overrides(stem: str):
    p = OVERRIDE_DIR / (stem + ".json")
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


# ---------------------------------------------------------------------------
# Circuit grouping
# ---------------------------------------------------------------------------
def group_circuits(file_name, pages):
    """Split one PDF's analyzed pages into circuits (lists of page indexes)."""
    out = []
    cur = None
    for i, p in enumerate(pages):
        t = p["title"]
        if t and not t.startswith("("):
            info = tx.classify(t)
            gk = tx.group_key(info)
            if cur is None or cur["gk"] != gk:
                cur = {"file": file_name, "info": info, "gk": gk,
                       "pages": [], "subtitles": {}}
                out.append(cur)
        elif cur is None:
            info = tx.classify(t[1:-1] if t else "")
            cur = {"file": file_name, "info": info, "gk": tx.group_key(info),
                   "pages": [], "subtitles": {}}
            out.append(cur)
        if t and t.startswith("("):
            cur["subtitles"][len(cur["pages"])] = t
        cur["pages"].append(i)
    return out


def circuits_from_overrides(file_name, pages, ov):
    out = []
    for c in ov.get("circuits", []):
        if "page_list" in c:
            idx = [p - 1 for p in c["page_list"] if 1 <= p <= len(pages)]
        else:
            a, b = c["pages"]
            idx = list(range(a - 1, min(b, len(pages))))
        if not idx:
            continue
        info = tx.classify(c["title"])
        if c.get("printed_first") is not None:
            for k, i in enumerate(idx):
                if pages[i]["printed"] is None:
                    pages[i]["printed"] = c["printed_first"] + k
        # kept per circuit: one page may be mapped into several circuits
        feats = [(min(max(f["page"], 1), len(idx)), f["n"], f["title"].upper())
                 for f in c.get("features", [])]
        if c["title"].startswith("(") and out:
            prev = out[-1]
            offset = len(prev["pages"])
            prev["subtitles"][offset] = tx.normalize_title(c["title"])
            prev["pages"] += idx
            prev["features"] += [(pg + offset, n, t) for pg, n, t in feats]
            continue
        out.append({"file": file_name, "info": info, "gk": tx.group_key(info),
                    "pages": idx, "subtitles": {}, "mapped": True, "features": feats})
    return out


# ---------------------------------------------------------------------------
# Table parsing
# ---------------------------------------------------------------------------
_PART_CODE = re.compile(r"^([A-Z])\s?(\d{1,2})$")
_PAGE_SPEC = re.compile(r"^\d{1,3}(?:\s*\([^)]*\))?(?:\s*,\s*\d{1,3}(?:\s*\([^)]*\))?)*$")
_JOINT_CODE = re.compile(r"^[A-Z]{2}\d$")
_JB_CODE = re.compile(r"^\d[A-Z]$")
_FUSE_AMP = re.compile(r"^(\d{1,3}(?:\.\d)?A)$")
_FUSE_NAME = re.compile(r"^[A-Z][A-Z0-9 &/.\-]{1,22}$")
_SEE_PAGE = re.compile(r"SEE PAGE\s+(\d{1,3})")
_OPTION = re.compile(r"\b(W/O?)\s+([A-Z0-9][A-Z0-9./\- ]{1,30})")
_LEGEND = (": PARTS LOCATION", ": RELAY BLOCKS", ": JUNCTION BLOCK", ": CONNECTOR JOINING",
           ": GROUND POINTS", ": SPLICE POINTS", "SERVICE HINTS", "SYSTEM OUTLINE")


def _lines(text):
    return [l.strip() for l in text.splitlines() if l.strip()]


def _section(lines, start_marker):
    """Lines after a legend marker up to the next legend marker."""
    out, on = [], False
    for l in lines:
        if l.startswith(start_marker):
            on = True
            continue
        if on and any(l.startswith(m) for m in _LEGEND):
            on = False
        if on:
            out.append(l)
    return out


def parse_parts_table(lines):
    """[(code, [printed pages], spec text)] from ': PARTS LOCATION' tables."""
    sec = _section(lines, ": PARTS LOCATION")
    out = []
    i = 0
    while i < len(sec) - 1:
        m = _PART_CODE.match(sec[i])
        if m and _PAGE_SPEC.match(sec[i + 1]):
            pages = [int(x) for x in re.findall(r"(?:^|,)\s*(\d{1,3})", sec[i + 1])]
            out.append((m.group(1) + m.group(2), pages, sec[i + 1]))
            i += 2
        else:
            i += 1
    return out


def parse_coded_table(lines, marker, code_rx):
    """[(code, [pages], description)] from relay/junction/joint tables."""
    sec = _section(lines, marker)
    out = []
    pending = []
    pages = []
    for l in sec:
        if code_rx.match(l):
            pending.append(l)
        elif _PAGE_SPEC.match(l):
            pages += [int(x) for x in re.findall(r"(?:^|,)\s*(\d{1,3})", l)]
        elif re.search(r"WIRE|J/B|R/B|RELAY BLOCK|KICK PANEL|COMPARTMENT", l) \
                and not l.startswith("CODE") and "(CONNECTOR LOCATION)" not in l \
                and "(RELAY BLOCK LOCATION)" not in l and pending:
            for c in pending:
                out.append((c, sorted(set(pages)), l))
            pending, pages = [], []
    return out


def parse_relay_blocks(lines):
    sec = _section(lines, ": RELAY BLOCKS")
    out = []
    for i, l in enumerate(sec):
        if l.startswith("R/B") and i >= 2 and re.fullmatch(r"\d{1,2}", sec[i - 2]):
            out.append(("R/B " + sec[i - 2], [int(sec[i - 1])] if sec[i - 1].isdigit() else [], l))
    return out


def parse_fuses(lines):
    out = []
    for i in range(len(lines) - 1):
        m = _FUSE_AMP.match(lines[i])
        if m and _FUSE_NAME.match(lines[i + 1]) and not lines[i + 1].startswith("FROM"):
            name = lines[i + 1]
            if name.endswith("&") and i + 2 < len(lines) and _FUSE_NAME.match(lines[i + 2]):
                name += " " + lines[i + 2]
            out.append(m.group(1) + " " + name)
        else:
            m2 = re.match(r"^(\d{1,3}A)\s+([A-Z][A-Z0-9 &/.\-]{1,22})$", lines[i])
            if m2:
                out.append(m2.group(1) + " " + m2.group(2))
    seen, res = set(), []
    for f in out:
        if f not in seen:
            seen.add(f)
            res.append(f)
    return res


def parse_options(text):
    found = set()
    for m in _OPTION.finditer(text.upper()):
        words = re.split(r"[)\]:;,]", m.group(2))[0].split()
        words = [w for w in words if w not in ("AND", "OR")][:3]
        while words and (words[-1] in ("TYPE", "SW", "OF") or re.fullmatch(r"\d+", words[-1])):
            words.pop()
        if words:
            found.add(m.group(1) + " " + " ".join(words))
    return sorted(found)


def parse_parts_directory(lines):
    """Part code -> name from 'Position of Parts in ...' wiring-routing pages."""
    out = {}
    for i in range(len(lines) - 2):
        if re.fullmatch(r"[A-Z]", lines[i]) and re.fullmatch(r"\d{1,2}", lines[i + 1]):
            name = lines[i + 2]
            if len(name) > 2 and not re.fullmatch(r"[A-Z]|\d{1,3}", name):
                out.setdefault(lines[i] + lines[i + 1], name)
    return out


def parse_joint_directory(lines):
    out = {}
    for i in range(len(lines) - 1):
        if _JOINT_CODE.match(lines[i]) and "WIRE" in lines[i + 1]:
            out.setdefault(lines[i], lines[i + 1])
    return out


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def _hvac_blower(c_text, info):
    b = info["variant"].get("blower") or tx.blower_types(c_text)
    return b


def build():
    ocr_pages.convert_tree(SRC_DIR)
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    for d in (DATA_DIR, THUMB_DIR, PAGES_DIR, CIRCUIT_DIR):
        d.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(SRC_DIR.glob("*.pdf"), key=lambda p: p.name.lower())
    print(f"Found {len(pdfs)} PDFs in {SRC_DIR}")

    sources = load_sources()
    by_file = {}
    for s in sources:
        for f in s.get("files", []):
            by_file[f.lower()] = s
    prev_maps = {}
    if (DATA_DIR / "index.json").is_file():
        try:
            prev_maps = json.loads((DATA_DIR / "index.json").read_text(
                encoding="utf-8")).get("page_maps", {})
        except ValueError:
            prev_maps = {}

    analyzed = {}
    for path in pdfs:
        pages = analyze_pdf(path)
        analyzed[path.name] = pages
        print(f"  {path.name}: {len(pages)} pages"
              + ("  [image-only]" if is_image_only(pages) else ""))

    # --- assign files to editions --------------------------------------
    src_by_id = {s["id"]: dict(s, files=[]) for s in sources}
    file_src = {}
    pending = []
    for path in pdfs:
        ov = load_overrides(path.stem)
        s = by_file.get(path.name.lower())
        if ov and ov.get("source"):
            sid = ov["source"].get("id") or "x-" + slug(path.stem)
            src_by_id.setdefault(sid, {"kind": "book", "models": ["ST185"],
                                       **ov["source"], "id": sid, "files": []})
            file_src[path.name] = sid
        elif s:
            file_src[path.name] = s["id"]
        else:
            pending.append(path)
    for path in pending:
        pages = analyzed[path.name]
        fe = foreword_edition(pages)
        if fe:
            sid = f"ewd{fe['year']}" if f"ewd{fe['year']}" not in src_by_id \
                else "x-" + slug(path.stem)
            src_by_id.setdefault(sid, {
                "id": sid, "year": fe["year"], "pub": fe["pub"] or path.stem,
                "title": f"{fe['year']} Celica Electrical Wiring Diagram",
                "models": fe["models"], "kind": "book", "files": [],
                "note": "Edition detected from the manual's foreword."})
            file_src[path.name] = sid
            continue
        sid = match_page_map(pages, prev_maps)
        if sid and sid in src_by_id:
            file_src[path.name] = sid
            continue
        sid = "x-" + slug(path.stem)
        src_by_id[sid] = {"id": sid, "year": None, "pub": path.stem,
                          "title": path.stem.replace("_", " "),
                          "models": ["ST185"], "kind": "pulls" if len(pages) < 40 else "book",
                          "files": [], "note": "Edition not recognized — add it to "
                          "manuals-electrical/sources.json to set the year."}
        file_src[path.name] = sid
    for fname, sid in file_src.items():
        src_by_id[sid]["files"].append(fname)
        src_by_id[sid].setdefault("file_pages", {})[fname] = len(analyzed[fname])

    # --- split into circuits ---------------------------------------------
    circuits = []
    unsplit = []
    for path in pdfs:
        pages = analyzed[path.name]
        ov = load_overrides(path.stem)
        if ov and ov.get("circuits"):
            groups = circuits_from_overrides(path.name, pages, ov)
        elif is_image_only(pages):
            unsplit.append(path.name)
            groups = [{"file": path.name, "info": tx.classify(path.stem.replace("_", " ")),
                       "gk": "", "pages": list(range(len(pages))), "subtitles": {}}]
        else:
            groups = group_circuits(path.name, pages)
        for g in groups:
            g["source"] = file_src[path.name]
            circuits.append(g)

    # --- ids, page maps --------------------------------------------------
    used = set()
    page_map = defaultdict(dict)        # source -> printed -> (circuit id, cpage)
    for g in circuits:
        info = g["info"]
        base_id = g["source"] + "-" + info["key"] + \
            ("-" + slug(info["paren"]) if info["paren"] else "")
        cid, n = base_id, 2
        while cid in used:
            cid, n = f"{base_id}-{n}", n + 1
        used.add(cid)
        g["id"] = cid
        pages = analyzed[g["file"]]
        for k, i in enumerate(g["pages"]):
            pr = pages[i]["printed"]
            if pr is not None:
                page_map[g["source"]].setdefault(pr, (cid, k + 1))

    # --- per-source directories (parts, harness joints) ---------------
    parts_dir = defaultdict(dict)       # source -> code -> {name, pages}
    joints_dir = defaultdict(dict)
    for g in circuits:
        if g["info"]["key"] != "wiring-routing":
            continue
        pages = analyzed[g["file"]]
        for i in g["pages"]:
            ls = _lines(pages[i]["text"])
            pr = pages[i]["printed"]
            for code, name in parse_parts_directory(ls).items():
                ent = parts_dir[g["source"]].setdefault(code, {"name": name, "pages": []})
                if pr is not None and pr not in ent["pages"]:
                    ent["pages"].append(pr)
            for code, desc in parse_joint_directory(ls).items():
                ent = joints_dir[g["source"]].setdefault(code, {"name": desc, "pages": []})
                if pr is not None and pr not in ent["pages"]:
                    ent["pages"].append(pr)

    def resolve(source, printed):
        hit = page_map[source].get(printed)
        return {"circuit": hit[0], "page": hit[1], "printed": printed} if hit else \
            {"circuit": None, "page": None, "printed": printed}

    # --- records ---------------------------------------------------------
    records = []
    for g in circuits:
        info = g["info"]
        src = src_by_id[g["source"]]
        pages = analyzed[g["file"]]
        cpages = [pages[i] for i in g["pages"]]
        plain = "\n".join(p["text"] for p in cpages)
        # Page banners let the app open the page a search hit came from.
        # Parsers keep using the plain text so the banners are not parts.
        text = "\n".join(
            f"\n===== PAGE {i} of {len(cpages)} =====\n{p['text']}"
            for i, p in enumerate(cpages, 1))
        ls = _lines(plain)
        v = dict(info["variant"])
        if info["key"].startswith("hvac-"):
            heads = " ".join(h for _pg, _n, h in g["features"]) if "features" in g \
                else " ".join(h for p in cpages for _n, h in p["features"])
            b = _hvac_blower(" ".join([plain, heads, *g["subtitles"].values()]), info)
            if b:
                v["blower"] = b
            label = tx.variant_label(info["key"], info["paren"], v)
        else:
            label = info["variant_label"]
        if not v.get("engines") and src.get("engines") and len(src["engines"]) == 1:
            v["engines"] = list(src["engines"])
        if v.get("drive") is None and info["key"] == "starting-ignition" \
                and src.get("models") == ["ST185"]:
            v["drive"] = ["ALL-TRAC/4WD"]

        if "features" in g:
            raw_feats = g["features"]
        else:
            raw_feats = [(k + 1, num, head) for k, p in enumerate(cpages)
                         for num, head in p["features"]]
        features = [{"n": num, "title": tx.pretty(head), "page": pg,
                     "blower": tx.blower_types(head),
                     "auto_ac": ("W/O AUTO A/C" not in head and "W/ AUTO A/C" in head) or None}
                    for pg, num, head in raw_feats]
        page_tags = {}
        for k, p in enumerate(cpages):
            if "TYPE OF BLOWER CONTROL SW" in p["text"].upper() \
                    and "TYPE OF BLOWER CONTROL SW" not in info["title"]:
                page_tags[str(k + 1)] = {
                    "label": "Wiring differs by blower control type (see * notes)",
                    "blower": tx.blower_types(p["text"])}
        for k, sub in g["subtitles"].items():
            page_tags[str(k + 1)] = {"label": tx.pretty(sub.strip("()")),
                                     "blower": tx.blower_types(sub)}

        own_printed = {p["printed"] for p in cpages if p["printed"] is not None}
        components = []
        seen_codes = set()
        for code, pg_list, spec in parse_parts_table(ls):
            key = (code, spec)
            if key in seen_codes:
                continue
            seen_codes.add(key)
            ent = parts_dir[g["source"]].get(code)
            components.append({
                "code": code, "name": ent["name"] if ent else "",
                "spec": spec, "loc": [resolve(g["source"], p) for p in pg_list]})
        joints = [{"code": c, "name": d, "loc": [resolve(g["source"], p) for p in pg]}
                  for c, pg, d in parse_coded_table(ls, ": CONNECTOR JOINING", _JOINT_CODE)]
        jblocks = [{"code": c, "name": d, "loc": [resolve(g["source"], p) for p in pg]}
                   for c, pg, d in parse_coded_table(ls, ": JUNCTION BLOCK", _JB_CODE)]
        rblocks = [{"code": c, "name": d, "loc": [resolve(g["source"], p) for p in pg]}
                   for c, pg, d in parse_relay_blocks(ls)]
        refs, seen = [], set()
        for m in _SEE_PAGE.finditer(plain):
            pr = int(m.group(1))
            if pr in seen or pr in own_printed:
                continue
            seen.add(pr)
            r = resolve(g["source"], pr)
            if r["circuit"]:
                refs.append(r)

        printed = [p["printed"] for p in cpages if p["printed"] is not None]
        records.append({
            "id": g["id"],
            "source": g["source"],
            "year": src.get("year"),
            "file": g["file"],
            "pdf": "circuits/" + g["id"] + ".pdf",
            "thumb": "thumbs/" + g["id"] + ".png",
            "system": info["key"],
            "name": info["name"],
            "category": info["category"],
            "title": info["title"],
            "variant": label,
            "applies": v,
            "option": info.get("option"),
            "src_pages": [i + 1 for i in g["pages"]],
            "mapped": bool(g.get("mapped")),
            "printed": [min(printed), max(printed)] if printed else None,
            "pages": len(g["pages"]),
            "features": features,
            "page_tags": page_tags,
            "components": components,
            "joints": joints,
            "junction_blocks": jblocks,
            "relay_blocks": rblocks,
            "fuses": parse_fuses(ls),
            "options": parse_options(plain),
            "refs": refs,
            "image_only": len(plain.strip()) < 25 * max(1, len(cpages)),
            "text": re.sub(r"[ \t]*\n[ \t]*", "\n", text).strip(),
        })

    # --- locations index -------------------------------------------------
    locations = []
    for sid, d in parts_dir.items():
        for code, ent in sorted(d.items()):
            locations.append({"source": sid, "kind": "part", "code": code, "name": ent["name"],
                              "loc": [resolve(sid, p) for p in ent["pages"]]})
    for sid, d in joints_dir.items():
        for code, ent in sorted(d.items()):
            locations.append({"source": sid, "kind": "joint", "code": code, "name": ent["name"],
                              "loc": [resolve(sid, p) for p in ent["pages"]]})
    blocks = {}
    for r in records:
        for kind, lst in (("junction", r["junction_blocks"]), ("relay", r["relay_blocks"])):
            for b in lst:
                blocks.setdefault((r["source"], kind, b["code"]),
                                  {"source": r["source"], "kind": kind, "code": b["code"],
                                   "name": b["name"], "loc": b["loc"]})
    locations += sorted(blocks.values(), key=lambda x: (x["source"], x["kind"], x["code"]))

    # --- systems (one card per system key, editions inside) -------------
    systems = {}
    order = {k: i for i, (k, *_r) in enumerate(tx.RULES)}
    for r in records:
        s = systems.setdefault(r["system"], {
            "key": r["system"], "name": r["name"], "category": r["category"],
            "circuits": [], "years": [], "order": order.get(r["system"], 999)})
        s["circuits"].append(r["id"])
        if r["year"] and r["year"] not in s["years"]:
            s["years"].append(r["year"])
    for s in systems.values():
        s["years"].sort()

    repair_links, repair_reverse = cross_links(systems)
    for key, links in repair_links.items():
        systems[key]["repair"] = links

    write_page_previews(records, analyzed)
    write_outputs(records, src_by_id, systems, locations, page_map, repair_reverse, unsplit)
    return records, unsplit


def cross_links(systems):
    """Repair-manual sections per system, and the reverse map for the repair app."""
    if not REPAIR_INDEX.is_file():
        return {}, {}
    recs = json.loads(REPAIR_INDEX.read_text(encoding="utf-8")).get("records", [])
    titles = {r["id"]: r["title"] for r in recs}
    wanted = defaultdict(list)
    for key, ids in tx.REPAIR_LINKS.items():
        wanted[key] += ids
    for r in sorted(recs, key=lambda r: r["title"]):
        if r.get("relevance") != "car":
            continue
        for key, prefixes in tx.REPAIR_CODE_LINKS.items():
            if r.get("code") in prefixes:
                wanted[key].append(r["id"])
        for key, names in tx.REPAIR_SYSTEM_LINKS.items():
            if r.get("system") in names:
                wanted[key].append(r["id"])
    fwd, rev = {}, defaultdict(list)
    for key, ids in wanted.items():
        if key not in systems:
            continue
        ids = list(dict.fromkeys(ids))[:24]
        links = [{"id": i, "title": titles[i]} for i in ids if i in titles]
        if links:
            fwd[key] = links
        for i in ids:
            if i in titles:
                rev[i].append({"system": key, "name": systems[key]["name"]})
    return fwd, dict(rev)


# ---------------------------------------------------------------------------
# Generated files
# ---------------------------------------------------------------------------
def _load_state():
    try:
        return json.loads(STATE_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _render(page, out_path):
    zoom = max(0.4, min(1.3, THUMB_TARGET_W / (page.rect.width or 612)))
    page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False).save(out_path)


def write_page_previews(records, analyzed):
    """Per-circuit PDFs, first-page thumbs, and previews of linked-to pages."""
    state = _load_state()
    new_state = {}
    by_id = {r["id"]: r for r in records}
    targets = defaultdict(set)          # circuit id -> pages to preview
    for r in records:
        for ref in r["refs"]:
            targets[ref["circuit"]].add(ref["page"])
        for c in r["components"] + r["joints"] + r["junction_blocks"] + r["relay_blocks"]:
            for loc in c["loc"]:
                if loc["circuit"]:
                    targets[loc["circuit"]].add(loc["page"])
    by_file = defaultdict(list)
    for r in records:
        by_file[r["file"]].append(r)
    made_pdf = made_png = 0
    for fname, recs in by_file.items():
        st = (SRC_DIR / fname).stat()
        # whole seconds: Windows and Linux report sub-second mtimes differently
        stamp = f"{int(st.st_mtime)}:{st.st_size}"
        doc = None
        for r in recs:
            src = r["src_pages"]
            span = f"{src[0]}-{src[-1]}" if src == list(range(src[0], src[-1] + 1)) \
                else ",".join(map(str, src))
            sig = f"{fname}|{span}|{stamp}"
            new_state[r["id"]] = sig
            fresh = state.get(r["id"]) == sig and not FORCE_THUMBS
            out_pdf = CIRCUIT_DIR / (r["id"] + ".pdf")
            out_png = THUMB_DIR / (r["id"] + ".png")
            need_pages = [p for p in sorted(targets.get(r["id"], ()))
                          if not (fresh and (PAGES_DIR / f"{r['id']}_p{p}.png").exists())]
            if fresh and out_pdf.exists() and out_png.exists() and not need_pages:
                continue
            if doc is None:
                doc = fitz.open(SRC_DIR / fname)
            if not (fresh and out_pdf.exists()):
                sub = fitz.open()
                for p in src:
                    sub.insert_pdf(doc, from_page=p - 1, to_page=p - 1)
                # no_new_id keeps output byte-identical across rebuilds
                sub.save(str(out_pdf), garbage=3, deflate=True, no_new_id=True)
                sub.close()
                made_pdf += 1
            if not (fresh and out_png.exists()):
                _render(doc.load_page(src[0] - 1), out_png)
                made_png += 1
            for p in need_pages:
                if 1 <= p <= r["pages"]:
                    _render(doc.load_page(src[p - 1] - 1), PAGES_DIR / f"{r['id']}_p{p}.png")
                    made_png += 1
        if doc is not None:
            doc.close()
    # drop outputs of circuits that no longer exist
    removed = 0
    for d, pat in ((CIRCUIT_DIR, "*.pdf"), (THUMB_DIR, "*.png")):
        for f in d.glob(pat):
            if f.stem not in by_id:
                f.unlink()
                removed += 1
    for f in PAGES_DIR.glob("*.png"):
        cid, _, pg = f.stem.rpartition("_p")
        if cid not in by_id or not pg.isdigit() or int(pg) not in targets.get(cid, ()):
            f.unlink()
            removed += 1
    STATE_JSON.write_text(json.dumps(new_state, indent=1), encoding="utf-8", newline="\n")
    print(f"Circuit PDFs written: {made_pdf} · images rendered: {made_png} · "
          f"stale files removed: {removed}")


def write_outputs(records, src_by_id, systems, locations, page_map, repair_reverse, unsplit):
    srcs = sorted(src_by_id.values(), key=lambda s: (s.get("year") or 9999, s["id"]))
    srcs = [s for s in srcs if s.get("files")]
    payload = {
        "sources": srcs,
        "categories": [{"key": k, "name": n} for k, n in tx.CATEGORIES],
        "systems": sorted(systems.values(), key=lambda s: s["order"]),
        "circuits": records,
        "locations": locations,
        "unsplit": unsplit,
    }
    (DATA_DIR / "data.js").write_text(
        "window.EWD_DATA = " + json.dumps(payload, ensure_ascii=False) + ";",
        encoding="utf-8", newline="\n")
    slim = dict(payload, circuits=[{k: v for k, v in r.items() if k != "text"}
                                   for r in records])
    gk = {r["id"]: tx.group_key(tx.classify(r["title"])) for r in records}
    slim["page_maps"] = {sid: {str(pr): gk[cid] for pr, (cid, _k) in m.items()}
                         for sid, m in page_map.items()}
    (DATA_DIR / "index.json").write_text(json.dumps(slim, indent=1, ensure_ascii=False),
                                         encoding="utf-8", newline="\n")
    (DATA_DIR / "repair_links.js").write_text(
        "window.EWD_LINKS = " + json.dumps(repair_reverse, ensure_ascii=False) + ";",
        encoding="utf-8", newline="\n")

    by_id = {r["id"]: r for r in records}
    lines = ["# ST185 Celica - Electrical Wiring Diagram System Index", "",
             "Editions:", ""]
    for s in srcs:
        lines.append(f"- **{s['id']}** — {s.get('title', '')} ({s.get('pub', '')}), "
                     f"{len(s['files'])} file(s)")
    lines.append("")
    for ck, cname in tx.CATEGORIES:
        syss = [s for s in payload["systems"] if s["category"] == ck]
        if not syss:
            continue
        lines += [f"## {cname}", "", "| System | Edition | Variant | Printed pages | Features |",
                  "|---|---|---|---|---|"]
        for s in syss:
            for cid in s["circuits"]:
                r = by_id[cid]
                pr = f"{r['printed'][0]}–{r['printed'][1]}" if r["printed"] else "-"
                lines.append(f"| {s['name']} | {r['source']} | {r['variant'] or '-'} | {pr} "
                             f"| {len(r['features'])} |")
        lines.append("")
    (APP_DIR / "SYSTEM_INDEX.md").write_text("\n".join(lines), encoding="utf-8",
                                             newline="\n")


def report(records, unsplit):
    print("\n=== BUILD REPORT ===")
    by_src = defaultdict(int)
    for r in records:
        by_src[r["source"]] += 1
    print("Circuits per edition:", dict(by_src))
    print("Systems:", len({r["system"] for r in records}))
    other = sorted({r["title"] for r in records if r["category"] == "other"})
    if other:
        print("Unclassified titles:", other)
    print("Features:", sum(len(r["features"]) for r in records),
          "· components:", sum(len(r["components"]) for r in records),
          "· resolved refs:", sum(len(r["refs"]) for r in records))
    if unsplit:
        print("Image-only PDFs without an override map (shown unsplit):", unsplit)
    djs = (DATA_DIR / "data.js").stat().st_size
    print(f"data.js size: {djs / 1024 / 1024:.2f} MB")


def scan_signatures(path):
    """(page_count, {"<edition>|<circuit>|<printed page>"}, label) for the app's
    upload conflict check: same edition + same circuit pages = same content."""
    pages = analyze_pdf(Path(path))
    name = Path(path).name.lower()
    edition = None
    for s in load_sources():
        if name in (f.lower() for f in s.get("files", [])):
            edition = s["id"]
    year = None
    if edition is None:
        fe = foreword_edition(pages)
        if fe:
            edition, year = f"ewd{fe['year']}", fe["year"]
    if edition is None and (DATA_DIR / "index.json").is_file():
        try:
            maps = json.loads((DATA_DIR / "index.json").read_text(
                encoding="utf-8")).get("page_maps", {})
            edition = match_page_map(pages, maps)
        except ValueError:
            pass
    edition = edition or "?"
    sigs, titles = set(), set()
    for p in pages:
        if p["title"] and not p["title"].startswith("("):
            gk = tx.group_key(tx.classify(p["title"]))
            titles.add(gk)
            sigs.add(f"{edition}|{gk}|{p['printed']}")
    for s in load_sources():
        if s["id"] == edition:
            year = s.get("year")
    label = f"{year or 'unknown edition'} · {len(titles)} circuit title(s)"
    return len(pages), sigs, label


def run_build(force_thumbs: bool = False) -> dict:
    """Run the full catalog build. Importable entry point (used by the app's
    /api/rebuild?app=electrical endpoint)."""
    global FORCE_THUMBS
    FORCE_THUMBS = force_thumbs
    recs, unsplit = build()
    report(recs, unsplit)
    print("\nDone. Outputs in:", APP_DIR)
    return {"circuits": len(recs), "unsplit": len(unsplit)}


if __name__ == "__main__":
    run_build(force_thumbs="--thumbs" in sys.argv)
