"""'Where to sell' mandi recommender: prices -> geocode -> road distance -> net realisation ranking."""
import datetime as dt
import json
import math
import os
import re
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = DATA / "cache"
CACHE.mkdir(parents=True, exist_ok=True)
GEO_FILE = DATA / "mandi_geo.json"
SNAPSHOT_GLOB = "snapshot_karnataka_*.json"
UA = {"User-Agent": "MandiMitra-prototype/0.1 (hackathon demo; contact: local)"}
OGD_RESOURCE = "9ef84268-d588-465a-a308-a864a43d0070"
OGD_SAMPLE_KEY = "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b"
MIRROR = "https://api.dharun.dev/v1/mandi"           # keyless mirror of the same data.gov.in feed
HISTORY_MIRROR = "https://mandi-api.onrender.com/v1/prices/history"  # keyless, daily state averages (may lag)
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

# key -> (label, Agmarknet name aliases, perishability class)
COMMODITIES = {
    "paddy":     ("Paddy", ["Paddy(Common)", "Paddy(Dhan)(Common)", "Paddy(Dhan)(Basmati)"], "durable"),
    "rice":      ("Rice", ["Rice"], "durable"),
    "ragi":      ("Ragi (finger millet)", ["Ragi(Finger Millet)", "Ragi (Finger Millet)"], "durable"),
    "maize":     ("Maize", ["Maize"], "durable"),
    "jowar":     ("Jowar", ["Jowar(Sorghum)"], "durable"),
    "tur":       ("Tur / red gram", ["Red gram/Arhar/Tur(whole)", "Arhar (Tur/Red Gram)(Whole)", "Arhar(Tur/Red Gram)(Whole)"], "durable"),
    "bengalgram": ("Bengal gram", ["Bengal Gram(Gram)(Whole)"], "durable"),
    "greengram": ("Green gram", ["Green Gram(Moong)(Whole)", "Green Gram (Moong)(Whole)"], "durable"),
    "groundnut": ("Groundnut", ["Groundnut"], "durable"),
    "sunflower": ("Sunflower", ["Sunflower/Sunflower Seed", "Sunflower"], "durable"),
    "soyabean":  ("Soyabean", ["Soyabean"], "durable"),
    "cotton":    ("Cotton", ["Cotton"], "durable"),
    "arecanut":  ("Arecanut", ["Arecanut(Betelnut/Supari)"], "durable"),
    "copra":     ("Copra", ["Copra"], "durable"),
    "coconut":   ("Coconut", ["Coconut"], "semi"),
    "jaggery":   ("Sugarcane jaggery (gur)", ["Gur(Jaggery)"], "durable"),
    "blackpepper": ("Black pepper", ["Black pepper"], "durable"),
    "onion":     ("Onion", ["Onion"], "semi"),
    "potato":    ("Potato", ["Potato"], "semi"),
    "tomato":    ("Tomato", ["Tomato"], "perishable"),
    "beans":     ("Beans", ["Beans"], "perishable"),
    "brinjal":   ("Brinjal", ["Brinjal"], "perishable"),
    "greenchilli": ("Green chilli", ["Green Chilli"], "perishable"),
    "cabbage":   ("Cabbage", ["Cabbage"], "perishable"),
    "carrot":    ("Carrot", ["Carrot"], "perishable"),
    "banana":    ("Banana", ["Banana", "Banana - Green"], "perishable"),
}

_GEO_LOCK = threading.Lock()
_NOMI_LOCK = threading.Lock()
_last_nominatim = [0.0]


def config():
    return json.loads((DATA / "market_config.json").read_text(encoding="utf-8"))


def today_ist():
    return dt.datetime.now(IST).date()


# ------------------------------------------------------------------ prices
def _norm_row(r):
    """Normalise official OGD rows and mirror rows to one schema."""
    g = lambda *ks: next((r[k] for k in ks if k in r and r[k] not in (None, "")), None)
    date = g("date", "arrival_date", "Arrival_Date")
    if date and re.match(r"\d{2}/\d{2}/\d{4}", str(date)):
        d, m, y = str(date).split("/")
        date = f"{y}-{m}-{d}"
    num = lambda v: None if v in (None, "", "NA") else float(v)
    return {"date": date, "state": g("state", "State"), "district": g("district", "District"),
            "market": g("market", "Market"), "commodity": g("commodity", "Commodity"),
            "variety": g("variety", "Variety"), "grade": g("grade", "Grade"),
            "min_price": num(g("min_price", "Min_Price", "Min_x0020_Price")),
            "max_price": num(g("max_price", "Max_Price", "Max_x0020_Price")),
            "modal_price": num(g("modal_price", "Modal_Price", "Modal_x0020_Price"))}


