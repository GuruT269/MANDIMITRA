"""Farm Quality Passport storage (SQLite) + organic score + QR code."""
import datetime as dt
import io
import secrets
import sqlite3
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "mandimitra.db"
UPLOADS = ROOT / "data" / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)
_lock = threading.Lock()

SYNTHETIC = {"chemical fertiliser", "chemical pesticide", "chemical fungicide", "herbicide"}
ORGANIC = {"organic manure", "bio-fertiliser", "bio-pesticide", "botanical (neem etc.)", "green manure"}
INPUT_TYPES = sorted(SYNTHETIC | ORGANIC)


def _conn():
    c = sqlite3.connect(DB, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _lock, _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS farms(id TEXT PRIMARY KEY, farmer TEXT, village TEXT, crop TEXT, lat REAL, lon REAL,
            radius REAL, area_acres REAL, created TEXT, demo INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY AUTOINCREMENT, farm_id TEXT, date TEXT, input_type TEXT,
            product TEXT, quantity TEXT, notes TEXT, bill_file TEXT, created TEXT, demo INTEGER DEFAULT 0);
        """)


def create_farm(farmer, village, crop, lat, lon, radius, area_acres=None, demo=False, fid=None):
    fid = fid or secrets.token_urlsafe(5).replace("-", "x").replace("_", "y")
    with _lock, _conn() as c:
        c.execute("INSERT OR REPLACE INTO farms VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (fid, farmer, village, crop, lat, lon, radius, area_acres, dt.datetime.now().isoformat(timespec="seconds"), int(demo)))
    return fid


def add_log(fid, date, input_type, product, quantity, notes="", bill_bytes=None, bill_name=None, demo=False):
    bill_file = None
    if bill_bytes:
        ext = (Path(bill_name or "bill.jpg").suffix or ".jpg").lower()[:5]
        bill_file = f"{fid}_{secrets.token_hex(4)}{ext}"
        (UPLOADS / bill_file).write_bytes(bill_bytes)
    with _lock, _conn() as c:
        c.execute("INSERT INTO logs(farm_id,date,input_type,product,quantity,notes,bill_file,created,demo) VALUES(?,?,?,?,?,?,?,?,?)",
                  (fid, date, input_type, product, quantity, notes, bill_file, dt.datetime.now().isoformat(timespec="seconds"), int(demo)))


def get_farm(fid):
    with _conn() as c:
        f = c.execute("SELECT * FROM farms WHERE id=?", (fid,)).fetchone()
        if not f:
            return None
        logs = [dict(r) for r in c.execute("SELECT * FROM logs WHERE farm_id=? ORDER BY date DESC, id DESC", (fid,))]
    return {**dict(f), "logs": logs}


def list_farms():
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM farms ORDER BY demo DESC, created DESC")]


def organic_score(logs, days=180):
    """Self-declared input log -> 0-100 (100 = only organic/bio inputs in the last `days`)."""
    cutoff = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    recent = [l for l in logs if (l["date"] or "") >= cutoff]
    score, notes = 100, []
    syn = [l for l in recent if l["input_type"] in SYNTHETIC]
    org = [l for l in recent if l["input_type"] in ORGANIC]
    for l in syn:
        pen = 15 if l["input_type"] in ("chemical pesticide", "herbicide", "chemical fungicide") else 8
        score -= pen
    if syn:  # organic practice softens, but never erases, declared chemical use
        score = max(0, min(90, score + min(5, len(org))))
    with_bill = sum(1 for l in recent if l["bill_file"])
    if not recent:
        level, label = "none", "No inputs declared yet"
    elif not syn:
        level, label = "organic", "Only organic / bio inputs declared"
    elif score >= 70:
        level, label = "low-chemical", "Low chemical use"
    else:
        level, label = "conventional", "Conventional (chemical inputs used)"
    last_syn = max((l["date"] for l in syn if l["input_type"] in ("chemical pesticide", "chemical fungicide", "herbicide")), default=None)
    return {"score": score, "level": level, "label": label, "window_days": days, "entries": len(recent),
            "synthetic_entries": len(syn), "organic_entries": len(org), "entries_with_bill": with_bill,
            "last_chemical_spray": last_syn,
            "days_since_chemical_spray": (dt.date.today() - dt.date.fromisoformat(last_syn)).days if last_syn else None,
            "basis": "SELF-DECLARED by the farmer (bill photos optional). Satellites cannot detect chemical use."}


def qr_png(url):
    import qrcode
    img = qrcode.make(url, box_size=8, border=2)
    b = io.BytesIO()
    img.save(b, format="PNG")
    return b.getvalue()


def seed_demo():
    """Demo farm for the judges' walkthrough; its log entries are flagged demo=1 and shown as DEMO ENTRY."""
    init()
    if get_farm("mandya-demo"):
        return "mandya-demo"
    create_farm("Demo farmer (sample)", "Near Mandya", "paddy", 12.50, 76.85, 100, 7.8, demo=True, fid="mandya-demo")
    today = dt.date.today()
    for days, t, p, q, n in [(95, "organic manure", "Farmyard manure", "2 t/acre", "Before transplanting"),
                             (80, "green manure", "Dhaincha incorporated", "20 kg seed/acre", ""),
                             (60, "bio-fertiliser", "Azospirillum + PSB", "2 kg/acre", "Seedling root dip"),
                             (40, "chemical fertiliser", "Urea", "25 kg/acre", "Top dressing"),
                             (22, "botanical (neem etc.)", "Neem oil 1500 ppm", "5 mL/L", "Leaf folder scouting")]:
        add_log("mandya-demo", (today - dt.timedelta(days=days)).isoformat(), t, p, q, n, demo=True)
    return "mandya-demo"
