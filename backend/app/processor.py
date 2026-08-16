from __future__ import annotations
import asyncio
import multiprocessing
from pathlib import Path
import fitz
from .models import DocumentJob, PageResult
from .structure import clean_text, extract_embedded_blocks, blocks_to_markdown, structure_ocr_lines, suppress_repeated_headers_footers
from .ocr import correct_orientation, preprocess_image, run_tesseract_tsv
from .config import settings
from .llm import refine_markdown

MIN_USEFUL_CHARS = 24


class _ConcurrencyLimiter:
    """Non-blocking admission control: rejects instead of queuing once the limit is hit."""

    def __init__(self, limit: int):
        self._limit = limit
        self._count = 0
        self._lock = asyncio.Lock()

    async def try_acquire(self) -> bool:
        async with self._lock:
            if self._count >= self._limit:
                return False
            self._count += 1
            return True

    async def release(self) -> None:
        async with self._lock:
            self._count = max(0, self._count - 1)


_job_limiter = _ConcurrencyLimiter(settings.max_concurrent_jobs)


async def try_acquire_job_slot() -> bool:
    return await _job_limiter.try_acquire()


async def release_job_slot() -> None:
    await _job_limiter.release()


def _embedded_is_useful(text: str) -> bool:
    cleaned = "".join(ch for ch in text if ch.isprintable()).strip()
    alpha_num = sum(ch.isalnum() for ch in cleaned)
    return len(cleaned) >= MIN_USEFUL_CHARS and alpha_num >= 12


def _render_page(page: fitz.Page, target: Path) -> None:
    zoom = settings.ocr_dpi / 72.0
    width_px = page.rect.width * zoom
    height_px = page.rect.height * zoom
    if width_px * height_px > settings.max_render_pixels:
        raise ValueError(
            f"Seite ist zu groß zum Rendern ({int(width_px)}x{int(height_px)} px bei {settings.ocr_dpi} DPI, "
            f"Limit {settings.max_render_pixels} Pixel)."
        )
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    pix.save(str(target))


def _render_page_worker(pdf_path: str, page_index: int, target: str, queue: multiprocessing.Queue) -> None:
    try:
        with fitz.open(pdf_path) as doc:
            _render_page(doc[page_index], Path(target))
        queue.put(("ok", None))
    except Exception as exc:
        queue.put(("error", str(exc)))


def render_page_isolated(pdf_path: str, page_index: int, target: Path) -> None:
    """Renders a single page in a separate, killable process.

    asyncio.wait_for cannot actually stop a fitz call once it's running in native code —
    cancelling the coroutine just stops waiting for it, the thread-pool worker keeps
    running underneath. A subprocess can be terminated for real, so a pathological page
    (see MAX_RENDER_PIXELS) can't tie up worker capacity indefinitely.
    """
    ctx = multiprocessing.get_context("spawn")
    queue: multiprocessing.Queue = ctx.Queue()
    proc = ctx.Process(target=_render_page_worker, args=(pdf_path, page_index, str(target), queue))
    proc.start()
    proc.join(settings.page_render_timeout_seconds)
    if proc.is_alive():
        proc.terminate()
        proc.join(5)
        if proc.is_alive():
            proc.kill()
            # Falls der Kindprozess in einem unkillbaren Systemaufruf hängt (D-State),
            # liefert SIGKILL das Signal, aber der Kernel beendet den Prozess erst beim
            # Rückkehren aus dem Syscall — das kann beliebig lange dauern. Ein join() ohne
            # Timeout würde hier den aufrufenden Thread-Pool-Worker (asyncio.to_thread)
            # unbegrenzt blockieren und damit genau das Leck reproduzieren, das die
            # Subprozess-Isolation verhindern soll. Timeout + kontrolliertes Aufgeben statt
            # unbegrenzt warten; der Kindprozess bleibt im Worst Case als Waise zurück, was
            # ein bekanntes OS-Limit bei D-State-Prozessen ist, kein Regressionsrisiko.
            proc.join(5)
        raise TimeoutError(f"Seitenrendering hat das Zeitlimit von {settings.page_render_timeout_seconds} Sekunden überschritten und wurde beendet.")
    if queue.empty():
        raise RuntimeError("Seitenrendering wurde unerwartet beendet (möglicherweise durch Speichermangel).")
    status, message = queue.get()
    if status == "error":
        raise ValueError(message)

