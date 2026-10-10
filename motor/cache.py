"""
Cache local con SQLite para failover.
"""

import sqlite3
import json
import time
from pathlib import Path

DB_PATH = Path("data/cache.db")
DB_PATH.parent.mkdir(exist_ok=True)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS cache (
        key TEXT PRIMARY KEY,
        data TEXT,
        timestamp REAL
    )""")
    conn.commit()
    conn.close()


def guardar_cache(key, data):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO cache (key, data, timestamp) VALUES (?, ?, ?)",
        (key, json.dumps(data), time.time())
    )
    conn.commit()
    conn.close()


def leer_cache(key, ttl=3600):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT data, timestamp FROM cache WHERE key = ?", (key,)
    ).fetchone()
    conn.close()

    if not row:
        return None

    data, ts = row
    if time.time() - ts > ttl:
        return None

    return json.loads(data)


init_db()
