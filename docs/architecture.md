# Architektur

PDFPress besteht absichtlich nur aus zwei Containern: einem statisch ausgelieferten React-Frontend mit Nginx-Reverse-Proxy und einem FastAPI-Backend. Es gibt keine Datenbank und keinen Message Broker.

## Datenfluss

1. Browser lädt genau ein PDF per `POST /api/documents` hoch.
2. Backend validiert Endung, Größe und PDF-Magic-Bytes und legt die Datei in `/tmp/paperdrop/<uuid>/document.pdf` ab.
3. PyMuPDF analysiert jede Seite einzeln.
4. Brauchbarer eingebetteter Text wird direkt extrahiert. Seiten ohne brauchbaren Text werden einmal für Tesseract gerendert.
5. Blöcke werden normalisiert und regelbasiert zu Markdown strukturiert.
6. Optional kann Ollama das bereits extrahierte Markdown nur strukturell verfeinern. Fehler führen immer zum lokalen Fallback.
7. Frontend pollt echte Statusdaten und lädt bereits verfügbare Seitenergebnisse.
8. Exporter erzeugen Markdown, TXT und JSON aus denselben Seitenobjekten.
9. Manuelles Löschen oder Retention-Cleanup entfernt das komplette Job-Verzeichnis.

## Datenmodell

`DocumentJob -> PageResult -> TextBlock`. Die Seitennummer ist auf jeder Ebene explizit erhalten. `PageResult` hält `text`, `markdown`, `source`, `confidence`, `warning` und Blocks. Intern bleibt zusätzlich `raw_text` vorhanden.
