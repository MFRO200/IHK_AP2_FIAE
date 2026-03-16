#!/usr/bin/env bash
# ============================================================
# setup.sh — IHK AP2 FIAE Projekt auf einem neuen Rechner einrichten
# ============================================================
# Voraussetzungen:
#   - Git
#   - Docker + Docker Compose
#   - Node.js >= 18 (empfohlen: 20+)
#   - Python >= 3.10 (optional, für Seeding/OCR)
#
# Nutzung:
#   chmod +x setup.sh && ./setup.sh
# ============================================================

set -e

echo "============================================================"
echo "  IHK AP2 FIAE - Projekt-Setup"
echo "============================================================"
echo ""

# ─── 1) .env anlegen ───
if [ ! -f .env ]; then
  echo "[1/7] .env-Datei erstellen..."
  cat > .env << 'EOF'
# --- PostgreSQL ---
POSTGRES_DB=ihk_ap2
POSTGRES_USER=ihk
POSTGRES_PASSWORD=CHANGE_ME

# --- Prisma ---
DATABASE_URL=postgresql://ihk:CHANGE_ME@127.0.0.1:15432/ihk_ap2

# --- pgAdmin ---
PGADMIN_DEFAULT_EMAIL=admin@ihk.local
PGADMIN_DEFAULT_PASSWORD=admin
EOF
  echo "  .env erstellt. Bitte Passwort ggf. anpassen!"
else
  echo "[1/7] .env existiert bereits."
fi

# ─── 2) Docker-Container starten ───
echo ""
echo "[2/7] Docker-Container starten (PostgreSQL + pgAdmin)..."
docker compose up -d
echo "  Warte auf Datenbank..."
sleep 5

# Health-Check
until docker exec ihk_ap2_db pg_isready -U ihk -d ihk_ap2 > /dev/null 2>&1; do
  echo "  ... Datenbank noch nicht bereit, warte..."
  sleep 2
done
echo "  Datenbank ist bereit!"

# ─── 3) Backend-Dependencies ───
echo ""
echo "[3/7] Backend-Dependencies installieren..."
cd backend
npm install
echo "  Prisma Client generieren..."
npx prisma generate
npx prisma db push
cd ..

# ─── 4) Frontend-Dependencies ───
echo ""
echo "[4/7] Frontend-Dependencies installieren..."
cd frontend
npm install
cd ..

# ─── 5) Python-Umgebung (optional) ───
echo ""
echo "[5/7] Python-Umgebung einrichten..."
if command -v python3 &> /dev/null || command -v python &> /dev/null; then
  PYTHON_CMD=$(command -v python3 || command -v python)
  if [ ! -d .venv ]; then
    $PYTHON_CMD -m venv .venv
  fi
  source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate 2>/dev/null
  pip install --quiet psycopg python-dotenv
  echo "  Python-Umgebung bereit."
else
  echo "  Python nicht gefunden - ueberspringe (optional)"
fi

# ─── 6) Datenbank seeden ───
echo ""
echo "[6/7] Datenbank seeden..."
if [ -f seed_db.py ] && [ -f .ocr_cache.json ]; then
  if command -v python3 &> /dev/null || command -v python &> /dev/null; then
    source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate 2>/dev/null
    python seed_db.py
    echo "  Seeding abgeschlossen."
  else
    echo "  Python fehlt - Seeding uebersprungen."
    echo "  Manuell: python seed_db.py"
  fi
else
  echo "  seed_db.py oder .ocr_cache.json nicht gefunden."
  echo "  Seeding muss manuell durchgefuehrt werden."
fi

# ─── 7) PDFs konsolidieren ───
echo ""
echo "[7/7] PDFs nach storage/ konsolidieren..."
if [ -f consolidate_pdfs.py ]; then
  if command -v python3 &> /dev/null || command -v python &> /dev/null; then
    source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate 2>/dev/null
    python consolidate_pdfs.py
    echo "  Konsolidierung abgeschlossen."
  else
    echo "  Python fehlt - Konsolidierung uebersprungen."
  fi
else
  echo "  consolidate_pdfs.py nicht gefunden."
fi

# ─── Fertig ───
echo ""
echo "============================================================"
echo "  Setup abgeschlossen!"
echo ""
echo "  Starten:"
echo "    Backend:  cd backend && npm run start:dev"
echo "    Frontend: cd frontend && npm run dev"
echo ""
echo "  URLs:"
echo "    Frontend:  http://localhost:5173"
echo "    API:       http://localhost:3000/api"
echo "    Swagger:   http://localhost:3000/api/docs"
echo "    pgAdmin:   http://localhost:8080"
echo "    Prisma:    npx prisma studio (im backend/)"
echo "============================================================"
