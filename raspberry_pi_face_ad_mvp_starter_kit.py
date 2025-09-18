# 📦 Raspberry Pi Face Ad MVP — Starter Kit

Below are the starter files you can copy directly into your repo. They implement:
- Flask web app to display ads
- Camera loop on the Pi creating anonymous member IDs
- SQLite schema + helpers
- HMAC-based ID hashing (no images or embeddings stored)
- GitHub Actions workflow to deploy via SSH to the Pi
- Bootstrap script for Pi dependencies

---

## .env.sample
```ini
APP_ENV=production
HOST=0.0.0.0
PORT=8000
SECRET_KEY=change-me
CORS_ALLOW_ORIGINS=http://raspberrypi.local:8000
SQLITE_PATH=./data/app.db
DB_ECHO=false
CAMERA_INDEX=0
FRAME_WIDTH=640
FRAME_HEIGHT=480
DLIB_MODEL_DIR=./models
ID_HASH_SALT=please-change-me
AD_TEMPLATE_PATH=./templates/ad.html
PUSH_DELAY_MS=5000
```

---

## requirements.txt
```txt
Flask==3.0.3
itsdangerous==2.2.0
Werkzeug==3.0.3
Jinja2==3.1.4
python-dotenv==1.0.1
opencv-python==4.8.1.78
face-recognition==1.3.0
numpy==1.26.4
```
> 若 `opencv-python`/`face-recognition` 在 Pi3 裝不起來，可改用系統庫 + `opencv-python-headless` 或事先安裝 dlib；此為常見在 Pi 上的相依情況。

---

## app.py (Flask API + 前端頁)
```python
import os, json, time, hmac, hashlib
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any

from flask import Flask, request, jsonify, render_template_string
from flask import send_from_directory
from dotenv import load_dotenv
from sqlite3 import Connection

from db import get_db, init_db
from services.id_hash import stable_id

load_dotenv()

APP_ENV = os.getenv("APP_ENV", "production")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
SECRET_KEY = os.getenv("SECRET_KEY", "dev")
SQLITE_PATH = os.getenv("SQLITE_PATH", "./data/app.db")
AD_TEMPLATE_PATH = os.getenv("AD_TEMPLATE_PATH", "./templates/ad.html")
CORS_ALLOW_ORIGINS = [s.strip() for s in os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if s.strip()]

app = Flask(__name__)
app.secret_key = SECRET_KEY

# --- CORS (極簡) ---
@app.after_request
def add_cors(resp):
    origin = request.headers.get("Origin")
    if origin and (not CORS_ALLOW_ORIGINS or origin in CORS_ALLOW_ORIGINS):
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Credentials"] = "true"
        resp.headers["Vary"] = "Origin"
    return resp

# --- Template 加載 ---
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

def render_ad(member_id: str, db: Connection):
    # 取假資料
    purchases = []
    cur = db.execute("SELECT ts, sku, amount FROM purchases WHERE id=? ORDER BY ts DESC LIMIT 5", (member_id,))
    rows = cur.fetchall()
    now = int(time.time())
    for r in rows:
        ago_s = now - int(r[0])
        if ago_s < 60: ago = f"{ago_s}s"
        elif ago_s < 3600: ago = f"{ago_s//60}m"
        elif ago_s < 86400: ago = f"{ago_s//3600}h"
        else: ago = f"{ago_s//86400}d"
        purchases.append({"sku": r[1], "offer": "9折", "ago": ago})

    headline = f"會員 {member_id[:8]}，歡迎回來！"

    # 模板
    path = Path(AD_TEMPLATE_PATH)
    if path.exists():
        html = path.read_text(encoding="utf-8")
        return render_template_string(html, member_id=member_id, purchases=purchases, headline=headline)
    else:
        return render_template_string(_DEFAULT_AD_TEMPLATE, member_id=member_id, purchases=purchases, headline=headline)

@app.route("/health")
def health():
    return {"ok": True}

@app.route("/")
def index():
    # 簡單輪詢最新 ID 並導向 /ad
    return """
<!doctype html>
<html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Display</title></head>
<body style="margin:0;display:grid;place-items:center;height:100vh;font-family:sans-serif;background:#0b1220;color:#e6edf3">
<div id="s">等待來賓中…</div>
<script>
async function tick(){
  try{
    const r = await fetch('/latest', {credentials:'include'});
    const j = await r.json();
    if(j && j.member_id){ location.href = '/ad?member_id=' + encodeURIComponent(j.member_id); return; }
  }catch(e){}
  setTimeout(tick, 1500);
}
setTimeout(tick, 100);
</script>
</body></html>
"""

@app.route("/latest")
def latest():
    db = get_db(SQLITE_PATH)
    cur = db.execute("SELECT id FROM members ORDER BY last_seen_ts DESC LIMIT 1")
    row = cur.fetchone()
    return jsonify({"member_id": row[0] if row else None})

@app.route("/ad")
def ad():
    mid = request.args.get("member_id")
    if not mid:
        return jsonify({"error":"missing member_id"}), 400
    db = get_db(SQLITE_PATH)
    return render_ad(mid, db)

if __name__ == "__main__":
    Path(SQLITE_PATH).parent.mkdir(parents=True, exist_ok=True)
    init_db(SQLITE_PATH)
    app.run(host=HOST, port=PORT, debug=(APP_ENV!="production"))
```

