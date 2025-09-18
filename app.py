"""Flask web application used to display personalised template ads."""
from __future__ import annotations

import os
import time
from pathlib import Path
from sqlite3 import Connection
from typing import Any, Dict, List

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template_string, request

from db import get_db, init_db

load_dotenv()

APP_ENV = os.getenv("APP_ENV", "production")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
SECRET_KEY = os.getenv("SECRET_KEY", "dev")
SQLITE_PATH = os.getenv("SQLITE_PATH", "./data/app.db")
AD_TEMPLATE_PATH = os.getenv("AD_TEMPLATE_PATH", "./templates/ad.html")
PUSH_DELAY_MS = int(os.getenv("PUSH_DELAY_MS", "5000"))
CORS_ALLOW_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
    if origin.strip()
]

app = Flask(__name__)
app.secret_key = SECRET_KEY

@app.after_request
def add_cors_headers(resp):
    """Append minimal CORS headers for trusted origins."""
    origin = request.headers.get("Origin")
    if origin and (not CORS_ALLOW_ORIGINS or origin in CORS_ALLOW_ORIGINS):
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Credentials"] = "true"
        resp.headers["Vary"] = "Origin"
    return resp

_DEFAULT_AD_TEMPLATE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Smart Ad</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 0; background:#0b1220; color:#e6edf3; }
    .wrap { display:grid; place-items:center; min-height:100vh; }
    .card { background:#111b2a; padding:32px; border-radius:20px; box-shadow:0 8px 30px rgba(0,0,0,.35); width:min(720px, 92vw); }
    h1 { margin: 0 0 12px; }
    .muted { opacity:.7; }
    .pill { display:inline-block; padding:6px 10px; border-radius:999px; background:#1f2b41; font-size:12px; }
    ul { line-height:1.8; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <div class="pill">匿名會員：{{ member_id }}</div>
      <h1>嗨！{{ headline }}</h1>
      <p class="muted">根據你的最近消費紀錄，我們幫你挑了這些好物：</p>
      <ul>
        {% for x in purchases %}
        <li>{{ x['sku'] }} — 上次 {{ x['ago'] }} 前買過。<strong>今日{{ x['offer'] }}</strong></li>
        {% endfor %}
      </ul>
      <p class="muted">隱私已保護：只使用不可逆的匿名 ID。</p>
    </div>
  </div>
</body>
</html>
"""

def _format_elapsed(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"

def render_ad(member_id: str, conn: Connection):
    """Render the HTML advertisement for ``member_id``."""
    purchases: List[Dict[str, Any]] = []
    cur = conn.execute(
        "SELECT ts, sku, amount FROM purchases WHERE id=? ORDER BY ts DESC LIMIT 5",
        (member_id,),
    )
    now = int(time.time())
    for ts, sku, amount in cur.fetchall():
        delta = max(0, now - int(ts))
        purchases.append(
            {
                "sku": f"{sku} ×{int(amount)}",
                "offer": "9折",
                "ago": _format_elapsed(delta),
            }
        )

    headline = f"會員 {member_id[:8]}，歡迎回來！"

    path = Path(AD_TEMPLATE_PATH)
    template_source = (
        path.read_text(encoding="utf-8") if path.exists() else _DEFAULT_AD_TEMPLATE
    )
    return render_template_string(
        template_source,
        member_id=member_id,
        purchases=purchases,
        headline=headline,
    )

@app.before_first_request
def ensure_database():
    Path(SQLITE_PATH).parent.mkdir(parents=True, exist_ok=True)
    init_db(SQLITE_PATH)

@app.route("/health")
def health():
    return jsonify({"ok": True})

@app.route("/")
def index():
    return """
<!doctype html>
<html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Display</title></head>
<body style=\"margin:0;display:grid;place-items:center;height:100vh;font-family:sans-serif;background:#0b1220;color:#e6edf3\">
<div id=\"s\">等待來賓中…</div>
<script>
const delay = {delay};
async function tick(){
  try{
    const r = await fetch('/latest', {{credentials:'include'}});
    const j = await r.json();
    if(j && j.member_id){ location.href = '/ad?member_id=' + encodeURIComponent(j.member_id); return; }
  }catch(e){}
  setTimeout(tick, delay);
}
setTimeout(tick, delay);
</script>
</body></html>
""".format(delay=PUSH_DELAY_MS)

@app.route("/latest")
def latest():
    conn = get_db(SQLITE_PATH)
    cur = conn.execute("SELECT id FROM members ORDER BY last_seen_ts DESC LIMIT 1")
    row = cur.fetchone()
    return jsonify({"member_id": row[0] if row else None})

@app.route("/ad")
def ad():
    member_id = request.args.get("member_id")
    if not member_id:
        return jsonify({"error": "missing member_id"}), 400
    conn = get_db(SQLITE_PATH)
    return render_ad(member_id, conn)

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=(APP_ENV != "production"))
