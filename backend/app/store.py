from __future__ import annotations
import asyncio
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from .models import DocumentJob
from .config import settings

ROOT = Path("/tmp/paperdrop")
ROOT.mkdir(parents=True, exist_ok=True)

class JobStore:
    def __init__(self):
        self.jobs: dict[str, DocumentJob] = {}
        self._lock = asyncio.Lock()

    async def add(self, job: DocumentJob):
        async with self._lock:
            self.jobs[job.id] = job

    def get(self, job_id: str) -> DocumentJob | None:
        return self.jobs.get(job_id)

    async def delete(self, job_id: str) -> bool:
        async with self._lock:
            job = self.jobs.pop(job_id, None)
        if not job:
            return False
        try:
            shutil.rmtree(Path(job.path).parent, ignore_errors=True)
        except Exception:
            pass
        return True

    async def cleanup_expired(self):
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.document_retention_minutes)
        expired = [job_id for job_id, job in self.jobs.items() if job.updated_at < cutoff]
        for job_id in expired:
            await self.delete(job_id)
        return len(expired)

store = JobStore()
