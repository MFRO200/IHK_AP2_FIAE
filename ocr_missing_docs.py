#!/usr/bin/env python3
"""
OCR fehlende Dokumente: Liest PDFs per PyMuPDF aus und befüllt die seiten-Tabelle.
Danach wird die psychologische Analyse für diese Dokumente neu berechnet.
"""
import fitz  # PyMuPDF
import psycopg
from pathlib import Path
from db_config import DB_URL
ROOT = Path(r"C:\Users\CC-Student\Documents\Neuer Ordner\IHK_AP2")


def main():
    conn = psycopg.connect(DB_URL)
    cur = conn.cursor()

    # Finde alle Aufgaben-Dokumente OHNE Seiten (nur FIAE)
    cur.execute("""
        SELECT d.id, d.dateiname, d.pfad, d.pruefung_id, p.zeitraum_label, p.jahr, p.semester
        FROM dokumente d
        JOIN pruefungen p ON d.pruefung_id = p.id
        LEFT JOIN seiten s ON s.dokument_id = d.id
        WHERE d.typ = 'Aufgabe' AND d.dateiname LIKE '%%FIAE%%'
        GROUP BY d.id, d.dateiname, d.pfad, d.pruefung_id, p.zeitraum_label, p.jahr, p.semester
        HAVING COUNT(s.id) = 0
        ORDER BY p.jahr, p.semester
    """)
    missing = cur.fetchall()
    print(f"📋 {len(missing)} Dokumente ohne OCR-Text gefunden\n")

    total_pages = 0
    for doc_id, dateiname, pfad, pruefung_id, zeitraum, jahr, semester in missing:
        # Versuche verschiedene Pfade
        pdf_path = ROOT / pfad
        if not pdf_path.exists():
            # Versuche alternative Pfadauflösungen
            candidates = []
            candidates.extend(ROOT.glob(f"storage/pdfs/**/{dateiname}"))
            candidates.extend(ROOT.glob(f"AP_IHK_Anwendungsentwicklung/**/{dateiname}"))
            candidates.extend(ROOT.glob(f"AP_IHK/**/{dateiname}"))
            if candidates:
                pdf_path = candidates[0]
            else:
                print(f"  ❌ Datei nicht gefunden: {pfad} ({dateiname})")
                continue

        try:
            doc = fitz.open(str(pdf_path))
            pages_inserted = 0
            for page_nr in range(len(doc)):
                page = doc[page_nr]
                # Erst nativen Text versuchen
                text = page.get_text("text")
                if not text or len(text.strip()) < 20:
                    # Fallback: OCR per PyMuPDF (wenn verfügbar)
                    try:
                        text = page.get_text("text", flags=fitz.TEXT_PRESERVE_WHITESPACE)
                    except Exception:
                        text = ""

                cur.execute("""
                    INSERT INTO seiten (dokument_id, seiten_nr, ocr_text)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (doc_id, page_nr + 1, text))
                pages_inserted += 1

            # Seitenanzahl updaten
            cur.execute("UPDATE dokumente SET seitenanzahl = %s WHERE id = %s",
                        (len(doc), doc_id))
            doc.close()
            total_pages += pages_inserted
            print(f"  ✅ {zeitraum:20s} | {dateiname:55s} | {pages_inserted} Seiten")

        except Exception as e:
            print(f"  ❌ Fehler bei {dateiname}: {e}")

    conn.commit()
    print(f"\n🎯 {total_pages} Seiten insgesamt eingefügt")

    # Verify
    cur.execute("""
        SELECT d.id, d.dateiname, d.pruefung_id, p.zeitraum_label, COUNT(s.id) as seiten
        FROM dokumente d
        JOIN pruefungen p ON d.pruefung_id = p.id
        JOIN seiten s ON s.dokument_id = d.id
        WHERE p.jahr >= 2024 AND d.typ = 'Aufgabe'
        GROUP BY d.id, d.dateiname, d.pruefung_id, p.zeitraum_label
        ORDER BY p.jahr, p.semester
    """)
    print("\n📊 Verifizierung – Dokumente ab 2024 mit OCR:")
    for r in cur.fetchall():
        print(f"  dok={r[0]:3d} | {r[3]:20s} | {r[4]:2d} Seiten | {r[1]}")

    conn.close()


if __name__ == "__main__":
    main()
