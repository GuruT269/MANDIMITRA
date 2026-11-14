"""Sentinel-2 L2A field analytics from Microsoft Planetary Computer (keyless, anonymous SAS signing)."""
import os
for k, v in {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.TIF,.tiff",
    "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
    "GDAL_HTTP_MULTIPLEX": "YES",
    "VSI_CACHE": "TRUE",
    "GDAL_HTTP_MAX_RETRY": "3",
    "GDAL_HTTP_RETRY_DELAY": "1",
}.items():
    os.environ.setdefault(k, v)

import base64
import datetime as dt
import io
import math
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import planetary_computer
import pystac_client
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import transform as warp_transform
from rasterio.windows import from_bounds

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
CLEAR_SCL = {4, 5, 6}  # vegetation, bare soil, water
SCL_NAMES = {0: "no data", 1: "saturated", 2: "dark/shadow", 3: "cloud shadow", 4: "vegetation",
             5: "bare soil", 6: "water", 7: "unclassified", 8: "cloud (medium)", 9: "cloud (high)",
             10: "thin cirrus", 11: "snow"}
WORLDCOVER = {10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland", 50: "Built-up",
              60: "Bare / sparse vegetation", 70: "Snow and ice", 80: "Permanent water bodies",
              90: "Herbaceous wetland", 95: "Mangroves", 100: "Moss and lichen"}

_POOL = ThreadPoolExecutor(max_workers=48)


def client():
    return pystac_client.Client.open(STAC_URL, modifier=planetary_computer.sign_inplace)


def _offset(item):
    item = _L(item)[0]
    try:
        return 1000 if float(item.properties.get("s2:processing_baseline", "0")) >= 4.0 else 0
    except ValueError:
        return 0


class Field:
    """Circular field buffer around lat/lon, gridded at 10 m in the scene's UTM CRS."""

    def __init__(self, lat, lon, radius):
        self.lat, self.lon, self.radius = lat, lon, radius
        self.n = max(3, int(math.ceil(2 * radius / 10.0)))
        c = (np.arange(self.n) + 0.5) * (2 * radius / self.n) - radius
        xx, yy = np.meshgrid(c, -c)
        self.mask = (xx ** 2 + yy ** 2) <= radius ** 2

    def bounds(self, crs, r=None):
        r = r or self.radius
        xs, ys = warp_transform("EPSG:4326", crs, [self.lon], [self.lat])
        return (xs[0] - r, ys[0] - r, xs[0] + r, ys[0] + r)


def read_band(href, field, shape=None, r=None, indexes=1, resampling=Resampling.nearest):
    shape = shape or (field.n, field.n)
    with rasterio.open(href) as ds:
        b = field.bounds(ds.crs, r)
        w = from_bounds(*b, transform=ds.transform)
        if isinstance(indexes, list):
            shape = (len(indexes),) + tuple(shape)
        return ds.read(indexes, window=w, out_shape=shape, boundless=True, fill_value=0,
                       resampling=resampling)


def _L(x):
    return x if isinstance(x, list) else [x]


def read_m(items, asset, field, shape=None, r=None, indexes=1):
    """Read from the first item; fill no-data (0) pixels from other tiles of the same pass (tile-edge mosaic)."""
    out = None
    for it in _L(items):
        a = read_band(it.assets[asset].href, field, shape, r, indexes)
        if out is None:
            out = a
        else:
            hole = (out == 0) if out.ndim == 2 else (out == 0).all(axis=0)
            if out.ndim == 2:
                out[hole] = a[hole]
            else:
                out[:, hole] = a[:, hole]
        hole = (out == 0) if out.ndim == 2 else (out == 0).all(axis=0)
        if not hole.any():
            break
    return out


def _refl(dn, off):
    dn = dn.astype("float32")
    out = (dn - off) / 10000.0
    out[dn == 0] = np.nan
    return out


def _nd(a, b):
    with np.errstate(divide="ignore", invalid="ignore"):
        return (a - b) / (a + b)