async def process_job(job: DocumentJob):
    try:
        job.state = "ANALYZING"
        job.current_message = "Dokument wird analysiert"
        job.touch()
        with fitz.open(job.path) as doc:
            if doc.needs_pass:
                raise ValueError("Das PDF ist verschlüsselt und benötigt ein Passwort.")
            job.total_pages = len(doc)
            if job.total_pages == 0:
                raise ValueError("Das PDF enthält keine Seiten.")
            if job.total_pages > settings.max_pages:
                raise ValueError(f"Das PDF enthält {job.total_pages} Seiten; erlaubt sind maximal {settings.max_pages}.")
            workdir = Path(job.path).parent
            for index in range(len(doc)):
                page_no = index + 1
                page = doc[index]
                job.state = "EXTRACTING"
                job.current_message = f"Seite {page_no} / {job.total_pages} wird analysiert"
                job.touch()
                raw = page.get_text("text") or ""
                if _embedded_is_useful(raw):
                    blocks = extract_embedded_blocks(page.get_text("dict"))
                    text = clean_text("\n\n".join(b.text for b in blocks) or raw)
                    markdown = blocks_to_markdown(blocks) or text
                    result = PageResult(page=page_no, source="embedded_text", raw_text=raw, text=text, markdown=markdown, blocks=blocks, confidence=1.0, width=page.rect.width, height=page.rect.height)
                    job.text_pages += 1
                else:
                    job.state = "OCR"
                    job.current_message = f"Seite {page_no} / {job.total_pages} wird per OCR verarbeitet"
                    image = workdir / f"page-{page_no}.png"
                    try:
                        await asyncio.to_thread(render_page_isolated, job.path, index, image)
                        await asyncio.to_thread(correct_orientation, image)
                        prepped = await asyncio.to_thread(preprocess_image, image)
                        lines, confidence = await asyncio.to_thread(run_tesseract_tsv, prepped, settings.ocr_language)
                        blocks = structure_ocr_lines(lines)
                        raw_text = "\n".join(line[0] for line in lines)
                        text = clean_text(raw_text)
                        markdown = blocks_to_markdown(blocks) or text
                        warning = "Niedrige OCR-Erkennungsqualität" if confidence is not None and confidence < 0.70 else None
                        source = "ocr" if text else "empty"
                        result = PageResult(page=page_no, source=source, raw_text=raw_text, text=text, markdown=markdown, blocks=blocks, confidence=confidence, warning=warning, width=page.rect.width, height=page.rect.height)
                        job.ocr_pages += 1
                    except Exception as exc:
                        result = PageResult(page=page_no, source="failed", warning=str(exc), width=page.rect.width, height=page.rect.height)
                job.state = "STRUCTURING"
                job.current_message = f"Seite {page_no} wird strukturiert"
                result.markdown = await refine_markdown(page_no, result.markdown)
                job.pages[page_no] = result
                job.processed_pages = page_no
                job.touch()
        suppress_repeated_headers_footers(job.pages)
        job.state = "COMPLETE"
        job.current_message = "Verarbeitung abgeschlossen"
        job.touch()
    except Exception as exc:
        job.state = "FAILED"
        job.error = str(exc)
        job.current_message = "Verarbeitung fehlgeschlagen"
        job.touch()


async def process_job_with_timeout(job: DocumentJob):
    try:
        await asyncio.wait_for(process_job(job), timeout=settings.processing_timeout_seconds)
    except asyncio.TimeoutError:
        job.state = "FAILED"
        job.error = f"Verarbeitung hat das Zeitlimit von {settings.processing_timeout_seconds} Sekunden überschritten."
        job.current_message = "Verarbeitung wegen Zeitüberschreitung abgebrochen"
        job.touch()
    finally:
        await release_job_slot()
