"""Sanity checks for the generated Electrical (EWD) library. Exit code 1 on failure."""
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
raw = (APP / "data" / "data.js").read_text(encoding="utf-8")
assert raw.startswith("window.EWD_DATA = ") and raw.rstrip().endswith(";")
data = json.loads(raw.removeprefix("window.EWD_DATA = ").rstrip().rstrip(";"))
circ = data["circuits"]
by_id = {c["id"]: c for c in circ}
problems = []

need = {"id", "source", "file", "pdf", "thumb", "system", "name", "category", "title",
        "variant", "applies", "src_pages", "pages", "features", "page_tags", "components",
        "joints", "junction_blocks", "relay_blocks", "fuses", "options", "refs", "text"}
for c in circ:
    missing = need - set(c)
    if missing:
        problems.append(f"{c['id']}: missing fields {sorted(missing)}")

# every page of every source PDF belongs to exactly one circuit
for s in data["sources"]:
    for f, n in s.get("file_pages", {}).items():
        owner = [0] * (n + 1)
        mapped = False
        for c in circ:
            if c["file"] == f:
                mapped = mapped or c.get("mapped", False)
                for p in c["src_pages"]:
                    owner[p] += 1
        gaps = [p for p in range(1, n + 1) if owner[p] == 0]
        # page-mapped manuals may show one page (e.g. an overall wiring
        # figure) in several systems
        dupes = [] if mapped else [p for p in range(1, n + 1) if owner[p] > 1]
        if gaps or dupes:
            problems.append(f"{f}: unassigned pages {gaps[:10]} / pages in 2+ circuits {dupes[:10]}")

# links resolve to real circuits and pages
def check_loc(cid, what, loc):
    if loc.get("circuit") is None:
        return
    t = by_id.get(loc["circuit"])
    if not t:
        problems.append(f"{cid}: {what} -> unknown circuit {loc['circuit']}")
    elif not 1 <= loc["page"] <= t["pages"]:
        problems.append(f"{cid}: {what} -> page {loc['page']} outside {t['id']} (1..{t['pages']})")

for c in circ:
    for r in c["refs"]:
        check_loc(c["id"], "see page", r)
    for x in c["components"] + c["joints"] + c["junction_blocks"] + c["relay_blocks"]:
        for loc in x["loc"]:
            check_loc(c["id"], x["code"], loc)
    for f in c["features"]:
        if not 1 <= f["page"] <= c["pages"]:
            problems.append(f"{c['id']}: feature {f['n']} page {f['page']} out of range")
for l in data["locations"]:
    for loc in l["loc"]:
        check_loc("locations", l["code"], loc)

# generated files exist
for c in circ:
    for rel in (c["pdf"], c["thumb"]):
        if not (APP / rel).is_file():
            problems.append(f"{c['id']}: missing {rel}")
    for r in c["refs"]:
        png = APP / "thumbs" / "pages" / f"{r['circuit']}_p{r['page']}.png"
        if not png.is_file():
            problems.append(f"{c['id']}: missing preview {png.name}")

# A/C breakdown: each control type is covered by the editions known to have it
EXPECTED_HVAC = {
    ("hvac-auto", "PUSH"): [1990, 1992],
    ("hvac-auto", "DIAL"): [1992, 1993],
    ("hvac-manual", "PUSH"): [1990],
    ("hvac-manual", "DIAL"): [1992, 1993],
}
for (sysk, blower), years in EXPECTED_HVAC.items():
    have = sorted({c["year"] for c in circ
                   if c["system"] == sysk and blower in c["applies"].get("blower", [])})
    lacking = [y for y in years if y not in have]
    print(f"{sysk:12s} {blower:5s} editions: {have}")
    if lacking:
        problems.append(f"{sysk} {blower}: no circuit for {lacking}")
    for c in circ:
        if c["system"] == sysk and blower in c["applies"].get("blower", []) and not c["features"]:
            problems.append(f"{c['id']}: A/C circuit without feature anchors")

# repair cross-links point at real repair-manual sections
repair_index = APP.parent / "celica-manual" / "data" / "index.json"
if repair_index.is_file():
    ids = {r["id"] for r in json.loads(repair_index.read_text(encoding="utf-8"))["records"]}
    for s in data["systems"]:
        for r in s.get("repair", []):
            if r["id"] not in ids:
                problems.append(f"system {s['key']}: repair link to unknown {r['id']}")

other = sorted({c["title"] for c in circ if c["category"] == "other"})
print("circuits:", len(circ), "| systems:", len(data["systems"]),
      "| editions:", [s["id"] for s in data["sources"]])
print("features:", sum(len(c["features"]) for c in circ),
      "| components:", sum(len(c["components"]) for c in circ),
      "| unnamed components:", sum(1 for c in circ for x in c["components"] if not x["name"]),
      "| refs:", sum(len(c["refs"]) for c in circ))
if other:
    print("WARNING unclassified circuit titles:", other)
if data.get("unsplit"):
    print("WARNING image-only PDFs without a page map:", data["unsplit"])
if problems:
    print(f"\n{len(problems)} PROBLEM(S):")
    for p in problems[:60]:
        print("  -", p)
    sys.exit(1)
print("VALIDATION OK")