def _stats(arr):
    v = arr[np.isfinite(arr)]
    if v.size == 0:
        return None
    return {"mean": round(float(v.mean()), 3), "median": round(float(np.median(v)), 3),
            "min": round(float(v.min()), 3), "max": round(float(v.max()), 3),
            "std": round(float(v.std()), 3), "p10": round(float(np.percentile(v, 10)), 3),
            "p90": round(float(np.percentile(v, 90)), 3)}


def scl_clear(item, field):
    scl = read_m(item, "SCL", field)
    inside = scl[field.mask]
    valid = inside[inside > 0]
    if valid.size == 0:
        return 0.0, scl
    return float(np.isin(valid, list(CLEAR_SCL)).mean()), scl


def scene_ndvi(items, field, min_clear=0.6):
    """Quick NDVI (clear pixels only) for time series."""
    item = _L(items)[0]
    try:
        frac, scl = scl_clear(items, field)
        if frac < min_clear:
            return {"date": item.datetime.date().isoformat(), "clear": round(frac, 2), "ndvi": None}
        off = _offset(items)
        red = _refl(read_m(items, "B04", field), off)
        nir = _refl(read_m(items, "B08", field), off)
        ndvi = _nd(nir, red)
        m = field.mask & np.isin(scl, list(CLEAR_SCL)) & np.isfinite(ndvi)
        val = float(np.nanmean(ndvi[m])) if m.any() else None
        return {"date": item.datetime.date().isoformat(), "clear": round(frac, 2),
                "ndvi": None if val is None else round(val, 3)}
    except Exception as e:  # network hiccup etc.
        return {"date": item.datetime.date().isoformat(), "clear": None, "ndvi": None, "error": str(e)[:120]}


