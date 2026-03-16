#!/usr/bin/env python3
"""
OCR mit Tesseract für Dokumente die nur gescannte Bilder enthalten (text_len=0).
Aktualisiert die seiten-Tabelle mit dem OCR-Text.
Nur FIAE-Dokumente.
"""

import fitz
import pytesseract
from PIL import Image
import io
import os
import sys
import warnings
import psycopg
from pathlib import Path
from db_config import DB_URL

# Decompression bomb warning unterdrücken (große Scan-Seiten)
Image.MAX_IMAGE_PIXELS = None
warnings.filterwarnings("ignore", category=Image.DecompressionBombWarning)
ROOT = Path(r"C:\Users\CC-Student\Documents\Neuer Ordner\IHK_AP2")
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSDATA_DIR = str(ROOT / "tessdata")
os.environ["TESSDATA_PREFIX"] = TESSDATA_DIR
DPI = 200  # Reduziert für schnellere Verarbeitung, reicht für OCR
LANG = "deu+eng"  # Deutsch primär, Englisch als Fallback


def ocr_page(page) -> str:
    """Extrahiere Text aus einer PDF-Seite mittels Tesseract OCR."""
    mat = fitz.Matrix(DPI / 72, DPI / 72)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    text = pytesseract.image_to_string(
        img,
        lang=LANG,
        config='--psm 3'
    )
    return text.strip()


def find_pdf(dateiname: str, pfad: str | None) -> Path | None:
    """Finde die PDF-Datei auf dem Dateisystem."""
    # Direkt im storage
    if pfad:
        full = ROOT / pfad
        if full.exists():
            return full

    # Suche in gängigen Verzeichnissen
    search_dirs = [
        ROOT / "storage" / "pdfs",
        ROOT / "AP_IHK_Anwendungsentwicklung",
        ROOT / "AP_IHK",
    ]
    for sd in search_dirs:
        if not sd.exists():
            continue
        matches = list(sd.rglob(dateiname))
        if matches:
            return matches[0]

    # Globale Suche
    matches = list(ROOT.rglob(dateiname))
    if matches:
        return matches[0]

    return None


def main():
    conn = psycopg.connect(DB_URL)
    cur = conn.cursor()

    # Dokumente mit seiten-Einträgen aber leerem OCR-Text (gescannte PDFs)
    cur.execute("""
        SELECT d.id, d.dateiname, d.pfad, d.pruefungsbereich, p.zeitraum_label
        FROM dokumente d
        JOIN pruefungen p ON d.pruefung_id = p.id
        LEFT JOIN psycho_analyse pa ON pa.pruefung_id = d.pruefung_id AND pa.pruefungsbereich = d.pruefungsbereich
        WHERE d.typ = 'Aufgabe'
          AND d.dateiname LIKE '%%FIAE%%'
          AND d.pruefungsbereich IS NOT NULL
          AND pa.id IS NULL
          AND EXISTS (
              SELECT 1 FROM seiten s WHERE s.dokument_id = d.id
          )
        ORDER BY p.zeitraum_label, d.pruefungsbereich
    """)

    docs = cur.fetchall()
    print(f"[INFO] {len(docs)} Dokumente mit leerem OCR-Text gefunden (brauchen Tesseract)", flush=True)

    if not docs:
        print("[OK] Keine fehlenden Dokumente!")
        conn.close()
        return

    # Teste Tesseract
    try:
        v = pytesseract.get_tesseract_version()
        print(f"[OCR] Tesseract v{v}, Lang: {LANG}, DPI: {DPI}", flush=True)
    except Exception as e:
        print(f"[WARN]  Tesseract Check warnung: {e}", flush=True)

    total_updated = 0
    total_pages = 0
    errors = []

    for idx, (doc_id, dateiname, pfad, bereich, zeitraum) in enumerate(docs, 1):
        pdf_path = find_pdf(dateiname, pfad)
        if not pdf_path:
            errors.append(f"  [FAIL] PDF nicht gefunden: {dateiname}")
            continue

        try:
            doc = fitz.open(str(pdf_path))
            pages_updated = 0

            for page_nr in range(len(doc)):
                try:
                    text = ocr_page(doc[page_nr])
                except Exception as pe:
                    print(f"    [SKIP] Seite {page_nr+1} Fehler: {pe}", flush=True)
                    continue
                if text:
                    # Update bestehende seiten-Einträge
                    cur.execute("""
                        UPDATE seiten SET ocr_text = %s
                        WHERE dokument_id = %s AND seiten_nr = %s AND (ocr_text IS NULL OR LENGTH(ocr_text) < 10)
                    """, (text, doc_id, page_nr + 1))
                    if cur.rowcount > 0:
                        pages_updated += 1

            doc.close()
            total_pages += pages_updated
            total_updated += 1

            print(f"  [OK] [{idx}/{len(docs)}] {bereich:5s} | {zeitraum:20s} | {pages_updated:2d} Seiten | {dateiname[:55]}", flush=True)

            # Zwischenspeichern alle 5 Dokumente
            if idx % 5 == 0:
                conn.commit()

        except Exception as e:
            errors.append(f"  [FAIL] [{idx}] {dateiname}: {e}")
            print(f"  [FAIL] [{idx}] {dateiname}: {e}", flush=True)

    conn.commit()
    conn.close()

    print(f"\n{'='*60}")
    print(f"\n[DONE] {total_updated} Dokumente mit Tesseract-OCR aktualisiert")
    print(f"[PAGES] {total_pages} Seiten mit Text befuellt")
    if errors:
        print(f"\n[WARN]  {len(errors)} Fehler:")
        for e in errors:
            print(e)


if __name__ == "__main__":
    main()
