"""Rule-based crop / land-cover estimate from a 12-month NDVI profile.

HEURISTIC ONLY: no trained model, no ground truth. Indian cropping seasons:
  Kharif (monsoon): sown Jun-Jul, peak greenness Aug-Oct, harvest Oct-Nov
  Rabi (winter):    sown Oct-Dec, peak Dec-Feb, harvest Feb-Apr
  Zaid (summer):    Mar-Jun (irrigated short crops)
"""
import numpy as np

KARNATAKA_HINTS = {
    "kharif": "paddy (irrigated), ragi, maize, tur, groundnut",
    "rabi": "paddy (2nd crop in canal areas), ragi, horse gram, pulses, vegetables",
    "summer": "summer paddy (canal areas, planted Dec-Jan, harvested Apr-May), vegetables, pulses, fodder",
    "long": "sugarcane (10-14 month crop, very common in Mandya/Cauvery command)",
    "perennial": "coconut, areca, mango, mulberry (sericulture), banana",
}


def _season(month):
    if month in (7, 8, 9, 10, 11):
        return "kharif"
    if month in (12, 1, 2, 3):
        return "rabi"
    return "summer"


def _interp(vals):
    a = np.array([np.nan if v is None else v for v in vals], dtype=float)
    idx = np.arange(len(a))
    ok = np.isfinite(a)
    if ok.sum() < 2:
        return a
    return np.interp(idx, idx[ok], a[ok])


