from __future__ import annotations
import csv
import html
import io
import secrets
from datetime import datetime, timedelta, timezone
import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from .config import settings
from .stats import stats, DAILY_HISTORY_DAYS
from .store import store, ROOT

router = APIRouter(prefix="/api/admin")
_security = HTTPBasic()

# Ab wie vielen gleichzeitig auf Platte liegenden Job-Ordnern wir im Dashboard warnen.
# Ein normal laufendes System räumt Jobs nach DOCUMENT_RETENTION_MINUTES auf, d.h. im
# Dauerbetrieb sollten hier nie deutlich mehr als max_concurrent_jobs Ordner liegen.
# Ein hoher Wert deutet auf einen hängenden Cleanup-Loop oder Datenmüll hin.
STORAGE_WARN_MULTIPLIER = 10


def require_admin(credentials: HTTPBasicCredentials = Depends(_security)) -> None:
    """Basic Auth gegen ein einzelnes Token aus der Config. Ohne gesetztes ADMIN_TOKEN
    ist der gesamte /api/admin-Bereich deaktiviert (404), damit er nicht versehentlich
    offen im Netz landet, weil jemand vergessen hat, das Token zu setzen."""
    if not settings.admin_token:
        raise HTTPException(404)
    valid = secrets.compare_digest(credentials.password, settings.admin_token)
    if not valid:
        raise HTTPException(401, "Ungültiges Admin-Token.", headers={"WWW-Authenticate": "Basic"})


def _storage_usage() -> tuple[int, int]:
    count, total_bytes = 0, 0
    if ROOT.exists():
        for job_dir in ROOT.iterdir():
            if job_dir.is_dir():
                count += 1
                total_bytes += sum(f.stat().st_size for f in job_dir.rglob("*") if f.is_file())
    return count, total_bytes


async def _ollama_reachable() -> bool | None:
    if not settings.llm_enabled:
        return None
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            res = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            return res.status_code == 200
    except Exception:
        return False


@router.get("/stats")
async def admin_stats(_: None = Depends(require_admin)):
    snapshot = stats.snapshot()
    job_states: dict[str, int] = {}
    for job in store.jobs.values():
        job_states[job.state] = job_states.get(job.state, 0) + 1
    storage_count, storage_bytes = _storage_usage()
    warn_threshold = settings.max_concurrent_jobs * STORAGE_WARN_MULTIPLIER
    return {
        **snapshot,
        "queue": {"active_jobs": len(store.jobs), "by_state": job_states, "max_concurrent_jobs": settings.max_concurrent_jobs},
        "storage": {
            "job_dirs": storage_count,
            "bytes": storage_bytes,
            "warn_threshold": warn_threshold,
            "warning": storage_count > warn_threshold,
        },
        "ollama_reachable": await _ollama_reachable(),
    }


@router.get("/stats.csv")
async def admin_stats_csv(_: None = Depends(require_admin)):
    snapshot = stats.snapshot()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["date", "uploads", "page_views", "complete", "failed"])
    for day in sorted(snapshot["daily"].keys()):
        bucket = snapshot["daily"][day]
        writer.writerow([day, bucket.get("uploads", 0), bucket.get("page_views", 0), bucket.get("complete", 0), bucket.get("failed", 0)])
    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=pdfpress-stats.csv"},
    )


