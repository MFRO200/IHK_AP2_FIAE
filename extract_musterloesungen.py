#!/usr/bin/env python3
"""
extract_musterloesungen.py
Extrahiert Musterlösungen aus Lösungs-PDFs (OCR-Text) und speichert sie
strukturiert in der Tabelle 'musterloesungen'.

Patterns:
  - "1. Aufgabe (25 Punkte)"  /  "1. Handlungsschritt (25 Punkte)"
  - Sub-tasks: "a)  4 Punkte"  /  "a) 4 Punkte"
"""

import re
import psycopg
from db_config import DB_URL

# Regex: Hauptaufgabe erkennen
RE_AUFGABE = re.compile(
    r'^(\d+)\.\s*(?:Aufgabe|Handlungsschritt)\s*\((\d+)\s*Punkte?\)',
    re.IGNORECASE | re.MULTILINE,
)

# Regex: Sub-Aufgabe erkennen  "a)  4 Punkte"  oder "ba) 9 Punkte"
RE_SUB = re.compile(
    r'^([a-z]{1,2})\)\s+(\d+)\s*Punkte?',
    re.IGNORECASE | re.MULTILINE,
)


def parse_solution_text(full_text: str) -> list[dict]:
    """
    Parsed den OCR-Text eines Lösungsdokuments in strukturierte Aufgaben.
    Returns list of {aufgabe: "1", text: "...", max_punkte: 25, subs: [{aufgabe: "1a", ...}]}
    """
    results = []

    # Alle Hauptaufgaben finden
    aufgabe_matches = list(RE_AUFGABE.finditer(full_text))
    if not aufgabe_matches:
        return results

    for i, m in enumerate(aufgabe_matches):
        aufg_nr = m.group(1)
        max_punkte = int(m.group(2))
        start = m.end()
        end = aufgabe_matches[i + 1].start() if i + 1 < len(aufgabe_matches) else len(full_text)
        block = full_text[start:end].strip()

        # Sub-Aufgaben in diesem Block finden
        sub_matches = list(RE_SUB.finditer(block))
        subs = []

        if sub_matches:
            for j, sm in enumerate(sub_matches):
                sub_label = sm.group(1).lower()
                sub_punkte = int(sm.group(2))
                sub_start = sm.end()
                sub_end = sub_matches[j + 1].start() if j + 1 < len(sub_matches) else len(block)
                sub_text = block[sub_start:sub_end].strip()
                # Clean up: remove trailing page headers like "ZPA FIA II 3"
                sub_text = re.sub(r'\nZPA\s+FI[A-Z]*\s+.*$', '', sub_text, flags=re.MULTILINE).strip()

                subs.append({
                    'aufgabe': f"{aufg_nr}.{sub_label}",
                    'text': sub_text,
                    'max_punkte': sub_punkte,
                })

        # Hauptaufgabe-Text (alles vor der ersten Sub oder der ganze Block)
        if sub_matches:
            main_text = block[:sub_matches[0].start()].strip()
        else:
            main_text = block

        # Clean up
        main_text = re.sub(r'\nZPA\s+FI[A-Z]*\s+.*$', '', main_text, flags=re.MULTILINE).strip()

        results.append({
            'aufgabe': aufg_nr,
            'text': main_text,
            'max_punkte': max_punkte,
            'subs': subs,
        })

    return results


def main():
    inserted = 0
    skipped = 0
    errors = 0

    with psycopg.connect(DB_URL) as conn:
        cur = conn.cursor()

        # Alle FIAE Lösungs-Dokumente laden
        cur.execute("""
            SELECT d.id, d.pruefung_id, d.dateiname, d.pruefungsbereich
            FROM dokumente d
            WHERE d.typ = 'Lösung'
              AND d.dateiname LIKE '%FIAE%'
              AND d.pruefung_id IS NOT NULL
            ORDER BY d.dateiname
        """)
        docs = cur.fetchall()
        print(f"Verarbeite {len(docs)} Lösungs-Dokumente...")

        for doc_id, pruefung_id, dateiname, bereich in docs:
            # OCR-Text aller Seiten zusammenführen
            cur.execute(
                "SELECT ocr_text FROM seiten WHERE dokument_id = %s ORDER BY seiten_nr",
                (doc_id,)
            )
            pages = [r[0] for r in cur.fetchall() if r[0]]
            if not pages:
                continue

            full_text = "\n".join(pages)
            aufgaben = parse_solution_text(full_text)

            if not aufgaben:
                continue

            for aufg in aufgaben:
                # Hauptaufgabe speichern
                aufgabe_key = aufg['aufgabe']
                text = aufg['text']

                # Falls Subs vorhanden, auch deren Text anhängen für die Gesamtübersicht
                if aufg['subs']:
                    combined = text + "\n\n" if text else ""
                    for s in aufg['subs']:
                        combined += f"{s['aufgabe']}) ({s['max_punkte']} P.): {s['text']}\n\n"
                    text = combined.strip()

                if not text or len(text) < 10:
                    continue

                try:
                    cur.execute("""
                        INSERT INTO musterloesungen (pruefung_id, aufgabe, erwartung_text, max_punkte, hinweise)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (pruefung_id, aufgabe) DO UPDATE
                        SET erwartung_text = EXCLUDED.erwartung_text,
                            max_punkte = EXCLUDED.max_punkte,
                            hinweise = EXCLUDED.hinweise
                    """, (pruefung_id, aufgabe_key, text, aufg['max_punkte'],
                          f"Quelle: {dateiname}, Bereich: {bereich}"))
                    inserted += 1
                except Exception as e:
                    errors += 1
                    print(f"  FEHLER {dateiname} Aufg.{aufgabe_key}: {e}")

                # Sub-Aufgaben einzeln speichern
                for s in aufg['subs']:
                    if len(s['text']) < 5:
                        continue
                    try:
                        cur.execute("""
                            INSERT INTO musterloesungen (pruefung_id, aufgabe, erwartung_text, max_punkte, hinweise)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (pruefung_id, aufgabe) DO UPDATE
                            SET erwartung_text = EXCLUDED.erwartung_text,
                                max_punkte = EXCLUDED.max_punkte,
                                hinweise = EXCLUDED.hinweise
                        """, (pruefung_id, s['aufgabe'], s['text'], s['max_punkte'],
                              f"Quelle: {dateiname}, Bereich: {bereich}"))
                        inserted += 1
                    except Exception as e:
                        errors += 1

        conn.commit()

    print(f"\nFertig: {inserted} Musterlösungen gespeichert, {errors} Fehler")


if __name__ == "__main__":
    main()
