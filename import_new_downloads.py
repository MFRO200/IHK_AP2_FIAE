#!/usr/bin/env python3
"""
import_new_downloads.py — Importiert neue FIAE-Prüfungs-PDFs aus Downloads
in die Datenbank und kopiert sie nach storage/pdfs/.

Identifizierte neue PDFs (Stand 15.03.2026):
- Sommer 2024: 2 neue Dokumente (GA2 Algorithmen, Belegsatz)
- Winter 2024_25: 1 neues Dokument (WISO hochauflösender Scan)
- Sommer 2025: 4 neue Dokumente (NEUER Prüfungszeitraum)
- Winter 2025_26: 5 neue Dokumente (NEUER Prüfungszeitraum)
"""
import os
import sys
import shutil
import fitz  # PyMuPDF

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import psycopg

# ─── Konfiguration ───
DB_CONFIG = {
    'host':     os.environ.get('DB_HOST', '127.0.0.1'),
    'port':     int(os.environ.get('DB_PORT', '15432')),
    'dbname':   os.environ.get('POSTGRES_DB', 'ihk_ap2'),
    'user':     os.environ.get('POSTGRES_USER', 'ihk'),
    'password': os.environ.get('POSTGRES_PASSWORD', ''),
}

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
STORAGE_ROOT = os.path.join(PROJECT_ROOT, 'storage', 'pdfs')
DOWNLOADS    = os.path.expanduser('~/Downloads')

def get_connection():
    return psycopg.connect(**DB_CONFIG)


def page_count(filepath):
    """Gibt Seitenanzahl eines PDFs zurück."""
    try:
        doc = fitz.open(filepath)
        c = len(doc)
        doc.close()
        return c
    except:
        return 0


def detect_doc_type(filename):
    """Erkennt Dokumenttyp: Aufgabe / Lösung / Handreichung"""
    fl = filename.lower()
    if any(x in fl for x in ['lösung', 'loesung', 'lösungen', 'loesungen']):
        return 'Lösung'
    if any(x in fl for x in ['hinweis', 'handreichung']):
        return 'Handreichung'
    return 'Aufgabe'


def ensure_pruefung(conn, zeitraum_label, ordner_name, jahr, semester):
    """Erstellt Prüfungszeitraum falls noch nicht vorhanden, gibt ID zurück."""
    row = conn.execute(
        "SELECT id FROM pruefungen WHERE zeitraum_label = %s",
        (zeitraum_label,)
    ).fetchone()
    if row:
        print(f"  Prüfungszeitraum '{zeitraum_label}' existiert bereits (id={row[0]})")
        return row[0]

    row = conn.execute(
        """INSERT INTO pruefungen (jahr, semester, zeitraum_label, ordner_name)
           VALUES (%s, %s, %s, %s) RETURNING id""",
        (jahr, semester, zeitraum_label, ordner_name)
    ).fetchone()
    conn.commit()
    pid = row[0]
    print(f"  ✓ Prüfungszeitraum '{zeitraum_label}' angelegt (id={pid})")
    return pid


