import json, re
from pathlib import Path
from collections import Counter, defaultdict

APP = Path(__file__).resolve().parents[1]
data = json.loads((APP / "data" / "data.js").read_text(encoding="utf-8")
                  .removeprefix("window.CELICA_DATA = ").rstrip(";"))
recs = data["records"]

# text length buckets
short = [(r["id"], len(r["text"])) for r in recs if len(r["text"]) < 200]
print(f"Files with <200 chars extracted (likely image-only): {len(short)}")
for i, (rid, n) in enumerate(sorted(short, key=lambda x: x[1])):
    print(f"   {n:5d}  {rid}")

print("\nFiles by code == 'RE':")
for r in recs:
    if r["code"] == "RE":
        print(f"   {r['id']}  -> system={r['system']} group={r['group']} len={len(r['text'])}")

print("\nSample own_codes for a few code=='RE' + code=='' body files:")
for r in recs:
    if r["code"] in ("RE", "CN", "EX", "AP", "PP") :
        print(f"   {r['id']}: {r['own_codes'][:6]}")
