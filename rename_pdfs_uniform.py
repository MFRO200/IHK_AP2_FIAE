"""
Einheitliche Benennung aller PDFs in storage/pdfs/.

Schema: {YYYY}[_{YY}]_{Sommer|Winter}_{Beruf}_2_{Bereich}_{Typ}[_{N}].pdf

Schritte:
  1. Nicht-Standard-dateiname in der DB korrigieren
  2. Alle Dateien auf Platte umbenennen  →  dateiname
  3. pfad in dokumente + dokument_versionen aktualisieren
"""
from __future__ import annotations
import os, re, shutil, psycopg
from db_config import DB_URL as DSN

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
STORAGE   = os.path.join(WORKSPACE, "storage", "pdfs")

# ── 1. DB-Dateinamen korrigieren (die 14 Nicht-Standard-Einträge) ──────────

def fix_db_name(cur):
    """Korrigiert dateiname (und ggf. pruefungsbereich/typ) für nicht-
    standardkonforme Einträge."""
    # Wir holen alle Dokumente mit den Zeitraum-Infos
    cur.execute("""
        SELECT d.id, d.dateiname, d.pfad, d.typ, d.pruefungsbereich,
               p.zeitraum_label, p.jahr, p.semester, p.id as pid
        FROM dokumente d
        JOIN pruefungen p ON d.pruefung_id = p.id
        ORDER BY d.id
    """)
    rows = cur.fetchall()
    cols = [c.name for c in cur.description]
    docs = [dict(zip(cols, r)) for r in rows]

    # Standard pattern
    STD = re.compile(
        r"^\d{4}(_\d{2})?_(Sommer|Winter)_(FIAE|FISI|IT-SE|IT-SK|IK)"
        r"_2_(GA1|GA2|WISO|AP1|Sonstige|Handreichung)"
        r"_(Aufgabe|Lösung|Handreichung)(_\d+)?\.pdf$",
        re.IGNORECASE,
    )

    updated = 0
    for d in docs:
        old_name = d["dateiname"]
        if STD.match(old_name):
            continue  # schon ok

        new_name = _build_standard_name(d)
        if new_name and new_name != old_name:
            # Prüfe Kollision
            new_name = _avoid_collision(cur, d["id"], d["pid"], new_name)
            print(f"  DB-FIX  id={d['id']:4d}  {old_name}  →  {new_name}")
            cur.execute(
                "UPDATE dokumente SET dateiname = %s WHERE id = %s",
                (new_name, d["id"]),
            )
            updated += 1
        elif not new_name:
            print(f"  SKIP    id={d['id']:4d}  {old_name}  (kein Mapping)")

    print(f"DB-Namen korrigiert: {updated}")
    return updated


def _zeitraum_prefix(d: dict) -> str:
    """Baut den Zeitraum-Prefix, z.B. '2023_24_Winter' oder '2003_Sommer'."""
    label: str = d["zeitraum_label"]
    sem: str = d["semester"]
    jahr: int = d["jahr"]

    # label ist z.B. "Winter 2023_24", "Sommer 2003", "Unbekannt 2008"
    if "Sommer" in label:
        return f"{jahr}_Sommer"
    elif "Winter" in label:
        # Winter hat immer 2 Jahre, z.B. "Winter 2023_24"
        m = re.search(r"(\d{4})_(\d{2})", label)
        if m:
            return f"{m.group(1)}_{m.group(2)}_Winter"
        else:
            return f"{jahr}_Winter"
    else:
        # "Unbekannt" — wir machen trotzdem Standard
        return f"{jahr}_Sommer"  # Fallback


def _build_standard_name(d: dict) -> str | None:
    """Erzeugt einen Standard-Dateinamen aus DB-Metadaten."""
    prefix = _zeitraum_prefix(d)
    bereich = d["pruefungsbereich"] or "Sonstige"
    typ = d["typ"] or "Aufgabe"

    # Beruf — für FIAE-spezifische Bereiche nehmen wir FIAE
    beruf = "FIAE"
    if "FISI" in bereich:
        beruf = "FISI"
    elif "IT-SE" in bereich:
        beruf = "IT-SE"
    elif "IT-SK" in bereich:
        beruf = "IT-SK"
    elif "IK" in bereich and "IT-SK" not in bereich:
        beruf = "IK"

    # Bereich normalisieren — z.B. "GA1 FISI" → "GA1"
    bereich_clean = bereich.split()[0] if bereich else "Sonstige"
    # Handreichung ist sowohl Bereich als auch Typ
    if typ == "Handreichung" or bereich_clean == "Handreichung":
        bereich_clean = "GA1"  # Handreichungen beziehen sich meistens auf GA1
        typ = "Handreichung"

    return f"{prefix}_{beruf}_2_{bereich_clean}_{typ}.pdf"


