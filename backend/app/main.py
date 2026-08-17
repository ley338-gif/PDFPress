from __future__ import annotations
import asyncio
import json
import mimetypes
import re
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote
from fastapi import FastAPI, UploadFile, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse, PlainTextResponse, Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.formparsers import MultiPartException
from .config import settings
from .models import DocumentJob
from .store import store, ROOT
from .processor import process_job_with_timeout, try_acquire_job_slot, release_job_slot
from .exporter import markdown_export, text_export, json_export
from .stats import stats
from .tools import strip_metadata, extract_images, merge_pdfs
from .admin import router as admin_router

MAX_MERGE_FILES = 20

async def cleanup_loop():
    while True:
        await asyncio.sleep(60)
        await store.cleanup_expired()

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(cleanup_loop())
    yield
    task.cancel()

app = FastAPI(
    title="PDFPress",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.enable_api_docs else None,
    redoc_url="/api/redoc" if settings.enable_api_docs else None,
    openapi_url="/api/openapi.json" if settings.enable_api_docs else None,
)
app.add_middleware(CORSMiddleware, allow_origins=[], allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"])
app.include_router(admin_router)

@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; worker-src 'self' blob:; font-src 'self' data:; frame-ancestors 'none'"
    # Zusätzlich zum HSTS-Header, den ein vorgeschalteter Reverse Proxy (z. B. Caddy, siehe
    # docs/deployment.md) setzen sollte: greift auch, falls PDFPress direkt (ohne separaten
    # Proxy) hinter TLS deployed wird. Über Klartext-HTTP ignorieren Browser den Header ohnehin.
    response.headers["Strict-Transport-Security"] = "max-age=15552000; includeSubDomains"
    return response

@app.get("/api/health")
async def health():
    return {"status": "ok", "ocr_language": settings.ocr_language, "llm_enabled": settings.llm_enabled}

@app.get("/api/stats")
async def usage_stats():
    snapshot = stats.snapshot()
    return {"total_uploads": snapshot["total_uploads"], "since": snapshot["since"]}

@app.post("/api/track/pageview", status_code=204)
async def track_pageview():
    await stats.record_page_view()
    return Response(status_code=204)

@app.get("/api/config")
async def config_public():
    return {
        "max_file_size_mb": settings.max_file_size_mb,
        "max_pages": settings.max_pages,
        "retention_minutes": settings.document_retention_minutes,
        "ocr_language": settings.ocr_language,
        "llm_enabled": settings.llm_enabled,
        "llm_model": settings.ollama_model if settings.llm_enabled else None,
    }

async def _extract_upload(request: Request) -> UploadFile:
    """Parst das Formular manuell statt über `UploadFile = File(...)`.

    FastAPI ruft für die automatische File-Dependency intern `request.form()` ohne
    Parameter auf — Starlette begrenzt dabei jeden Multipart-Teil hart auf 1 MB
    (`MultiPartParser.max_part_size`, Default seit neueren Starlette-Versionen), egal
    wie `MAX_FILE_SIZE_MB` konfiguriert ist. Jede PDF über 1 MB würde damit unabhängig
    vom eigentlichen Limit mit einem kryptischen "error parsing the body" abgelehnt.
    """
    max_part_size = (settings.max_file_size_mb + 5) * 1024 * 1024
    try:
        form = await request.form(max_part_size=max_part_size)
    except MultiPartException:
        raise HTTPException(413, f"Datei ist größer als {settings.max_file_size_mb} MB.")
    file = form.get("file")
    if file is None or isinstance(file, str):
        raise HTTPException(422, "Kein Datei-Feld 'file' im Formular gefunden.")
    return file


@app.post("/api/documents", status_code=202)
async def upload_document(background_tasks: BackgroundTasks, request: Request):
    file = await _extract_upload(request)
    filename = Path(file.filename or "document.pdf").name
    if file.content_type and file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(415, "Der MIME-Typ des Uploads ist kein PDF.")
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(415, "Es sind ausschließlich PDF-Dateien erlaubt.")
    if not await try_acquire_job_slot():
        raise HTTPException(429, f"Server verarbeitet aktuell die maximale Anzahl gleichzeitiger Dokumente ({settings.max_concurrent_jobs}). Bitte in Kürze erneut versuchen.")
    job_id = str(uuid.uuid4())
    job_dir = ROOT / job_id
    try:
        job_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
        target = job_dir / "document.pdf"
        max_bytes = settings.max_file_size_mb * 1024 * 1024
        size = 0
        first = b""
        with target.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                if not first:
                    first = chunk[:8]
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(413, f"Datei ist größer als {settings.max_file_size_mb} MB.")
                out.write(chunk)
        if not first.startswith(b"%PDF-"):
            raise HTTPException(415, "Die Datei besitzt keine gültige PDF-Signatur.")
        job = DocumentJob(id=job_id, filename=filename, size_bytes=size, path=str(target))
        await store.add(job)
        background_tasks.add_task(process_job_with_timeout, job)
        await stats.record_upload()
        return job.status()
    except Exception:
        shutil.rmtree(job_dir, ignore_errors=True)
        await release_job_slot()
        raise


_UNSAFE_DISPOSITION_CHARS = re.compile(r'[\x00-\x1f\x7f"\\]')


def content_disposition(filename: str, disposition: str = "attachment") -> str:
    """RFC 6266 compliant Content-Disposition header value.

    filename may contain quotes, control characters, or non-ASCII text (it comes from the
    original uploaded filename). The plain `filename` parameter gets an escaped ASCII-only
    fallback; the `filename*` parameter carries the full UTF-8 name for modern browsers.
    """
    ascii_fallback = _UNSAFE_DISPOSITION_CHARS.sub("_", filename.encode("ascii", "replace").decode("ascii")) or "download"
    encoded = quote(filename, safe="")
    return f"{disposition}; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded}"


async def _read_and_validate_pdf(file: UploadFile) -> bytes:
    if file.content_type and file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(415, "Der MIME-Typ des Uploads ist kein PDF.")
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    chunks: list[bytes] = []
    size = 0
    first = b""
    while chunk := await file.read(1024 * 1024):
        if not first:
            first = chunk[:8]
        size += len(chunk)
        if size > max_bytes:
            raise HTTPException(413, f"Datei ist größer als {settings.max_file_size_mb} MB.")
        chunks.append(chunk)
    if not first.startswith(b"%PDF-"):
        raise HTTPException(415, "Die Datei besitzt keine gültige PDF-Signatur.")
    return b"".join(chunks)


async def _extract_uploads(request: Request) -> list[UploadFile]:
    """Wie `_extract_upload`, aber für mehrere Dateien unter dem Formularfeld 'files'."""
    max_part_size = (settings.max_file_size_mb + 5) * 1024 * 1024
    try:
        form = await request.form(max_part_size=max_part_size)
    except MultiPartException:
        raise HTTPException(413, f"Datei ist größer als {settings.max_file_size_mb} MB.")
    files = [f for f in form.getlist("files") if not isinstance(f, str)]
    if len(files) < 2:
        raise HTTPException(422, "Bitte mindestens zwei PDF-Dateien zum Zusammenführen auswählen.")
    if len(files) > MAX_MERGE_FILES:
        raise HTTPException(413, f"Maximal {MAX_MERGE_FILES} Dateien auf einmal zusammenführbar.")
    return files


@app.post("/api/tools/merge")
async def tool_merge(request: Request):
    uploads = await _extract_uploads(request)
    datas = [await _read_and_validate_pdf(f) for f in uploads]
    try:
        result = merge_pdfs(datas)
    except Exception:
        raise HTTPException(422, "Mindestens eine PDF konnte nicht verarbeitet werden (evtl. verschlüsselt oder beschädigt).")
    await stats.record_tool_use("merge")
    return Response(result, media_type="application/pdf", headers={"Content-Disposition": content_disposition("zusammengefuehrt.pdf")})


@app.post("/api/tools/metadata/strip")
async def tool_strip_metadata(request: Request):
    file = await _extract_upload(request)
    data = await _read_and_validate_pdf(file)
    try:
        result = strip_metadata(data)
    except Exception:
        raise HTTPException(422, "PDF konnte nicht verarbeitet werden (evtl. verschlüsselt oder beschädigt).")
    await stats.record_tool_use("metadata_strip")
    stem = Path(file.filename or "document.pdf").stem
    return Response(result, media_type="application/pdf", headers={"Content-Disposition": content_disposition(f"{stem}-ohne-metadaten.pdf")})


@app.post("/api/tools/images/extract")
async def tool_extract_images(request: Request):
    file = await _extract_upload(request)
    data = await _read_and_validate_pdf(file)
    try:
        result = extract_images(data)
    except Exception:
        raise HTTPException(422, "PDF konnte nicht verarbeitet werden (evtl. verschlüsselt oder beschädigt).")
    if not result:
        raise HTTPException(404, "In diesem PDF wurden keine eingebetteten Bilder gefunden.")
    await stats.record_tool_use("images_extract")
    stem = Path(file.filename or "document.pdf").stem
    return Response(result, media_type="application/zip", headers={"Content-Disposition": content_disposition(f"{stem}-bilder.zip")})


def require_job(job_id: str) -> DocumentJob:
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "Dokument nicht gefunden oder bereits gelöscht.")
    return job

