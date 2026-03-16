# -*- coding: utf-8 -*-
"""
SCHNELL-Scan: Sucht PDFs in IHK_AP2 nach 'Anwendungsentwicklung' etc.
Methode: Dateiname + fitz-Textextraktion (KEIN OCR = schnell).
Verschiebt Treffer nach AP_IHK_Anwendungsentwicklung.
"""
import sys, shutil
from pathlib import Path
import fitz

ROOT   = Path(r"C:\Users\CC-Student\Documents\Neuer Ordner\IHK_AP2")
TARGET = ROOT / "AP_IHK_Anwendungsentwicklung"
TARGET.mkdir(exist_ok=True)
LOG    = ROOT / "scan_anw_fast_log.txt"

SKIP = {"AP_IHK_Anwendungsentwicklung", "Zustandsdiagramm", ".venv", "__pycache__"}
KEYWORDS = ["anwendungsentwicklung", "fiae", "fi-ae"]

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

def log(msg):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

# Sammle PDFs
all_pdfs = []
for p in ROOT.rglob("*.pdf"):
    top = p.relative_to(ROOT).parts[0]
    if top in SKIP:
        continue
    all_pdfs.append(p)

# Dedupliziere
seen = {}
for p in all_pdfs:
    if p.name not in seen:
        seen[p.name] = p
pdfs = list(seen.values())

log(f"Gesamt: {len(all_pdfs)}, Einzigartig: {len(pdfs)}")

moved = []
for i, pdf in enumerate(pdfs, 1):
    hit, method = False, ""

    # 1) Dateiname
    if has_kw(pdf.name):
        hit, method = True, "Name"

    # 2) fitz Text (schnell, kein OCR)
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

    if hit:
        dest = unique_dest(pdf.name)
        try:
            shutil.move(str(pdf), str(dest))
            moved.append(f"{pdf.relative_to(ROOT)}  [{method}]")
            log(f"[OK] [{i}/{len(pdfs)}] {pdf.name}  ({method})")
        except Exception as e:
            log(f"[ERR] {pdf.name}: {e}")
    elif i % 50 == 0:
        log(f"... [{i}/{len(pdfs)}]")

log(f"\nFertig. {len(moved)} PDF(s) verschoben.")
for m in moved:
    log(f"  - {m}")
