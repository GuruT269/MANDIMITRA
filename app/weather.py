"""Open-Meteo (forecast + soil), NASA POWER (30-day history), SoilGrids (optional), irrigation & alerts."""
import datetime as dt
import math
import requests

UA = {"User-Agent": "MandiMitra-prototype/0.1"}
WMO = {0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Rime fog",
       51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
       66: "Freezing rain", 67: "Freezing rain", 71: "Light snow", 73: "Snow", 75: "Heavy snow", 80: "Rain showers",
       81: "Rain showers", 82: "Violent showers", 95: "Thunderstorm", 96: "Thunderstorm + hail", 99: "Thunderstorm + hail"}


def open_meteo(lat, lon):
    params = {
        "latitude": lat, "longitude": lon, "timezone": "auto", "past_days": 7, "forecast_days": 7,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,"
                   "wind_speed_10m,weather_code,cloud_cover",
        "hourly": "soil_moisture_0_to_7cm,soil_moisture_7_to_28cm,soil_temperature_0_to_7cm,"
                  "soil_temperature_7_to_28cm,relative_humidity_2m,temperature_2m,wind_speed_10m,wind_gusts_10m,"
                  "precipitation,precipitation_probability,is_day",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,"
                 "et0_fao_evapotranspiration,relative_humidity_2m_max,relative_humidity_2m_min,"
                 "wind_speed_10m_max,weather_code",
    }
    r = requests.get("https://api.open-meteo.com/v1/forecast", params=params, headers=UA, timeout=25)
    r.raise_for_status()
    d = r.json()
    cur = d["current"]
    cur["weather"] = WMO.get(cur.get("weather_code"), "")
    h = d["hourly"]
    # soil values at the current hour
    now = cur["time"][:13]
    i = next((k for k, t in enumerate(h["time"]) if t[:13] == now), len(h["time"]) // 2)

    def g(k):
        v = h[k][i]
        return v
    soil = {"moisture_0_7cm_m3m3": g("soil_moisture_0_to_7cm"), "moisture_7_28cm_m3m3": g("soil_moisture_7_to_28cm"),
            "temperature_0_7cm_c": g("soil_temperature_0_to_7cm"), "temperature_7_28cm_c": g("soil_temperature_7_to_28cm"),
            "source": "Open-Meteo model soil layers (ECMWF/ERA5-based), ~9-11 km grid, not a field measurement"}
    dd = d["daily"]
    days = []
    today = cur["time"][:10]
    for k, t in enumerate(dd["time"]):
        days.append({"date": t, "tmax": dd["temperature_2m_max"][k], "tmin": dd["temperature_2m_min"][k],
                     "rain_mm": dd["precipitation_sum"][k], "rain_prob": dd["precipitation_probability_max"][k],
                     "et0_mm": dd["et0_fao_evapotranspiration"][k], "rh_max": dd["relative_humidity_2m_max"][k],
                     "rh_min": dd["relative_humidity_2m_min"][k], "wind_max_kmh": dd["wind_speed_10m_max"][k],
                     "weather": WMO.get(dd["weather_code"][k], ""), "past": t < today})
    # soil moisture 7-day trend (daily means of 7-28cm)
    sm_trend = {}
    for t, v in zip(h["time"], h["soil_moisture_7_to_28cm"]):
        if v is not None:
            sm_trend.setdefault(t[:10], []).append(v)
    sm_trend = [{"date": k, "sm_7_28": round(sum(v) / len(v), 3)} for k, v in sm_trend.items()]
    nxt = []
    for k, t in enumerate(h["time"]):
        if t[:13] >= now and len(nxt) < 72:
            nxt.append({"time": t, "temp": h["temperature_2m"][k], "rh": h["relative_humidity_2m"][k],
                        "wind": h["wind_speed_10m"][k], "gust": h["wind_gusts_10m"][k],
                        "rain": h["precipitation"][k], "rain_prob": h["precipitation_probability"][k],
                        "is_day": h["is_day"][k]})
    return {"current": cur, "soil": soil, "daily": days, "soil_moisture_daily": sm_trend, "hourly_next72": nxt,
            "elevation_m": d.get("elevation"), "timezone": d.get("timezone")}


def kc_from_ndvi(ndvi):
    """Crop coefficient from NDVI (linear Kc-NDVI relation, e.g. Kc ~ 1.25*NDVI + 0.2, clamped)."""
    if ndvi is None:
        return 0.8
    return round(max(0.3, min(1.2, 1.25 * ndvi + 0.2)), 2)


def irrigation(wx, ndvi, area_ha):
    """FAO-56 style simple water balance: ETc = Kc * ET0; deficit = sum(ETc) - effective rain."""
    kc = kc_from_ndvi(ndvi)
    past = [d for d in wx["daily"] if d["past"]][-7:]
    fut = [d for d in wx["daily"] if not d["past"]][:3]
    def bal(ds):
        etc = sum(kc * (d["et0_mm"] or 0) for d in ds)
        rain = sum(d["rain_mm"] or 0 for d in ds)
        eff = sum(0.8 * r if r > 5 else 0.0 for r in (d["rain_mm"] or 0 for d in ds))  # tiny showers ineffective
        return round(etc, 1), round(rain, 1), round(eff, 1)
    p_etc, p_rain, p_eff = bal(past)
    f_etc, f_rain, f_eff = bal(fut)
    deficit_past = round(p_etc - p_eff, 1)
    deficit_next3 = round(f_etc - f_eff, 1)
    sm = wx["soil"]["moisture_7_28cm_m3m3"]
    # generic loam: field capacity ~0.30, wilting ~0.12 m3/m3; refill trigger at 50% depletion (~0.21)
    fc, wp = 0.30, 0.12
    trigger = wp + 0.5 * (fc - wp)
    if sm is not None:
        depl = max(0.0, min(1.0, (fc - sm) / (fc - wp)))
    else:
        depl = None
    need = deficit_past > 15 or (sm is not None and sm < trigger)
    rain_coming = f_eff >= 10
    if need and not rain_coming:
        depth = round(max(20.0, min(60.0, deficit_past)), 0)
        action = "IRRIGATE"
        msg = (f"Irrigate about {depth:.0f} mm in the next 1-2 days "
               f"(≈ {depth * area_ha * 10:,.0f} m³ = {depth * area_ha * 10000:,.0f} litres for {area_ha:.2f} ha; "
               f"{depth * 4046.86:,.0f} litres per acre).")
    elif need and rain_coming:
        depth = 0
        action = "WAIT"
        msg = f"Soil is drying, but ~{f_rain:.0f} mm rain is forecast in 3 days. Hold irrigation and re-check."
    else:
        depth = 0
        action = "NO IRRIGATION NEEDED"
        msg = "Root-zone moisture and recent rain cover crop demand. No irrigation needed now."
    return {"action": action, "advice": msg, "kc": kc, "kc_basis": "Kc = 1.25*NDVI + 0.2 (clamped 0.3-1.2)",
            "last7": {"etc_mm": p_etc, "rain_mm": p_rain, "effective_rain_mm": p_eff, "deficit_mm": deficit_past},
            "next3": {"etc_mm": f_etc, "rain_mm": f_rain, "effective_rain_mm": f_eff, "deficit_mm": deficit_next3},
            "root_zone_sm": sm, "root_zone_depletion": None if depl is None else round(depl, 2),
            "refill_trigger_sm": round(trigger, 3), "suggested_depth_mm": depth,
            "assumptions": "Generic loam (FC 0.30, WP 0.12 m³/m³), effective rain = 80% of days >5 mm. "
                           "Calibrate with the farm's soil type and crop stage."}


def alerts(wx):
    out = []
    for d in wx["daily"]:
        if d["past"]:
            continue
        if d["tmax"] is not None and d["tmax"] > 38:
            out.append({"date": d["date"], "level": "high", "type": "Heat stress",
                        "msg": f"Max {d['tmax']}°C. Irrigate early morning/evening, mulch, avoid spraying at midday."})
        if d["rain_mm"] is not None and d["rain_mm"] > 50:
            out.append({"date": d["date"], "level": "high", "type": "Heavy rain",
                        "msg": f"{d['rain_mm']} mm forecast. Clear field drains, postpone fertiliser/pesticide application and harvest."})
        elif d["rain_mm"] is not None and d["rain_mm"] > 20:
            out.append({"date": d["date"], "level": "medium", "type": "Moderate rain",
                        "msg": f"{d['rain_mm']} mm forecast. Avoid spraying; washes off chemicals."})
        if d["tmin"] is not None and d["tmin"] < 4:
            out.append({"date": d["date"], "level": "high", "type": "Frost risk",
                        "msg": f"Min {d['tmin']}°C. Light irrigation in the evening protects crops from frost."})
        if d["rh_max"] is not None and d["rh_min"] is not None and d["rh_max"] >= 90 and d["rh_min"] >= 60 \
                and d["tmax"] is not None and 15 <= d["tmax"] <= 32:
            out.append({"date": d["date"], "level": "medium", "type": "Fungal disease risk",
                        "msg": f"Humidity {d['rh_min']}-{d['rh_max']}% at {d['tmin']}-{d['tmax']}°C favours blast/blight/mildew. Scout leaves; prefer bio-fungicides (Trichoderma/Pseudomonas)."})
        if d["wind_max_kmh"] is not None and d["wind_max_kmh"] > 40:
            out.append({"date": d["date"], "level": "medium", "type": "Strong wind",
                        "msg": f"Gusts to {d['wind_max_kmh']} km/h. Don't spray; stake tall crops."})
    # fungal risk on consecutive humid days, de-duplicate summary
    return out


def nasa_power(lat, lon, days=30):
    end = dt.date.today() - dt.timedelta(days=3)  # POWER lags a few days
    start = end - dt.timedelta(days=days - 1)
    p = {"parameters": "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M,ALLSKY_SFC_SW_DWN,WS2M", "community": "AG",
         "latitude": lat, "longitude": lon, "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"),
         "format": "JSON"}
    r = requests.get("https://power.larc.nasa.gov/api/temporal/daily/point", params=p, headers=UA, timeout=40)
    r.raise_for_status()
    par = r.json()["properties"]["parameter"]

    def vals(k):
        return [v for v in par[k].values() if v is not None and v > -900]
    t, tx, tn, pr, rh, sw = (vals(k) for k in ["T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR", "RH2M", "ALLSKY_SFC_SW_DWN"])
    avg = lambda a: round(sum(a) / len(a), 1) if a else None
    return {"period": f"{start.isoformat()} to {end.isoformat()}", "days_with_data": len(t),
            "mean_temp_c": avg(t), "mean_tmax_c": avg(tx), "mean_tmin_c": avg(tn),
            "abs_max_c": max(tx) if tx else None, "abs_min_c": min(tn) if tn else None,
            "total_rain_mm": round(sum(pr), 1) if pr else None, "rainy_days_gt2_5mm": sum(1 for x in pr if x > 2.5),
            "mean_rh_pct": avg(rh), "mean_solar_kwh_m2_day": avg(sw),
            "growing_degree_days_base10": round(sum(max(0, x - 10) for x in t), 0) if t else None,
            "source": "NASA POWER daily (MERRA-2 / CERES), 0.5° grid"}


