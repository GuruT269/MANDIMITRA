"""MandiMitra API: progressive, memoised section endpoints + passport + advisor + market."""
import datetime as dt
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import advisor, crop, market, passport, revisit, satellite, weather
from .memo import memo, peek

app = FastAPI(title="MandiMitra", version="0.3.0")
ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")
POOL = ThreadPoolExecutor(max_workers=16)
PRESETS = [("Mandya", 12.50, 76.85), ("Tumakuru", 13.30, 77.05), ("Davanagere", 14.42, 75.95), ("Raichur", 16.18, 77.30)]
H = 3600


def K(lat, lon):
    return (round(lat, 4), round(lon, 4))


def in_ka(lat, lon):
    return 11.5 <= lat <= 18.5 and 74.0 <= lon <= 78.6


# ---------------------------------------------------------------- memoised building blocks
def sat_search(lat, lon):
    return memo(("search",) + K(lat, lon), lambda: satellite.search(lat, lon), ttl=40 * 60)[0]


def sat_latest(lat, lon, r):
    return memo(("latest",) + K(lat, lon) + (round(r),), lambda: satellite.latest(sat_search(lat, lon), lat, lon, r), ttl=6 * H)


def sat_series(lat, lon, r):
    def run():
        se = satellite.series(sat_search(lat, lon), lat, lon, r)
        lat_res = sat_latest(lat, lon, r)[0]
        ndwi = (((lat_res.get("latest_scene") or {}).get("indices") or {}).get("NDWI") or {}).get("mean")
        se["crop_estimate"] = crop.classify(se["ndvi_monthly"], lat_res.get("worldcover"), ndwi, in_ka(lat, lon))
        return se
    return memo(("series",) + K(lat, lon) + (round(r),), run, ttl=6 * H)


def wx(lat, lon):
    def run():
        w = weather.open_meteo(lat, lon)
        w["alerts"] = weather.alerts(w)
        w["spray"] = weather.spray_windows(w)
        return w
    return memo(("wx",) + K(lat, lon), run, ttl=30 * 60)


def climate(lat, lon):
    return memo(("climate",) + K(lat, lon), lambda: weather.nasa_power(lat, lon), ttl=12 * H, err_ttl=300)


def soil(lat, lon):
    return memo(("soil",) + K(lat, lon), lambda: weather.soilgrids(lat, lon), ttl=24 * H, err_ttl=600)


def missions(lat, lon):
    return memo(("missions",) + K(lat, lon), lambda: satellite.other_missions(lat, lon), ttl=6 * H)


def auto_crop(lat, lon, r, crop_key):
    if crop_key and crop_key != "auto":
        return crop_key
    se = peek(("series",) + K(lat, lon) + (round(r),))
    cands = ((se or {}).get("crop_estimate") or {}).get("candidates", "").lower()
    lab = ((se or {}).get("crop_estimate") or {}).get("label", "").lower()
    for k in ["sugarcane", "paddy", "ragi", "maize", "tomato", "coconut", "arecanut", "cotton", "groundnut"]:
        if k in lab or k in cands.split(";")[0]:
            return k
    return "paddy" if "crop" in lab else "general"