def import_pdf(conn, src_path, dateiname, zeitraum_label, ordner_name, typ):
    """Kopiert PDF nach storage und legt DB-Einträge an."""
    # Zielverzeichnis
    dest_dir = os.path.join(STORAGE_ROOT, ordner_name)
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, dateiname)

    # Prüfe ob Datei schon existiert (nach Name + Größe)
    src_size = os.path.getsize(src_path)
    existing = conn.execute(
        "SELECT id, dateigroesse FROM dokumente WHERE dateiname = %s",
        (dateiname,)
    ).fetchone()
    if existing and existing[1] == src_size:
        print(f"  ⊘ SKIP (bereits in DB): {dateiname}")
        return False

    # Kopiere PDF
    if not os.path.exists(dest_path):
        shutil.copy2(src_path, dest_path)
        print(f"  → Kopiert: {dateiname}")
    else:
        print(f"  → Datei existiert bereits in storage: {dateiname}")

    # Prüfung-ID holen
    pruefung_id = conn.execute(
        "SELECT id FROM pruefungen WHERE zeitraum_label = %s",
        (zeitraum_label,)
    ).fetchone()[0]

    # Seitenanzahl
    pages = page_count(src_path)
    rel_path = f"storage/pdfs/{ordner_name}/{dateiname}"

    # In dokumente einfügen
    row = conn.execute(
        """INSERT INTO dokumente (pruefung_id, dateiname, pfad, typ, dateigroesse, seitenanzahl)
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
        (pruefung_id, dateiname, rel_path, typ, src_size, pages)
    ).fetchone()
    doc_id = row[0]
    conn.commit()

    # Version 1 (Original) anlegen
    try:
        conn.execute(
            """INSERT INTO dokument_versionen (dokument_id, version_nr, label, dateiname, storage_pfad, dateigroesse)
               VALUES (%s, 1, 'Original', %s, %s, %s)
               ON CONFLICT (dokument_id, version_nr) DO NOTHING""",
            (doc_id, dateiname, rel_path, src_size)
        )
        conn.commit()
    except Exception as e:
        print(f"    (Version-Eintrag übersprungen: {e})")
        conn.rollback()

    print(f"  ✓ DB-Eintrag: id={doc_id} | {typ} | {pages} Seiten | {src_size:,} Bytes")
    return True


def main():
    conn = get_connection()

    # ═══════════════════════════════════════════════════════════
    # Zu importierende PDFs: (Quelldatei, Zieldateiname, zeitraum_label, ordner_name, jahr, semester)
    # ═══════════════════════════════════════════════════════════
    imports = [
        # ── Sommer 2024: 2 neue Dokumente ──
        {
            'src':      os.path.join(DOWNLOADS, '2024_Sommer_FIAE_2_Entwicklung_von_Algorithmen.pdf'),
            'name':     '2024_Sommer_FIAE_2_Entwicklung_von_Algorithmen.pdf',
            'zeitraum': 'Sommer 2024',
            'ordner':   'Sommer 2024',
            'jahr':     2024,
            'semester': 'Sommer',
        },
        {
            'src':      os.path.join(DOWNLOADS, '2024_Sommer_FIAE_Belegsatz.pdf'),
            'name':     '2024_Sommer_FIAE_Belegsatz.pdf',
            'zeitraum': 'Sommer 2024',
            'ordner':   'Sommer 2024',
            'jahr':     2024,
            'semester': 'Sommer',
        },

        # ── Winter 2024_25: 1 neues Dokument (hochauflösender WISO-Scan) ──
        {
            'src':      os.path.join(DOWNLOADS, '2024_25 Winter_ FIAE_WISO.pdf'),
            'name':     '2024_25_Winter_FIAE_WISO.pdf',
            'zeitraum': 'Winter 2024_25',
            'ordner':   'Winter 2024_25',
            'jahr':     2024,
            'semester': 'Winter',
        },

        # ── Sommer 2025: NEUER Prüfungszeitraum ──
        {
            'src':      os.path.join(DOWNLOADS, '2025_Sommer_FIAE_2_Entwicklung und Umsetzung von Algorithmen.pdf'),
            'name':     '2025_Sommer_FIAE_2_Entwicklung_und_Umsetzung_von_Algorithmen.pdf',
            'zeitraum': 'Sommer 2025',
            'ordner':   'Sommer 2025',
            'jahr':     2025,
            'semester': 'Sommer',
        },
        {
            'src':      os.path.join(DOWNLOADS, '2025_Sommer_FIAE_Belegsatz.pdf'),
            'name':     '2025_Sommer_FIAE_Belegsatz.pdf',
            'zeitraum': 'Sommer 2025',
            'ordner':   'Sommer 2025',
            'jahr':     2025,
            'semester': 'Sommer',
        },
        {
            'src':      os.path.join(DOWNLOADS, '2025_Sommer_FIAE_WISO.pdf'),
            'name':     '2025_Sommer_FIAE_WISO.pdf',
            'zeitraum': 'Sommer 2025',
            'ordner':   'Sommer 2025',
            'jahr':     2025,
            'semester': 'Sommer',
        },
        {
            'src':      os.path.join(DOWNLOADS, '2025_Sommer_WISO_Lösung.pdf'),
            'name':     '2025_Sommer_WISO_Lösung.pdf',
            'zeitraum': 'Sommer 2025',
            'ordner':   'Sommer 2025',
            'jahr':     2025,
            'semester': 'Sommer',
        },

        # ── Winter 2025_26: NEUER Prüfungszeitraum ──
        {
            'src':      os.path.join(DOWNLOADS, '2025_26_Winter_FIAE_1_Planen_eines_Softwareproduktes.pdf'),
            'name':     '2025_26_Winter_FIAE_1_Planen_eines_Softwareproduktes.pdf',
            'zeitraum': 'Winter 2025_26',
            'ordner':   'Winter 2025_26',
            'jahr':     2025,
            'semester': 'Winter',
        },
        {
            'src':      os.path.join(DOWNLOADS, '2025_26_Winter_FIAE_2_Entwicklung_und_Umsetzung_von_Algorithmen.pdf'),
            'name':     '2025_26_Winter_FIAE_2_Entwicklung_und_Umsetzung_von_Algorithmen.pdf',
            'zeitraum': 'Winter 2025_26',
            'ordner':   'Winter 2025_26',
            'jahr':     2025,
            'semester': 'Winter',
        },
        {
            'src':      os.path.join(DOWNLOADS, '2025_26_Winter_FIAE_2_Belegsatz.pdf'),
            'name':     '2025_26_Winter_FIAE_2_Belegsatz.pdf',
            'zeitraum': 'Winter 2025_26',
            'ordner':   'Winter 2025_26',
            'jahr':     2025,
            'semester': 'Winter',
        },
        {
            'src':      os.path.join(DOWNLOADS, '2025_26_Winter_FIAE_WISO.pdf'),
            'name':     '2025_26_Winter_FIAE_WISO.pdf',
            'zeitraum': 'Winter 2025_26',
            'ordner':   'Winter 2025_26',
            'jahr':     2025,
            'semester': 'Winter',
        },
        {
            'src':      os.path.join(DOWNLOADS, '2025_26_Winter_FIAE_WISO_Lösungen.pdf'),
            'name':     '2025_26_Winter_FIAE_WISO_Lösungen.pdf',
            'zeitraum': 'Winter 2025_26',
            'ordner':   'Winter 2025_26',
            'jahr':     2025,
            'semester': 'Winter',
        },
    ]

    # Prüfe ob alle Quelldateien existieren
    missing = [i for i in imports if not os.path.exists(i['src'])]
    if missing:
        print("FEHLER: Folgende Quelldateien fehlen:")
        for m in missing:
            print(f"  {m['src']}")
        sys.exit(1)

    print(f"═══ Import von {len(imports)} PDFs ═══\n")

    # Prüfungszeiträume sicherstellen
    seen = set()
    for imp in imports:
        key = imp['zeitraum']
        if key not in seen:
            ensure_pruefung(conn, imp['zeitraum'], imp['ordner'], imp['jahr'], imp['semester'])
            seen.add(key)

    print()

    # PDFs importieren
    imported = 0
    skipped = 0
    for imp in imports:
        typ = detect_doc_type(imp['name'])
        print(f"[{imp['zeitraum']}] {imp['name']} ({typ})")
        ok = import_pdf(conn, imp['src'], imp['name'], imp['zeitraum'], imp['ordner'], typ)
        if ok:
            imported += 1
        else:
            skipped += 1

    print(f"\n═══ Ergebnis: {imported} importiert, {skipped} übersprungen ═══")
    conn.close()


if __name__ == '__main__':
    main()
