import json
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
raw = (APP / "data" / "data.js").read_text(encoding="utf-8")
data = json.loads(raw.removeprefix("window.CELICA_DATA = ").rstrip().rstrip(";"))
recs = data["records"]

pat = re.compile(r"\b(E1?5\d[A-Z]?\d?|E54|S5[34]|W5\d)\b")

print("=== Transmission designations in Drivetrain sections ===")
for r in recs:
    hits = sorted(set(pat.findall(r["text"])))
    if hits and r["group"] == "Drivetrain":
        print(f"{r['id']:42s} code={r['code'] or '--':3s} "
              f"tables={r['torque_table_pages']} hits={hits}")

print()
print("=== Designations anywhere else (non-Drivetrain) ===")
for r in recs:
    hits = sorted(set(pat.findall(r["text"])))
    if hits and r["group"] != "Drivetrain":
        print(f"{r['id']:42s} grp={r['group']:12s} hits={hits}")

print()
print("=== MT-coded files: any TORQUE mention lines ===")
for r in recs:
    if r["code"] == "MT":
        tl = [l.strip() for l in r["text"].splitlines()
              if "TORQUE" in l.upper()][:3]
        print(f"{r['id']:42s} pages={r['pages']:3d} "
              f"tableP={r['torque_table_pages']} lines={tl}")