def summary(lat, lon, r, crop_key="auto"):
    fl = POOL.submit(sat_latest, lat, lon, r)
    fw = POOL.submit(wx, lat, lon)
    latest_res, w = fl.result()[0], fw.result()[0]
    ck = auto_crop(lat, lon, r, crop_key)
    lt = latest_res.get("latest_scene") or {}
    ndvi = ((lt.get("indices") or {}).get("NDVI") or {}).get("mean")
    irr = weather.irrigation(w, ndvi, latest_res["field"]["area_ha"])
    se = peek(("series",) + K(lat, lon) + (round(r),))
    lab = ((se or {}).get("crop_estimate") or {}).get("label", "")
    wc = (latest_res.get("worldcover") or {}).get("point_class", "")
    if lab.startswith(("Built-up", "Water body")) or wc in ("Built-up", "Permanent water bodies"):
        irr = {**irr, "action": "N/A", "advice": "Pin is on built-up land or water. Move it onto a field."}
    pests = weather.pest_risk(w, ck)
    score = advisor.health_score(lt, irr, w["alerts"], pests)
    soil_p = peek(("soil",) + K(lat, lon))
    crop_label = market.COMMODITIES.get(ck, (ck,))[0] if ck in market.COMMODITIES else ck.replace("general", "crop")
    card = advisor.action_card(score, irr, w["spray"], pests, w["alerts"], soil_p, lt, crop_label)
    llm = None
    if os.environ.get("GROQ_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        llm = advisor.llm_polish(card, {"score": score["score"], "irrigation": irr["advice"], "spray": w["spray"]["windows"][:2],
                                        "pests": pests["risks"], "alerts": w["alerts"][:3], "crop": crop_label})
    return {"crop": ck, "crop_label": crop_label, "score": score, "irrigation": irr, "spray": w["spray"], "pests": pests,
            "alerts": w["alerts"], "card": card, "llm": llm,
            "scene_date": lt.get("date"), "weather_time": w["current"]["time"]}


def timed(fn, *a):
    t0 = time.time()
    res, took, cached = fn(*a)
    return JSONResponse({**res, "_meta": {"compute_s": took, "cached": cached, "served_s": round(time.time() - t0, 2)}},
                        headers={"Cache-Control": "no-store"})


# ---------------------------------------------------------------- pages
@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/passport/{fid}")
def passport_page(fid: str):
    return FileResponse(STATIC / "passport.html")


# ---------------------------------------------------------------- field section APIs (progressive)
LatQ = Query(..., ge=-60, le=75)
LonQ = Query(..., ge=-180, le=180)
RadQ = Query(100, ge=20, le=1000)


@app.get("/api/weather")
def api_weather(lat: float = LatQ, lon: float = LonQ):
    return timed(wx, lat, lon)


@app.get("/api/sat/latest")
def api_sat_latest(lat: float = LatQ, lon: float = LonQ, radius: float = RadQ):
    return timed(sat_latest, lat, lon, radius)


@app.get("/api/sat/series")
def api_sat_series(lat: float = LatQ, lon: float = LonQ, radius: float = RadQ):
    return timed(sat_series, lat, lon, radius)


@app.get("/api/climate")
def api_climate(lat: float = LatQ, lon: float = LonQ):
    try:
        return timed(climate, lat, lon)
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {str(e)[:150]}"})


@app.get("/api/soil")
def api_soil(lat: float = LatQ, lon: float = LonQ):
    try:
        return timed(soil, lat, lon)
    except Exception as e:
        return JSONResponse({"error": f"SoilGrids unavailable ({type(e).__name__})"})


@app.get("/api/revisit")
def api_revisit(lat: float = LatQ, lon: float = LonQ):
    def run():
        S = sat_search(lat, lon)
        return revisit.build(S["acquisitions"], missions(lat, lon)[0]), 0, False
    t0 = time.time()
    res = run()[0]
    return JSONResponse({**res, "_meta": {"served_s": round(time.time() - t0, 2)}})


@app.get("/api/summary")
def api_summary(lat: float = LatQ, lon: float = LonQ, radius: float = RadQ, crop_key: str = Query("auto", alias="crop")):
    t0 = time.time()
    res = summary(lat, lon, radius, crop_key)
    return JSONResponse({**res, "_meta": {"served_s": round(time.time() - t0, 2)}})


@app.get("/api/schemes")
def api_schemes(land_acres: float = 2.0, owner: bool = True, income_tax: bool = False, govt_employee: bool = False,
                irrigation: str = "borewell", grid_pump: bool = True, organic_interest: bool = False, crop: str = "paddy"):
    return advisor.schemes(land_acres, owner, income_tax, govt_employee, irrigation, grid_pump, organic_interest, crop)


