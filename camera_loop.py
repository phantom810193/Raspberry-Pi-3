"""Camera loop that generates anonymised member IDs using face embeddings."""
from __future__ import annotations

import os
import signal
import time
from pathlib import Path
from typing import Dict

import cv2
import face_recognition
import numpy as np
from dotenv import load_dotenv

from db import ensure_member_and_seed, get_db, init_db
from services.id_hash import stable_id

load_dotenv()

SQLITE_PATH = os.getenv("SQLITE_PATH", "./data/app.db")
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
FRAME_WIDTH = int(os.getenv("FRAME_WIDTH", "640"))
FRAME_HEIGHT = int(os.getenv("FRAME_HEIGHT", "480"))
ID_HASH_SALT = os.getenv("ID_HASH_SALT", "please-change-me")
COOLDOWN_SEC = float(os.getenv("COOLDOWN_SEC", "3.0"))

running = True
last_emit: Dict[str, float] = {}

def _handle_stop(sig, frame):  # type: ignore[override]
    global running
    running = False

signal.signal(signal.SIGINT, _handle_stop)
signal.signal(signal.SIGTERM, _handle_stop)

Path(SQLITE_PATH).parent.mkdir(parents=True, exist_ok=True)
init_db(SQLITE_PATH)

conn = get_db(SQLITE_PATH)
cap = cv2.VideoCapture(CAMERA_INDEX)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

if not cap.isOpened():
    raise SystemExit("Camera open failed")

print("[camera] running… Press Ctrl+C to stop")

try:
    while running:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.1)
            continue

        rgb = frame[:, :, ::-1]
        boxes = face_recognition.face_locations(rgb, model="hog")
        if not boxes:
            time.sleep(0.15)
            continue

        encodings = face_recognition.face_encodings(rgb, boxes)
        now = time.time()

        for enc in encodings:
            vector = np.round(enc, 3).tolist()
            member_id = stable_id(vector, ID_HASH_SALT)

            last = last_emit.get(member_id, 0.0)
            if now - last < COOLDOWN_SEC:
                continue
            last_emit[member_id] = now

            ensure_member_and_seed(conn, member_id)
            print(f"[camera] seen {member_id}")

        time.sleep(0.15)
finally:
    cap.release()
    conn.close()
    print("[camera] stopped")
