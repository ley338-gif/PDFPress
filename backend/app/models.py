from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Literal

Source = Literal["embedded_text", "ocr", "empty", "failed"]

@dataclass
class TextBlock:
    text: str
    type: str
    bbox: list[float] | None = None
    confidence: float | None = None
    source: Source = "embedded_text"

@dataclass
class PageResult:
    page: int
    source: Source
    raw_text: str = ""
    text: str = ""
    markdown: str = ""
    blocks: list[TextBlock] = field(default_factory=list)
    confidence: float | None = None
    warning: str | None = None
    width: float | None = None
    height: float | None = None

    def public(self):
        data = asdict(self)
        data.pop("raw_text", None)
        return data

@dataclass
class DocumentJob:
    id: str
    filename: str
    size_bytes: int
    path: str
    state: str = "UPLOADED"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_pages: int = 0
    processed_pages: int = 0
    text_pages: int = 0
    ocr_pages: int = 0
    pages: dict[int, PageResult] = field(default_factory=dict)
    current_message: str = "PDF hochgeladen"
    error: str | None = None
    events: list[dict] = field(default_factory=list)

    def touch(self):
        self.updated_at = datetime.now(timezone.utc)

    def status(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "size_bytes": self.size_bytes,
            "state": self.state,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "total_pages": self.total_pages,
            "processed_pages": self.processed_pages,
            "text_pages": self.text_pages,
            "ocr_pages": self.ocr_pages,
            "current_message": self.current_message,
            "error": self.error,
        }