---

## camera_loop.py（OpenCV + face_recognition → 匿名ID → SQLite）
```python
import os, time, json, hmac, hashlib, signal
from pathlib import Path
import cv2
import numpy as np
from dotenv import load_dotenv
import face_recognition
from db import get_db, init_db, ensure_member_and_seed
from services.id_hash import stable_id

load_dotenv()
SQLITE_PATH = os.getenv("SQLITE_PATH", "./data/app.db")
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
FRAME_WIDTH = int(os.getenv("FRAME_WIDTH", "640"))
FRAME_HEIGHT = int(os.getenv("FRAME_HEIGHT", "480"))
ID_HASH_SALT = os.getenv("ID_HASH_SALT", "please-change-me")

cooldown_sec = 3.0
last_emit: dict[str,float] = {}

running = True

def handle_sigterm(sig, frame):
    global running
    running = False

signal.signal(signal.SIGINT, handle_sigterm)
signal.signal(signal.SIGTERM, handle_sigterm)

Path(SQLITE_PATH).parent.mkdir(parents=True, exist_ok=True)
init_db(SQLITE_PATH)

cap = cv2.VideoCapture(CAMERA_INDEX)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

if not cap.isOpened():
    raise SystemExit("Camera open failed")

print("[camera] running… Press Ctrl+C to stop")

while running:
    ok, frame = cap.read()
    if not ok:
        time.sleep(0.1)
        continue

    # 只在有臉時處理
    rgb = frame[:, :, ::-1]
    boxes = face_recognition.face_locations(rgb, model='hog')  # 輕量
    if not boxes:
        time.sleep(0.15)
        continue

    encs = face_recognition.face_encodings(rgb, boxes)
    now = time.time()

    for enc in encs:
        # 降精度以減少抖動
        v = np.round(enc, 3).tolist()
        member_id = stable_id(v, ID_HASH_SALT)

        if member_id in last_emit and (now - last_emit[member_id] < cooldown_sec):
            continue
        last_emit[member_id] = now

        db = get_db(SQLITE_PATH)
        ensure_member_and_seed(db, member_id)
        print(f"[camera] seen {member_id}")

    # 降低 CPU
    time.sleep(0.15)

cap.release()
print("[camera] stopped")
```

---

## db.py（SQLite schema 與 helper）
```python
import sqlite3, time, random
from typing import Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
  id TEXT PRIMARY KEY,
  first_seen_ts INTEGER NOT NULL,
  last_seen_ts INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_members_last ON members(last_seen_ts);

CREATE TABLE IF NOT EXISTS purchases (
  id TEXT NOT NULL,
  ts INTEGER NOT NULL,
  sku TEXT NOT NULL,
  amount INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_purchases_id ON purchases(id);
"""

_SKUS = ["牛奶", "咖啡豆", "麵包", "蘋果", "洗衣精", "牙膏", "泡麵", "雞蛋"]

def get_db(path: str) -> sqlite3.Connection:
    db = sqlite3.connect(path, check_same_thread=False)
    db.execute("PRAGMA journal_mode=WAL;")
    return db

def init_db(path: str):
    db = get_db(path)
    db.executescript(SCHEMA)
    db.commit()

def ensure_member_and_seed(db: sqlite3.Connection, member_id: str):
    now = int(time.time())
    cur = db.execute("SELECT id FROM members WHERE id=?", (member_id,))
    row = cur.fetchone()
    if row is None:
        db.execute("INSERT INTO members(id, first_seen_ts, last_seen_ts) VALUES(?,?,?)", (member_id, now, now))
        # 生成 5 筆假消費紀錄（時間往前錯開）
        base = now
        for i in range(5):
            ts = base - (i+1) * random.randint(3600, 86400)
            sku = random.choice(_SKUS)
            amt = random.randint(1, 3)
            db.execute("INSERT INTO purchases(id, ts, sku, amount) VALUES(?,?,?,?)", (member_id, ts, sku, amt))
        db.commit()
    else:
        db.execute("UPDATE members SET last_seen_ts=? WHERE id=?", (now, member_id))
        db.commit()
```

