#!/usr/bin/env python3
"""
consolidate_pdfs.py — Kopiert alle in der DB referenzierten PDFs
nach storage/pdfs/<pruefung_zeitraum>/<dateiname> und legt für jedes
Dokument eine Version 1 (Original) in der Tabelle dokument_versionen an.

Nutzung:
  python consolidate_pdfs.py          # PDFs konsolidieren
  python consolidate_pdfs.py --check  # Nur Status anzeigen
"""
import os, sys, shutil
import psycopg

# ─── Konfiguration ───
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DB_CONFIG = {
    'host':     os.environ.get('DB_HOST', '127.0.0.1'),
    'port':     int(os.environ.get('DB_PORT', '15432')),
    'dbname':   os.environ.get('POSTGRES_DB', 'ihk_ap2'),
    'user':     os.environ.get('POSTGRES_USER', 'ihk'),
    'password': os.environ.get('POSTGRES_PASSWORD', ''),
}

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
STORAGE_ROOT = os.path.join(PROJECT_ROOT, 'storage', 'pdfs')


def _find_source(pfad: str, dateiname: str) -> str | None:
    """Findet die Quelldatei anhand verschiedener Strategien."""
    # 1) Direkter Pfad im Workspace
    candidate = os.path.join(PROJECT_ROOT, pfad)
    if os.path.isfile(candidate):
        return candidate

    # 2) ~/... → Home-Verzeichnis auflösen
    if pfad.startswith('~/') or pfad.startswith('~\\'):
        expanded = os.path.expanduser(pfad)
        if os.path.isfile(expanded):
            return expanded

    # 3) zip:// Pfade: zip://archiv.zip/inner/path.pdf → suche inner path
    if pfad.startswith('zip://'):
        zip_rest = pfad[len('zip://'):]
        zip_idx = zip_rest.lower().find('.zip/')
        if zip_idx >= 0:
            inner_path = zip_rest[zip_idx + 5:]  # nach ".zip/"
            # Suche in bekannten Ordnern
            for search_dir in ['AP_IHK_Anwendungsentwicklung', 'AP_IHK', 'AP_IHK_Andere_Berufe', 'storage/pdfs']:
                candidate = os.path.join(PROJECT_ROOT, search_dir, inner_path)
                if os.path.isfile(candidate):
                    return candidate

    # 4) Suche im storage/pdfs/ nach dem dateiname
    for root, dirs, files in os.walk(STORAGE_ROOT):
        if dateiname in files:
            return os.path.join(root, dateiname)

    # 5) Suche den Dateinamen nur in den bekannten PDF-Ordnern (nicht gesamter Workspace)
    basename = os.path.basename(pfad) if not pfad.startswith('zip://') else dateiname
    for search_dir in ['AP_IHK_Anwendungsentwicklung', 'AP_IHK', 'AP_IHK_Andere_Berufe',
                       'FIAE_GA1 Abschlussprüfungen', 'Lösungen der Prüfungen',
                       'WISO Aufgaben', 'WISO Lösungen', 'Sequenzdiagramm']:
        search_root = os.path.join(PROJECT_ROOT, search_dir)
        if not os.path.isdir(search_root):
            continue
        for root, dirs, files in os.walk(search_root):
            if basename in files:
                return os.path.join(root, basename)

    return None


def get_connection():
    return psycopg.connect(**DB_CONFIG)


def ensure_versionen_table(conn):
    """Erstellt die dokument_versionen-Tabelle falls nicht vorhanden."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dokument_versionen (
            id              SERIAL PRIMARY KEY,
            dokument_id     INTEGER      NOT NULL REFERENCES dokumente(id) ON DELETE CASCADE,
            version_nr      INTEGER      NOT NULL DEFAULT 1,
            label           VARCHAR(200) NOT NULL DEFAULT 'Original',
            dateiname       VARCHAR(500) NOT NULL,
            storage_pfad    TEXT         NOT NULL,
            dateigroesse    BIGINT,
            kommentar       TEXT,
            erstellt_am     TIMESTAMP    NOT NULL DEFAULT NOW(),
            UNIQUE(dokument_id, version_nr)
        );
        CREATE INDEX IF NOT EXISTS idx_versionen_dokument
            ON dokument_versionen(dokument_id);
    """)
    conn.commit()