def classify(monthly, worldcover=None, latest_ndwi=None, in_karnataka=True):
    monthly = monthly[-12:]  # exactly one year so the same season is not counted twice
    months = [m["month"] for m in monthly]
    raw = [m["ndvi"] for m in monthly]
    n_valid = sum(v is not None for v in raw)
    wc = (worldcover or {}).get("point_class_code") if isinstance(worldcover, dict) else None
    res = {"method": "rule-based NDVI phenology heuristic (not a trained model)",
           "valid_months": n_valid, "total_months": len(raw), "peaks": []}

    def done(label, conf, why, candidates=None):
        conf = max(0.1, min(conf, 0.75))  # never claim high certainty
        res.update(label=label, confidence=round(conf, 2),
                   confidence_level="medium" if conf >= 0.55 else "low",
                   reasoning=why, candidates=candidates or "")
        return res

    if wc == 80 or (latest_ndwi is not None and latest_ndwi > 0.1):
        return done("Water body", 0.7, "WorldCover marks permanent water and/or NDWI > 0.1 (open water).")
    if n_valid < 4:
        return done("Insufficient data", 0.1, f"Only {n_valid} cloud-free months; cannot read the season pattern.")

    s = _interp(raw)
    mx, mn, mean = float(np.nanmax(s)), float(np.nanmin(s)), float(np.nanmean(s))
    amp = mx - mn
    res.update(ndvi_max=round(mx, 3), ndvi_min=round(mn, 3), ndvi_mean=round(mean, 3), amplitude=round(amp, 3))
    base = 0.35 + 0.03 * n_valid

    if mx < 0.25:
        if wc == 50:
            return done("Built-up / settlement", base, "NDVI stays below 0.25 all year and WorldCover says built-up.")
        return done("Fallow / barren land", base - 0.05,
                    "NDVI stays below 0.25 all year: no crop cycle detected (fallow, bare soil, rock or built-up).")
    if wc == 50 and mx < 0.5:
        return done("Built-up / settlement (with some vegetation)", base - 0.05,
                    "WorldCover marks the point as built-up and NDVI never shows a strong crop peak; "
                    "vegetation signal is likely trees/gardens between buildings.")

    # peaks: local maxima with value >= 0.45 and >= 0.12 above the lowest point on either side
    peaks = []
    L = len(s)
    for i in range(L):
        left = s[max(0, i - 1)] if i > 0 else -1
        right = s[min(L - 1, i + 1)] if i < L - 1 else -1
        if s[i] >= 0.45 and s[i] >= left and s[i] >= right:
            lmin, rmin = np.min(s[:i + 1]), np.min(s[i:])
            if i >= L - 2:   # peak at the end of the record: the decline hasn't happened yet
                rmin = lmin
            if i <= 1:
                lmin = rmin
            prom = s[i] - max(lmin, rmin)
            if prom >= 0.12 or (i in (0, L - 1) and s[i] - mn >= 0.15):
                mon = int(months[i][5:7])
                if not peaks or i - peaks[-1]["i"] > 2:
                    peaks.append({"i": i, "month": months[i], "ndvi": round(float(s[i]), 3), "season": _season(mon)})
                elif s[i] > peaks[-1]["ndvi"]:
                    peaks[-1] = {"i": i, "month": months[i], "ndvi": round(float(s[i]), 3), "season": _season(mon)}
    # a peak at the very first month is usually the tail of the cycle that also shows at the end
    if len(peaks) >= 2 and peaks[0]["i"] == 0 and peaks[-1]["i"] >= L - 2 and peaks[0]["season"] == peaks[-1]["season"]:
        peaks = peaks[1:]
    elif peaks and peaks[0]["i"] == 0 and s[0] > s[1] and len(peaks) >= 2:
        peaks = peaks[1:]
    res["peaks"] = [{k: v for k, v in p.items() if k != "i"} for p in peaks]
    run = best = 0
    for v in s:
        run = run + 1 if v >= 0.5 else 0
        best = max(best, run)
    green_months = best  # longest consecutive green spell
    seasons = [p["season"] for p in peaks]
    H = KARNATAKA_HINTS if in_karnataka else {k: "" for k in KARNATAKA_HINTS}

    if mn >= 0.5 and amp < 0.25:
        if wc == 10:
            return done("Perennial tree crop / plantation or tree cover", base,
                        f"NDVI stays >= {mn:.2f} all year with little seasonal swing and WorldCover says tree cover.",
                        H["perennial"])
        return done("Perennial crop or plantation", base - 0.05,
                    f"Evergreen canopy: NDVI >= {mn:.2f} all year, seasonal amplitude only {amp:.2f}.",
                    H["perennial"] + "; or a ratoon sugarcane field")
    if green_months >= 7 and mn < 0.45:
        return done("Long-duration crop (sugarcane-like)", base - 0.05,
                    f"NDVI >= 0.5 for {green_months} consecutive months followed by a drop (harvest) to {mn:.2f}: "
                    "matches a 10-14 month crop cycle.", H["long"])
    if len(peaks) >= 3:
        return done("Triple / intensive cropping", base - 0.1,
                    f"{len(peaks)} distinct greenness peaks ({', '.join(seasons)}).", "vegetables, short-duration crops")
    if len(peaks) == 2:
        return done(f"Double cropped ({seasons[0]} + {seasons[1]})", base - 0.05,
                    f"Two crop cycles: peaks in {peaks[0]['month']} (NDVI {peaks[0]['ndvi']}) and "
                    f"{peaks[1]['month']} (NDVI {peaks[1]['ndvi']}).",
                    f"{seasons[0]}: {H.get(seasons[0], '')}; {seasons[1]}: {H.get(seasons[1], '')}")
    if len(peaks) == 1:
        p = peaks[0]
        return done(f"Single-season crop ({p['season']})", base - 0.05,
                    f"One crop cycle peaking in {p['month']} (NDVI {p['ndvi']}); land is low/fallow the rest of the year.",
                    H.get(p["season"], ""))
    if mx < 0.45:
        lab = "Sparse vegetation / rainfed crop or grassland"
        if wc == 10:
            lab = "Open tree cover / scrub"
        return done(lab, base - 0.1,
                    f"NDVI between {mn:.2f} and {mx:.2f}: vegetation present but no strong crop peak "
                    "(low-input rainfed crop, grass, scrub, mixed trees or fallow with weeds).",
                    "ragi/horse gram (rainfed), pasture" if in_karnataka else "")
    return done("Mixed / unclear vegetation", base - 0.15,
                f"NDVI {mn:.2f}-{mx:.2f} without a clear seasonal pattern (mixed pixels, trees + fields).")
