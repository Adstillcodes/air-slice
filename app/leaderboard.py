"""Leaderboard in SQLite. Stores every play; serves the top 5 for display.

Auto-migrates a legacy leaderboard.json (pre-SQL format) on first run.
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

MAX_ENTRIES = 5


def _default_data_dir():
    if getattr(sys, "frozen", False):
        # PyInstaller build: keep data next to the executable, not the CWD
        return Path(sys.executable).parent / "data"
    return Path("data")


class Leaderboard:
    def __init__(self):
        env = os.getenv("DATA_DIR")
        data_dir = Path(env) if env else _default_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        self._db = data_dir / "leaderboard.db"
        self._init_db()
        self._migrate_legacy_json(data_dir / "leaderboard.json")

    def _connect(self):
        con = sqlite3.connect(self._db, timeout=5)
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def _init_db(self):
        con = self._connect()
        try:
            con.execute(
                """CREATE TABLE IF NOT EXISTS scores (
                       id        INTEGER PRIMARY KEY AUTOINCREMENT,
                       name      TEXT    NOT NULL,
                       score     INTEGER NOT NULL,
                       played_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
                   )"""
            )
            con.execute("CREATE INDEX IF NOT EXISTS idx_scores_score ON scores(score DESC)")
            con.commit()
        finally:
            con.close()

    def _migrate_legacy_json(self, path):
        if not path.exists():
            return
        try:
            entries = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        con = self._connect()
        try:
            if con.execute("SELECT COUNT(*) FROM scores").fetchone()[0] == 0:
                con.executemany(
                    "INSERT INTO scores (name, score) VALUES (?, ?)",
                    [(str(e["name"])[:12], int(e["score"])) for e in entries],
                )
                con.commit()
        except (KeyError, TypeError, ValueError):
            return
        finally:
            con.close()
        path.rename(path.with_suffix(".json.migrated"))

    def qualifies(self, score):
        if score <= 0:
            return False
        con = self._connect()
        try:
            rows = con.execute(
                "SELECT score FROM scores ORDER BY score DESC LIMIT ?", (MAX_ENTRIES,)
            ).fetchall()
        finally:
            con.close()
        return len(rows) < MAX_ENTRIES or score > rows[-1][0]

    def add(self, name, score):
        name = (name or "").strip()[:12] or "???"
        con = self._connect()
        try:
            con.execute("INSERT INTO scores (name, score) VALUES (?, ?)", (name, int(score)))
            con.commit()
        finally:
            con.close()

    def top(self):
        con = self._connect()
        try:
            rows = con.execute(
                "SELECT name, score FROM scores ORDER BY score DESC, played_at ASC LIMIT ?",
                (MAX_ENTRIES,),
            ).fetchall()
        finally:
            con.close()
        return [{"name": n, "score": s} for n, s in rows]
