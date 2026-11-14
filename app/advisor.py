"""Farm Health Score, daily action card (English + Kannada), optional LLM polish, scheme quick-eligibility."""
import json
import os

import requests


def _clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def health_score(latest, irrigation, alerts, pests):
    """0-100 = vigour (NDVI, 40) + chlorophyll (NDRE, 20) + water (root-zone + NDMI, 20) + weather risk (20)."""
    idx = (latest or {}).get("indices") or {}
    g = lambda k: (idx.get(k) or {}).get("mean")
    ndvi, ndre, ndmi = g("NDVI"), g("NDRE"), g("NDMI")
    parts = []
    if ndvi is not None:
        v = 40 * _clamp((ndvi - 0.15) / 0.6)
        parts.append({"name": "Crop vigour (NDVI)", "kn": "ಬೆಳೆ ಚೈತನ್ಯ (NDVI)", "points": round(v), "max": 40, "value": ndvi,
                      "why": "dense green canopy" if ndvi >= 0.6 else "moderate canopy" if ndvi >= 0.4 else "sparse / early-stage / stressed crop"})
    if ndre is not None:
        c = 20 * _clamp((ndre - 0.1) / 0.4)
        parts.append({"name": "Leaf chlorophyll / nitrogen (NDRE)", "kn": "ಎಲೆ ಹಸಿರು / ಸಾರಜನಕ (NDRE)", "points": round(c), "max": 20,
                      "value": ndre, "why": "good nitrogen status" if ndre >= 0.4 else "watch nitrogen" if ndre >= 0.25 else "likely nitrogen-deficient or sparse"})
    w_parts = []
    if irrigation and irrigation.get("root_zone_depletion") is not None:
        w_parts.append(1 - irrigation["root_zone_depletion"])
    if ndmi is not None:
        w_parts.append(_clamp((ndmi + 0.1) / 0.5))
    if w_parts:
        w = 20 * sum(w_parts) / len(w_parts)
        parts.append({"name": "Water status (soil + canopy)", "kn": "ನೀರಿನ ಸ್ಥಿತಿ (ಮಣ್ಣು + ಎಲೆ)", "points": round(w), "max": 20,
                      "value": round(sum(w_parts) / len(w_parts), 2),
                      "why": "adequate moisture" if w >= 14 else "moderate water stress" if w >= 8 else "high water stress"})
    pen = 0
    for a in alerts or []:
        pen += 6 if a["level"] == "high" else 3
    for r in (pests or {}).get("risks", []):
        pen += 5 if r["level"] == "high" else 2 if r["level"] == "medium" else 0
    wr = max(0, 20 - pen)
    parts.append({"name": "Weather & pest risk (next 3-7 days)", "kn": "ಹವಾಮಾನ ಮತ್ತು ಕೀಟ ಅಪಾಯ", "points": wr, "max": 20,
                  "value": pen, "why": "low risk" if wr >= 16 else "some risk, see alerts" if wr >= 10 else "high risk, act now"})
    got = sum(p["points"] for p in parts)
    mx = sum(p["max"] for p in parts)
    score = round(100 * got / mx) if mx else None
    grade = None if score is None else ("Excellent" if score >= 80 else "Good" if score >= 65 else "Fair" if score >= 50 else "Needs attention")
    kn_grade = {"Excellent": "ಅತ್ಯುತ್ತಮ", "Good": "ಉತ್ತಮ", "Fair": "ಸಾಧಾರಣ", "Needs attention": "ಗಮನ ಅಗತ್ಯ"}.get(grade)
    weakest = min(parts, key=lambda p: p["points"] / p["max"]) if parts else None
    expl = (f"Score {score}/100 ({grade}). Strongest: {max(parts, key=lambda p: p['points'] / p['max'])['name'].lower()}. "
            f"Weakest: {weakest['name'].lower()} ({weakest['why']}).") if parts else "Not enough data."
    expl_kn = (f"ಅಂಕ {score}/100 ({kn_grade}). ಸುಧಾರಿಸಬೇಕಾದ ಅಂಶ: {weakest['kn']}.") if parts else ""
    return {"score": score, "grade": grade, "grade_kn": kn_grade, "parts": parts, "explanation": expl, "explanation_kn": expl_kn,
            "method": "Rule-based composite of satellite indices, model soil moisture and forecast risk. Low scores for "
                      "just-harvested or newly sown fields are expected (low NDVI is crop stage, not poor health)."}


def _fmt_window(w):
    d = w["start"][5:10]
    return f"{d} {w['start'][11:16]}–{w['end'][11:16]}"


