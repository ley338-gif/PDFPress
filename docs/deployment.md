# Deployment

## Standard

```bash
cp .env.example .env
docker compose up -d --build
```

Frontend veröffentlicht standardmäßig Port 8080. Backend ist nicht direkt am Host exponiert.

## Ressourcen

Für kleine lokale Installationen sind als Startwert 2 CPU-Kerne und 2–4 GB RAM sinnvoll. Digitale PDFs benötigen meist wenig Ressourcen; OCR kann pro aktiver Seite deutlich mehr CPU und kurzfristig mehrere hundert MB RAM beanspruchen.

Beide Container sind über `deploy.resources.limits` in `docker-compose.yml` hart gedeckelt (Backend: 2 CPUs / 3 GB RAM, Frontend: 0,5 CPU / 128 MB), damit ein einzelner rechenintensiver OCR-Job nicht die gesamte VM auslasten kann. Bei Bedarf (mehr gleichzeitige Nutzer, größere Dokumente) in `docker-compose.yml` anpassen.

## Hinter einem bestehenden Reverse Proxy (z. B. Caddy)

Läuft auf dem Host bereits ein Reverse Proxy in einem eigenen Docker-Netzwerk (z. B. `proxy`), lässt sich PDFPress darüber statt über einen Host-Port anbinden:

```bash
docker compose -f docker-compose.yml -f docker-compose.proxy.yml up -d --build
```

`docker-compose.proxy.yml` hängt den Frontend-Container zusätzlich an das externe Netzwerk `proxy` und vergibt den Containernamen `pdfpress-frontend`. Im Caddyfile genügt dann:

```caddyfile
pdfpress.example.tld {
    header Strict-Transport-Security "max-age=15552000"
    reverse_proxy pdfpress-frontend:8080
}
```

Nach Änderungen am Caddyfile: `docker exec caddy caddy reload --config /etc/caddy/Caddyfile` (kein Neustart nötig).

## Update

```bash
docker compose pull
docker compose up -d --build
```

Da Dokumente absichtlich temporär sind, gibt es keine persistente Applikationsdatenbank zu migrieren.