_SOIL_CACHE = {}


def soilgrids(lat, lon):
    key = (round(lat, 3), round(lon, 3))
    if key in _SOIL_CACHE:
        return _SOIL_CACHE[key]
    p = [("lon", lon), ("lat", lat), ("value", "mean"), ("depth", "0-5cm"), ("depth", "5-15cm"), ("depth", "15-30cm")]
    p += [("property", k) for k in ["phh2o", "soc", "nitrogen", "clay", "sand", "silt", "cec"]]
    r = requests.get("https://rest.isric.org/soilgrids/v2.0/properties/query", params=p, headers=UA, timeout=(3, 5))
    r.raise_for_status()
    out = {}
    for layer in r.json()["properties"]["layers"]:
        name, f = layer["name"], layer["unit_measure"]["d_factor"]
        unit = layer["unit_measure"]["target_units"]
        vals = {dd["label"]: (None if dd["values"]["mean"] is None else round(dd["values"]["mean"] / f, 2))
                for dd in layer["depths"]}
        out[name] = {"unit": unit, **vals}
    res = {"properties": out, "source": "ISRIC SoilGrids 250 m (modelled, not a soil test)"}
    _SOIL_CACHE[key] = res
    return res


def spray_windows(wx, hours=48):
    """Hours fit for spraying: daylight, wind < 10 km/h, gust < 20, temp < 32 C, no rain now and none
    (>0.2 mm or prob > 40%) in the following 6 hours. Contiguous runs of >= 2 h are windows."""
    hr = wx.get("hourly_next72", [])[:hours + 6]
    ok = []
    for i, h in enumerate(hr[:hours]):
        nxt6 = hr[i:i + 7]
        dry = all((x["rain"] or 0) <= 0.2 and (x["rain_prob"] or 0) <= 40 for x in nxt6)
        good = h["is_day"] == 1 and (h["wind"] or 99) < 10 and (h["gust"] or 99) < 20 and (h["temp"] or 99) < 32 and dry
        ok.append(good)
    wins, i = [], 0
    while i < len(ok):
        if ok[i]:
            j = i
            while j + 1 < len(ok) and ok[j + 1]:
                j += 1
            if j - i + 1 >= 2:
                seg = hr[i:j + 1]
                wins.append({"start": seg[0]["time"], "end": hr[j]["time"][:11] + f"{int(hr[j]['time'][11:13]) + 1:02d}:00",
                             "hours": j - i + 1, "max_wind": max(x["wind"] for x in seg),
                             "max_temp": max(x["temp"] for x in seg)})
            i = j + 1
        else:
            i += 1
    reasons = []
    if hr:
        if any((x["wind"] or 0) >= 10 for x in hr[:12] if x["is_day"]):
            reasons.append("wind ≥ 10 km/h at times today")
        if any((x["rain_prob"] or 0) > 40 for x in hr[:24]):
            reasons.append("rain likely within 24 h")
        if any((x["temp"] or 0) >= 32 for x in hr[:12] if x["is_day"]):
            reasons.append("midday heat ≥ 32 °C (spray evaporates/burns leaves)")
    return {"windows": wins[:6], "rules": "Daylight, wind < 10 km/h, gusts < 20 km/h, temp < 32 °C, no rain for 6 h after",
            "constraints_seen": reasons, "source": "Open-Meteo hourly forecast"}