def _png(rgb_uint8, field, scale_px=8, ctx_r=None):
    from PIL import Image, ImageDraw
    img = Image.fromarray(rgb_uint8)
    W = img.width * scale_px
    img = img.resize((W, W), Image.NEAREST)
    d = ImageDraw.Draw(img)
    # field circle
    rr = field.radius / ctx_r * (W / 2)
    c = W / 2
    d.ellipse([c - rr, c - rr, c + rr, c + rr], outline=(255, 255, 255), width=3)
    d.ellipse([c - 4, c - 4, c + 4, c + 4], fill=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def latest_scene_analysis(item, field):
    off = _offset(item)
    sh = (field.n, field.n)
    futs = {b: _POOL.submit(read_m, item, b, field, sh) for b in ["B03", "B04", "B05", "B08", "B11", "SCL"]}
    raw = {b: f.result() for b, f in futs.items()}
    scl = raw.pop("SCL")
    r = {b: _refl(v, off) for b, v in raw.items()}
    clear = field.mask & np.isin(scl, list(CLEAR_SCL))
    idx = {
        "NDVI": _nd(r["B08"], r["B04"]),
        "NDWI": _nd(r["B03"], r["B08"]),   # McFeeters: open water / flooding
        "NDMI": _nd(r["B08"], r["B11"]),   # Gao NDWI: canopy water content
        "NDRE": _nd(r["B08"], r["B05"]),   # red-edge: chlorophyll / nitrogen status
    }
    out = {k: _stats(np.where(clear, v, np.nan)) for k, v in idx.items()}
    inside = scl[field.mask]
    cls = {SCL_NAMES.get(int(k), str(k)): round(float((inside == k).mean()), 3) for k in np.unique(inside)}
    # health zones from NDVI
    nd = idx["NDVI"][clear]
    nd = nd[np.isfinite(nd)]
    zones = None
    if nd.size:
        zones = {"bare/stressed (<0.2)": round(float((nd < 0.2).mean()), 3),
                 "low (0.2-0.4)": round(float(((nd >= 0.2) & (nd < 0.4)).mean()), 3),
                 "moderate (0.4-0.6)": round(float(((nd >= 0.4) & (nd < 0.6)).mean()), 3),
                 "healthy (>=0.6)": round(float((nd >= 0.6).mean()), 3)}
    return {"indices": out, "scl_classes": cls, "ndvi_zones": zones,
            "clear_pixels": int(clear.sum()), "field_pixels": int(field.mask.sum())}


IST = dt.timezone(dt.timedelta(hours=5, minutes=30), "IST")
PC_ITEM = "https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-2-l2a/items/"
PC_PREVIEW = ("https://planetarycomputer.microsoft.com/api/data/v1/item/preview.png?collection=sentinel-2-l2a"
              "&item={}&assets=visual&asset_bidx=visual%7C1%2C2%2C3&nodata=0&format=png")


def scene_meta(item, field, clear=None):
    tiles = [i.properties.get("s2:mgrs_tile") for i in _L(item)]
    item = _L(item)[0]
    t = item.datetime.astimezone(IST)
    plat = item.properties.get("platform", "")
    short = plat.replace("Sentinel-", "S").replace("sentinel-", "S").upper()
    return {
        "item_id": item.id,
        "date": t.date().isoformat(),
        "datetime_ist": t.strftime("%d %b %Y, %H:%M IST"),
        "datetime_utc": item.datetime.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "satellite": plat, "satellite_short": short,
        "tile": "+".join(t for t in tiles if t),
        "relative_orbit": item.properties.get("sat:relative_orbit"),
        "tile_cloud_pct": round(item.properties.get("eo:cloud_cover", 0), 1),
        "field_clear_fraction": None if clear is None else round(clear, 2),
        "days_ago": (dt.datetime.now(IST).date() - t.date()).days,
        "stac_item_url": PC_ITEM + item.id,
        "scene_preview_url": PC_PREVIEW.format(item.id),
        "explorer_url": (f"https://planetarycomputer.microsoft.com/explore?c={field.lon:.5f},{field.lat:.5f}&z=15&v=2"
                         "&d=sentinel-2-l2a&s=false%3A%3A100%3A%3Atrue&sr=desc&m=Most+recent+%28low+cloud%29&r=Natural+color"),
    }


def _stretch(rgb):
    """Per-band 2-98 percentile contrast stretch + mild gamma -> uint8."""
    out = np.zeros(rgb.shape, dtype="uint8")
    for b in range(3):
        band = rgb[..., b]
        v = band[np.isfinite(band)]
        if v.size == 0:
            continue
        lo, hi = np.percentile(v, 2), np.percentile(v, 98)
        x = np.clip((np.nan_to_num(band, nan=lo) - lo) / max(hi - lo, 1e-6), 0, 1) ** 0.85
        out[..., b] = (x * 255).astype("uint8")
    return out


def rgb_image(item, field, ctx_r, target_px=480, with_ndvi=False):
    """True colour (B4,B3,B2 reflectance, contrast stretched) [+ NDVI colour map] around the field."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib as mpl
    n = int(math.ceil(2 * ctx_r / 10))
    off = _offset(item)
    bands = ["B04", "B03", "B02"] + (["B08"] if with_ndvi else [])
    futs = {b: _POOL.submit(read_m, item, b, field, (n, n), ctx_r) for b in bands}
    r = {b: _refl(f.result(), off) for b, f in futs.items()}
    tc = _stretch(np.dstack([r["B04"], r["B03"], r["B02"]]))
    scale = max(1, int(round(target_px / n)))
    out = {"true_color": _png(tc, field, scale, ctx_r)}
    if with_ndvi:
        ndvi = _nd(r["B08"], r["B04"])
        norm = np.clip((np.nan_to_num(ndvi, nan=0) + 0.1) / 1.0, 0, 1)
        col = (mpl.colormaps["RdYlGn"](norm)[..., :3] * 255).astype("uint8")
        out["ndvi"] = _png(col, field, scale, ctx_r)
    return out


def thumbnails(item, field, clear=None):
    ctx_r = max(3 * field.radius, 400.0)
    out = rgb_image(item, field, ctx_r, 480, with_ndvi=True)
    out.update(context_radius_m=ctx_r, bands="True colour = B4/B3/B2 (10 m), 2-98% stretch",
               ndvi_color_scale="RdYlGn, -0.1 (red) to 0.9 (green)", scene=scene_meta(item, field, clear))
    return out


def gallery_entry(item, field, clear):
    try:
        ctx_r = max(2.5 * field.radius, 300.0)
        img = rgb_image(item, field, ctx_r, 200)["true_color"]
        return {**scene_meta(item, field, clear), "true_color": img}
    except Exception as e:
        return {**scene_meta(item, field, clear), "error": str(e)[:150]}


def worldcover(cl, field):
    try:
        items = list(cl.search(collections=["esa-worldcover"],
                               intersects={"type": "Point", "coordinates": [field.lon, field.lat]}).items())
        if not items:
            return None
        items.sort(key=lambda i: i.properties.get("esa_worldcover:product_version", i.id), reverse=True)
        it = items[0]
        href = it.assets["map"].href
        with rasterio.open(href) as ds:
            r = field.radius
            dlat = r / 111320.0
            dlon = r / (111320.0 * math.cos(math.radians(field.lat)))
            w = from_bounds(field.lon - dlon, field.lat - dlat, field.lon + dlon, field.lat + dlat, ds.transform)
            arr = ds.read(1, window=w, boundless=True, fill_value=0)
            row, col = ds.index(field.lon, field.lat)
            pt = int(ds.read(1, window=((row, row + 1), (col, col + 1)))[0, 0])
        vals, cnt = np.unique(arr[arr > 0], return_counts=True)
        dist = {WORLDCOVER.get(int(v), str(v)): round(float(c / cnt.sum()), 3) for v, c in zip(vals, cnt)}
        return {"product": it.id, "point_class_code": pt, "point_class": WORLDCOVER.get(pt, "unknown"),
                "buffer_distribution": dist, "note": "ESA WorldCover 10 m (map year 2021)"}
    except Exception as e:
        return {"error": str(e)[:200]}


def search(lat, lon, months=12):
    """One STAC search per location (memoised by caller): groups of items per acquisition date."""
    cl = client()
    today = dt.date.today()
    start = (today.replace(day=1) - dt.timedelta(days=31 * (months - 1))).replace(day=1)
    items = list(cl.search(collections=["sentinel-2-l2a"],
                           intersects={"type": "Point", "coordinates": [lon, lat]},
                           datetime=f"{start.isoformat()}/{today.isoformat()}",
                           limit=500).items())
    groups = defaultdict(list)
    for it in items:
        groups[it.datetime.date()].append(it)
    for g in groups.values():
        g.sort(key=lambda i: i.properties["eo:cloud_cover"])
    by_date = {d: g[0] for d, g in groups.items()}
    dates = sorted(by_date, reverse=True)
    acquisitions = [{"date": d.isoformat(), "platform": by_date[d].properties.get("platform"),
                     "relative_orbit": by_date[d].properties.get("sat:relative_orbit"),
                     "tile": by_date[d].properties.get("s2:mgrs_tile"),
                     "tile_cloud_pct": round(by_date[d].properties["eo:cloud_cover"], 1)} for d in dates]
    return {"groups": groups, "by_date": by_date, "dates": dates, "start": start, "today": today,
            "acquisitions": acquisitions, "client": cl}


def field_info(field):
    return {"lat": field.lat, "lon": field.lon, "radius_m": field.radius,
            "area_ha": round(math.pi * field.radius ** 2 / 1e4, 3),
            "area_acres": round(math.pi * field.radius ** 2 / 4046.86, 2), "pixels_10m": int(field.mask.sum())}


def latest(S, lat, lon, radius=100.0, n_gallery=6):
    field = Field(lat, lon, radius)
    groups, by_date, dates = S["groups"], S["by_date"], S["dates"]
    wc_fut = _POOL.submit(worldcover, S["client"], field)
    clear_scenes = []
    cands = [by_date[d] for d in dates if by_date[d].properties["eo:cloud_cover"] < 80][:30]
    for i in range(0, len(cands), 10):
        res = list(_POOL.map(lambda it: (groups[it.datetime.date()], scl_clear(groups[it.datetime.date()], field)[0]),
                             cands[i:i + 10]))
        clear_scenes += [(it, fr) for it, fr in res if fr >= 0.8]
        if len(clear_scenes) >= n_gallery:
            break
    clear_scenes = clear_scenes[:n_gallery]
    lat_s, thumb_fut = None, None
    if clear_scenes:
        latest_item, frac = clear_scenes[0]
        thumb_fut = _POOL.submit(thumbnails, latest_item, field, frac)
        gallery_futs = [_POOL.submit(gallery_entry, it, field, fr) for it, fr in clear_scenes]
        lat_s = scene_meta(latest_item, field, frac)
        lat_s.update(latest_scene_analysis(latest_item, field))
    else:
        gallery_futs = []
    thumbs = None
    if thumb_fut:
        try:
            thumbs = thumb_fut.result()
        except Exception as e:
            thumbs = {"error": str(e)[:200]}
    return {"source": "Sentinel-2 L2A (ESA Copernicus) via Microsoft Planetary Computer STAC",
            "field": field_info(field), "latest_scene": lat_s, "thumbnails": thumbs,
            "recent_clear_scenes": [f.result() for f in gallery_futs],
            "acquisitions": S["acquisitions"], "worldcover": wc_fut.result()}


def series(S, lat, lon, radius=100.0, per_month=2):
    field = Field(lat, lon, radius)
    groups, by_date, dates, start, today = S["groups"], S["by_date"], S["dates"], S["start"], S["today"]
    pm = defaultdict(list)
    for d in dates:
        if by_date[d].properties["eo:cloud_cover"] < 85:
            pm[d.strftime("%Y-%m")].append(groups[d])
    picks = []
    for m, lst in pm.items():
        lst.sort(key=lambda g: g[0].properties["eo:cloud_cover"])
        picks += lst[:per_month]
    scenes = list(_POOL.map(lambda it: scene_ndvi(it, field), picks))
    scenes.sort(key=lambda s: s["date"])
    mvals = defaultdict(list)
    for s in scenes:
        if s["ndvi"] is not None:
            mvals[s["date"][:7]].append(s["ndvi"])
    monthly = []
    y, mo = start.year, start.month
    while (y, mo) <= (today.year, today.month):
        key = f"{y:04d}-{mo:02d}"
        v = mvals.get(key)
        monthly.append({"month": key, "ndvi": round(float(np.median(v)), 3) if v else None, "n_scenes": len(v) if v else 0})
        mo += 1
        if mo > 12:
            y, mo = y + 1, 1
    return {"ndvi_monthly": monthly, "ndvi_scenes": [s for s in scenes if s["ndvi"] is not None],
            "scenes_checked": len(scenes)}


def analyze(lat, lon, radius=100.0, months=12):
    """Back-compat: everything in one call."""
    S = search(lat, lon, months)
    fl = _POOL.submit(latest, S, lat, lon, radius)
    se = series(S, lat, lon, radius, per_month=3)
    return {**fl.result(), **se}


def other_missions(lat, lon, days=60):
    """Actual recent Landsat 8/9 and Sentinel-1 acquisition dates over the point."""
    cl = client()
    today = dt.date.today()
    rng = f"{(today - dt.timedelta(days=days)).isoformat()}/{today.isoformat()}"
    out = {}
    for name, coll in [("landsat", "landsat-c2-l2"), ("sentinel1", "sentinel-1-grd")]:
        try:
            its = list(cl.search(collections=[coll], intersects={"type": "Point", "coordinates": [lon, lat]},
                                 datetime=rng, limit=200).items())
            seen = {}
            for it in its:
                d = it.datetime.date().isoformat()
                seen.setdefault(d, it.properties.get("platform"))
            out[name] = [{"date": d, "platform": p} for d, p in sorted(seen.items(), reverse=True)]
        except Exception as e:
            out[name] = {"error": str(e)[:200]}
    return out
