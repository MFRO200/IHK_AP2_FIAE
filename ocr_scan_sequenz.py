#!/usr/bin/env python3
"""
OCR-Scan: Sucht 'Sequenzdiagramm' in gescannten PDFs via Tesseract + PyMuPDF.
Gefundene PDFs werden in AP_IHK_Anwendungsentwicklung/Sequenzdiagramme kopiert.
"""
import fitz
import pytesseract
from PIL import Image
import shutil
import io
from pathlib import Path

# Pfad zu Tesseract (Windows-Standard)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

SRC = Path(r"C:\Users\CC-Student\Documents\Neuer Ordner\IHK_AP2\AP_IHK_Anwendungsentwicklung")
TARGET = SRC / "Sequenzdiagramme"
TARGET.mkdir(exist_ok=True)

KW = "sequenzdiagramm"
DPI = 200       # höheres DPI = bessere Genauigkeit, aber langsamer
MAX_PAGES = 20  # max Seiten pro PDF (die meisten Prüfungen haben <15 Seiten)
LANG = "eng"  # Tesseract Sprachpakete (deu nicht installiert)

# Alle PDFs (Sequenzdiagramme-Ordner ausschließen)
all_pdfs = [p for p in SRC.rglob("*.pdf") if "Sequenzdiagramme" not in p.parts]

# Deduplizierung anhand Dateiname (vermeidet doppelten Scan identischer Prüfungen)
seen_names: dict[str, Path] = {}
for p in all_pdfs:
    if p.name not in seen_names:
        seen_names[p.name] = p
pdfs = list(seen_names.values())

print(f"Gesamt PDFs: {len(all_pdfs)}, nach Deduplizierung: {len(pdfs)}")
print(f"OCR-Sprache: {LANG}, DPI: {DPI}, max Seiten/PDF: {MAX_PAGES}")
print("Starte OCR-Scan (ca. 5–15 Sek./PDF) ...\n")

found: list[str] = []

for i, pdf in enumerate(pdfs, 1):
    try:
        doc = fitz.open(str(pdf))
        n = min(len(doc), MAX_PAGES)
        hit = False
        for pg in range(n):
            try:
                page = doc[pg]
                # Seite als Pixmap mit gewünschtem DPI rendern
                mat = fitz.Matrix(DPI / 72, DPI / 72)
                pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                text = pytesseract.image_to_string(img, lang=LANG, config="--psm 3")
                if KW in text.casefold():
                    hit = True
                    break
            except Exception as e:
                print(f"  Seitenfehler {pdf.name} S.{pg+1}: {e}")
        doc.close()

        if hit:
            dest = TARGET / pdf.name
            if not dest.exists():
                shutil.copy2(str(pdf), str(dest))
            found.append(pdf.name)
            print(f"  ✓ TREFFER [{i}/{len(pdfs)}]: {pdf.name}")
        else:
            print(f"  · [{i}/{len(pdfs)}] {pdf.name}")

    except Exception as e:
        print(f"  Fehler [{i}/{len(pdfs)}]: {pdf.name}: {e}")

print(f"\n{'='*60}")
print(f"Fertig. {len(found)} PDF(s) mit 'Sequenzdiagramm' gefunden:")
for f in found:
    print(f"  - {f}")
if found:
    print(f"\nKopiert nach: {TARGET}")
