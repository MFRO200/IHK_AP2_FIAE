#!/usr/bin/env python3
"""
ocr_extract_loesungen.py
OCR + Musterlösungen-Extraktion für Scan-only Lösungs-PDFs.

Schritt 1: Tesseract-OCR auf jede Seite → seiten-Tabelle
Schritt 2: Musterlösungen parsen → musterloesungen-Tabelle

Ziel: Sommer 2024 (IDs 716, 717, 781) + Winter 2025/26 (ID 793)
"""

import re
import sys
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import psycopg
from db_config import DB_URL

# Tesseract-Pfad (Windows)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# OCR-Einstellungen
DPI = 200
LANG = "deu+eng"
PSM = "--psm 3"

# Dokument-IDs der fehlenden Lösungs-PDFs
TARGET_DOC_IDS = [716, 717, 781, 793]

# ─── Regex für Musterlösungen-Parsing ───
RE_AUFGABE = re.compile(
    r'^(\d+)\.\s*(?:Aufgabe|Handlungsschritt)\s*\((\d+)\s*Punkte?\)',
    re.IGNORECASE | re.MULTILINE,
)

RE_SUB = re.compile(
    r'^([a-z]{1,2})\)\s+(\d+)\s*Punkte?',
    re.IGNORECASE | re.MULTILINE,
)

# WISO: "Aufgabe 1 ... richtig: B" Pattern
RE_WISO = re.compile(
    r'(?:Aufgabe|Frage)\s*(\d+).*?(?:richtig|Lösung|Antwort)\s*[:=]?\s*([A-E])',
    re.IGNORECASE | re.DOTALL,
)

# Alternative WISO: Tabellen-Format "1  B" oder "1. B"
RE_WISO_TABLE = re.compile(
    r'^(\d+)[.\s]+([A-E])\s*$',
    re.MULTILINE,
)


def ocr_page(page, dpi=DPI):
    """Rendert eine PDF-Seite und führt Tesseract OCR durch."""
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    text = pytesseract.image_to_string(img, lang=LANG, config=PSM)
    return text.strip()


def parse_ga_solutions(full_text: str) -> list[dict]:
    """Parsed GA-Lösungstext in strukturierte Aufgaben."""
    results = []
    aufgabe_matches = list(RE_AUFGABE.finditer(full_text))
    if not aufgabe_matches:
        return results

    for i, m in enumerate(aufgabe_matches):
        aufg_nr = m.group(1)
        max_punkte = int(m.group(2))
        start = m.end()
        end = aufgabe_matches[i + 1].start() if i + 1 < len(aufgabe_matches) else len(full_text)
        block = full_text[start:end].strip()

        sub_matches = list(RE_SUB.finditer(block))
        subs = []

        if sub_matches:
            for j, sm in enumerate(sub_matches):
                sub_label = sm.group(1).lower()
                sub_punkte = int(sm.group(2))
                sub_start = sm.end()
                sub_end = sub_matches[j + 1].start() if j + 1 < len(sub_matches) else len(block)
                sub_text = block[sub_start:sub_end].strip()
                sub_text = re.sub(r'\nZPA\s+FI[A-Z]*\s+.*$', '', sub_text, flags=re.MULTILINE).strip()
                subs.append({
                    'aufgabe': f"{aufg_nr}.{sub_label}",
                    'text': sub_text,
                    'max_punkte': sub_punkte,
                })

        if sub_matches:
            main_text = block[:sub_matches[0].start()].strip()
        else:
            main_text = block

        main_text = re.sub(r'\nZPA\s+FI[A-Z]*\s+.*$', '', main_text, flags=re.MULTILINE).strip()

        # Gesamttext mit Subs
        if subs:
            combined = main_text + "\n\n" if main_text else ""
            for s in subs:
                combined += f"{s['aufgabe']}) ({s['max_punkte']} P.): {s['text']}\n\n"
            main_text_full = combined.strip()
        else:
            main_text_full = main_text

        results.append({
            'aufgabe': aufg_nr,
            'text': main_text_full,
            'max_punkte': max_punkte,
            'subs': subs,
        })

    return results


def parse_wiso_solutions(full_text: str) -> list[dict]:
    """Parsed WISO-Lösungstext (Multiple-Choice-Antworten)."""
    results = []
    seen = set()

    # Methode 1: Explizites Pattern
    for m in RE_WISO.finditer(full_text):
        nr = m.group(1)
        answer = m.group(2).upper()
        if nr not in seen:
            seen.add(nr)
            results.append({
                'aufgabe': nr,
                'text': f"Richtige Antwort: {answer}",
                'max_punkte': 1,
                'subs': [],
            })

    # Methode 2: Tabellen-Format
    for m in RE_WISO_TABLE.finditer(full_text):
        nr = m.group(1)
        answer = m.group(2).upper()
        if nr not in seen:
            seen.add(nr)
            results.append({
                'aufgabe': nr,
                'text': f"Richtige Antwort: {answer}",
                'max_punkte': 1,
                'subs': [],
            })

    return sorted(results, key=lambda x: int(x['aufgabe']))


