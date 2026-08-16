<#
Deploy-Skript fuer PDFPress: committet + pusht zu GitHub, kopiert den Code zum Server
und baut die Docker-Container dort neu. Bewusst manuell ausgeloest (kein automatischer
Trigger) -- damit Server-Deploy und der oeffentliche AGPL-Quellcode-Stand (siehe README
"Lizenz") synchron bleiben, ohne dass man das Pushen vergisst.

Nutzung (aus dem Projekt-Root):
    .\scripts\deploy.ps1
    .\scripts\deploy.ps1 -Message "Kurze Beschreibung der Aenderung"
#>
param(
    [string]$Message = "Deploy $(Get-Date -Format 'yyyy-MM-dd HH:mm')",
    [string]$ServerHost = "root@217.160.36.200",
    [string]$ServerPath = "/opt/pdfpress",
    [string]$HealthUrl = "https://pdfpress.de/api/health"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

function Step($text) { Write-Host "`n== $text ==" -ForegroundColor Cyan }

Push-Location $RepoRoot
try {
    Step "1/4  Git: committen + pushen"
    git add .
    $changes = git status --porcelain
    if ($changes) {
        git commit -m $Message
        git push
        Write-Host "Gepusht: $Message" -ForegroundColor Green
    } else {
        Write-Host "Keine lokalen Aenderungen zum Committen -- Repo ist bereits aktuell." -ForegroundColor Yellow
    }

    Step "2/4  Dateien zum Server kopieren (scp)"
    scp -r "$RepoRoot\*" "${ServerHost}:${ServerPath}/"
    if ($LASTEXITCODE -ne 0) { throw "scp fehlgeschlagen (Exit $LASTEXITCODE)" }

    Step "3/4  Container auf dem Server neu bauen"
    ssh $ServerHost "cd $ServerPath && docker compose -f docker-compose.yml -f docker-compose.proxy.yml up -d --build"
    if ($LASTEXITCODE -ne 0) { throw "Server-Build fehlgeschlagen (Exit $LASTEXITCODE)" }

    Step "4/4  Health-Check"
    Start-Sleep -Seconds 3
    try {
        $health = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 10
        Write-Host "OK: $($health | ConvertTo-Json -Compress)" -ForegroundColor Green
    } catch {
        Write-Host "WARNUNG: Health-Check gegen $HealthUrl fehlgeschlagen -- bitte manuell pruefen!" -ForegroundColor Red
    }

    Write-Host "`nFertig." -ForegroundColor Green
} finally {
    Pop-Location
}