def _fetch_official(name, timeout=12):
    key = os.environ.get("DATA_GOV_IN_KEY") or OGD_SAMPLE_KEY
    rows, offset = [], 0
    while True:
        p = {"api-key": key, "format": "json", "limit": 1000, "offset": offset,
             "filters[state.keyword]": "Karnataka", "filters[commodity]": name}
        r = requests.get(f"https://api.data.gov.in/resource/{OGD_RESOURCE}", params=p, headers=UA, timeout=timeout)
        r.raise_for_status()
        recs = r.json().get("records", [])
        rows += recs
        if len(recs) < 10 or offset > 5000:  # sample key returns 10 per page
            break
        offset += len(recs)
    return [_norm_row(x) for x in rows]


def _fetch_mirror(name, date=None, timeout=20):
    p = {"state": "Karnataka", "commodity": name, "limit": 1000}
    if date:
        p["date"] = date
    r = requests.get(MIRROR, params=p, headers=UA, timeout=timeout)
    r.raise_for_status()
    j = r.json()
    return [_norm_row(x) for x in j.get("data", [])], j.get("meta", {}).get("source", {}).get("retrieved")


def _snapshot():
    files = sorted(DATA.glob(SNAPSHOT_GLOB))
    if not files:
        return None, None
    return json.loads(files[-1].read_text(encoding="utf-8")), files[-1].name


def get_prices(key):
    """Returns (rows, info). Order: official OGD API -> keyless mirror -> today's disk cache -> latest disk cache -> bundled snapshot."""
    label, aliases, _ = COMMODITIES[key]
    tday = today_ist().isoformat()
    cfile = CACHE / f"prices_{key}_{tday}.json"
    attempts = []
    if cfile.exists() and time.time() - cfile.stat().st_mtime < 3 * 3600:
        c = json.loads(cfile.read_text(encoding="utf-8"))
        c["info"]["status"] = "cached"
        c["info"]["note"] = f"Disk cache from {dt.datetime.fromtimestamp(cfile.stat().st_mtime, IST):%d %b %H:%M} IST (refreshes every 3 h)"
        return c["rows"], c["info"]
    # 1) official API
    rows, info = [], {}
    for name in aliases:
        try:
            rows = [r for r in _fetch_official(name) if r["modal_price"]]
            if rows:
                info = {"status": "live", "source": "data.gov.in OGD API (Agmarknet), resource " + OGD_RESOURCE,
                        "fetched_at": dt.datetime.now(IST).strftime("%d %b %Y %H:%M IST")}
                break
            attempts.append(f"official {name}: 0 rows")
        except Exception as e:
            attempts.append(f"official API: {type(e).__name__}")
            break
    # 2) mirror
    if not rows:
        for name in aliases:
            try:
                rws, retrieved = _fetch_mirror(name)
                rws = [r for r in rws if r["modal_price"]]
                if rws:
                    rows = rws
                    info = {"status": "live", "source": "Agmarknet daily feed (data.gov.in) via keyless mirror api.dharun.dev "
                            "(official api.data.gov.in unreachable from this server)",
                            "fetched_at": dt.datetime.now(IST).strftime("%d %b %Y %H:%M IST"),
                            "mirror_retrieved_from_ogd": retrieved}
                    break
                attempts.append(f"mirror {name}: 0 rows")
            except Exception as e:
                attempts.append(f"mirror: {type(e).__name__}")
                break
    if rows:
        info["attempts"] = attempts
        info["data_date"] = max(r["date"] for r in rows if r["date"])
        cfile.write_text(json.dumps({"rows": rows, "info": info}), encoding="utf-8")
        _append_history(key, rows)
        return rows, info
    # 3) any older disk cache
    olds = sorted(CACHE.glob(f"prices_{key}_*.json"))
    if olds:
        c = json.loads(olds[-1].read_text(encoding="utf-8"))
        info = {**c["info"], "status": "cached", "attempts": attempts,
                "note": f"Live sources failed; showing last cached pull ({olds[-1].stem.split('_')[-1]})"}
        return c["rows"], info
    # 4) bundled snapshot
    snap, fname = _snapshot()
    if snap:
        rows = [r for r in snap["rows"] if r["commodity"] in aliases and r["modal_price"]]
        if rows:
            return rows, {"status": "fallback", "source": f"Bundled snapshot {fname}: {snap['source']}",
                          "data_date": max(r["date"] for r in rows), "attempts": attempts,
                          "note": "Real Agmarknet prices saved earlier, NOT today's. Use for demo only."}
    return [], {"status": "unavailable", "attempts": attempts, "source": None, "data_date": None}