def action_card(score, irrigation, spray, pests, alerts, soil_props, latest, crop_label):
    """Deterministic bilingual daily action list."""
    items = []
    # 1 irrigation
    if irrigation:
        a = irrigation["action"]
        if a == "IRRIGATE":
            mm = irrigation["suggested_depth_mm"]
            items.append({"icon": "💧", "en": f"Irrigate about {mm:.0f} mm in the next 1-2 days (early morning or evening).",
                          "kn": f"ಮುಂದಿನ 1-2 ದಿನಗಳಲ್ಲಿ ಸುಮಾರು {mm:.0f} ಮಿ.ಮೀ. ನೀರು ಹಾಯಿಸಿ (ಬೆಳಿಗ್ಗೆ ಅಥವಾ ಸಂಜೆ).", "priority": 1})
        elif a == "WAIT":
            items.append({"icon": "🌧", "en": "Soil is drying but rain is forecast. Hold irrigation and check again in 2 days.",
                          "kn": "ಮಣ್ಣು ಒಣಗುತ್ತಿದೆ, ಆದರೆ ಮಳೆ ಮುನ್ಸೂಚನೆ ಇದೆ. ನೀರಾವರಿ ಮುಂದೂಡಿ, 2 ದಿನಗಳ ನಂತರ ಮತ್ತೆ ಪರಿಶೀಲಿಸಿ.", "priority": 2})
        elif a != "N/A":
            items.append({"icon": "✅", "en": "No irrigation needed today. Soil moisture is sufficient.",
                          "kn": "ಇಂದು ನೀರಾವರಿ ಅಗತ್ಯವಿಲ್ಲ. ಮಣ್ಣಿನಲ್ಲಿ ಸಾಕಷ್ಟು ತೇವಾಂಶ ಇದೆ.", "priority": 3})
    # 2 spray window
    wins = (spray or {}).get("windows", [])
    if wins:
        w = wins[0]
        items.append({"icon": "🧴", "en": f"Best spray window: {_fmt_window(w)} (calm wind, no rain for 6 h after).",
                      "kn": f"ಸಿಂಪಡಣೆಗೆ ಉತ್ತಮ ಸಮಯ: {_fmt_window(w)} (ಗಾಳಿ ಕಡಿಮೆ, ನಂತರ 6 ಗಂಟೆ ಮಳೆ ಇಲ್ಲ).", "priority": 2})
    else:
        items.append({"icon": "⛔", "en": "No safe spray window in the next 48 h (wind/rain/heat). Do not spray.",
                      "kn": "ಮುಂದಿನ 48 ಗಂಟೆಗಳಲ್ಲಿ ಸಿಂಪಡಣೆಗೆ ಸುರಕ್ಷಿತ ಸಮಯ ಇಲ್ಲ (ಗಾಳಿ/ಮಳೆ/ಬಿಸಿಲು). ಸಿಂಪಡಿಸಬೇಡಿ.", "priority": 2})
    # 3 pest / disease
    for r in (pests or {}).get("risks", []):
        if r["level"] in ("high", "medium"):
            lvl_kn = "ಹೆಚ್ಚು" if r["level"] == "high" else "ಮಧ್ಯಮ"
            typ_kn = "ರೋಗ" if r["type"] == "disease" else "ಕೀಟ"
            items.append({"icon": "🐛" if r["type"] == "pest" else "🍂",
                          "en": f"{r['level'].title()} risk of {r['risk']}. Scout the field. Organic option: {r['organic_action']}.",
                          "kn": f"{r['risk']} {typ_kn}ದ ಅಪಾಯ {lvl_kn}. ಹೊಲವನ್ನು ಪರಿಶೀಲಿಸಿ. ಸಾವಯವ ಪರಿಹಾರ: ಬೇವಿನ ಎಣ್ಣೆ / ಟ್ರೈಕೋಡರ್ಮಾ / ಸೂಡೋಮೊನಾಸ್ ಬಳಸಿ.",
                          "priority": 1 if r["level"] == "high" else 2})
    # 4 weather alerts
    for a in (alerts or [])[:2]:
        items.append({"icon": "⚠️", "en": f"{a['date']}: {a['type']}. {a['msg']}",
                      "kn": f"{a['date']}: ಹವಾಮಾನ ಎಚ್ಚರಿಕೆ – {a['type']}. ಮುನ್ನೆಚ್ಚರಿಕೆ ವಹಿಸಿ.", "priority": 1 if a["level"] == "high" else 2})
    # 5 organic nutrition
    idx = (latest or {}).get("indices") or {}
    ndre = (idx.get("NDRE") or {}).get("mean")
    ndvi = (idx.get("NDVI") or {}).get("mean")
    soc = None
    try:
        soc = soil_props["properties"]["soc"]["0-5cm"]
    except Exception:
        pass
    if ndre is not None and ndvi is not None and ndvi >= 0.35 and ndre < 0.3:
        items.append({"icon": "🌱", "en": "Leaves show low chlorophyll (NDRE). Top-dress with vermicompost (500 kg/acre) or "
                                         "jeevamrutha (200 L/acre via irrigation) instead of extra urea.",
                      "kn": "ಎಲೆಗಳಲ್ಲಿ ಹಸಿರು ಕಡಿಮೆ (NDRE). ಹೆಚ್ಚುವರಿ ಯೂರಿಯಾ ಬದಲು ಎರೆಹುಳು ಗೊಬ್ಬರ (ಎಕರೆಗೆ 500 ಕೆ.ಜಿ.) ಅಥವಾ "
                            "ಜೀವಾಮೃತ (ಎಕರೆಗೆ 200 ಲೀ. ನೀರಿನೊಂದಿಗೆ) ನೀಡಿ.", "priority": 2})
    elif ndvi is not None and ndvi < 0.25:
        items.append({"icon": "🌾", "en": "Field looks bare or just harvested. Good time for green manure (dhaincha / sunhemp) "
                                         "or 2-4 t/acre farmyard manure before the next crop.",
                      "kn": "ಹೊಲ ಖಾಲಿ ಅಥವಾ ಕಟಾವು ಆದಂತಿದೆ. ಮುಂದಿನ ಬೆಳೆಗೆ ಮೊದಲು ಹಸಿರೆಲೆ ಗೊಬ್ಬರ (ಡೈಂಚಾ / ಸೆಣಬು) ಅಥವಾ "
                            "ಎಕರೆಗೆ 2-4 ಟನ್ ಕೊಟ್ಟಿಗೆ ಗೊಬ್ಬರ ಹಾಕಲು ಸೂಕ್ತ ಸಮಯ.", "priority": 3})
    else:
        items.append({"icon": "🌿", "en": "Crop nutrition looks fine. Keep using compost/FYM; get a free Soil Health Card test every 2 years.",
                      "kn": "ಬೆಳೆಯ ಪೋಷಣೆ ಸರಿಯಾಗಿದೆ. ಕಾಂಪೋಸ್ಟ್/ಕೊಟ್ಟಿಗೆ ಗೊಬ್ಬರ ಮುಂದುವರಿಸಿ; 2 ವರ್ಷಕ್ಕೊಮ್ಮೆ ಉಚಿತ ಮಣ್ಣು ಆರೋಗ್ಯ ಚೀಟಿ ಪರೀಕ್ಷೆ ಮಾಡಿಸಿ.",
                      "priority": 3})
    if soc is not None and soc < 10:
        items.append({"icon": "🪱", "en": f"Soil organic carbon looks low (~{soc} g/kg, SoilGrids model). Add FYM/compost and crop residue.",
                      "kn": f"ಮಣ್ಣಿನ ಸಾವಯವ ಇಂಗಾಲ ಕಡಿಮೆ ಇರುವಂತಿದೆ (~{soc} ಗ್ರಾಂ/ಕೆ.ಜಿ.). ಕೊಟ್ಟಿಗೆ ಗೊಬ್ಬರ/ಕಾಂಪೋಸ್ಟ್ ಮತ್ತು ಬೆಳೆ ಉಳಿಕೆ ಸೇರಿಸಿ.",
                      "priority": 3})
    items.sort(key=lambda x: x["priority"])
    sc = score.get("score") if score else None
    head_en = f"Farm Health Score {sc}/100 ({score.get('grade')}). Today's top actions for your {crop_label} field:" if sc is not None else "Today's actions:"
    head_kn = f"ಹೊಲದ ಆರೋಗ್ಯ ಅಂಕ {sc}/100 ({score.get('grade_kn')}). ನಿಮ್ಮ ಹೊಲಕ್ಕೆ ಇಂದಿನ ಮುಖ್ಯ ಕೆಲಸಗಳು:" if sc is not None else "ಇಂದಿನ ಕೆಲಸಗಳು:"
    return {"headline_en": head_en, "headline_kn": head_kn, "items": items[:6], "engine": "rule-based templates",
            "kn_note": "Kannada text is template-based; please have a native speaker review it before field use."}


