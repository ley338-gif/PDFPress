from __future__ import annotations
import json
from .models import DocumentJob


def markdown_export(job: DocumentJob) -> str:
    parts = []
    for page_no in sorted(job.pages):
        page = job.pages[page_no]
        parts.append(f"<!-- page: {page_no} -->\n\n{page.markdown}".rstrip())
    return "\n\n".join(parts) + "\n"


def text_export(job: DocumentJob) -> str:
    parts = []
    for page_no in sorted(job.pages):
        page = job.pages[page_no]
        parts.append(f"--- Seite {page_no} ---\n\n{page.text}".rstrip())
    return "\n\n".join(parts) + "\n"


def json_export(job: DocumentJob) -> str:
    data = {
        "filename": job.filename,
        "pages": [job.pages[n].public() for n in sorted(job.pages)],
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"
