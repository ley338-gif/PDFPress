# Validierung

Lokaler Pipeline-Test in der bereitgestellten Ausführungsumgebung am 15.08.2026. Docker selbst ist in dieser Umgebung nicht installiert; deshalb konnte der Compose-Start hier nicht ausgeführt werden. Python-Backend, PyMuPDF und Tesseract 5.5.0 waren verfügbar.

## Ergebnisse

| Fixture | Status | Seiten | Direkttext | OCR | Gesamtzeit |
|---|---|---:|---:|---:|---:|
| `digital-text.pdf` | COMPLETE | 3 | 3 | 0 | 0.01 s |
| `scan.pdf` | COMPLETE | 1 | 0 | 1 | 0.63 s |
| `hybrid.pdf` | COMPLETE | 2 | 1 | 1 | 0.65 s |
| `headings-lists.pdf` | COMPLETE | 3 | 3 | 0 | 0.00 s |
| `table.pdf` | COMPLETE | 3 | 3 | 0 | 0.00 s |

Gemessener maximaler RSS des Python-Testprozesses über den kompletten Lauf: ca. 188.1 MiB. Der Wert enthält Python, PyMuPDF und alle fünf Tests; er ist kein Container-Limit.

## Automatisierte Tests

`pytest -q`: **6 passed**. Getestet werden unter anderem Healthcheck, PDF-Upload, Ablehnung ungültiger Dateien, Textnormalisierung, Zahlenerhalt sowie Markdown-Struktur für Überschriften/Listen.

## OCR Engine

Tesseract wurde gewählt, weil es CPU-first arbeitet, deutsche und englische Sprachpakete stabil verfügbar sind, keine GPU voraussetzt und TSV-Ausgabe mit Bounding Boxes und Confidence-Werten liefert. Für komplexe Layoutanalyse wäre PaddleOCR leistungsfähiger, erhöht aber Image-Größe, RAM-Verbrauch und Deployment-Komplexität deutlich.

## Bekannte Einschränkungen

- Tabellen werden derzeit heuristisch als Textstruktur behandelt; komplexe Zellgeometrie ist noch kein eigener Tabellenparser.
- Handschrift und stark degradierte Scans sind kein primärer v0.1-Fall.
- Automatische Deskew-/Orientierungskorrektur verlässt sich derzeit überwiegend auf Tesseracts Seitensegmentierung und die PDF-Rotation; eine separate Bildgeometrie-Pipeline ist nicht enthalten.
- Frontend-NPM-Abhängigkeiten konnten in dieser isolierten Laufzeit nicht aus dem Internet installiert werden. Der TypeScript/Vite-Build wurde deshalb hier nicht ausgeführt; das Dockerfile installiert diese beim Build.
