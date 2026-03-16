# -*- coding: utf-8 -*-
"""
Durchsucht alle PDFs in AP_IHK_Anwendungsentwicklung nach 'Sequenzdiagramm'.
Treffer werden in IHK_AP2/Sequenzdiagramm kopiert.
Methode: 1) fitz-Text  2) Tesseract-OCR (max 15 Seiten)
"""
import sys, shutil, io
from pathlib import Path
import fitz
import pytesseract
from PIL import Image

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

ROOT   = Path(r"C:\Users\CC-Student\Documents\Neuer Ordner\IHK_AP2")
SRC    = ROOT / "AP_IHK_Anwendungsentwicklung"
TARGET = ROOT / "Sequenzdiagramm"
TARGET.mkdir(exist_ok=True)
LOG    = ROOT / "scan_sequenz_log.txt"

KW = "sequenzdiagramm"
DPI = 180
MAX_PAGES = 15

def log(msg):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def unique_dest(name):
    dest = TARGET / name
    stem, suffix = Path(name).stem, Path(name).suffix
    n = 1
    while dest.exists():
        dest = TARGET / f"{stem}_{n}{suffix}"
        n += 1
    return dest

# Alle PDFs sammeln (Sequenzdiagramme-Unterordner ausschliessen)
all_pdfs = [p for p in SRC.rglob("*.pdf") if "Sequenzdiagramme" not in p.parts]
total = len(all_pdfs)
log(f"PDFs zu durchsuchen: {total}")
log(f"Keyword: {KW}")
log(f"Ziel: {TARGET}\n")

found = []
for i, pdf in enumerate(all_pdfs, 1):
    hit, method = False, ""

    # 1) fitz Text
    try:
        doc = fitz.open(str(pdf))
        for page in doc:
            if KW in page.get_text().casefold():
                hit, method = True, "Text"
                break
        doc.close()
    except Exception:
        pass

    # 2) OCR
    if not hit:
        try:
            doc = fitz.open(str(pdf))
            n = min(len(doc), MAX_PAGES)
            for pg in range(n):
                try:
                    pix = doc[pg].get_pixmap(
                        matrix=fitz.Matrix(DPI/72, DPI/72),
                        colorspace=fitz.csGRAY)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    text = pytesseract.image_to_string(img, lang="eng", config="--psm 3")
                    if KW in text.casefold():
                        hit, method = True, "OCR"
                        break
                except Exception:
                    pass
            doc.close()
        except Exception:
            pass

    if hit:
        dest = unique_dest(pdf.name)
        shutil.copy2(str(pdf), str(dest))
        found.append(pdf.name)
        log(f"[OK] [{i}/{total}] {pdf.name}  ({method})")
    elif i % 20 == 0:
        log(f"... [{i}/{total}]")

log(f"\nFertig. {len(found)} PDF(s) mit 'Sequenzdiagramm' gefunden und kopiert.")
for f in found:
    log(f"  - {f}")