def _bar_chart(title: str, labels: list[str], values: list[int], width: int = 640, bar_h: int = 22, color: str = "#4f7df3") -> str:
    if not values:
        return f"<h3>{html.escape(title)}</h3><p class='muted'>Keine Daten.</p>"
    max_v = max(values) or 1
    gap = 6
    height = len(values) * (bar_h + gap) + 10
    label_w = 90
    chart_w = width - label_w - 50
    rows = []
    for i, (label, value) in enumerate(zip(labels, values)):
        y = 10 + i * (bar_h + gap)
        bw = max(2, int(chart_w * value / max_v))
        rows.append(
            f'<text x="{label_w - 8}" y="{y + bar_h * 0.7}" text-anchor="end" class="lbl">{html.escape(label)}</text>'
            f'<rect x="{label_w}" y="{y}" width="{bw}" height="{bar_h}" rx="3" fill="{color}"/>'
            f'<text x="{label_w + bw + 6}" y="{y + bar_h * 0.7}" class="val">{value}</text>'
        )
    svg = (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{html.escape(title)}">'
        + "".join(rows)
        + "</svg>"
    )
    return f"<h3>{html.escape(title)}</h3>{svg}"


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(_: None = Depends(require_admin)):
    data = await admin_stats()
    days = sorted(data["daily"].keys())[-14:]
    today = datetime.now(timezone.utc).date()
    if not days:
        days = [(today - timedelta(days=i)).isoformat() for i in range(13, -1, -1)]
    upload_labels = [d[5:] for d in days]
    upload_values = [data["daily"].get(d, {}).get("uploads", 0) for d in days]
    outcome_labels = ["Abgeschlossen", "Fehlgeschlagen"]
    outcome_values = [data["total_complete"], data["total_failed"]]
    tool_labels = {"documents": "Volltext-Analyse", "merge": "PDFs zusammenführen", "metadata_strip": "Metadaten entfernen", "images_extract": "Bilder extrahieren"}
    tool_values = [data["tool_usage"].get(k, 0) for k in tool_labels]
    proc = data["processing_seconds"]
    ollama = data["ollama_reachable"]
    ollama_label = "deaktiviert" if ollama is None else ("erreichbar" if ollama else "NICHT erreichbar")

    storage = data["storage"]
    warning_html = ""
    if storage["warning"]:
        warning_html = (
            f'<div class="warn">⚠ {storage["job_dirs"]} Job-Ordner belegt (Schwelle: {storage["warn_threshold"]}). '
            f"Das ist ungewöhnlich viel für {data['queue']['max_concurrent_jobs']} gleichzeitige Jobs — "
            f"möglicherweise räumt der Cleanup-Loop nicht wie erwartet auf.</div>"
        )

    body = f"""
    {warning_html}
    <div class="grid">
      <div class="card"><span class="big">{data['total_uploads']}</span><span class="muted">Dokumente insgesamt</span></div>
      <div class="card"><span class="big">{data['total_page_views']}</span><span class="muted">Seitenaufrufe insgesamt</span></div>
      <div class="card"><span class="big">{data['queue']['active_jobs']}</span><span class="muted">Jobs aktuell aktiv (von max. {data['queue']['max_concurrent_jobs']})</span></div>
      <div class="card"><span class="big">{storage['job_dirs']}</span><span class="muted">Job-Ordner belegt ({storage['bytes'] // (1024*1024)} MB)</span></div>
      <div class="card"><span class="big">{proc['median'] if proc['median'] is not None else '–'}s</span><span class="muted">Median-Verarbeitungsdauer (p95: {proc['p95'] if proc['p95'] is not None else '–'}s, n={proc['samples']})</span></div>
      <div class="card"><span class="big">{ollama_label}</span><span class="muted">LLM-Backend (Ollama)</span></div>
    </div>
    <div class="charts">
      {_bar_chart(f"Uploads pro Tag (letzte {len(days)} Tage)", upload_labels, upload_values)}
      {_bar_chart("Verarbeitung: Erfolg vs. Fehler (gesamt)", outcome_labels, outcome_values, color="#4f7df3")}
      {_bar_chart("Tool-Nutzung (gesamt)", list(tool_labels.values()), tool_values, color="#22b8a0")}
    </div>
    <p class="muted small">Erfasst seit {html.escape(data['since'])}. Ausschließlich aggregierte Zähler — keine IPs, Dateinamen oder Dokumentinhalte.
    &nbsp;·&nbsp;<a class="csvlink" href="/api/admin/stats.csv">Tagesverlauf als CSV herunterladen</a></p>
    """
    page = f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><title>PDFPress Admin</title>
<style>
  body {{ font-family: system-ui, sans-serif; background:#0f1420; color:#e6e9f0; margin:0; padding:24px; }}
  h1 {{ font-size:1.3rem; margin:0 0 20px; }}
  h3 {{ font-size:0.95rem; color:#a9b2c6; margin:24px 0 8px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; }}
  .card {{ background:#161c2c; border:1px solid #262e44; border-radius:10px; padding:14px 16px; display:flex; flex-direction:column; gap:4px; }}
  .big {{ font-size:1.6rem; font-weight:600; }}
  .muted {{ color:#8a93a8; font-size:0.82rem; }}
  .small {{ font-size:0.75rem; margin-top:28px; }}
  .charts {{ max-width:680px; }}
  svg {{ background:#161c2c; border:1px solid #262e44; border-radius:10px; }}
  .lbl {{ fill:#a9b2c6; font-size:11px; }}
  .val {{ fill:#e6e9f0; font-size:11px; }}
  .warn {{ background:#3a2412; border:1px solid #6b3f12; color:#f0b45c; border-radius:8px; padding:10px 14px; margin-bottom:16px; font-size:0.85rem; }}
  .csvlink {{ color:#7ea3ff; }}
</style></head>
<body><h1>PDFPress — Betriebsstatistik</h1>{body}</body></html>"""
    return HTMLResponse(page)
