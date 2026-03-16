#!/usr/bin/env python3
"""
detect_belegsatz.py - Erkennt PDFs die NUR Belegsatz-Inhalte enthalten,
benennt sie um und aktualisiert die Datenbank.

Erkennung:
1. Seite 1 enthält explizit "Belegsatz" als Titel -> sicher
2. Anlagenblatt / Anlage zum Aufgabensatz auf Seite 1 -> sicher
3. Content-Analyse: viele Beleg-Indikatoren, wenige Aufgaben-Indikatoren -> wahrscheinlich
"""

import os
import re
import psycopg
from db_config import DB_URL

DRY_RUN = False  # True = nur anzeigen, False = tatsächlich umbenennen

STORAGE = os.path.join(os.path.dirname(__file__), "storage")


def is_pure_belegsatz(pages_text: list[str]) -> tuple[bool, str]:
    """
    Prüft ob ein Dokument ein REINER Belegsatz ist (keine Prüfungsaufgaben).
    Returns: (is_beleg, reason)
    """
    if not pages_text:
        return False, "Kein OCR-Text"

    page1 = pages_text[0].lower() if pages_text else ""
    full_text = "\n".join(pages_text).lower()
    num_pages = len(pages_text)

    # Aufgabe-Indikatoren - wenn vorhanden, ist es KEIN reiner Belegsatz
    aufgabe_markers = [
        'handlungsschritt 1', 'handlungsschritt 2', 'handlungsschritt 3',
        'teilaufgabe a', 'teilaufgabe b', 'teilaufgabe c',
        'bearbeitungshinweis', 'prüfungszeit',
        'in der prüfung zu bearbeiten',
    ]
    aufgabe_operators = [
        'nennen sie', 'beschreiben sie', 'erklären sie', 'erläutern sie',
        'berechnen sie', 'erstellen sie', 'begründen sie', 'beurteilen sie',
        'ermitteln sie', 'vergleichen sie', 'analysieren sie',
    ]

    aufgabe_m_hits = sum(1 for w in aufgabe_markers if w in full_text)
    aufgabe_o_hits = sum(1 for w in aufgabe_operators if w in full_text)
    has_aufgaben = aufgabe_m_hits >= 1 or aufgabe_o_hits >= 3

    # ── Regel 1: Expliziter Belegsatz-Titel als eigene Zeile auf Seite 1 ──
    lines = page1.split('\n')
    for line in lines[:20]:
        stripped = line.strip()
        # "Belegsatz" muss als eigene Zeile stehen (Titel), nicht mitten im Satz
        if stripped == 'belegsatz':
            if not has_aufgaben:
                return True, "Seite 1: 'Belegsatz' als Titel-Zeile"
            else:
                return False, f"Hat 'Belegsatz'-Titel aber auch Aufgaben ({aufgabe_m_hits}m+{aufgabe_o_hits}o)"

    # ── Regel 2: "Anlage zum Aufgabensatz" / "Anlagenblatt" als Titel ──
    if re.search(r'anlage\s+(zum\s+)?aufgabensatz', page1):
        if not has_aufgaben:
            return True, "Seite 1: 'Anlage zum Aufgabensatz'"
        else:
            return False, f"Hat 'Anlage' aber auch Aufgaben ({aufgabe_m_hits}m+{aufgabe_o_hits}o)"
    if 'anlagenblatt' in page1 and not has_aufgaben:
        return True, "Seite 1: 'Anlagenblatt'"

    # ── Regel 3: Content-Analyse ──
    # NUR wenn KEINE Prüfungsaufgaben im Dokument
    if has_aufgaben:
        return False, f"Enthält Aufgaben ({aufgabe_m_hits}m+{aufgabe_o_hits}o)"

    beleg_content = [
        'rechnung nr', 'rechnungsnr', 'rechnungs-nr', 're-nr',
        'lieferschein', 'angebot nr', 'angebotsnr',
        'bestellnr', 'bestell-nr', 'kontoauszug', 'buchungsbeleg',
        'gehaltsabrechnung', 'entgeltabrechnung', 'lohnabrechnung',
        'gutschrift', 'quittung', 'kassenbon',
        'ust-id', 'ust.-id', 'steuernummer',
        'artikelnr', 'artikel-nr', 'wareneingangsschein',
    ]
    content_hits = sum(1 for w in beleg_content if w in full_text)

    # Auch "belegsatz" irgendwo im Dokument (aber nicht nur einmal beiläufig)
    beleg_count = full_text.count('belegsatz')
    anlage_count = len(re.findall(r'anlage\s+(zum\s+)?aufgabensatz', full_text))

    if (beleg_count >= 1 or anlage_count >= 1) and content_hits >= 2:
        return True, f"Content: belegsatz={beleg_count}, anlage={anlage_count}, beleg_content={content_hits}"

    if content_hits >= 5:
        return True, f"Content: {content_hits} Beleg-Inhalte, keine Aufgaben"

    return False, f"Kein Belegsatz (beleg={beleg_count}, content={content_hits}, aufg={aufgabe_m_hits}m+{aufgabe_o_hits}o)"