def _append_history(key, rows):
    """Accumulate our own daily per-market price history on disk."""
    hfile = CACHE / f"history_{key}.json"
    h = json.loads(hfile.read_text(encoding="utf-8")) if hfile.exists() else {}
    for r in rows:
        h.setdefault(r["date"], {}).setdefault(r["market"], []).append(r["modal_price"])
    for d in h:
        for m in h[d]:
            h[d][m] = sorted(set(h[d][m]))
    hfile.write_text(json.dumps(h), encoding="utf-8")


def history(key, market_names=None):
    """State-average modal price per day, merged from our disk history + keyless history mirror."""
    label, aliases, _ = COMMODITIES[key]
    series = {}
    src = []
    cf = CACHE / f"hist_mirror_{key}_{today_ist().isoformat()}.json"
    data = None
    if cf.exists():
        data = json.loads(cf.read_text(encoding="utf-8"))
    else:
        for name in aliases:
            try:
                r = requests.get(HISTORY_MIRROR, params={"state": "Karnataka", "commodity": name}, headers=UA, timeout=25)
                r.raise_for_status()
                d = r.json().get("data", [])
                if d:
                    data = d
                    cf.write_text(json.dumps(d), encoding="utf-8")
                    break
            except Exception:
                break
    if data:
        for p in data:
            series[p["arrival_date"]] = {"modal": p["avg_modal_price"], "n": p.get("data_points"), "src": "mirror"}
        src.append("mandi-api.onrender.com (daily Karnataka averages of Agmarknet data)")
    hfile = CACHE / f"history_{key}.json"
    if hfile.exists():
        for d, mk in json.loads(hfile.read_text(encoding="utf-8")).items():
            vals = [statistics.median(v) for v in mk.values() if v]
            if vals:
                series[d] = {"modal": round(statistics.mean(vals)), "n": len(vals), "src": "local"}
        src.append("MandiMitra local daily cache")
    pts = [{"date": d, **v} for d, v in sorted(series.items())]
    return pts, src


def trend_and_hint(pts, klass, current_avg):
    out = {"points": pts[-60:], "change_7d_pct": None, "change_30d_pct": None}
    if not pts or current_avg is None:
        out["hint"] = {"action": "NO TREND DATA", "why": "No price history available."}
        return out
    last = dt.date.fromisoformat(pts[-1]["date"])

    def near(days):
        tgt = last - dt.timedelta(days=days)
        c = [p for p in pts if abs((dt.date.fromisoformat(p["date"]) - tgt).days) <= 3]
        return min(c, key=lambda p: abs((dt.date.fromisoformat(p["date"]) - tgt).days)) if c else None
    p7, p30 = near(7), near(30)
    if p7:
        out["change_7d_pct"] = round(100 * (current_avg - p7["modal"]) / p7["modal"], 1)
        out["ref_7d"] = p7
    if p30:
        out["change_30d_pct"] = round(100 * (current_avg - p30["modal"]) / p30["modal"], 1)
        out["ref_30d"] = p30
    recent = [p["modal"] for p in pts if (last - dt.date.fromisoformat(p["date"])).days <= 30]
    mean30 = statistics.mean(recent) if recent else None
    out["mean_30d"] = round(mean30) if mean30 else None
    gap_days = (today_ist() - last).days
    out["history_last_date"] = pts[-1]["date"]
    out["history_gap_days"] = gap_days
    dev = None if not mean30 else 100 * (current_avg - mean30) / mean30
    c7 = out["change_7d_pct"]
    if klass == "perishable":
        if c7 is not None and c7 < -10:
            a, why = "SELL NOW", f"Perishable and prices fell {abs(c7)}% in a week; waiting risks both spoilage and lower prices."
        elif dev is not None and dev > 10:
            a, why = "SELL NOW", f"Price is {dev:.0f}% above its recent average. Good time to sell a perishable crop."
        else:
            a, why = "SELL NOW (within 1-2 days)", "Perishable: storage losses usually outweigh small price gains. Pick the best net-price mandi below."
    else:
        if dev is None:
            a, why = "NEUTRAL", "Not enough recent history to compare."
        elif dev < -8:
            a, why = "CONSIDER WAITING", (f"Current state average is {abs(dev):.0f}% below the recent average. If you have dry storage "
                                         "(or a warehouse receipt loan), holding 2-4 weeks may pay.")
        elif dev > 8:
            a, why = "SELL NOW", f"Prices are {dev:.0f}% above the recent average. Lock in the gain."
        else:
            a, why = "NEUTRAL / SELL IF CASH NEEDED", f"Prices are within ±8% of the recent average ({dev:+.1f}%)."
    ds = [dt.date.fromisoformat(p["date"]) for p in pts if (last - dt.date.fromisoformat(p["date"])).days <= 45]
    gaps = [((b - a).days, a, b) for a, b in zip(ds, ds[1:])]
    big = max(gaps, default=(0, None, None))
    if big[0] > 7:
        why += f" (Caution: no history between {big[1]} and {big[2]}, so the trend is approximate.)"
        out["history_gap"] = {"days": big[0], "from": big[1].isoformat(), "to": big[2].isoformat()}
    if gap_days > 10:
        why += f" (Caution: price history only runs to {pts[-1]['date']}.)"
    out["hint"] = {"action": a, "why": why, "rule_based": True}
    return out