def llm_polish(card, facts):
    """Optional: if GROQ_API_KEY or GEMINI_API_KEY is set, ask an LLM for a 3-sentence bilingual summary. Never required."""
    prompt = ("You are an agronomy assistant for small farmers in Karnataka. Using ONLY these facts, write a 3-sentence "
              "practical advice summary in simple English, then the same in Kannada. Do not invent numbers.\nFACTS: "
              + json.dumps(facts, ensure_ascii=False)[:3500])
    try:
        if os.environ.get("GROQ_API_KEY"):
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", timeout=10,
                              headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
                              json={"model": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
                                    "messages": [{"role": "user", "content": prompt}], "temperature": 0.2})
            r.raise_for_status()
            return {"text": r.json()["choices"][0]["message"]["content"], "engine": "Groq LLM"}
        if os.environ.get("GEMINI_API_KEY"):
            m = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                              params={"key": os.environ["GEMINI_API_KEY"]}, timeout=10,
                              json={"contents": [{"parts": [{"text": prompt}]}]})
            r.raise_for_status()
            return {"text": r.json()["candidates"][0]["content"]["parts"][0]["text"], "engine": "Gemini LLM"}
    except Exception as e:
        return {"text": None, "engine": f"LLM failed ({type(e).__name__}); using templates"}
    return None


