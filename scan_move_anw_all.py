# -*- coding: utf-8 -*-
"""
Verschiebt ALLE PDFs (keine Deduplizierung!) mit Anwendungsentwicklung/FIAE/FI-AE
nach AP_IHK_Anwendungsentwicklung. Dateiname + fitz-Text.
"""
import sys, shutil
from pathlib import Path
import fitz

ROOT   = Path(r"C:\Users\CC-Student\Documents\Neuer Ordner\IHK_AP2")
TARGET = ROOT / "AP_IHK_Anwendungsentwicklung"
TARGET.mkdir(exist_ok=True)
LOG    = ROOT / "scan_anw_all_log.txt"

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

# Alle PDFs sammeln - OHNE Deduplizierung
all_pdfs = []
for p in ROOT.rglob("*.pdf"):
    top = p.relative_to(ROOT).parts[0]
    if top in SKIP:
        continue
    all_pdfs.append(p)

total = len(all_pdfs)
log(f"Gesamt PDFs zu pruefen: {total}")
log(f"Ziel: {TARGET}\n")

moved = []
for i, pdf in enumerate(all_pdfs, 1):
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

    if hit:
        dest = unique_dest(pdf.name)
        try:
            shutil.move(str(pdf), str(dest))
            rel = str(pdf.relative_to(ROOT))
            moved.append(f"{rel}  [{method}]")
            log(f"[OK] [{i}/{total}] {pdf.name}  ({method})")
        except Exception as e:
            log(f"[ERR] {pdf.name}: {e}")
    elif i % 100 == 0:
        log(f"... [{i}/{total}]")

log(f"\nFertig. {len(moved)} PDF(s) verschoben.")
for m in moved:
    log(f"  - {m}")
