# -*- coding: utf-8 -*-
"""
Durchsucht ALLE PDFs in IHK_AP2 (inkl. AP_IHK) nach Anwendungsentwicklung.
Ausgenommen: AP_IHK_Anwendungsentwicklung, Zustandsdiagramm, .venv
Methode: 1) Dateiname  2) fitz-Text  3) Tesseract-OCR
Treffer werden nach AP_IHK_Anwendungsentwicklung VERSCHOBEN.
"""
import sys
import io
import shutil
from pathlib import Path

import fitz
import pytesseract
from PIL import Image

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

ROOT   = Path(r"C:\Users\CC-Student\Documents\Neuer Ordner\IHK_AP2")
TARGET = ROOT / "AP_IHK_Anwendungsentwicklung"
TARGET.mkdir(exist_ok=True)
LOG    = ROOT / "scan_anw_log.txt"

SKIP = {"AP_IHK_Anwendungsentwicklung", "Zustandsdiagramm", ".venv",
        "Sequenzdiagramme", "__pycache__"}
KEYWORDS = ["anwendungsentwicklung", "fachinformatiker/in anwendungsentwicklung",
            "fiae", "fi-ae", "fi ae"]
DPI       = 180
MAX_PAGES = 15

def log(msg):
    print(msg, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def has_kw(text):
    t = text.casefold()
    return any(k in t for k in KEYWORDS)

def unique_dest(name):
    dest = TARGET / name
    stem, suffix = Path(name).stem, Path(name).suffix
    n = 1
    while dest.exists():
        dest = TARGET / f"{stem}_{n}{suffix}"
        n += 1
    return dest

# Sammle alle PDFs, Duplikate per Name herausfiltern
all_pdfs: list[Path] = []
for p in ROOT.rglob("*.pdf"):
    top = p.relative_to(ROOT).parts[0]
    if top in SKIP:
        continue
    all_pdfs.append(p)

seen: dict[str, Path] = {}
for p in all_pdfs:
    if p.name not in seen:
        seen[p.name] = p
pdfs = list(seen.values())

log(f"Gesamt PDFs (alle Ordner): {len(all_pdfs)}")
log(f"Einzigartig nach Dateiname: {len(pdfs)}")
log(f"Ziel: {TARGET}\n")

moved = []

for i, pdf in enumerate(pdfs, 1):
    hit, method = False, ""

    # 1) Dateiname
    if has_kw(pdf.name):
        hit, method = True, "Name"

    # 2) fitz Text
    if not hit:
        try:
            doc = fitz.open(str(pdf))
            for page in doc:
                if has_kw(page.get_text()):
                    hit, method = True, "Text"
                    break
            doc.close()
        except Exception:
            pass

    # 3) OCR
    if not hit:
        try:
            doc = fitz.open(str(pdf))
            for pg in range(min(len(doc), MAX_PAGES)):
                try:
                    pix = doc[pg].get_pixmap(
                        matrix=fitz.Matrix(DPI/72, DPI/72),
                        colorspace=fitz.csGRAY)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    text = pytesseract.image_to_string(img, lang="eng", config="--psm 3")
                    if has_kw(text):
                        hit, method = True, "OCR"
                        break
                except Exception:
                    pass
            doc.close()
        except Exception:
            pass

    if hit:
        dest = unique_dest(pdf.name)
        try:
            shutil.move(str(pdf), str(dest))
            rel = str(pdf.relative_to(ROOT))
            moved.append(f"{rel}  [{method}]")
            log(f"[OK] [{i}/{len(pdfs)}] {pdf.name}  ({method})")
        except Exception as e:
            log(f"[ERR] [{i}/{len(pdfs)}] {pdf.name}: {e}")
    elif i % 20 == 0:
        log(f"[ ] [{i}/{len(pdfs)}] verarbeitet...")

log(f"\n{'='*60}")
log(f"Fertig. {len(moved)} PDF(s) verschoben nach AP_IHK_Anwendungsentwicklung:")
for m in moved:
    log(f"  - {m}")
