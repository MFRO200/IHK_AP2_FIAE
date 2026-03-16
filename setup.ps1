# ============================================================
# setup.ps1 — IHK AP2 FIAE Projekt auf einem neuen Windows-Rechner
# ============================================================
# Voraussetzungen:
#   - Git
#   - Docker Desktop
#   - Node.js >= 18 (empfohlen: 20+)
#   - Python >= 3.10 (optional, fuer Seeding/OCR)
#
# Nutzung (PowerShell als Admin):
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\setup.ps1
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================================"
Write-Host "  IHK AP2 FIAE - Projekt-Setup (Windows)"
Write-Host "============================================================"
Write-Host ""

# --- 1) .env anlegen ---
if (-not (Test-Path ".env")) {
    Write-Host "[1/7] .env-Datei erstellen..."
    @"
# --- PostgreSQL ---
POSTGRES_DB=ihk_ap2
POSTGRES_USER=ihk
POSTGRES_PASSWORD=CHANGE_ME

# --- Prisma ---
DATABASE_URL=postgresql://ihk:CHANGE_ME@127.0.0.1:15432/ihk_ap2

# --- pgAdmin ---
PGADMIN_DEFAULT_EMAIL=admin@ihk.local
PGADMIN_DEFAULT_PASSWORD=admin
"@ | Out-File -Encoding utf8 .env
    Write-Host "  .env erstellt. Bitte Passwort ggf. anpassen!"
} else {
    Write-Host "[1/7] .env existiert bereits."
}

# --- 2) Docker-Container starten ---
Write-Host ""
Write-Host "[2/7] Docker-Container starten (PostgreSQL + pgAdmin)..."
docker compose up -d
Write-Host "  Warte auf Datenbank (10s)..."
Start-Sleep -Seconds 10

# --- 3) Backend-Dependencies ---
Write-Host ""
Write-Host "[3/7] Backend-Dependencies installieren..."
Push-Location backend
npm install
Write-Host "  Prisma Client generieren..."
npx prisma generate
npx prisma db push
Pop-Location

# --- 4) Frontend-Dependencies ---
Write-Host ""
Write-Host "[4/7] Frontend-Dependencies installieren..."
Push-Location frontend
npm install
Pop-Location

# --- 5) Python-Umgebung ---
Write-Host ""
Write-Host "[5/7] Python-Umgebung einrichten..."
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCmd) {
    if (-not (Test-Path ".venv")) {
        & python -m venv .venv
    }
    & .\.venv\Scripts\Activate.ps1
    pip install --quiet psycopg python-dotenv
    Write-Host "  Python-Umgebung bereit."
} else {
    Write-Host "  Python nicht gefunden - ueberspringe (optional)"
}

# --- 6) Datenbank seeden ---
Write-Host ""
Write-Host "[6/7] Datenbank seeden..."
if ((Test-Path "seed_db.py") -and (Test-Path ".ocr_cache.json")) {
    if ($pythonCmd) {
        & .\.venv\Scripts\Activate.ps1
        python seed_db.py
        Write-Host "  Seeding abgeschlossen."
    } else {
        Write-Host "  Python fehlt - Seeding uebersprungen."
    }
} else {
    Write-Host "  seed_db.py oder .ocr_cache.json nicht gefunden."
}

# --- 7) PDFs konsolidieren ---
Write-Host ""
Write-Host "[7/7] PDFs nach storage/ konsolidieren..."
if (Test-Path "consolidate_pdfs.py") {
    if ($pythonCmd) {
        & .\.venv\Scripts\Activate.ps1
        python consolidate_pdfs.py
    } else {
        Write-Host "  Python fehlt."
    }
}

# --- Fertig ---
Write-Host ""
Write-Host "============================================================"
Write-Host "  Setup abgeschlossen!"
Write-Host ""
Write-Host "  Starten:"
Write-Host "    Backend:  cd backend; npm run start:dev"
Write-Host "    Frontend: cd frontend; npm run dev"
Write-Host ""
Write-Host "  URLs:"
Write-Host "    Frontend:  http://localhost:5173"
Write-Host "    API:       http://localhost:3000/api"
Write-Host "    Swagger:   http://localhost:3000/api/docs"
Write-Host "    pgAdmin:   http://localhost:8080"
Write-Host "============================================================"