---

## services/id_hash.py（匿名 ID）
```python
import json, hmac, hashlib
from typing import Iterable

def stable_id(embedding: Iterable[float], salt: str) -> str:
    payload = json.dumps(list(embedding), separators=(",", ":"))
    mac = hmac.new(salt.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return mac
```

---

## templates/ad.html（可選，自訂樣式）
```html
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
      <h1>{{ headline }}</h1>
      <p class="muted">特別推薦：</p>
      <ul>
        {% for x in purchases %}
        <li>{{ x['sku'] }} — 上次 {{ x['ago'] }} 前購買。<strong>今日{{ x['offer'] }}</strong></li>
        {% endfor %}
      </ul>
      <p class="muted">* 僅使用不可逆的匿名 ID；不會上傳或保存影像。</p>
    </div>
  </div>
</body>
</html>
```

---

## scripts/bootstrap_pi.sh（Pi 首次安裝）
```bash
#!/usr/bin/env bash
set -euo pipefail
sudo apt update
sudo apt install -y git python3-venv python3-dev build-essential cmake \
  libopenblas-dev liblapack-dev libatlas-base-dev \
  libjpeg-dev libpng-dev libtiff5-dev libavcodec-dev libavformat-dev \
  libswscale-dev libv4l-dev libgtk-3-dev

mkdir -p data models templates static
cp -n .env.sample .env || true
```

---

## scripts/run_all.sh（本機啟動）
```bash
#!/usr/bin/env bash
set -e
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# camera loop
nohup .venv/bin/python camera_loop.py > cam.log 2>&1 &
# web
nohup .venv/bin/python app.py > web.log 2>&1 &

echo "running. open http://raspberrypi.local:8000/"
```

---

## .github/workflows/deploy.yml（GitHub Actions → Pi）
```yaml
name: Deploy to Raspberry Pi

on:
  push:
    branches: [ "main" ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Create .env from sample
        run: |
          mkdir -p data models templates static
          cp .env.sample .env

      - name: Add SSH key
        uses: webfactory/ssh-agent@v0.9.0
        with:
          ssh-private-key: |
            ${{ secrets.PI_SSH_KEY }}

      - name: Copy files to Pi
        run: |
          rsync -avz --delete \
            -e "ssh -o StrictHostKeyChecking=no" \
            ./ ${{ secrets.PI_USER }}@${{ secrets.PI_HOST }}:${{ vars.PI_APP_DIR }}/

      - name: Remote install & restart
        run: |
          ssh -o StrictHostKeyChecking=no ${{ secrets.PI_USER }}@${{ secrets.PI_HOST }} << 'EOF'
          set -e
          cd ${{ vars.PI_APP_DIR }}
          python3 -m venv .venv
          . .venv/bin/activate
          pip install --upgrade pip
          pip install -r requirements.txt
          pkill -f "python.*app.py" || true
          pkill -f "python.*camera_loop.py" || true
          nohup .venv/bin/python camera_loop.py > cam.log 2>&1 &
          nohup .venv/bin/python app.py > web.log 2>&1 &
          echo "Deployed and restarted."
          EOF
```

---

### 接下來怎麼跑
1. 在 Pi 上先執行：`bash scripts/bootstrap_pi.sh`。
2. 建 `.env`（從 sample 複製後修改 `SECRET_KEY/ID_HASH_SALT/SQLITE_PATH`）。
3. 在 GitHub → Settings → Secrets and variables → Actions 設定：
   - `PI_HOST`, `PI_USER`, `PI_SSH_KEY`（private key PEM）
   - Variables：`PI_APP_DIR`（如 `/home/pi/app`）
4. 推到 `main`，Actions 會自動部署；iPad 連 `http://raspberrypi.local:8000/`。

> 若要走 Docker/multi-arch，我可以再加上 `docker-compose.yml` 與 buildx workflow。
