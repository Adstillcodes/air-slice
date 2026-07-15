"""Top-5 leaderboard persisted to a JSON file (survives container restarts via volume)."""

import json
import os
import threading
from pathlib import Path

MAX_ENTRIES = 5


class Leaderboard:
    def __init__(self):
        self._path = Path(os.getenv("DATA_DIR", "data")) / "leaderboard.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._scores = self._load()

    def _load(self):
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return [
                {"name": str(e["name"])[:12], "score": int(e["score"])}
                for e in data
            ][:MAX_ENTRIES]
        except (OSError, ValueError, KeyError, TypeError):
            return []

    def _save(self):
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._scores, indent=2), encoding="utf-8")
        tmp.replace(self._path)

    def qualifies(self, score):
        if score <= 0:
            return False
        with self._lock:
            if len(self._scores) < MAX_ENTRIES:
                return True
            return score > self._scores[-1]["score"]

    def add(self, name, score):
        name = (name or "").strip()[:12] or "???"
        with self._lock:
            self._scores.append({"name": name, "score": int(score)})
            self._scores.sort(key=lambda e: e["score"], reverse=True)
            del self._scores[MAX_ENTRIES:]
            self._save()

    def top(self):
        with self._lock:
            return list(self._scores)
