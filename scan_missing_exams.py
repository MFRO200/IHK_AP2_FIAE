"""
Scannt Downloads + Documents nach fehlenden FIAE GA1/GA2/WISO Prüfungen.
Vergleicht mit DB und zeigt was importiert werden könnte.
"""
import os, re, json, subprocess

# ── 1. Fehlende Dokumente aus DB ermitteln ──
raw = subprocess.run(['curl','-s','http://localhost:3000/api/dokumente'], capture_output=True).stdout
docs = json.loads(raw.decode('utf-8'))
pruef = json.loads(subprocess.run(['curl','-s','http://localhost:3000/api/pruefungen'], capture_output=True).stdout.decode('utf-8'))

from collections import defaultdict
have = defaultdict(lambda: defaultdict(set))
for d in docs:
    if not d.get('pruefung_id'): continue
    b = d.get('pruefungsbereich', '')
    t = d.get('typ', '')
    if b in ('GA1','GA2','WISO'):
        have[d['pruefung_id']][b].add(t)

# DB-Dateien für Duplikatprüfung
db_files = set()
for d in docs:
    db_files.add((d['dateiname'].lower().strip(), d.get('dateigroesse', 0)))

ordner_to_id = {p['ordner_name']: p['id'] for p in pruef}
pruef_by_id = {p['id']: p for p in pruef}

# Fehlende ermitteln
missing = []
for p in sorted(pruef, key=lambda x: (x['jahr'], x['semester'])):
    if p['jahr'] < 2000: continue
    pid = p['id']
    for b in ('GA1','GA2','WISO'):
        for t in ('Aufgabe', 'Lösung'):
            if t not in have[pid].get(b, set()):
                missing.append({
                    'pruefung_id': pid,
                    'ordner': p['ordner_name'],
                    'jahr': p['jahr'],
                    'semester': p['semester'],
                    'bereich': b,
                    'typ': t,
                })

print(f"=== {len(missing)} fehlende Dokumente in der DB ===\n")

# ── 2. Scan Downloads + Documents ──
scan_dirs = [
    'c:/Users/CC-Student/Downloads',
    'c:/Users/CC-Student/Documents',
    'c:/Users/CC-Student/Desktop',
]

RELEVANT = re.compile(
    r'(ga[12]|gh[12]|ganzheitliche|wiso|wirtschaft|teil.?2|'
    r'planen.*software|algorithmen|fq|abschluss|anwendung|fiae|fi.?ae)',
    re.IGNORECASE
)

print("Scanne Ordner...")
all_pdfs = []
for base in scan_dirs:
    if not os.path.isdir(base):
        continue
    for root, dirs, files in os.walk(base):
        # Skip IHK_AP2 workspace sub-dirs die schon gescannt wurden
        if 'IHK_AP2' in root:
            skip = any(s in root for s in ['AP_IHK', 'backend', 'frontend', '.venv', 'node_modules'])
            if skip:
                continue
        for f in files:
            if not f.lower().endswith('.pdf'):
                continue
            full = os.path.join(root, f)
            if RELEVANT.search(f) or RELEVANT.search(root):
                try:
                    size = os.path.getsize(full)
                    all_pdfs.append({'name': f, 'path': full, 'size': size})
                except:
                    pass

print(f"Relevante PDFs gefunden: {len(all_pdfs)}\n")

# ── 3. Zeitraum und Bereich aus Dateinamen extrahieren ──
def extract_zeitraum(name, path):
    """Versucht Prüfungszeitraum aus Dateiname/Pfad zu extrahieren."""
    text = name + ' ' + path
    
    # "Winter 2023" / "Sommer 2024" / "W2023" / "S2024"
    m = re.search(r'(?:Winter|W)\s*(\d{4})', text, re.IGNORECASE)
    if m:
        j = int(m.group(1))
        return f"{j}_{str(j+1)[-2:]} Winter"
    
    m = re.search(r'(?:Sommer|S)\s*(\d{4})', text, re.IGNORECASE)
    if m:
        return f"{m.group(1)} Sommer"
    
    # "2023_24 Winter" / "2023_2024 Winter"  
    m = re.search(r'(\d{4})[_/](\d{2,4})\s*(Winter|Sommer)', text, re.IGNORECASE)
    if m:
        j = int(m.group(1))
        sem = m.group(3).capitalize()
        return f"{j}_{str(j+1)[-2:]} {sem}" if sem == 'Winter' else f"{j} {sem}"
    
    # "Sommer2024" / "Winter2023"
    m = re.search(r'(Sommer|Winter)(\d{4})', text, re.IGNORECASE)
    if m:
        sem = m.group(1).capitalize()
        j = int(m.group(2))
        if sem == 'Winter':
            return f"{j}_{str(j+1)[-2:]} Winter"
        return f"{j} Sommer"
    
    # Nur Jahreszahl im Kontext
    m = re.search(r'20(\d{2})', text)
    if m:
        return f"20{m.group(1)}"
    
    return None

