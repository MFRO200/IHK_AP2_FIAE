#!/usr/bin/env python3
"""
Durchsucht alle PDFs in IHK_AP2 (außer AP_IHK*, Zustandsdiagramm) nach
'Anwendungsentwicklung' und verschiebt Treffer nach AP_IHK_Anwendungsentwicklung.
Suche: 1) Dateiname  2) fitz-Textextraktion  3) Tesseract-OCR
"""
import fitz
import pytesseract
from PIL import Image
import shutil
import io
from pathlib import Path

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

ROOT   = Path(r"C:\Users\CC-Student\Documents\Neuer Ordner\IHK_AP2")
TARGET = ROOT / "AP_IHK_Anwendungsentwicklung"
TARGET.mkdir(exist_ok=True)

# Ordner die übersprungen werden sollen
SKIP_DIRS = {"AP_IHK_Anwendungsentwicklung", "Zustandsdiagramm", ".venv"}

KEYWORDS  = ["anwendungsentwicklung", "fiae", "fachinformatiker anwendungsentwicklung"]
DPI       = 200
MAX_PAGES = 20

# Alle PDFs außerhalb der Skip-Ordner sammeln, mit Deduplizierung per Dateiname
seen: dict[str, Path] = {}
for p in ROOT.rglob("*.pdf"):
    parts = p.relative_to(ROOT).parts
    if parts[0] in SKIP_DIRS:
        continue
    if p.name not in seen:
        seen[p.name] = p
all_pdfs = list(seen.values())

print(f"Einzigartige PDFs zum Durchsuchen: {len(all_pdfs)}")
print(f"Zielordner: {TARGET}\n")

def has_kw(text: str) -> bool:
    t = text.casefold()
    return any(k in t for k in KEYWORDS)

moved: list[str] = []

def unique_dest(target_dir: Path, name: str) -> Path:
    dest = target_dir / name
    stem, suffix = Path(name).stem, Path(name).suffix
    counter = 1
    while dest.exists():
        dest = target_dir / f"{stem}_{counter}{suffix}"
        counter += 1
    return dest

for i, pdf in enumerate(all_pdfs, 1):
    hit = False
    method = ""

    # 1) Dateiname
    if has_kw(pdf.name):
        hit = True
        method = "Dateiname"

    # 2) fitz Textextraktion
    if not hit:
        try:
            doc = fitz.open(str(pdf))
            for page in doc:
                if has_kw(page.get_text()):
                    hit = True
                    method = "Text"
                    break
            doc.close()
        except Exception:
            pass

    # 3) OCR (nur wenn keine Textschicht gefunden)
    if not hit:
        try:
            doc = fitz.open(str(pdf))
            n = min(len(doc), MAX_PAGES)
            for pg in range(n):
                try:
                    mat = fitz.Matrix(DPI / 72, DPI / 72)
                    pix = doc[pg].get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    text = pytesseract.image_to_string(img, lang="eng", config="--psm 3")
                    if has_kw(text):
                        hit = True
                        method = "OCR"
                        break
                except Exception:
                    pass
            doc.close()
        except Exception:
            pass

    if hit:
        dest = unique_dest(TARGET, pdf.name)
        shutil.move(str(pdf), str(dest))
        moved.append(f"{pdf.relative_to(ROOT)}  [{method}]")
        print(f"  [OK] [{i}/{len(all_pdfs)}] {pdf.name}  ({method})", flush=True)
    elif i % 10 == 0:
        print(f"  · [{i}/{len(all_pdfs)}] verarbeitet ...", flush=True)

print(f"\n{'='*60}")
print(f"Fertig. {len(moved)} PDF(s) verschoben:")
for m in moved:
    print(f"  - {m}")
