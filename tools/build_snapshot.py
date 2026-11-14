"""Save a real Agmarknet snapshot (all MandiMitra commodities, Karnataka) and pre-geocode every mandi.
Run: python tools/build_snapshot.py   (takes a few minutes because Nominatim allows 1 request/second)"""
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import market as M  # noqa

import os
snaps = sorted(M.DATA.glob(M.SNAPSHOT_GLOB))
rows, retrieved = [], None
if snaps and "--refresh" not in sys.argv:
    rows = json.loads(snaps[-1].read_text())["rows"]
    print("using existing", snaps[-1].name)
for key, (label, aliases, _) in (M.COMMODITIES.items() if not rows else []):
    for name in aliases:
        try:
            r, ret = M._fetch_mirror(name)
        except Exception as e:
            print("fail", name, e)
            continue
        if r:
            rows += r
            retrieved = retrieved or ret
            print(f"{name}: {len(r)} rows, {r[0]['date']}")
            break
date = max(r["date"] for r in rows)
if retrieved:
  out = {"source": f"Agmarknet daily prices (data.gov.in resource {M.OGD_RESOURCE}) via api.dharun.dev mirror, "
                 f"OGD retrieval {retrieved}; saved {dt.datetime.now(M.IST):%Y-%m-%d %H:%M} IST",
         "data_date": date, "rows": rows}
  f = M.DATA / f"snapshot_karnataka_{date}.json"
  f.write_text(json.dumps(out))
  print("saved", f, len(rows))
mk = sorted({(r["market"], r["district"]) for r in rows})
print(len(mk), "markets to geocode")
for i, (m, d) in enumerate(mk):
    g = M.geocode(m, d)
    print(i, m, "|", d, "->", g.get("precision"), g.get("lat"), g.get("lon"))