def main():
    renamed = []
    skipped = []

    with psycopg.connect(DB_URL) as conn:
        cur = conn.cursor()

        # Alle FIAE Aufgabe-Dokumente laden
        cur.execute("""
            SELECT d.id, d.dateiname, d.pfad, d.seitenanzahl, d.typ,
                   d.pruefungsbereich, p.zeitraum_label, p.id as pruefung_id
            FROM dokumente d
            LEFT JOIN pruefungen p ON d.pruefung_id = p.id
            WHERE d.typ = 'Aufgabe'
              AND d.dateiname LIKE '%FIAE%'
            ORDER BY p.zeitraum_label, d.dateiname
        """)
        docs = cur.fetchall()

        print(f"Prüfe {len(docs)} FIAE-Aufgabe-Dokumente...")
        print("=" * 80)

        for doc in docs:
            doc_id, dateiname, pfad, seiten, typ, bereich, label, p_id = doc

            # OCR-Text aller Seiten laden
            cur.execute(
                "SELECT ocr_text FROM seiten WHERE dokument_id = %s ORDER BY seiten_nr",
                (doc_id,)
            )
            pages = [r[0] for r in cur.fetchall() if r[0]]

            is_beleg, reason = is_pure_belegsatz(pages)

            if not is_beleg:
                continue

            # Neuer Dateiname: Aufgabe -> Belegsatz
            new_name = dateiname.replace('_Aufgabe_2', '_Belegsatz')
            new_name = new_name.replace('_Aufgabe_3', '_Belegsatz_2')
            new_name = new_name.replace('_Aufgabe_4', '_Belegsatz_3')
            new_name = new_name.replace('_Aufgabe', '_Belegsatz')
            # Falls Name schon Belegsatz enthält, nicht doppelt
            if new_name == dateiname:
                new_name = dateiname.replace('.pdf', '_Belegsatz.pdf') if 'Belegsatz' not in dateiname else dateiname

            # Neuer Pfad
            new_pfad = pfad.replace(dateiname, new_name) if pfad else None

            print(f"[BELEGSATZ] ID={doc_id:4d} | {label or '???':20s} | {bereich or '-':8s} | S={seiten:2d}")
            print(f"  Grund:  {reason}")
            print(f"  Alt:    {dateiname}")
            print(f"  Neu:    {new_name}")

            if not DRY_RUN:
                # 1. Physische Datei umbenennen (in storage/)
                old_path = os.path.join(STORAGE, dateiname)
                new_path = os.path.join(STORAGE, new_name)
                if os.path.exists(old_path):
                    os.rename(old_path, new_path)
                    print(f"  Datei umbenannt: OK")
                else:
                    print(f"  Datei nicht in storage/ gefunden (skip Rename)")

                # 2. Datenbank aktualisieren
                cur.execute("""
                    UPDATE dokumente 
                    SET dateiname = %s, 
                        pfad = REPLACE(pfad, %s, %s),
                        typ = 'Belegsatz'
                    WHERE id = %s
                """, (new_name, dateiname, new_name, doc_id))

                # 3. Auch Versionen aktualisieren
                cur.execute("""
                    UPDATE dokument_versionen
                    SET dateiname = REPLACE(dateiname, %s, %s),
                        storage_pfad = REPLACE(storage_pfad, %s, %s)
                    WHERE dokument_id = %s
                """, (dateiname, new_name, dateiname, new_name, doc_id))

                renamed.append((doc_id, dateiname, new_name, label))
            else:
                renamed.append((doc_id, dateiname, new_name, label))

            print()

        if not DRY_RUN:
            conn.commit()

    # Zusammenfassung
    print("=" * 80)
    if DRY_RUN:
        print(f"[DRY RUN] {len(renamed)} Dateien würden umbenannt werden:")
    else:
        print(f"[DONE] {len(renamed)} Dateien umbenannt und DB aktualisiert:")

    for doc_id, old, new, label in renamed:
        print(f"  ID={doc_id:4d} | {label or '???':20s} | {old} -> {new}")


if __name__ == "__main__":
    main()
