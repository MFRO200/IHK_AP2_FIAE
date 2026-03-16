#!/usr/bin/env python3
"""Scan all PDFs in AP_IHK_Anwendungsentwicklung for 'Sequenzdiagramm' using PyMuPDF (fitz)."""
import fitz
import shutil
from pathlib import Path
import sys

src = Path(r"C:\Users\CC-Student\Documents\Neuer Ordner\IHK_AP2\AP_IHK_Anwendungsentwicklung")
target = src / "Sequenzdiagramme"
target.mkdir(exist_ok=True)

kw = "sequenzdiagramm"
found = []

pdfs = [p for p in src.rglob("*.pdf") if "Sequenzdiagramme" not in p.parts]
total = len(pdfs)
print(f"Scanne {total} PDFs ...", flush=True)

for i, pdf in enumerate(pdfs, 1):
    try:
        doc = fitz.open(str(pdf))
        hit = False
        for page in doc:
            if kw in page.get_text().casefold():
                hit = True
                break
        doc.close()
        if hit:
            dest = target / pdf.name
            if not dest.exists():
                shutil.copy2(str(pdf), str(dest))
            found.append(str(pdf.relative_to(src)))
            print(f"  TREFFER [{i}/{total}]: {pdf.name}", flush=True)
    except Exception as e:
        print(f"  Fehler [{i}/{total}]: {pdf.name}: {e}", flush=True)

    if i % 20 == 0:
        print(f"  ... {i}/{total} verarbeitet", flush=True)

print(f"\nFertig. {len(found)} PDF(s) mit 'Sequenzdiagramm' gefunden.")
for f in found:
    print(" -", f)