# ---------------------------------------------------------------- back-compat one-shot endpoint
@app.get("/analyze")
def analyze(lat: float = LatQ, lon: float = LonQ, radius: float = RadQ):
    t0 = time.time()
    fs = {k: POOL.submit(f, lat, lon, *([radius] if k in ("latest", "series") else []))
          for k, f in [("latest", sat_latest), ("series", sat_series), ("wx", wx)]}
    out = {k: f.result()[0] for k, f in fs.items()}
    s = summary(lat, lon, radius)
    out["summary"] = s
    out["elapsed_s"] = round(time.time() - t0, 1)
    for k in ("latest",):
        th = out[k].get("thumbnails") or {}
        out[k] = {**out[k]}
    return JSONResponse(out)


# ---------------------------------------------------------------- passport
def base_url(request: Request):
    return (os.environ.get("PUBLIC_BASE_URL") or str(request.base_url)).rstrip("/")


@app.get("/api/farms")
def api_farms():
    return {"farms": passport.list_farms(), "input_types": passport.INPUT_TYPES}


@app.post("/api/farms")
async def api_create_farm(request: Request):
    j = await request.json()
    try:
        lat, lon = float(j["lat"]), float(j["lon"])
    except Exception:
        raise HTTPException(400, "lat/lon required")
    fid = passport.create_farm(j.get("farmer") or "Farmer", j.get("village") or "", j.get("crop") or "paddy",
                               lat, lon, float(j.get("radius") or 100), j.get("area_acres"))
    POOL.submit(sat_latest, lat, lon, float(j.get("radius") or 100))
    POOL.submit(sat_series, lat, lon, float(j.get("radius") or 100))
    return {"id": fid, "url": f"{base_url(request)}/passport/{fid}"}


@app.post("/api/farms/{fid}/logs")
async def api_add_log(fid: str, date: str = Form(...), input_type: str = Form(...), product: str = Form(...),
                      quantity: str = Form(""), notes: str = Form(""), bill: UploadFile | None = File(None)):
    if not passport.get_farm(fid):
        raise HTTPException(404, "farm not found")
    if input_type not in passport.INPUT_TYPES:
        raise HTTPException(400, "bad input_type")
    data = await bill.read() if bill and bill.filename else None
    if data and len(data) > 5_000_000:
        raise HTTPException(400, "bill photo too large (max 5 MB)")
    passport.add_log(fid, date, input_type, product[:80], quantity[:40], notes[:200], data, bill.filename if data else None)
    return {"ok": True}


@app.get("/api/passport/{fid}")
def api_passport(fid: str, request: Request):
    f = passport.get_farm(fid)
    if not f:
        raise HTTPException(404, "farm not found")
    lat, lon, r = f["lat"], f["lon"], f["radius"]
    fl, fs, fsum = POOL.submit(sat_latest, lat, lon, r), POOL.submit(sat_series, lat, lon, r), POOL.submit(summary, lat, lon, r, f["crop"])
    try:
        soil_p = soil(lat, lon)[0]
    except Exception:
        soil_p = None
    L, S, SUM = fl.result()[0], fs.result()[0], fsum.result()
    return {"farm": {k: f[k] for k in ("id", "farmer", "village", "crop", "lat", "lon", "radius", "area_acres", "created", "demo")},
            "url": f"{base_url(request)}/passport/{fid}", "qr": f"/api/qr/{fid}.png",
            "satellite": {"scene": (L.get("thumbnails") or {}).get("scene"), "true_color": (L.get("thumbnails") or {}).get("true_color"),
                          "ndvi_img": (L.get("thumbnails") or {}).get("ndvi"), "indices": (L.get("latest_scene") or {}).get("indices"),
                          "zones": (L.get("latest_scene") or {}).get("ndvi_zones"),
                          "gallery": [{k: g.get(k) for k in ("date", "satellite_short", "true_color", "scene_preview_url")} for g in L.get("recent_clear_scenes", [])],
                          "worldcover": L.get("worldcover")},
            "ndvi_monthly": S["ndvi_monthly"], "crop_estimate": S["crop_estimate"],
            "health": SUM["score"], "pests": SUM["pests"]["risks"],
            "organic": passport.organic_score(f["logs"]), "logs": f["logs"], "soil": soil_p,
            "generated": dt.datetime.now().strftime("%d %b %Y %H:%M IST")}


