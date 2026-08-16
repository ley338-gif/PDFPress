from __future__ import annotations
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

STATS_FILE = Path("/data/stats.json")


class UsageStats:
    """Zählt nur, wie viele Dokumente insgesamt eingereicht wurden — keine Dateinamen,
    keine IPs, keine Inhalte. Persistiert in einer einzelnen JSON-Datei auf einem
    dedizierten Volume, damit die Zahl Redeploys übersteht."""

    def __init__(self, path: Path):
        self._path = path
        self._lock = asyncio.Lock()
        self._data = self._load()

    def _load(self) -> dict:
        try:
            return json.loads(self._path.read_text())
        except Exception:
            return {"total_uploads": 0, "since": datetime.now(timezone.utc).isoformat()}

    async def record_upload(self) -> None:
        async with self._lock:
            self._data["total_uploads"] += 1
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data))
            tmp.replace(self._path)

    def snapshot(self) -> dict:
        return dict(self._data)


stats = UsageStats(STATS_FILE)
