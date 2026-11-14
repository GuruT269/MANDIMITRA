"""Satellite revisit info: static mission table + observed acquisitions + next-pass estimate."""
import datetime as dt
from collections import defaultdict

REVISIT_TABLE = [
    {"mission": "Sentinel-2 (A/B/C) MSI", "agency": "ESA", "resolution": "10/20/60 m optical", "revisit": "5 days (constellation); 2-3 days at mid-latitudes with tile overlap", "free": True},
    {"mission": "Landsat 8 + 9 OLI/TIRS", "agency": "NASA/USGS", "resolution": "30 m optical, 100 m thermal", "revisit": "16 days each, 8 days combined", "free": True},
    {"mission": "Sentinel-1 C-band SAR", "agency": "ESA", "resolution": "10 m radar (sees through clouds)", "revisit": "12 days per satellite (6 days with 2 satellites)", "free": True},
    {"mission": "Resourcesat-2/2A LISS-IV", "agency": "ISRO", "resolution": "5.8 m optical", "revisit": "5 days nominal (steerable), 24 days nadir repeat", "free": "via Bhuvan/NRSC (registration)"},
    {"mission": "MODIS Terra/Aqua", "agency": "NASA", "resolution": "250-500 m", "revisit": "daily", "free": True},
    {"mission": "NISAR L+S-band SAR", "agency": "NASA/ISRO", "resolution": "3-10 m radar", "revisit": "12 days", "free": True},
]


def s2_next_passes(acquisitions, today=None, n=4):
    """Each relative orbit repeats every 5 days (constellation pattern). Project last pass per orbit forward."""
    today = today or dt.date.today()
    last_by_orbit = {}
    for a in acquisitions:
        ro = a.get("relative_orbit")
        d = dt.date.fromisoformat(a["date"])
        if ro is not None and (ro not in last_by_orbit or d > last_by_orbit[ro]):
            last_by_orbit[ro] = d
    nxt = []
    for ro, d in last_by_orbit.items():
        k = d
        while k <= today:
            k += dt.timedelta(days=5)
        for j in range(n):
            nxt.append({"date": (k + dt.timedelta(days=5 * j)).isoformat(), "relative_orbit": ro})
    nxt.sort(key=lambda x: x["date"])
    # observed median interval over last 60 days
    ds = sorted({dt.date.fromisoformat(a["date"]) for a in acquisitions if
                 dt.date.fromisoformat(a["date"]) >= today - dt.timedelta(days=60)})
    gaps = sorted((b - a).days for a, b in zip(ds, ds[1:]))
    med = gaps[len(gaps) // 2] if gaps else None
    return nxt[:n], med, len(ds)


def build(acquisitions, others):
    nxt, med, n60 = s2_next_passes(acquisitions)
    def proj(lst, step):
        if not isinstance(lst, list) or not lst:
            return None
        k = dt.date.fromisoformat(lst[0]["date"])
        while k <= dt.date.today():
            k += dt.timedelta(days=step)
        return k.isoformat()
    return {
        "table": REVISIT_TABLE,
        "sentinel2": {"last_acquisitions": acquisitions[:8], "observed_median_gap_days": med,
                      "acquisitions_last_60d": n60, "estimated_next": nxt,
                      "method": "last pass of each relative orbit + 5-day repeat"},
        "landsat": {"last_acquisitions": others.get("landsat"), "estimated_next": proj(others.get("landsat"), 8)},
        "sentinel1": {"last_acquisitions": others.get("sentinel1"), "estimated_next": proj(others.get("sentinel1"), 12)},
    }