@app.get("/api/qr/{fid}.png")
def api_qr(fid: str, request: Request):
    return Response(passport.qr_png(f"{base_url(request)}/passport/{fid}"), media_type="image/png")


@app.get("/uploads/{name}")
def uploads(name: str):
    p = passport.UPLOADS / Path(name).name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


# ---------------------------------------------------------------- market (existing)
@app.get("/commodities")
def commodities():
    cfg = market.config()
    return {"commodities": market.commodity_list(), "vehicles": [{"key": k, **v} for k, v in cfg["vehicles"].items()]}


@app.get("/market")
def market_reco(lat: float = LatQ, lon: float = LonQ, commodity: str = "tomato", qty: float = Query(10, gt=0, le=5000),
                vehicle: str = "tractor", variety: str = "all"):
    t0 = time.time()
    try:
        out, took, cached = memo(("market", round(lat, 3), round(lon, 3), commodity, qty, vehicle, variety),
                                 lambda: market.recommend(lat, lon, commodity, qty, vehicle, variety=variety), ttl=1800)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return JSONResponse({**out, "elapsed_s": round(time.time() - t0, 1), "_meta": {"compute_s": took, "cached": cached}})


COORD_PATTERNS = [r"@(-?\d+\.\d+),(-?\d+\.\d+)", r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)",
                  r"[?&](?:q|ll|query|destination|center)=(-?\d+\.\d+)(?:,|%2C)\s*(-?\d+\.\d+)",
                  r"(-?\d{1,2}\.\d+)\s*[, ]\s*(-?\d{1,3}\.\d+)"]


def parse_coords(text):
    for pat in COORD_PATTERNS:
        m = re.search(pat, text)
        if m:
            return float(m.group(1)), float(m.group(2))
    return None


@app.get("/resolve")
def resolve(q: str):
    c = parse_coords(q)
    if c is None and re.match(r"https?://", q):
        host = urlparse(q).hostname or ""
        if not (host.endswith("goo.gl") or "google." in host):
            raise HTTPException(400, "Only Google Maps links are supported")
        try:
            r = requests.get(q, allow_redirects=True, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            c = parse_coords(unquote(r.url)) or parse_coords(unquote(r.text[:200000]))
        except requests.RequestException as e:
            raise HTTPException(502, f"Could not expand link: {e}")
    if c is None:
        raise HTTPException(400, "No coordinates found. Paste 'lat, lon' or a Google Maps link.")
    return {"lat": c[0], "lon": c[1]}


@app.get("/health")
def health():
    return {"ok": True, "warm": WARM}


# ---------------------------------------------------------------- pre-warm presets on startup
WARM = {"done": False, "log": []}


def prewarm():
    passport.seed_demo()
    for name, la, lo in PRESETS:
        t0 = time.time()
        futs = [POOL.submit(f, la, lo, 100) for f in (sat_latest, sat_series)] + \
               [POOL.submit(f, la, lo) for f in (wx, climate, soil, missions)]
        for f in futs:
            try:
                f.result()
            except Exception:
                pass
        try:
            summary(la, lo, 100)
        except Exception:
            pass
        WARM["log"].append(f"{name}: {time.time() - t0:.1f}s")
    for c in ("tomato", "paddy"):
        try:
            memo(("market", 12.5, 76.85, c, 20.0, "tractor", "all"),
                 lambda c=c: market.recommend(12.50, 76.85, c, 20.0, "tractor", variety="all"), ttl=1800)
        except Exception:
            pass
    WARM["done"] = True


@app.on_event("startup")
def _startup():
    passport.init()
    if os.environ.get("NO_PREWARM") != "1":
        threading.Thread(target=prewarm, daemon=True).start()