SCHEMES = [
    {"id": "pmkisan", "name": "PM-KISAN", "kn": "ಪಿಎಂ-ಕಿಸಾನ್", "benefit": "₹6,000/year income support in 3 instalments",
     "url": "https://pmkisan.gov.in/"},
    {"id": "pmfby", "name": "PMFBY crop insurance", "kn": "ಪ್ರಧಾನ ಮಂತ್ರಿ ಫಸಲ್ ಬಿಮಾ ಯೋಜನೆ",
     "benefit": "Crop insurance; farmer premium 2% (kharif), 1.5% (rabi), 5% (commercial/horticulture)", "url": "https://pmfby.gov.in/"},
    {"id": "kcc", "name": "Kisan Credit Card (KCC)", "kn": "ಕಿಸಾನ್ ಕ್ರೆಡಿಟ್ ಕಾರ್ಡ್",
     "benefit": "Short-term crop loan with interest subvention for prompt repayment (check current limit with your bank)",
     "url": "https://www.myscheme.gov.in/schemes/kcc"},
    {"id": "pkvy", "name": "PKVY organic farming", "kn": "ಪರಂಪರಾಗತ ಕೃಷಿ ವಿಕಾಸ ಯೋಜನೆ",
     "benefit": "Support for organic conversion in clusters/FPOs (inputs, certification via PGS-India)", "url": "https://pgsindia-ncof.gov.in/pkvy/index.aspx"},
    {"id": "kusum", "name": "PM-KUSUM solar pump", "kn": "ಪಿಎಂ-ಕುಸುಮ್ ಸೌರ ಪಂಪ್",
     "benefit": "Subsidised standalone solar pumps (Comp. B) or solarising grid pumps (Comp. C)", "url": "https://pmkusum.mnre.gov.in/"},
    {"id": "shc", "name": "Soil Health Card", "kn": "ಮಣ್ಣು ಆರೋಗ್ಯ ಚೀಟಿ",
     "benefit": "Free soil test with nutrient and fertiliser recommendations", "url": "https://soilhealth.dac.gov.in/"},
]


def schemes(land_acres=2.0, owner=True, income_tax=False, govt_employee=False, irrigation="borewell",
            grid_pump=True, organic_interest=False, crop="paddy"):
    out = []
    for s in SCHEMES:
        st, why = "likely", ""
        if s["id"] == "pmkisan":
            if not owner:
                st, why = "not eligible", "Needs cultivable land in your own name (tenants are not covered)."
            elif income_tax or govt_employee:
                st, why = "not eligible", "Income-tax payers and government employees are excluded."
            else:
                why = "You own cultivable land and fall outside the exclusion list."
        elif s["id"] == "pmfby":
            why = "Open to owners and tenants growing notified crops in notified areas; enrol before the season cut-off via bank/CSC."
        elif s["id"] == "kcc":
            why = "Open to owner, tenant and sharecropper farmers; apply at your bank with land/lease records."
        elif s["id"] == "pkvy":
            st = "likely" if organic_interest else "optional"
            why = "Join an organic cluster/FPO; fits farmers moving away from chemical inputs." if organic_interest else \
                "Relevant if you want to convert to organic; ask your agriculture officer about local clusters."
        elif s["id"] == "kusum":
            if irrigation == "rainfed":
                st, why = "check", "Useful if you plan irrigation; standalone solar pump subsidy is meant for off-grid farmers."
            elif grid_pump:
                st, why = "likely", "You have a grid pump, so Component C (pump solarisation) may apply where notified."
            else:
                st, why = "likely", "No grid connection: Component B standalone solar pump fits."
        elif s["id"] == "shc":
            why = "Every farmer can get a free soil test. Recommended every 2 years."
        out.append({**s, "status": st, "why": why})
    return {"schemes": out, "inputs": {"land_acres": land_acres, "owner": owner, "income_tax": income_tax,
                                       "govt_employee": govt_employee, "irrigation": irrigation, "grid_pump": grid_pump,
                                       "organic_interest": organic_interest, "crop": crop},
            "note": "Indicative only, based on simple rules. Eligibility is decided by the official portal or office. In Karnataka, "
                    "register on the FRUITS farmer ID portal and visit your Raitha Samparka Kendra (RSK).",
            "fruits_url": "https://fruits.karnataka.gov.in/"}