@app.get("/api/documents/{job_id}")
async def document(job_id: str):
    job = require_job(job_id)
    return {**job.status(), "pages": [job.pages[n].public() for n in sorted(job.pages)]}

@app.get("/api/documents/{job_id}/status")
async def status(job_id: str):
    return require_job(job_id).status()

@app.get("/api/documents/{job_id}/pages")
async def pages(job_id: str):
    job = require_job(job_id)
    return [job.pages[n].public() for n in sorted(job.pages)]

@app.get("/api/documents/{job_id}/pages/{page_no}")
async def page(job_id: str, page_no: int):
    job = require_job(job_id)
    if page_no not in job.pages:
        raise HTTPException(404, "Seite wurde noch nicht verarbeitet oder existiert nicht.")
    return job.pages[page_no].public()

@app.get("/api/documents/{job_id}/file")
async def original_file(job_id: str):
    job = require_job(job_id)
    return FileResponse(job.path, media_type="application/pdf", filename=job.filename, content_disposition_type="inline")

@app.get("/api/documents/{job_id}/export/markdown")
async def export_markdown(job_id: str):
    job = require_job(job_id)
    return Response(markdown_export(job), media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": content_disposition(f"{Path(job.filename).stem}.md")})

@app.get("/api/documents/{job_id}/export/text")
async def export_text(job_id: str):
    job = require_job(job_id)
    return Response(text_export(job), media_type="text/plain; charset=utf-8", headers={"Content-Disposition": content_disposition(f"{Path(job.filename).stem}.txt")})

@app.get("/api/documents/{job_id}/export/json")
async def export_json(job_id: str):
    job = require_job(job_id)
    return Response(json_export(job), media_type="application/json; charset=utf-8", headers={"Content-Disposition": content_disposition(f"{Path(job.filename).stem}.json")})

@app.get("/api/documents/{job_id}/events")
async def events(job_id: str):
    require_job(job_id)
    async def stream():
        last = None
        while True:
            job = store.get(job_id)
            if not job:
                yield "event: deleted\ndata: {}\n\n"
                return
            payload = json.dumps(job.status(), ensure_ascii=False)
            if payload != last:
                yield f"event: status\ndata: {payload}\n\n"
                last = payload
            if job.state in {"COMPLETE", "FAILED"}:
                return
            await asyncio.sleep(0.5)
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.delete("/api/documents/{job_id}", status_code=204)
async def delete(job_id: str):
    if not await store.delete(job_id):
        raise HTTPException(404, "Dokument nicht gefunden.")
    return Response(status_code=204)
