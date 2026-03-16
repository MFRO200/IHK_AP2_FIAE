"""Analysiert die Telegram-PDFs um GA1/GA2/WISO zuzuordnen"""
import fitz, os, hashlib

base = 'c:/Users/CC-Student/Downloads/Telegram Desktop'
files = [
    # 2024 Sommer variants
    'Abschlusspruefung_Sommer_2024_Teil_2_Fachinformatiker_Anwendungsentwicklung.pdf',
    'Abschlusspruefung_Sommer_2024_Teil_2_Fachinformatiker_Anwendungsentwicklung (2).pdf',
    'Abschlusspruefung_Sommer_2024_Teil_2_Fachinformatiker_Anwendungsentwicklung (3).pdf',
    'Abschlusspruefung_Sommer_2024_Teil_2_Fachinformatiker_Anwendungsentwicklung (4).pdf',
    'AP_Sommer_2024_Lösungshinweise_Fachinformatiker_Anwendungsentwicklung.pdf',
    'AP_Sommer_2024_Lösungshinweise_Fachinformatiker_Anwendungsentwicklung (2).pdf',
    'AP Sommer 2024 Wirtschafts- und Sozialkunde Fragen IT-Berufe.pdf',
    'AP_Sommer_2024_Vorläufige_Lösungen_Wirtschafts_und_Sozialkunde_IT.pdf',
    # 2024_25 Winter variants
    'Abschlussprüfung_Winter_2024_25_Fachinformatiker_Anwendungsentwicklung.pdf',
    'Abschlussprüfung_Winter_2024_25_Fachinformatiker_Anwendungsentwicklung (2).pdf',
    'Abschlussprüfung_Winter_2024_25_Fachinformatiker_Anwendungsentwicklung (3).pdf',
    'Abschlussprüfung_Winter_2024_25_Fachinformatiker_Anwendungsentwicklung (4).pdf',
    'Abschlussprüfung_Winter_2024_25_Aufgaben_Fachinformatiker_Anwen.pdf',
    'Abschlussprüfung_Winter_2024_25_Aufgaben_Fachinformatiker_Anwen (2).pdf',
    'Abschlussprüfung_Winter_2024_25_Aufgaben_Fachinformatiker_Anwen (3).pdf',
    'Abschlussprüfung_Winter_2024_25_Aufgaben_Fachinformatiker_Anwen (4).pdf',
    'Abschlussprüfung_Winter_2024_25_Lösungshinweise_Fachinformatiker.pdf',
    'Abschlussprüfung_Winter_2024_25_Lösungshinweise_Fachinformatiker (2).pdf',
    'Abschlussprüfung_Winter_2024_25_Lösungshinweise_Fachinformatiker (3).pdf',
    'Abschlussprüfung_Winter_2024_25_Lösungshinweise_Fachinformatiker (4).pdf',
    'Abschlussprüfung_Winter_2024_25_AP2_Teil_3_Wirtschafts_und_Sozialkunde.pdf',
    'Abschlussprüfung_Winter_2024_25_Vorläufige_Lösungen_IT_Berufe_AP2.pdf',
    'Abschlussprüfung_Winter_2024_25_Vorläufige_Lösungen_IT_Berufe_AP2 (2).pdf',
]

seen_hashes = set()
for f in files:
    fp = os.path.join(base, f)
    if not os.path.exists(fp):
        print(f'MISSING: {f}')
        continue

    doc = fitz.open(fp)
    sz = os.path.getsize(fp)
    pages = len(doc)

    with open(fp, 'rb') as fh:
        h = hashlib.md5(fh.read()).hexdigest()[:8]

    dup = ' (DUP)' if h in seen_hashes else ''
    seen_hashes.add(h)

    text = doc[0].get_text()[:400].replace('\n', ' ').strip()
    doc.close()

    print(f'{sz:>10} {pages:2}p {h} {f}{dup}')
    print(f'  >> {text[:180]}')
    print()
