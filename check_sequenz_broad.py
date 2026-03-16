import fitz
from pathlib import Path

src = Path(r"C:\Users\CC-Student\Documents\Neuer Ordner\IHK_AP2\AP_IHK_Anwendungsentwicklung")
pdfs = [p for p in src.rglob("*.pdf") if "Sequenzdiagramme" not in p.parts]
hits = {}
for pdf in pdfs:
    try:
        doc = fitz.open(str(pdf))
        for page in doc:
            t = page.get_text().casefold()
            if "sequenz" in t:
                idx = t.find("sequenz")
                hits[pdf.name] = t[max(0, idx-30):idx+80].strip()
                break
        doc.close()
    except Exception:
        pass

print(f"PDFs mit 'sequenz': {len(hits)}")
for name, ctx in hits.items():
    print(f"  {name}: ...{ctx}...")
