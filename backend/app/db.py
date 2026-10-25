"""SQLite storage: games, analysis results, engine and coach caches, drills."""

import json
import sqlite3
import threading
import time
from typing import Any

import sqlite_vec

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY,
    pgn TEXT NOT NULL,
    headers TEXT NOT NULL,
    created_at REAL NOT NULL,
    analysis TEXT,
    summary TEXT
);
CREATE TABLE IF NOT EXISTS engine_cache (
    key TEXT PRIMARY KEY,
    lines TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS coach_cache (
    game_id TEXT NOT NULL,
    ply INTEGER NOT NULL,
    kind TEXT NOT NULL,
    extra TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL,
    sources TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (game_id, ply, kind, extra)
);
CREATE TABLE IF NOT EXISTS drills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,
    ply INTEGER NOT NULL,
    fen TEXT NOT NULL,
    played_san TEXT NOT NULL,
    solution_uci TEXT NOT NULL,
    solution_san TEXT NOT NULL,
    classification TEXT NOT NULL,
    themes TEXT NOT NULL,
    phase TEXT NOT NULL,
    ease REAL NOT NULL DEFAULT 2.5,
    interval REAL NOT NULL DEFAULT 0,
    reps INTEGER NOT NULL DEFAULT 0,
    lapses INTEGER NOT NULL DEFAULT 0,
    due REAL NOT NULL,
    created_at REAL NOT NULL,
    UNIQUE (game_id, ply)
);
CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class DB:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.enable_load_extension(True)
        sqlite_vec.load(self.conn)
        self.conn.enable_load_extension(False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        self.lock = threading.Lock()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self.lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def executemany(self, sql: str, rows: list[tuple]) -> None:
        with self.lock:
            self.conn.executemany(sql, rows)
            self.conn.commit()

    def one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        with self.lock:
            return self.conn.execute(sql, params).fetchone()

    def all(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(sql, params).fetchall()

    # engine cache
    def engine_get(self, key: str) -> Any | None:
        row = self.one("SELECT lines FROM engine_cache WHERE key = ?", (key,))
        return json.loads(row["lines"]) if row else None

    def engine_put(self, key: str, lines: Any) -> None:
        self.execute("INSERT OR REPLACE INTO engine_cache (key, lines) VALUES (?, ?)", (key, json.dumps(lines)))

    # kv settings
    def kv_get(self, key: str, default: Any = None) -> Any:
        row = self.one("SELECT value FROM kv WHERE key = ?", (key,))
        return json.loads(row["value"]) if row else default

    def kv_set(self, key: str, value: Any) -> None:
        self.execute("INSERT OR REPLACE INTO kv (key, value) VALUES (?, ?)", (key, json.dumps(value)))

    def clear_user_data(self) -> None:
        """Games, reviews, drills, sides and the linked account. Engine cache and knowledge base stay."""
        with self.lock:
            for table in ("games", "coach_cache", "drills", "kv"):
                self.conn.execute(f"DELETE FROM {table}")
            self.conn.commit()


db = DB(settings.db_path)


def now() -> float:
    return time.time()