# ------------------------------------------------------------------ geocoding
def _load_geo():
    return json.loads(GEO_FILE.read_text(encoding="utf-8")) if GEO_FILE.exists() else {}


def _save_geo(g):
    with _GEO_LOCK:
        GEO_FILE.write_text(json.dumps(g, indent=1, ensure_ascii=False), encoding="utf-8")


def _nominatim(q):
    with _NOMI_LOCK:  # usage policy: max 1 request / second
        wait = 1.1 - (time.time() - _last_nominatim[0])
        if wait > 0:
            time.sleep(wait)
        try:
            r = requests.get("https://nominatim.openstreetmap.org/search",
                             params={"q": q, "format": "json", "limit": 1, "countrycodes": "in"}, headers=UA, timeout=15)
            _last_nominatim[0] = time.time()
            r.raise_for_status()
            j = r.json()
            return (float(j[0]["lat"]), float(j[0]["lon"]), j[0].get("display_name", "")) if j else None
        except Exception:
            _last_nominatim[0] = time.time()
            return None


def town_name(market):
    t = re.sub(r"\(.*?\)", "", market)
    t = re.sub(r"\b(APMC|Apmc|Market|Yard|Sub ?Yard|F&V|FF&V|Fruits? ?& ?Vegetables?)\b", "", t)
    return re.sub(r"\s+", " ", t).strip(" ,-")


# Agmarknet spellings that Nominatim does not know -> OSM town names
TOWN_FIX = {"Bantwala": "Bantwal", "Belthangdi": "Belthangady", "Gonikappal": "Gonikoppal", "Bailahongal": "Bailhongal",
            "Basava Kalayana": "Basavakalyan", "Thirthahalli": "Tirthahalli", "Laxmeshwar": "Lakshmeshwar",
            "Soundati": "Saundatti", "Srinivasapur": "Srinivaspur", "Talikot": "Talikoti", "Mulbagal": "Mulbagal", "Hunsur": "Hunsur",
            "Belgaum": "Belagavi", "Mysore": "Mysuru", "Shimoga": "Shivamogga", "Tumkur": "Tumakuru",
            "Gulbarga": "Kalaburagi", "Bellary": "Ballari", "Hospet": "Hosapete", "Chickmagalur": "Chikkamagaluru",
            "Kundapura": "Kundapura", "Puttur": "Puttur", "Sagar": "Sagara", "Siddapur": "Siddapura",
            "Yellapur": "Yellapura", "Sirsi": "Sirsi", "Kumta": "Kumta", "Madikeri": "Madikeri",
            "Somvarpet": "Somwarpet", "Holalkere": "Holalkere", "Harihar": "Harihara", "Ranebennur": "Ranebennur",
            "Hubballi": "Hubballi", "Binny Mill": "Bengaluru", "K.R. Pet": "Krishnarajpet", "KR Pet": "Krishnarajpet",
            "Sreerangapattana": "Srirangapatna", "Gundlupet": "Gundlupet", "Kollegal": "Kollegala"}


def _ok(display, town):
    d = display.lower().replace(" ", "")
    t = town.lower().replace(" ", "")
    return t[:5] in d or t[:4] in d


