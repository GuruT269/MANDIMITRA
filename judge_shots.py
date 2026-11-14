"""Capture judge screenshots of every tab + record load timings. Usage: python judge_shots.py [base_url]"""
import sys, json, time
from playwright.sync_api import sync_playwright
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8077"
FIELD_DONE = "document.getElementById('status').textContent.includes('7/7')"
res = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    def shot(name, url, wait, full=True, vp=(1440, 900), extra=1500):
        pg = b.new_page(viewport={"width": vp[0], "height": vp[1]})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        t0 = time.time(); pg.goto(BASE + url)
        pg.wait_for_function(wait, timeout=120000)
        el = time.time() - t0
        pg.wait_for_timeout(extra)
        status = pg.inner_text("#status") if pg.query_selector("#status") else ""
        pg.screenshot(path=f"demo_shots/{name}.png", full_page=full)
        res[name] = {"wall_s": round(el, 1), "status": status[:300], "errors": errs}
        print(name, res[name]); pg.close()
    shot("judge_field", "/?lat=12.50&lon=76.85", FIELD_DONE)
    shot("judge_field_top", "/?lat=12.50&lon=76.85", FIELD_DONE, full=False)
    for n, la, lo in [("tumakuru", 13.30, 77.05), ("davanagere", 14.42, 75.95), ("raichur", 16.18, 77.30)]:
        shot(f"judge_field_{n}", f"/?lat={la}&lon={lo}", FIELD_DONE, full=False)
    shot("judge_field_kannada", "/?lat=12.50&lon=76.85&lang=kn", FIELD_DONE, full=False)
    shot("judge_market", "/?lat=12.50&lon=76.85&tab=market&commodity=tomato", "document.getElementById('mstatus').textContent.includes('Done')", extra=2500)
    shot("judge_passport", "/?lat=12.50&lon=76.85&tab=passport", "document.querySelector('#pcard img') && document.querySelector('#pcard img').complete", extra=4000)
    shot("judge_passport_page", "/passport/mandya-demo", "document.querySelector('.hdr')", extra=2500)
    shot("judge_advisor", "/?lat=12.50&lon=76.85&tab=advisor", "document.querySelector('#a-card .act') && document.querySelector('#s-out .sch')")
    shot("judge_mobile", "/?lat=12.50&lon=76.85", FIELD_DONE, full=False, vp=(390, 844))
    shot("judge_cold_new_location", "/?lat=13.0012&lon=76.1004", FIELD_DONE, full=False)
    b.close()
json.dump(res, open("demo_shots/timings.json", "w"), indent=1)
