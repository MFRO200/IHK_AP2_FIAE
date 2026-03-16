#!/usr/bin/env python3
"""
OCR-Scan: Sucht 'Sequenzdiagramm' in allen PDFs unter AP_IHK via Tesseract + PyMuPDF.
Ergebnisse werden in AP_IHK_Anwendungsentwicklung/Sequenzdiagramme kopiert.
"""
import fitz
import pytesseract
from PIL import Image
import shutil
import io
from pathlib import Path

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

ROOT     = Path(r"C:\Users\CC-Student\Documents\Neuer Ordner\IHK_AP2")
SRC      = ROOT / "AP_IHK"
TARGET   = ROOT / "AP_IHK_Anwendungsentwicklung" / "Sequenzdiagramme"
TARGET.mkdir(parents=True, exist_ok=True)

KW        = "sequenzdiagramm"
DPI       = 200
MAX_PAGES = 20
LANG      = "eng"

# Alle PDFs in AP_IHK; Deduplizierung per Dateiname
all_pdfs = list(SRC.rglob("*.pdf"))
seen: dict[str, Path] = {}
for p in all_pdfs:
    if p.name not in seen:
        seen[p.name] = p
pdfs = list(seen.values())

print(f"Gesamt PDFs in AP_IHK: {len(all_pdfs)}")
print(f"Einzigartig (nach Name): {len(pdfs)}")
print(f"Starte OCR-Scan ...\n")

found: list[tuple[str, str]] = []

for i, pdf in enumerate(pdfs, 1):
    try:
        doc = fitz.open(str(pdf))
        n   = min(len(doc), MAX_PAGES)
        hit = False
        for pg in range(n):
            try:
                mat = fitz.Matrix(DPI / 72, DPI / 72)
                pix = doc[pg].get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                text = pytesseract.image_to_string(img, lang=LANG, config="--psm 3")
                if KW in text.casefold():
                    hit = True
                    break
            except Exception:
                pass
        doc.close()

        if hit:
            dest = TARGET / pdf.name
            if not dest.exists():
                shutil.copy2(str(pdf), str(dest))
            rel = str(pdf.relative_to(SRC))
            found.append((pdf.name, rel))
            print(f"  ✓ TREFFER [{i}/{len(pdfs)}]: {pdf.name}", flush=True)
        elif i % 10 == 0:
            print(f"  · [{i}/{len(pdfs)}] verarbeitet ...", flush=True)

    except Exception as e:
        print(f"  Fehler [{i}/{len(pdfs)}]: {pdf.name}: {e}", flush=True)

print(f"\n{'='*60}")
print(f"Fertig. {len(found)} PDF(s) mit 'Sequenzdiagramm' gefunden:")
for name, rel in found:
    print(f"  - {name}  ({rel})")
if found:
    print(f"\nKopiert nach: {TARGET}")
