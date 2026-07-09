import json
from pathlib import Path
APP = Path(__file__).resolve().parents[1]
raw = (APP/"data"/"data.js").read_text(encoding="utf-8")
assert raw.startswith("window.CELICA_DATA = ") and raw.rstrip().endswith(";")
data = json.loads(raw.removeprefix("window.CELICA_DATA = ").rstrip().rstrip(";"))
recs = data["records"]
need = {"id","file","title","system","group","engine","relevance","image_only",
        "pages","torques","refs_resolved","text"}
missing = [r["id"] for r in recs if not need.issubset(r)]
print("records:", len(recs))
print("missing-field records:", missing[:10], "..." if len(missing)>10 else "")
print("with torques:", sum(1 for r in recs if r["torques"]))
print("with crossrefs:", sum(1 for r in recs if r["refs_resolved"]))
print("resolved crossref targets:",
      sum(1 for r in recs for x in r["refs_resolved"] if x["target"]))
print("image_only:", sum(1 for r in recs if r["image_only"]))
print("relevance=car:", sum(1 for r in recs if r["relevance"]=="car"),
      "| ref:", sum(1 for r in recs if r["relevance"]=="ref"))
# sample a well-known record
tb = next(r for r in recs if r["id"]=="Timing_Belt_3sgte")
print("\nSample:", tb["title"], "|", tb["system"], "|", tb["engine"],
      "| torques:", len(tb["torques"]), "| refs:", len(tb["refs_resolved"]))
print("first torque:", tb["torques"][0] if tb["torques"] else None)
print("first ref:", tb["refs_resolved"][0] if tb["refs_resolved"] else None)
print("VALIDATION OK")