def _avoid_collision(cur, doc_id: int, pruefung_id: int, name: str) -> str:
    """Hängt _2, _3, ... an, wenn ein anderes Dokument den gleichen Namen hat."""
    base, ext = os.path.splitext(name)
    candidate = name
    n = 2
    while True:
        cur.execute(
            "SELECT id FROM dokumente WHERE dateiname = %s AND id != %s AND pruefung_id = %s",
            (candidate, doc_id, pruefung_id),
        )
        if not cur.fetchone():
            return candidate
        candidate = f"{base}_{n}{ext}"
        n += 1


# ── 2. Dateien auf Platte umbenennen ───────────────────────────────────────

def rename_files(cur):
    """Benennt die physischen Dateien um, aktualisiert pfad + versionen."""
    cur.execute("""
        SELECT d.id, d.dateiname, d.pfad, p.zeitraum_label
        FROM dokumente d
        JOIN pruefungen p ON d.pruefung_id = p.id
    """)
    rows = cur.fetchall()

    renamed = 0
    already_ok = 0
    missing = 0

    for doc_id, dateiname, pfad, zeitraum in rows:
        if not pfad:
            continue

        # aktuellen Dateipfad auflösen
        if pfad.startswith("storage/"):
            abs_path = os.path.join(WORKSPACE, pfad)
        else:
            abs_path = pfad

        actual_basename = os.path.basename(abs_path)
        target_dir = os.path.dirname(abs_path)

        if actual_basename == dateiname:
            already_ok += 1
            continue

        if not os.path.isfile(abs_path):
            print(f"  MISSING id={doc_id}: {abs_path}")
            missing += 1
            continue

        new_path = os.path.join(target_dir, dateiname)

        # Falls Ziel schon existiert (anderes Dok?), Suffix anhängen
        if os.path.exists(new_path) and os.path.abspath(new_path) != os.path.abspath(abs_path):
            base, ext = os.path.splitext(dateiname)
            n = 2
            while os.path.exists(new_path):
                new_path = os.path.join(target_dir, f"{base}_{n}{ext}")
                n += 1
            # dateiname in DB anpassen
            dateiname = os.path.basename(new_path)
            cur.execute(
                "UPDATE dokumente SET dateiname = %s WHERE id = %s",
                (dateiname, doc_id),
            )

        os.rename(abs_path, new_path)

        # Neuen pfad berechnen (relative zum Workspace)
        new_rel = os.path.relpath(new_path, WORKSPACE).replace("\\", "/")
        cur.execute(
            "UPDATE dokumente SET pfad = %s WHERE id = %s",
            (new_rel, doc_id),
        )

        # dokument_versionen aktualisieren
        cur.execute(
            """UPDATE dokument_versionen
               SET dateiname = %s, storage_pfad = %s
               WHERE dokument_id = %s AND version_nr = 1""",
            (dateiname, new_rel, doc_id),
        )

        renamed += 1

    print(f"Umbenannt: {renamed}, Bereits OK: {already_ok}, Fehlend: {missing}")
    return renamed


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    conn = psycopg.connect(DSN)
    conn.autocommit = False
    cur = conn.cursor()

    print("=== Schritt 1: DB-Dateinamen korrigieren ===")
    fix_db_name(cur)

    print("\n=== Schritt 2: Dateien auf Platte umbenennen ===")
    rename_files(cur)

    conn.commit()
    cur.close()
    conn.close()

    # Verifizierung
    conn2 = psycopg.connect(DSN)
    cur2 = conn2.cursor()
    cur2.execute("""
        SELECT COUNT(*) FROM dokumente
        WHERE pfad LIKE 'storage/%'
          AND dateiname = SPLIT_PART(pfad, '/', -1)
    """)
    match_count = cur2.fetchone()[0]
    cur2.execute("SELECT COUNT(*) FROM dokumente WHERE pfad LIKE 'storage/%'")
    total = cur2.fetchone()[0]
    print(f"\n=== Verifizierung: {match_count}/{total} Dateinamen = Pfad-Basename ===")
    if match_count < total:
        cur2.execute("""
            SELECT id, dateiname, SPLIT_PART(pfad, '/', -1) as basename, pfad
            FROM dokumente
            WHERE pfad LIKE 'storage/%'
              AND dateiname != SPLIT_PART(pfad, '/', -1)
            LIMIT 20
        """)
        for r in cur2.fetchall():
            print(f"  DIFF id={r[0]}: dateiname={r[1]} vs basename={r[2]}")
    conn2.close()


if __name__ == "__main__":
    main()