def geocode(market, district):
    key = f"{market}|{district}"
    g = _load_geo()
    if key in g:
        return g[key]
    town = town_name(market)
    town = TOWN_FIX.get(town, TOWN_FIX.get(town.title(), town.title() if town.isupper() else town))
    res = None
    for q, prec, check in [(f"{town}, {district}, Karnataka", "town", True),
                           (f"{town}, Karnataka", "town", True),
                           (f"{district} district, Karnataka", "district (approx.)", False)]:
        r = _nominatim(q)
        if r and 11.4 <= r[0] <= 18.6 and 74.0 <= r[1] <= 78.7 and (not check or _ok(r[2], town)):
            res = {"lat": r[0], "lon": r[1], "precision": prec, "query": q, "display": r[2][:120]}
            break
    if not res:
        res = {"lat": None, "lon": None, "precision": "failed"}
    g = _load_geo()
    g[key] = res
    _save_geo(g)
    return res


# ------------------------------------------------------------------ routing
def haversine(a, b):
    R = 6371.0
    la1, lo1, la2, lo2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def road_distances(origin, dests):
    """OSRM public table (one request); fallback haversine x 1.3 road factor at 40 km/h."""
    if not dests:
        return [], "none"
    coords = ";".join(f"{lo:.5f},{la:.5f}" for la, lo in [origin] + dests)
    try:
        r = requests.get(f"https://router.project-osrm.org/table/v1/driving/{coords}",
                         params={"sources": "0", "annotations": "distance,duration"}, headers=UA, timeout=20)
        r.raise_for_status()
        j = r.json()
        if j.get("code") == "Ok":
            out = []
            for i, d in enumerate(dests):
                dist, dur = j["distances"][0][i + 1], j["durations"][0][i + 1]
                if dist is None:
                    km = haversine(origin, d) * 1.3
                    out.append((km, km / 40 * 60, "haversine"))
                else:
                    out.append((dist / 1000, dur / 60, "osrm"))
            return out, "OSRM public demo server (OpenStreetMap roads)"
    except Exception:
        pass
    return [(haversine(origin, d) * 1.3, haversine(origin, d) * 1.3 / 40 * 60, "haversine") for d in dests], \
        "Straight-line distance x 1.3 (OSRM unavailable)"


def route_geometry(origin, dest):
    try:
        r = requests.get(f"https://router.project-osrm.org/route/v1/driving/{origin[1]:.5f},{origin[0]:.5f};{dest[1]:.5f},{dest[0]:.5f}",
                         params={"overview": "simplified", "geometries": "geojson"}, headers=UA, timeout=15)
        j = r.json()
        if j.get("code") == "Ok":
            return [[c[1], c[0]] for c in j["routes"][0]["geometry"]["coordinates"]]
    except Exception:
        pass
    return [[origin[0], origin[1]], [dest[0], dest[1]]]


