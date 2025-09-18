"""SQLite helper utilities for the Raspberry Pi face-ad MVP."""
from __future__ import annotations

import random
import sqlite3
import time

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

_SKUS = [
    "牛奶",
    "咖啡豆",
    "麵包",
    "蘋果",
    "洗衣精",
    "牙膏",
    "泡麵",
    "雞蛋",
]

_connections: dict[str, sqlite3.Connection] = {}

def get_db(path: str) -> sqlite3.Connection:
    """Return a cached SQLite connection for ``path``."""
    conn = _connections.get(path)
    if conn is None:
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        _connections[path] = conn
    return conn

def init_db(path: str) -> None:
    """Initialise the SQLite schema if it does not yet exist."""
    conn = get_db(path)
    conn.executescript(SCHEMA)
    conn.commit()

def ensure_member_and_seed(conn: sqlite3.Connection, member_id: str) -> None:
    """Ensure that ``member_id`` exists and generate mock purchases if new."""
    now = int(time.time())
    cur = conn.execute("SELECT id FROM members WHERE id=?", (member_id,))
    row = cur.fetchone()

    if row is None:
        conn.execute(
            "INSERT INTO members(id, first_seen_ts, last_seen_ts) VALUES(?,?,?)",
            (member_id, now, now),
        )
        base = now
        for i in range(5):
            ts = base - (i + 1) * random.randint(3600, 86400)
            sku = random.choice(_SKUS)
            amt = random.randint(1, 3)
            conn.execute(
                "INSERT INTO purchases(id, ts, sku, amount) VALUES(?,?,?,?)",
                (member_id, ts, sku, amt),
            )
        conn.commit()
    else:
        conn.execute(
            "UPDATE members SET last_seen_ts=? WHERE id=?",
            (now, member_id),
        )
        conn.commit()
