from __future__ import annotations
import httpx
from .config import settings

SYSTEM = """Du strukturierst extrahierten PDF-Text zu Markdown. Regeln: Inhalte niemals ergänzen, zusammenfassen, umformulieren oder korrigieren. Zahlen, Namen und Seitenzuordnung exakt erhalten. Nur Überschriften, Absätze, Listen, Tabellen und störende Zeilenumbrüche strukturieren. Gib ausschließlich Markdown zurück."""

async def refine_markdown(page_number: int, markdown: str) -> str:
    if not settings.llm_enabled or not markdown.strip():
        return markdown
    payload = {
        "model": settings.ollama_model,
        "stream": False,
        "prompt": f"{SYSTEM}\n\nSeite: {page_number}\n\n{markdown}",
        "options": {"temperature": 0},
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(f"{settings.ollama_base_url.rstrip('/')}/api/generate", json=payload)
            res.raise_for_status()
            candidate = (res.json().get("response") or "").strip()
            # Refuse suspicious output inflation; fidelity beats formatting.
            if not candidate or len(candidate) > max(len(markdown) * 1.35, len(markdown) + 200):
                return markdown
            return candidate
    except Exception:
        return markdown