# ------------------------------------------------------------------ recommendation
def recommend(lat, lon, commodity, quantity_q=10.0, vehicle="tractor", top=8, variety=None):
    if commodity not in COMMODITIES:
        raise ValueError("unknown commodity")
    cfg = config()
    veh = cfg["vehicles"].get(vehicle) or cfg["vehicles"]["tractor"]
    label, aliases, klass = COMMODITIES[commodity]
    rows, info = get_prices(commodity)
    pool = ThreadPoolExecutor(max_workers=4)
    hist_f = pool.submit(history, commodity)
    if not rows:
        return {"commodity": label, "price_info": info, "mandis": [], "error": "No price data available from any source."}
    latest = max(r["date"] for r in rows)
    rows = [r for r in rows if r["date"] == latest] or rows
    from collections import Counter
    variety_counts = Counter(r["variety"] for r in rows)
    _pm = {}
    for r in rows:
        _pm.setdefault(r["market"], []).append(r["modal_price"])
    state_avg_all = round(statistics.mean(statistics.median(v) for v in _pm.values()))
    if variety and variety != "all":
        rows = [r for r in rows if r["variety"] == variety] or rows
    # aggregate per market (several varieties/grades)
    by_m = {}
    for r in rows:
        by_m.setdefault((r["market"], r["district"]), []).append(r)
    markets = []
    for (m, d), rs in by_m.items():
        modal = statistics.median([x["modal_price"] for x in rs])
        markets.append({"market": m, "district": d, "modal": round(modal), "min": round(min(x["min_price"] or modal for x in rs)),
                        "max": round(max(x["max_price"] or modal for x in rs)), "date": latest,
                        "variety_prices": [{"variety": x["variety"], "grade": x["grade"], "modal": round(x["modal_price"])} for x in rs],
                        "rows": len(rs)})
    # geocode (cached; unknown mandis geocoded at 1 req/s)
    for mk in markets:
        g = geocode(mk["market"], mk["district"])
        mk.update(lat=g["lat"], lon=g["lon"], geo_precision=g["precision"])
    located = [mk for mk in markets if mk["lat"] is not None]
    dists, dist_src = road_distances((lat, lon), [(mk["lat"], mk["lon"]) for mk in located])
    sp = cfg["spoilage"][klass]
    comm = cfg["commission_pct"][klass]
    fee = cfg["market_fee_pct"]
    for mk, (km, mins, how) in zip(located, dists):
        trips = max(1, math.ceil(quantity_q / veh["capacity_q"]))
        transport_total = trips * (veh["fixed"] + veh["rate_per_km"] * km)
        t_q = transport_total / quantity_q
        spoil_pct = min(sp["max_pct"], sp["base_pct"] + sp["per_100km_pct"] * km / 100) if sp["max_pct"] else 0.0
        spoil_q = mk["modal"] * spoil_pct / 100
        charges_q = mk["modal"] * (fee + comm) / 100 + cfg["hamali_per_q"]
        net = mk["modal"] - spoil_q - charges_q - t_q
        mk.update(road_km=round(km, 1), drive_min=round(mins), distance_method=how, trips=trips,
                  transport_total=round(transport_total), transport_per_q=round(t_q),
                  spoilage_pct=round(spoil_pct, 1), spoilage_per_q=round(spoil_q),
                  charges_per_q=round(charges_q), net_per_q=round(net), net_total=round(net * quantity_q))
    ranked = [mk for mk in located if mk["road_km"] <= cfg["max_road_km"]]
    ranked.sort(key=lambda m: m["net_per_q"], reverse=True)
    nearest = min(ranked, key=lambda m: m["road_km"]) if ranked else None
    for i, mk in enumerate(ranked):
        mk["rank"] = i + 1
        mk["gain_vs_nearest_total"] = round((mk["net_per_q"] - nearest["net_per_q"]) * quantity_q) if nearest else None
        mk["is_nearest"] = mk is nearest
    best = ranked[0] if ranked else None
    top_list = ranked[:top]
    if nearest and nearest not in top_list:
        top_list.append(nearest)
    for mk in top_list[:5] + ([nearest] if nearest and nearest not in top_list[:5] else []):
        mk["route"] = pool.submit(route_geometry, (lat, lon), (mk["lat"], mk["lon"]))
    for mk in top_list:
        if "route" in mk and hasattr(mk["route"], "result"):
            mk["route"] = mk["route"].result()
    state_avg = state_avg_all  # all varieties, comparable with the history series
    pts, hsrc = hist_f.result()
    # put today's state average as the newest history point (if newer)
    if not pts or pts[-1]["date"] < latest:
        pts.append({"date": latest, "modal": state_avg, "n": len(markets), "src": "current"})
    trend = trend_and_hint(pts, klass, state_avg)
    trend["sources"] = hsrc
    return {
        "varieties": [{"variety": v, "markets": c} for v, c in variety_counts.most_common()],
        "variety_selected": variety or "all",
        "commodity": label, "commodity_key": commodity, "agmarknet_names": aliases, "class": klass,
        "farm": {"lat": lat, "lon": lon}, "quantity_q": quantity_q,
        "vehicle": {"key": vehicle, **veh},
        "price_info": {**info, "data_date": latest, "markets_reporting": len(markets),
                       "unit": "₹ per quintal (100 kg) as reported to Agmarknet"},
        "assumptions": {"market_fee_pct": fee, "commission_pct": comm, "hamali_per_q": cfg["hamali_per_q"],
                        "spoilage": sp, "vehicle": veh, "distance_source": dist_src,
                        "note": "Edit data/market_config.json. All cost figures are prototype estimates."},
        "state_avg_modal": state_avg,
        "best": best and {k: best[k] for k in ("market", "district", "net_per_q", "net_total", "road_km", "modal")},
        "nearest": nearest and {k: nearest[k] for k in ("market", "district", "net_per_q", "net_total", "road_km", "modal")},
        "extra_gain_best_vs_nearest": (best["net_total"] - nearest["net_total"]) if best and nearest else None,
        "mandis": top_list,
        "all_mandis_count": len(ranked),
        "not_located": [m["market"] for m in markets if m["lat"] is None],
        "trend": trend,
    }


def commodity_list():
    return [{"key": k, "label": v[0], "class": v[2]} for k, v in COMMODITIES.items()]
