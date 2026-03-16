#!/usr/bin/env python3
"""
Fast OCR mit Tesseract + Multiprocessing fuer scanned FIAE-Dokumente.
Aktualisiert die seiten-Tabelle mit dem OCR-Text.
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
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
from db_config import DB_URL

# Decompression bomb warning unterdruecken
Image.MAX_IMAGE_PIXELS = None
warnings.filterwarnings("ignore", category=Image.DecompressionBombWarning)
ROOT = Path(r"C:\Users\CC-Student\Documents\Neuer Ordner\IHK_AP2")
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSDATA_DIR = str(ROOT / "tessdata")
DPI = 150  # Niedriger = schneller, 150 reicht fuer Textextraktion
LANG = "deu"  # Nur Deutsch, schneller als deu+eng
WORKERS = max(1, multiprocessing.cpu_count() - 1)  # CPU-Kerne - 1


def ocr_single_page(args):
    """OCR einer einzelnen Seite (fuer multiprocessing)."""
    pdf_path, page_nr, doc_id = args
    try:
        # Jeder Worker braucht eigene Tesseract-Konfiguration
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
        os.environ["TESSDATA_PREFIX"] = TESSDATA_DIR

        doc = fitz.open(str(pdf_path))
        page = doc[page_nr]
        mat = fitz.Matrix(DPI / 72, DPI / 72)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        text = pytesseract.image_to_string(img, lang=LANG, config="--psm 3")
        doc.close()
        return (doc_id, page_nr + 1, text.strip())
    except Exception as e:
        return (doc_id, page_nr + 1, None)


def find_pdf(dateiname, pfad):
    """Finde die PDF-Datei auf dem Dateisystem."""
    if pfad:
        full = ROOT / pfad
        if full.exists():
            return full
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
    matches = list(ROOT.rglob(dateiname))
    if matches:
        return matches[0]
    return None


def main():
    conn = psycopg.connect(DB_URL)
    cur = conn.cursor()

    # Dokumente mit leeren seiten-Eintraegen
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
              AND (s.ocr_text IS NULL OR LENGTH(s.ocr_text) < 10)
          )
        ORDER BY p.zeitraum_label, d.pruefungsbereich
    """)

    docs = cur.fetchall()
    print(f"[INFO] {len(docs)} Dokumente brauchen Tesseract-OCR", flush=True)
    print(f"[INFO] Workers: {WORKERS}, DPI: {DPI}, Lang: {LANG}", flush=True)

    if not docs:
        print("[OK] Fertig!")
        conn.close()
        return

    # Sammle alle OCR-Jobs
    all_jobs = []
    doc_info = {}
    for doc_id, dateiname, pfad, bereich, zeitraum in docs:
        pdf_path = find_pdf(dateiname, pfad)
        if not pdf_path:
            print(f"  [SKIP] PDF nicht gefunden: {dateiname}", flush=True)
            continue

        # Finde Seiten die OCR brauchen
        cur.execute("""
            SELECT seiten_nr FROM seiten
            WHERE dokument_id = %s AND (ocr_text IS NULL OR LENGTH(ocr_text) < 10)
            ORDER BY seiten_nr
        """, (doc_id,))
        seiten = [r[0] for r in cur.fetchall()]

        for sn in seiten:
            all_jobs.append((str(pdf_path), sn - 1, doc_id))  # page_nr ist 0-basiert in fitz

        doc_info[doc_id] = (dateiname, bereich, zeitraum, len(seiten))

    print(f"[INFO] {len(all_jobs)} Seiten zu verarbeiten aus {len(doc_info)} Dokumenten", flush=True)

    # Parallel OCR
    updated_pages = 0
    updated_docs = set()
    batch = []

    with ProcessPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(ocr_single_page, job): job for job in all_jobs}

        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            if result and result[2]:
                doc_id, seiten_nr, text = result
                batch.append((text, doc_id, seiten_nr))
                updated_docs.add(doc_id)

            # Batch-Update alle 50 Seiten
            if len(batch) >= 50 or i == len(futures):
                for text, did, sn in batch:
                    cur.execute("""
                        UPDATE seiten SET ocr_text = %s
                        WHERE dokument_id = %s AND seiten_nr = %s
                    """, (text, did, sn))
                    updated_pages += 1
                conn.commit()
                batch = []

            if i % 20 == 0 or i == len(futures):
                print(f"  [PROGRESS] {i}/{len(futures)} Seiten verarbeitet, {updated_pages} aktualisiert", flush=True)

    conn.close()

    print(f"\n{'='*60}", flush=True)
    print(f"[DONE] {updated_pages} Seiten in {len(updated_docs)} Dokumenten mit OCR-Text aktualisiert", flush=True)


if __name__ == "__main__":
    main()
