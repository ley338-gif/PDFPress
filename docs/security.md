# Sicherheit

PDFPress behandelt jedes PDF als untrusted input.

- Es werden nur `.pdf`-Uploads akzeptiert und `%PDF-` Magic Bytes geprüft.
- Uploadgröße und Seitenanzahl sind limitiert.
- Dateisystempfade basieren ausschließlich auf serverseitig generierten UUIDs.
- Container laufen non-root, mit `no-new-privileges`, reduzierten Capabilities und read-only Root-Filesystemen.
- Temporäre Daten liegen in einem dedizierten tmpfs.
- Browser-Sicherheitsheader werden vom Backend gesetzt; Nginx dient als einziger externer Entry Point.
- PDFs werden nie ausgeführt; PyMuPDF liest/rendert sie.
- Tesseract läuft ohne Shell und mit Zeitlimit.
- Das optionale LLM sieht nur bereits extrahierten Text und darf keine Inhalte erfinden oder verändern.

## Rate-Limiting / Ressourcenschutz

- App-Ebene: `MAX_CONCURRENT_JOBS` (Default 3) begrenzt gleichzeitig laufende Verarbeitungsjobs über eine In-Process-Sperre in `backend/app/processor.py`. Ist das Limit erreicht, antwortet `POST /api/documents` mit `429` statt den Job kommentarlos in eine Warteschlange zu legen.
- Einzelne Seiten mit übergroßer MediaBox werden vor dem Rendern anhand von `MAX_RENDER_PIXELS` (Default 50 Megapixel) abgelehnt, um Speicher-Exhaustion durch präparierte PDFs zu verhindern. Das Rendern läuft zusätzlich in einem eigenen, mit `PAGE_RENDER_TIMEOUT_SECONDS` (Default 60s) hart terminierbaren Subprozess, damit eine hängende Seite keine Thread-Pool-Kapazität dauerhaft blockiert.
- nginx-Ebene: `limit_req_zone`/`limit_req` auf `/api/` (10 Requests/Minute pro IP, kleiner Burst, Antwort `429`) als zweite, vom Backend unabhängige Verteidigungslinie.
- Diese beiden Ebenen ersetzen keine Absicherung auf einem vorgeschalteten Reverse Proxy (z. B. Caddy) — dessen Konfiguration (TLS, HSTS, ggf. eigenes Rate-Limiting/IP-Allowlisting) liegt außerhalb dieses Repos und ist bei einem Deployment separat zu prüfen und zu pflegen.

## API-Dokumentation

`/api/docs`, `/api/redoc` und `/api/openapi.json` sind standardmäßig deaktiviert (`ENABLE_API_DOCS=false`), um Angreifern keine unnötige Übersicht über die interne API zu geben. Für lokale Entwicklung kann `ENABLE_API_DOCS=true` gesetzt werden.

ClamAV, CDR und Quarantäne sind bewusst nicht Bestandteil des Produkts.