def consolidate(check_only=False):
    conn = get_connection()
    ensure_versionen_table(conn)

    # Alle Dokumente mit Prüfungszeitraum laden
    rows = conn.execute("""
        SELECT d.id, d.dateiname, d.pfad, d.dateigroesse, d.typ,
               COALESCE(p.zeitraum_label, 'Unbekannt') AS zeitraum
        FROM dokumente d
        LEFT JOIN pruefungen p ON d.pruefung_id = p.id
        ORDER BY d.id
    """).fetchall()

    # Prüfe welche Versionen schon existieren
    existing = set()
    for row in conn.execute("SELECT dokument_id, version_nr FROM dokument_versionen").fetchall():
        existing.add((row[0], row[1]))

    total = len(rows)
    copied = 0
    skipped = 0
    missing = 0
    already = 0
    errors = []

    print(f"\n{'='*60}")
    print(f"PDF-Konsolidierung: {total} Dokumente")
    print(f"Ziel: {STORAGE_ROOT}")
    print(f"{'='*60}\n")


    for doc_id, dateiname, pfad, dateigroesse, typ, zeitraum in rows:
        # Zielverzeichnis: storage/pdfs/<Zeitraum>/
        safe_zeitraum = zeitraum.replace('/', '_').replace('\\', '_')
        target_dir = os.path.join(STORAGE_ROOT, safe_zeitraum)
        target_path = os.path.join(target_dir, dateiname)
        storage_rel = os.path.relpath(target_path, PROJECT_ROOT).replace('\\', '/')

        # Schon als Version 1 registriert?
        if (doc_id, 1) in existing:
            # Prüfe ob die registrierte Datei auch wirklich existiert
            v1_path = conn.execute(
                "SELECT storage_pfad FROM dokument_versionen WHERE dokument_id = %s AND version_nr = 1",
                (doc_id,)
            ).fetchone()
            if v1_path:
                full_v1 = os.path.join(PROJECT_ROOT, v1_path[0])
                if os.path.isfile(full_v1):
                    already += 1
                    continue
                # Version existiert in DB aber Datei fehlt — nochmal kopieren
                print(f"  RE-COPY: [{doc_id}] Storage-Datei fehlt, kopiere erneut...")
            else:
                already += 1
                continue

        # Quelldatei finden (mehrere Strategien)
        source_path = _find_source(pfad, dateiname)
        if not source_path:
            missing += 1
            errors.append(f"  FEHLT: [{doc_id}] {pfad}")
            continue

        if check_only:
            print(f"  BEREIT: [{doc_id}] {dateiname} -> {safe_zeitraum}/")
            copied += 1
            continue

        # Ziel existiert schon? Nicht überschreiben wenn gleiche Größe
        if os.path.isfile(target_path):
            if os.path.getsize(target_path) == os.path.getsize(source_path):
                # Datei schon da, nur Version registrieren
                filesize = os.path.getsize(target_path)
            else:
                # Dateiname-Kollision: mit Suffix lösen
                base, ext = os.path.splitext(dateiname)
                target_path = os.path.join(target_dir, f"{base}_{doc_id}{ext}")
                storage_rel = os.path.relpath(target_path, PROJECT_ROOT).replace('\\', '/')
                shutil.copy2(source_path, target_path)
                filesize = os.path.getsize(target_path)
        else:
            # Kopieren
            os.makedirs(target_dir, exist_ok=True)
            shutil.copy2(source_path, target_path)
            filesize = os.path.getsize(target_path)

        # Version 1 (Original) in DB eintragen oder aktualisieren
        conn.execute("""
            INSERT INTO dokument_versionen
                (dokument_id, version_nr, label, dateiname, storage_pfad, dateigroesse, kommentar)
            VALUES (%s, 1, 'Original', %s, %s, %s, 'Automatisch konsolidiert')
            ON CONFLICT (dokument_id, version_nr) 
            DO UPDATE SET storage_pfad = EXCLUDED.storage_pfad, 
                          dateigroesse = EXCLUDED.dateigroesse,
                          dateiname = EXCLUDED.dateiname
        """, (doc_id, dateiname, storage_rel, filesize))

        # Auch den pfad im Dokument auf den Storage-Pfad aktualisieren
        conn.execute("""
            UPDATE dokumente SET pfad = %s WHERE id = %s
        """, (storage_rel, doc_id))

        copied += 1
        if copied % 10 == 0:
            conn.commit()
            print(f"  ... {copied} Dateien kopiert")

    conn.commit()

    # Zusammenfassung
    print(f"\n{'-'*60}")
    print(f"Ergebnis:")
    print(f"  Kopiert:        {copied}")
    print(f"  Bereits da:     {already}")
    print(f"  Nicht gefunden: {missing}")
    print(f"  Gesamt:         {total}")
    if errors:
        print(f"\nFehlende Dateien:")
        for e in errors[:20]:
            print(e)
        if len(errors) > 20:
            print(f"  ... und {len(errors)-20} weitere")

    # Storage-Größe
    if os.path.isdir(STORAGE_ROOT):
        total_size = sum(
            os.path.getsize(os.path.join(dp, f))
            for dp, _, fns in os.walk(STORAGE_ROOT)
            for f in fns
        )
        print(f"\nStorage-Größe: {total_size / (1024*1024):.1f} MB")

    conn.close()
    print(f"{'='*60}\n")


if __name__ == '__main__':
    check_only = '--check' in sys.argv
    consolidate(check_only)