CROP_GROUP = {"paddy": "paddy", "rice": "paddy", "tomato": "solanaceous", "potato": "solanaceous", "brinjal": "solanaceous",
              "greenchilli": "solanaceous", "maize": "maize", "ragi": "millet", "jowar": "millet", "cotton": "cotton",
              "onion": "onion", "groundnut": "pulse_oil", "tur": "pulse_oil", "sugarcane": "sugarcane",
              "arecanut": "plantation", "coconut": "plantation", "banana": "plantation"}


def pest_risk(wx, crop="paddy"):
    """Weather-driven pest/disease risk for the next 3 days (rule-based, general guidance)."""
    grp = CROP_GROUP.get(crop, "general")
    hr = wx.get("hourly_next72", [])
    days = {}
    for h in hr:
        days.setdefault(h["time"][:10], []).append(h)
    out = []
    wet = max((sum(1 for h in v if (h["rh"] or 0) >= 90 and 15 <= (h["temp"] or 0) <= 28) for v in days.values()), default=0)
    hotdry = max((sum(1 for h in v if (h["temp"] or 0) >= 32 and (h["rh"] or 100) <= 45) for v in days.values()), default=0)
    warmhum = max((sum(1 for h in v if 25 <= (h["temp"] or 0) <= 32 and (h["rh"] or 0) >= 80) for v in days.values()), default=0)
    lvl = lambda x, m, hi: "high" if x >= hi else "medium" if x >= m else "low"
    fungal = {"paddy": ("Blast / sheath blight", "Pseudomonas fluorescens 10 g/L or Trichoderma; avoid excess urea"),
              "solanaceous": ("Early / late blight", "Remove infected leaves; Trichoderma / copper-based organic spray; avoid overhead watering"),
              "onion": ("Purple blotch / downy mildew", "Trichoderma soil drench; ensure drainage"),
              "pulse_oil": ("Leaf spot / rust", "Pseudomonas 10 g/L spray"),
              "plantation": ("Fruit rot (Koleroga) / bud rot", "Bordeaux mixture 1% (traditional) before heavy rain spells"),
              }.get(grp, ("Fungal leaf disease", "Trichoderma / Pseudomonas bio-fungicide; improve airflow"))
    out.append({"risk": fungal[0], "type": "disease", "level": lvl(wet, 6, 10), "driver": f"up to {wet} h/day with RH ≥ 90% at 15-28 °C",
                "organic_action": fungal[1]})
    suck = {"paddy": "Brown planthopper (BPH)", "solanaceous": "Whitefly / thrips (leaf curl virus vectors)",
            "cotton": "Whitefly / jassids", "onion": "Thrips", "maize": "Aphids"}.get(grp, "Sucking pests (thrips, mites, aphids)")
    if grp == "paddy":
        out.append({"risk": suck, "type": "pest", "level": lvl(warmhum, 8, 14), "driver": f"up to {warmhum} h/day warm (25-32 °C) & humid (RH ≥ 80%)",
                    "organic_action": "Drain field 3-4 days, avoid excess nitrogen, neem oil 5 mL/L at base of plants"})
    else:
        out.append({"risk": suck, "type": "pest", "level": lvl(hotdry, 3, 6), "driver": f"up to {hotdry} h/day hot (≥ 32 °C) & dry (RH ≤ 45%)",
                    "organic_action": "Yellow sticky traps 10/acre, neem oil 1500 ppm 5 mL/L in the evening"})
    if grp == "maize":
        out.append({"risk": "Fall armyworm", "type": "pest", "level": "medium" if warmhum >= 6 else "low",
                    "driver": "warm humid nights favour egg-laying", "organic_action": "Scout whorls; pheromone traps 5/acre; Bt or neem spray in whorls"})
    return {"crop": crop, "group": grp, "risks": out,
            "note": "General weather-based risk rules, not a diagnosis. Confirm with field scouting / KVK / Raitha Samparka Kendra."}
