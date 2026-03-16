"""Analysiert die Sommer 2024 gescannten PDFs genauer (alle Seiten)"""
import fitz, os

base = 'c:/Users/CC-Student/Downloads/Telegram Desktop'
files = [
    'Abschlusspruefung_Sommer_2024_Teil_2_Fachinformatiker_Anwendungsentwicklung.pdf',
    'Abschlusspruefung_Sommer_2024_Teil_2_Fachinformatiker_Anwendungsentwicklung (2).pdf',
    'Abschlusspruefung_Sommer_2024_Teil_2_Fachinformatiker_Anwendungsentwicklung (3).pdf',
    'Abschlusspruefung_Sommer_2024_Teil_2_Fachinformatiker_Anwendungsentwicklung (4).pdf',
    'AP Sommer 2024 Wirtschafts- und Sozialkunde Fragen IT-Berufe.pdf',
    # Also check the Aufgaben Winter for GA2 hint
    'Abschlussprüfung_Winter_2024_25_Aufgaben_Fachinformatiker_Anwen.pdf',
    'Abschlussprüfung_Winter_2024_25_Aufgaben_Fachinformatiker_Anwen (2).pdf',
]

for f in files:
    fp = os.path.join(base, f)
    if not os.path.exists(fp):
        continue
    doc = fitz.open(fp)
    sz = os.path.getsize(fp)
    pages = len(doc)
    
    print(f"\n{'='*80}")
    print(f"FILE: {f}")
    print(f"SIZE: {sz:,} bytes, PAGES: {pages}")
    
    total_text = 0
    for i in range(min(pages, 3)):
        text = doc[i].get_text().strip()
        total_text += len(text)
        if text:
            print(f"  Page {i+1}: {text[:200].replace(chr(10), ' ')}")
        else:
            # Check if it has images
            img_list = doc[i].get_images()
            print(f"  Page {i+1}: [NO TEXT - {len(img_list)} images]")
    
    if total_text == 0:
        print(f"  ** Gescanntes Dokument (nur Bilder, kein Text) **")
    
    doc.close()