def main():
    print("=" * 60)
    print("OCR + Musterlösungen-Extraktion für fehlende Lösungs-PDFs")
    print("=" * 60)

    with psycopg.connect(DB_URL) as conn:
        cur = conn.cursor()

        # Ziel-Dokumente laden
        cur.execute("""
            SELECT d.id, d.dateiname, d.pfad, d.pruefungsbereich, d.pruefung_id
            FROM dokumente d
            WHERE d.id = ANY(%s)
            ORDER BY d.id
        """, (TARGET_DOC_IDS,))
        docs = cur.fetchall()

        if not docs:
            print("Keine Dokumente gefunden!")
            return

        total_seiten = 0
        total_muster = 0

        for doc_id, dateiname, pfad, bereich, pruefung_id in docs:
            print(f"\n{'─' * 50}")
            print(f"📄 {dateiname} (ID={doc_id}, Bereich={bereich})")
            print(f"   Pfad: {pfad}")

            # PDF öffnen
            try:
                doc = fitz.open(pfad)
            except Exception as e:
                print(f"   ❌ Kann PDF nicht öffnen: {e}")
                continue

            page_count = len(doc)
            print(f"   Seiten: {page_count}")

            # Schritt 1: OCR
            print(f"   🔍 Starte OCR ({LANG}, DPI={DPI})...")
            all_texts = []
            for page_nr in range(page_count):
                page = doc[page_nr]

                # Erst nativen Text versuchen
                native_text = page.get_text("text").strip()
                if len(native_text) > 50:
                    text = native_text
                    src = "nativ"
                else:
                    text = ocr_page(page)
                    src = "OCR"

                if text:
                    all_texts.append(text)
                    # In seiten-Tabelle einfügen
                    cur.execute("""
                        INSERT INTO seiten (dokument_id, seiten_nr, ocr_text)
                        VALUES (%s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, (doc_id, page_nr + 1, text))
                    total_seiten += 1
                    print(f"      Seite {page_nr + 1}/{page_count}: {len(text)} Zeichen ({src})")
                else:
                    print(f"      Seite {page_nr + 1}/{page_count}: ⚠ Kein Text erkannt")

            # seitenanzahl aktualisieren
            if page_count > 0:
                cur.execute("UPDATE dokumente SET seitenanzahl = %s WHERE id = %s", (page_count, doc_id))

            doc.close()

            if not all_texts:
                print(f"   ⚠ Kein Text extrahiert — überspringe Musterlösung")
                continue

            # Schritt 2: Musterlösungen parsen
            full_text = "\n".join(all_texts)
            print(f"\n   📝 Parse Musterlösungen (Bereich: {bereich})...")

            if bereich == "WISO":
                aufgaben = parse_wiso_solutions(full_text)
            else:
                aufgaben = parse_ga_solutions(full_text)

            if not aufgaben:
                # Fallback: ganzen Text als eine Musterlösung speichern
                if len(full_text) > 20:
                    print(f"   ⚠ Keine strukturierten Aufgaben erkannt — speichere als Gesamttext")
                    try:
                        cur.execute("""
                            INSERT INTO musterloesungen (pruefung_id, aufgabe, erwartung_text, max_punkte, hinweise)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (pruefung_id, aufgabe) DO UPDATE
                            SET erwartung_text = EXCLUDED.erwartung_text,
                                max_punkte = EXCLUDED.max_punkte,
                                hinweise = EXCLUDED.hinweise
                        """, (pruefung_id, f"{bereich}_gesamt", full_text[:5000], 0,
                              f"Quelle: {dateiname} (Gesamttext, keine Struktur erkannt)"))
                        total_muster += 1
                    except Exception as e:
                        print(f"   ❌ Fehler: {e}")
                continue

            for aufg in aufgaben:
                aufgabe_key = aufg['aufgabe']
                text = aufg['text']

                if not text or len(text) < 3:
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
                    total_muster += 1
                    print(f"      ✅ Aufgabe {aufgabe_key}: {len(text)} Zeichen, {aufg['max_punkte']} P.")
                except Exception as e:
                    print(f"      ❌ Aufgabe {aufgabe_key}: {e}")

                # Sub-Aufgaben einzeln
                for s in aufg.get('subs', []):
                    if len(s['text']) < 3:
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
                        total_muster += 1
                        print(f"      ✅ Aufgabe {s['aufgabe']}: {len(s['text'])} Zeichen, {s['max_punkte']} P.")
                    except Exception as e:
                        print(f"      ❌ Aufgabe {s['aufgabe']}: {e}")

        conn.commit()

    print(f"\n{'=' * 60}")
    print(f"✅ Fertig!")
    print(f"   Seiten OCR'd:       {total_seiten}")
    print(f"   Musterlösungen:     {total_muster}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
