"""
Benennt alle Dokumente in der DB einheitlich um.
Schema:
  Aufgabe/Lösung:    {zeitraum}_{beruf}_2_{bereich}_{typ}.pdf
  Belegsatz:         {zeitraum}_{beruf}_2_Belegsatz.pdf
  Handreichung:      {zeitraum}_{beruf}_2_Handreichung.pdf

Zeitraum:
  Sommer  → {jahr}_Sommer
  Winter  → {jahr}_{(jahr+1)%100:02d}_Winter
  Unbek.  → {jahr}

Beruf wird aus pruefungsbereich abgeleitet:
  GA1     → FIAE    GA2  → FIAE   WISO → FIAE
  GA1 FISI → FISI   GA1 IK → IK   GA1 IT-SE → IT-SE   GA1 IT-SK → IT-SK

AP1 und Sonstige werden übersprungen.
Nur dateiname in der DB wird geändert, keine physischen Dateien.
"""

import psycopg
import sys
from collections import Counter
from db_config import DB_DSN as DB

BEREICH_MAP = {
    "GA1":       ("FIAE", "GA1"),
    "GA2":       ("FIAE", "GA2"),
    "WISO":      ("FIAE", "WISO"),
    "GA1 FISI":  ("FISI", "GA1"),
    "GA1 IK":    ("IK",   "GA1"),
    "GA1 IT-SE": ("IT-SE","GA1"),
    "GA1 IT-SK": ("IT-SK","GA1"),
}

SKIP_BEREICHE = {"AP1", "Sonstige"}


def build_zeitraum(jahr: int, semester: str) -> str:
    if semester == "Sommer":
        return f"{jahr}_Sommer"
    elif semester == "Winter":
        return f"{jahr}_{(jahr + 1) % 100:02d}_Winter"
    else:
        return str(jahr)


def build_new_name(jahr: int, semester: str, pruefungsbereich: str, typ: str) -> str | None:
    if pruefungsbereich in SKIP_BEREICHE:
        return None
    mapping = BEREICH_MAP.get(pruefungsbereich)
    if not mapping:
        return None
    beruf, bereich = mapping
    zeitraum = build_zeitraum(jahr, semester)

    if typ in ("Aufgabe", "Lösung"):
        return f"{zeitraum}_{beruf}_2_{bereich}_{typ}.pdf"
    elif typ in ("Belegsatz", "Handreichung"):
        return f"{zeitraum}_{beruf}_2_{typ}.pdf"
    else:
        # Unbekannter Typ → mit Typ-Name
        return f"{zeitraum}_{beruf}_2_{bereich}_{typ}.pdf"


def main():
    dry_run = "--apply" not in sys.argv
    if dry_run:
        print("=== DRY RUN === (benutze --apply zum Ausführen)\n")

    conn = psycopg.connect(DB)
    cur = conn.cursor()

    cur.execute("""
        SELECT d.id, d.dateiname, d.typ, d.pruefungsbereich,
               p.jahr, p.semester
        FROM dokumente d
        JOIN pruefungen p ON d.pruefung_id = p.id
        ORDER BY p.jahr, p.semester, d.pruefungsbereich, d.typ, d.id
    """)

    rows = cur.fetchall()
    print(f"Gesamt: {len(rows)} Dokumente\n")

    # 1) Erzeuge neue Namen und erkenne Duplikate
    renames = []  # [(id, old_name, new_name)]
    skipped = 0
    name_counter: Counter = Counter()

    for doc_id, dateiname, typ, bereich, jahr, semester in rows:
        new_name = build_new_name(jahr, semester, bereich, typ)
        if new_name is None:
            skipped += 1
            continue
        name_counter[new_name] += 1
        count = name_counter[new_name]
        if count > 1:
            base, ext = new_name.rsplit(".", 1)
            final_name = f"{base}_{count}.{ext}"
        else:
            final_name = new_name
        renames.append((doc_id, dateiname, final_name))

    # Statistik
    changed = [(doc_id, old, new) for doc_id, old, new in renames if old != new]
    unchanged = [(doc_id, old, new) for doc_id, old, new in renames if old == new]

    print(f"Übersprungen (AP1/Sonstige/unbekannt): {skipped}")
    print(f"Zu benennen:  {len(renames)}")
    print(f"  Davon geändert: {len(changed)}")
    print(f"  Bereits korrekt: {len(unchanged)}")

    # Duplikate anzeigen
    dupes = {k: v for k, v in name_counter.items() if v > 1}
    if dupes:
        print(f"\nDuplikat-Gruppen: {len(dupes)}")
        for name, cnt in sorted(dupes.items()):
            print(f"  {name} → {cnt}x (Suffix _2, _3 … angehängt)")

    # Beispiele anzeigen
    print(f"\n--- Beispiele (erste 30 Änderungen) ---")
    for doc_id, old, new in changed[:30]:
        print(f"  [{doc_id:4d}] {old}")
        print(f"         → {new}\n")

    if dry_run:
        print("\n=== Kein Update ausgeführt. Starte mit --apply ===")
    else:
        print("\nAktualisiere Datenbank …")
        for doc_id, old, new in changed:
            cur.execute(
                "UPDATE dokumente SET dateiname = %s WHERE id = %s",
                (new, doc_id),
            )
        conn.commit()
        print(f"✓ {len(changed)} Dokumente umbenannt.")

    conn.close()


if __name__ == "__main__":
    main()