def extract_bereich(name):
    fn = name.lower()
    if re.search(r'ga2|gh2|teil.?2.?2|ganzheitliche.*2|algorithmen', fn):
        return 'GA2'
    if re.search(r'wiso|wirtschaft|wi.so|teil.?3', fn):
        return 'WISO'  
    if re.search(r'ga1|gh1|teil.?2.?1|ganzheitliche.*1|planen|fq', fn):
        return 'GA1'
    return None

def extract_typ(name):
    fn = name.lower()
    if any(k in fn for k in ['lösung', 'loesung', 'löser', 'lösungshinweis', 'loesungshinweis', '_l.', '_l-']):
        return 'Lösung'
    return 'Aufgabe'

def is_fiae(name, path):
    """Ist es FIAE-spezifisch oder allgemein (GA2/WISO)?"""
    text = (name + ' ' + path).lower()
    bereich = extract_bereich(name)
    
    # GA2 und WISO sind gleich für alle IT-Berufe → immer relevant
    if bereich in ('GA2', 'WISO'):
        return True
    
    # GA1 ist berufsspezifisch
    if bereich == 'GA1':
        # Explizit FISI/IT-SE/IT-SK/IK → nicht FIAE
        if re.search(r'fi[-_.]?si|fisi|it[-_.]?se|it[-_.]?sk|\bik\b', text):
            return False
        # Explizit FIAE oder aus Anwendungsentwicklung-Ordner
        if re.search(r'fi[-_.]?ae|fiae|fian|anw|awe|anwendung', text):
            return True
        # Unbekannt → könnte FIAE sein
        return True
    
    return True

# ── 4. Matchen ──
matches = []
for pdf in all_pdfs:
    # Bereits in DB?
    key = (pdf['name'].lower().strip(), pdf['size'])
    if key in db_files:
        continue
    
    if not is_fiae(pdf['name'], pdf['path']):
        continue
    
    bereich = extract_bereich(pdf['name'])
    if not bereich:
        continue
    
    typ = extract_typ(pdf['name'])
    zeitraum = extract_zeitraum(pdf['name'], pdf['path'])
    
    # Gegen fehlende Liste prüfen
    pruefung_id = ordner_to_id.get(zeitraum) if zeitraum else None
    
    matches.append({
        'name': pdf['name'],
        'path': pdf['path'],
        'size': pdf['size'],
        'bereich': bereich,
        'typ': typ,
        'zeitraum': zeitraum,
        'pruefung_id': pruefung_id,
        'fills_gap': any(
            m['bereich'] == bereich and m['typ'] == typ and m['pruefung_id'] == pruefung_id
            for m in missing
        ) if pruefung_id else False,
    })

# ── 5. Ergebnis ──
fills = [m for m in matches if m['fills_gap']]
others = [m for m in matches if not m['fills_gap']]

print(f"{'='*80}")
print(f"TREFFER: {len(fills)} PDFs die fehlende Lücken füllen können")
print(f"{'='*80}")
for m in sorted(fills, key=lambda x: (x['zeitraum'] or '', x['bereich'])):
    print(f"  {m['bereich']:5} {m['typ']:8} {m['zeitraum'] or '???':20} {m['name']}")
    print(f"         Pfad: {m['path']}")

if others:
    print(f"\n{'='*80}")
    print(f"WEITERE {len(others)} relevante PDFs (nicht direkt zuordbar oder bereits vorhanden):")
    print(f"{'='*80}")
    for m in sorted(others, key=lambda x: (x['zeitraum'] or '', x['bereich'])):
        status = f"Zeitraum: {m['zeitraum'] or '???'}, Prüfung: {'ja' if m['pruefung_id'] else 'nein'}"
        print(f"  {m['bereich']:5} {m['typ']:8} {m['name']}")
        print(f"         {status} | {m['path']}")

# Zusammenfassung der noch fehlenden
still_missing = [m for m in missing if not any(
    f['bereich'] == m['bereich'] and f['typ'] == m['typ'] and f['pruefung_id'] == m['pruefung_id']
    for f in fills
)]

print(f"\n{'='*80}")
print(f"WEITERHIN FEHLEND: {len(still_missing)} Dokumente (nicht auf Festplatte gefunden)")
print(f"{'='*80}")
for m in still_missing:
    p = pruef_by_id[m['pruefung_id']]
    # Skip spurious entries (2008, 2019, 2022 ohne Semester)
    if p['ordner_name'] in ('2008', '2019', '2022'):
        continue
    print(f"  {m['bereich']:5} {m['typ']:8} {p['ordner_name']}")
