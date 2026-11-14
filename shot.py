import sys
from playwright.sync_api import sync_playwright
url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8077/?lat=12.50&lon=76.85&rad=100&auto=1"
out = sys.argv[2] if len(sys.argv) > 2 else "screenshot.png"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    logs = []
    pg.on("console", lambda m: logs.append(m.text))
    pg.on("pageerror", lambda e: logs.append("PAGEERROR " + str(e)))
    pg.goto(url)
    pg.wait_for_function("""(() => { const t = (document.getElementById('status').textContent || '') + ' ' + ((document.getElementById('mstatus') || {}).textContent || '');
        return t.includes('Done in') || t.includes('⚠') || t.includes('Error'); })()""", timeout=240000)
    pg.wait_for_timeout(2500)
    print(pg.inner_text("#status"), "|", pg.inner_text("#mstatus")); print("\n".join(logs))
    pg.screenshot(path=out, full_page=(len(sys.argv) < 4))
    b.close()
