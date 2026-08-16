# Konfiguration

Alle zentralen Einstellungen kommen aus Umgebungsvariablen.

| Variable | Default | Zweck |
|---|---:|---|
| `APP_PORT` | `8080` | Host-Port des Frontends |
| `MAX_FILE_SIZE_MB` | `100` | maximales Uploadvolumen |
| `MAX_PAGES` | `200` | maximale PDF-Seitenzahl |
| `DOCUMENT_RETENTION_MINUTES` | `60` | automatische Löschfrist |
| `OCR_LANGUAGE` | `deu+eng` | Tesseract-Sprache |
| `OCR_DPI` | `200` | Render-DPI für OCR |
| `OCR_TIMEOUT_SECONDS` | `90` | Tesseract-Timeout je Seite |
| `PROCESSING_TIMEOUT_SECONDS` | `1800` | reserviert für globale Prozesslimits |
| `LLM_ENABLED` | `false` | Ollama-Strukturierung aktivieren |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Ollama-Endpoint |
| `OLLAMA_MODEL` | `qwen3:1.7b` | lokales Modell |
