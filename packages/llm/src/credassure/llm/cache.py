"""Response cache (NFR-05): SQLite, keyed by model + prompt name@version + messages + schema.

Only temperature-0 calls are cached, which is every call this client makes. A prompt version
bump is a cache miss, so a changed prompt is never answered from an old reply.
"""

import hashlib
import json
import sqlite3
import threading
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def cache_key(
    model: str,
    name: str,
    version: str,
    messages: Sequence[Mapping[str, Any]],
    schema: Mapping[str, Any] | None,
) -> str:
    blob = json.dumps([model, name, version, list(messages), schema], sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


class ResponseCache:
    def __init__(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS llm_cache (key TEXT PRIMARY KEY, reply TEXT)")
        self._lock = threading.Lock()

    def get(self, key: str) -> str | None:
        with self._lock:
            row = self._db.execute("SELECT reply FROM llm_cache WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row[0])

    def put(self, key: str, reply: str) -> None:
        with self._lock, self._db:
            self._db.execute("INSERT OR REPLACE INTO llm_cache VALUES (?, ?)", (key, reply))
