from __future__ import annotations
import asyncio
import json
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from .config import settings

STATS_FILE = Path(settings.stats_file)

# Wie viele Tage Tagesverlauf wir aufheben, und wie viele Verarbeitungsdauern für die
# Median/p95-Schätzung. Beides sind reine Zahlen (Datum -> Zähler, Dauer in Sekunden),
# kein Bezug zu einzelnen Dokumenten oder Nutzern.
DAILY_HISTORY_DAYS = 30
MAX_DURATION_SAMPLES = 200

TOOL_KEYS = ("documents", "merge", "metadata_strip", "images_extract")


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


class UsageStats:
    """Zählt ausschließlich aggregierte Nutzungszahlen — keine Dateinamen, IPs,
    Session-IDs oder Dokumentinhalte. Persistiert in einer einzelnen JSON-Datei auf
    einem dedizierten Volume, damit die Zahlen Redeploys überstehen."""

    def __init__(self, path: Path):
        self._path = path
        self._lock = asyncio.Lock()
        self._data = self._load()
        self._durations: deque[float] = deque(self._data.get("recent_durations_seconds", []), maxlen=MAX_DURATION_SAMPLES)

    def _load(self) -> dict:
        try:
            data = json.loads(self._path.read_text())
        except Exception:
            data = {}
        data.setdefault("since", datetime.now(timezone.utc).isoformat())
        data.setdefault("total_uploads", 0)
        data.setdefault("total_page_views", 0)
        data.setdefault("total_complete", 0)
        data.setdefault("total_failed", 0)
        data.setdefault("tool_usage", {k: 0 for k in TOOL_KEYS})
        data.setdefault("daily", {})
        data.setdefault("recent_durations_seconds", [])
        return data

    def _save_locked(self) -> None:
        self._data["recent_durations_seconds"] = list(self._durations)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data))
        tmp.replace(self._path)

    def _bump_daily_locked(self, field: str) -> None:
        day = _today()
        bucket = self._data["daily"].setdefault(day, {})
        bucket[field] = bucket.get(field, 0) + 1
        cutoff = sorted(self._data["daily"].keys())[:-DAILY_HISTORY_DAYS]
        for old_day in cutoff:
            del self._data["daily"][old_day]

    async def record_upload(self) -> None:
        async with self._lock:
            self._data["total_uploads"] += 1
            self._data["tool_usage"]["documents"] += 1
            self._bump_daily_locked("uploads")
            self._save_locked()

    async def record_page_view(self) -> None:
        async with self._lock:
            self._data["total_page_views"] += 1
            self._bump_daily_locked("page_views")
            self._save_locked()

    async def record_tool_use(self, tool: str) -> None:
        async with self._lock:
            if tool in self._data["tool_usage"]:
                self._data["tool_usage"][tool] += 1
                self._save_locked()

    async def record_job_outcome(self, state: str, duration_seconds: float | None = None) -> None:
        async with self._lock:
            if state == "COMPLETE":
                self._data["total_complete"] += 1
                self._bump_daily_locked("complete")
                if duration_seconds is not None:
                    self._durations.append(round(duration_seconds, 1))
            elif state == "FAILED":
                self._data["total_failed"] += 1
                self._bump_daily_locked("failed")
            self._save_locked()

    def snapshot(self) -> dict:
        data = dict(self._data)
        durations = sorted(self._durations)
        if durations:
            mid = len(durations) // 2
            median = durations[mid] if len(durations) % 2 else (durations[mid - 1] + durations[mid]) / 2
            p95 = durations[min(len(durations) - 1, int(len(durations) * 0.95))]
        else:
            median = p95 = None
        data["processing_seconds"] = {"median": median, "p95": p95, "samples": len(durations)}
        data.pop("recent_durations_seconds", None)
        return data


stats = UsageStats(STATS_FILE)
