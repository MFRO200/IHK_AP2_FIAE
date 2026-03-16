# IHK AP2 FIAE – Prüfungsanalyse

> **Vue 3 + NestJS + Prisma + PostgreSQL (Docker)** – Full-Stack-Anwendung zur Analyse von IHK-Abschlussprüfungen (Fachinformatiker Anwendungsentwicklung)

## Tech-Stack

| Komponente | Technologie |
|---|---|
| **Frontend** | [Vue 3](https://vuejs.org/) + [Vuetify 3](https://vuetifyjs.com/) + TypeScript (Vite) |
| **Backend** | [NestJS](https://nestjs.com/) 10 (TypeScript) |
| **ORM** | [Prisma](https://www.prisma.io/) 5 |
| **Datenbank** | PostgreSQL 16 (Docker) |
| **API-Doku** | Swagger UI (`/api/docs`) |
| **DB-Browser** | Prisma Studio / pgAdmin |
| **Daten-Pipeline** | Python 3.13 (OCR, Seed) |

## Features

- **Dashboard** mit KPI-Karten und Statistiken pro Bereich
- **Prüfungsübersicht** mit Detailansicht, Dokumenten und Treffern
- **Suchbegriff-Analyse** mit Gruppierung nach Prüfungszeitraum und Aufgabe/Lösung-Filter
- **Volltext-Suche** über 1.653 OCR-Seiten (PostgreSQL `ts_vector` mit GIN-Index)
- **PDF-Viewer** mit Seiten-Sprung zu Fundstellen (`#page=X`)
- **PDF-Versionierung** – Original + bearbeitete Kopien mit Zeitstempel und Upload
- **REST-API** mit 6 CRUD-Modulen: Prüfungen, Dokumente, Seiten, Suchbegriffe, Treffer, Versionen
- **Portables Storage** – alle PDFs konsolidiert in `storage/pdfs/` für einfache Migration
- **Score-Tabelle** mit 614 Suchbegriffen in Kategorien A/B/C/D
- **Seed-Pipeline** zum reproduzierbaren Befüllen der DB aus OCR-Cache + HTML-Ergebnissen

---

## Installation auf einem neuen Rechner

### Voraussetzungen
- **Git**
- **Docker Desktop** (inkl. Docker Compose)
- **Node.js** ≥ 18 (empfohlen: 20+)
- **Python** ≥ 3.10 (nur für Seeding/OCR/Konsolidierung)

### Automatisches Setup

**Linux/macOS/Git Bash:**
```bash
git clone https://github.com/MFRO200/IHK_AP2_FIAE.git
cd IHK_AP2_FIAE
chmod +x setup.sh && ./setup.sh
```

**Windows (PowerShell):**
```powershell
git clone https://github.com/MFRO200/IHK_AP2_FIAE.git
cd IHK_AP2_FIAE
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup.ps1
```

### Manuelles Setup (Schritt für Schritt)

#### 1. Repository klonen & .env erstellen
```bash
git clone https://github.com/MFRO200/IHK_AP2_FIAE.git
cd IHK_AP2_FIAE
cp .env.example .env       # Secrets anpassen
```

#### 2. Docker-Container starten
```bash
docker compose up -d       # PostgreSQL (Port 15432) + pgAdmin (Port 8080)
```

#### 3. Backend einrichten
```bash
cd backend
npm install
npx prisma generate
npx prisma db push
cd ..
```

#### 4. Frontend einrichten
```bash
cd frontend
npm install
cd ..
```

#### 5. Datenbank seeden (Python)
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install psycopg python-dotenv
python seed_db.py
```

#### 6. PDFs konsolidieren
```bash
python consolidate_pdfs.py
```
> Kopiert alle 150 PDFs nach `storage/pdfs/<Zeitraum>/` und registriert sie als Version 1 (Original) in der DB.

#### 7. PDFs bereitstellen
Die PDF-Dateien sind zu groß für Git. Du musst sie separat übertragen:
- **Option A:** `storage/`-Ordner per USB/Cloud kopieren
- **Option B:** Original-PDFs in `AP_IHK_Anwendungsentwicklung/` ablegen und `python consolidate_pdfs.py` ausführen

### Starten

```bash
# Terminal 1 — Backend
cd backend && npm run start:dev

# Terminal 2 — Frontend
cd frontend && npm run dev

# Optional — Ollama für KI-Bewertung (Docker)
docker run -d --name ollama -p 11434:11434 -v ollama:/root/.ollama ollama/ollama
docker exec ollama ollama pull llama3.2:3b
# Für Bild-/Diagramm-Bewertung (Vision-Modell, ~7 GB):
# docker exec ollama ollama pull llama3.2-vision:11b
```

### URLs

| Service | URL |
|---|---|
| **Frontend** | http://localhost:5173 |
| **API** | http://localhost:3000/api |
| **Swagger** | http://localhost:3000/api/docs |
| **pgAdmin** | http://localhost:8080 |
| **Prisma Studio** | `cd backend && npx prisma studio` |

---

## Lösungen eingeben & KI-Bewertung

### Wo trage ich Lösungen ein?

1. **Prüfung öffnen:** Im Frontend auf eine Prüfung klicken → **„Bearbeiten"**-Button
2. **Aufgaben bearbeiten:** Links das PDF der Aufgabenstellung, rechts das Antwort-Formular
   - Aufgabe (z. B. `1a`, `2b`) eintragen
   - Antworttext als Freitext eingeben
   - **Bilder / PDFs hochladen:** Button „Bild / PDF hochladen" unter jeder Aufgabe
3. **Speichern:** Jede Aufgabe einzeln mit dem Speichern-Button sichern
4. **Mehrere Durchläufe:** Die Prüfung kann mehrfach bearbeitet werden (Durchlauf 1, 2, …)

### Handschriftliche Lösungen & Diagramme als PDF/Bild hochladen

**Ja, das geht!** Du kannst handgeschriebene Lösungen und selbst gezeichnete Diagramme (UML, Sequenz, ER, Klassen etc.) als Bild oder PDF hochladen:

- **Unterstützte Formate:** JPG, PNG, GIF, WebP, BMP, PDF
- **Hochladen:** Im Bearbeitungs-Modus einer Prüfung auf „Bild / PDF hochladen" klicken
- **Mehrere Dateien:** Pro Aufgabe können beliebig viele Bilder/PDFs hochgeladen werden
- **Galerie:** Hochgeladene Bilder werden als Thumbnails angezeigt und können per Klick vergrößert werden

### KI-Bewertung (mit Ollama oder OpenAI)

Nach dem Eingeben der Lösungen: **Bewertungsseite** aufrufen (über die Prüfungsdetailseite → „KI-Bewertung").

| Antwort-Typ | Was passiert | Modell |
|---|---|---|
| **Nur Text** | Der Antworttext wird mit der Musterlösung verglichen | `llama3.2:3b` / `gpt-4o-mini` |
| **Text + Bilder** | Text + hochgeladene Bilder werden an ein Vision-Modell gesendet | `llama3.2-vision:11b` / `gpt-4o` |
| **Nur Bilder** | Die Bilder werden direkt an das Vision-Modell analysiert | `llama3.2-vision:11b` / `gpt-4o` |

**Hinweise:**
- Ollama auf CPU dauert ca. 1–3 Minuten pro Aufgabe (Text), Vision-Modelle brauchen deutlich länger
- Für **Vision-Modelle** (Bilder/Diagramme) muss `llama3.2-vision:11b` installiert sein oder ein OpenAI-Key konfiguriert sein
- Die Bewertung wird automatisch in der DB gespeichert und kann in der Bewertungsübersicht eingesehen werden

---

## API-Endpoints

| Methode | Endpoint | Beschreibung |
|---|---|---|
| `GET` | `/api/pruefungen` | Alle 48 Prüfungszeiträume |
| `GET` | `/api/pruefungen/:id` | Prüfung mit Dokumenten |
| `GET` | `/api/dokumente?typ=Aufgabe` | Dokumente filtern |
| `GET` | `/api/dokumente/:id/pdf` | PDF streamen (aus storage/) |
| `GET` | `/api/dokumente/:id/versionen` | Alle Versionen |
| `POST` | `/api/dokumente/:id/versionen/upload` | Bearbeitete Version hochladen |
| `GET` | `/api/suchbegriffe?section=A` | Begriffe nach Score-Section |
| `GET` | `/api/suchbegriffe/search?q=API` | Begriffe suchen |
| `GET` | `/api/seiten/search?q=Pseudocode` | **Volltext-Suche** (OCR) |
| `GET` | `/api/treffer/stats` | Statistik pro Section |

## Datenbank-Schema

```
pruefungen (48)  ──<  dokumente (150)  ──<  seiten (1.653)
                                        ──<  treffer (4.372)  >──  suchbegriffe (614)
                                        ──<  dokument_versionen
```

6 Tabellen, 8 Indizes (inkl. GIN für Volltext), 3 Views.

## Projektstruktur

```
├── frontend/                 # Vue 3 + Vuetify 3 (TypeScript)
│   ├── src/
│   │   ├── views/            # Dashboard, Prüfungen, Suchbegriffe, Suche, PDF-Viewer
│   │   ├── services/api.ts   # Axios API-Layer
│   │   ├── types/            # TypeScript-Interfaces
│   │   └── router/           # Vue Router
│   └── vite.config.ts        # Proxy /api → localhost:3000
├── backend/                  # NestJS API (TypeScript)
│   ├── src/
│   │   ├── prisma/           # PrismaService (DB-Connection)
│   │   ├── pruefungen/       # CRUD: Prüfungszeiträume
│   │   ├── dokumente/        # CRUD + PDF-Streaming
│   │   ├── seiten/           # OCR-Seiten + Volltext-Suche
│   │   ├── suchbegriffe/     # Score-Tabelle Begriffe
│   │   ├── treffer/          # Treffer + Statistik
│   │   ├── versionen/        # PDF-Versionierung + Upload
│   │   └── main.ts           # Swagger, CORS, Validation
│   └── prisma/schema.prisma  # Datenmodell (6 Tabellen)
├── storage/                  # Konsolidierte PDFs (nicht in Git)
│   └── pdfs/
│       ├── Sommer 2017/      # Original-PDFs nach Zeitraum
│       ├── Winter 2018_19/
│       └── versionen/        # Bearbeitete Versionen
├── db/init.sql               # SQL-Schema (auto-init)
├── docker-compose.yml        # PostgreSQL + pgAdmin
├── seed_db.py                # Python Seed-Script
├── consolidate_pdfs.py       # PDFs nach storage/ konsolidieren
├── setup.sh                  # Setup-Script (Linux/macOS/Git Bash)
├── setup.ps1                 # Setup-Script (Windows PowerShell)
├── Ergebnisse/               # Generierte HTML-Suchergebnisse
└── .env.example              # Umgebungsvariablen-Vorlage
```
