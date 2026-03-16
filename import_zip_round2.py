"""
Import der 2021 Sommer + 2023 Winter PDFs aus dem ZIP (2. Runde)
"""
import zipfile, os, json, subprocess, shutil

API = 'http://localhost:3000/api'

def api_get(path):
    r = subprocess.run(['curl','-s',f'{API}{path}'], capture_output=True)
    return json.loads(r.stdout.decode('utf-8'))

def api_post(path, data):
    r = subprocess.run(
        ['curl', '-s', '-X', 'POST', f'{API}{path}',
         '-H', 'Content-Type: application/json; charset=utf-8',
         '-d', json.dumps(data, ensure_ascii=False).encode('utf-8')],
        capture_output=True)
    return json.loads(r.stdout.decode('utf-8'))

def page_count(filepath):
    try:
        import fitz
        doc = fitz.open(filepath)
        c = len(doc)
        doc.close()
        return c
    except:
        return 0

pruef = api_get('/pruefungen')
ordner_to_id = {p['ordner_name']: p['id'] for p in pruef}
pid_2021s = ordner_to_id.get('2021 Sommer')
pid_2023w = ordner_to_id.get('2023_24 Winter')

print(f"2021 Sommer ID: {pid_2021s}")
print(f"2023_24 Winter ID: {pid_2023w}")

# Extrahieren
zip_path = 'c:/Users/CC-Student/Downloads/Telegram Desktop/IHK_Abschlussprüfungen_AP2 2020-2023.zip'
extract_dir = 'c:/Users/CC-Student/Documents/Neuer Ordner/IHK_AP2/zip_extract_temp'

if os.path.exists(extract_dir):
    shutil.rmtree(extract_dir)
os.makedirs(extract_dir)

zf = zipfile.ZipFile(zip_path, 'r')
# Nur die relevanten Ordner extrahieren
for name in zf.namelist():
    if name.startswith('2021 Sommer/') or name.startswith('2023 Winter/') or name.startswith('2023 Sommer FIAE/'):
        zf.extract(name, extract_dir)
zf.close()

# Manuelles Mapping
imports = []

# === 2021 Sommer (alle Dateien) ===
folder = os.path.join(extract_dir, '2021 Sommer')
if os.path.exists(folder):
    for f in os.listdir(folder):
        if not f.lower().endswith('.pdf'):
            continue
        fn = f.lower()
        
        bereich = 'Sonstige'
        typ = 'Aufgabe'
        
        if any(x in fn for x in ['lösung', 'loesung']):
            typ = 'Lösung'
        
        if 'wiso' in fn:
            bereich = 'WISO'
        elif 'ga2' in fn:
            bereich = 'GA2'
        elif 'ga1' in fn:
            if 'fiae' in fn:
                bereich = 'GA1'
            elif 'fisi' in fn:
                bereich = 'GA1 FISI'
            elif ' ik ' in fn or '_ik' in fn:
                bereich = 'GA1 IK'
            elif 'it-se' in fn or ' se ' in fn:
                bereich = 'GA1 IT-SE'
            elif 'it-sk' in fn or ' sk ' in fn:
                bereich = 'GA1 IT-SK'
            else:
                bereich = 'GA1'
        
        # Skip "(1)" duplicates
        if '(1)' in f:
            continue
        # Skip "Lösung Sommer 2021_GA1_FISI.pdf" / "Lösung Sommer 2021_GA2.pdf" (duplicates)
        if f.startswith('Lösung Sommer'):
            continue
        
        if bereich != 'Sonstige':
            imports.append((os.path.join(folder, f), f, bereich, typ, '2021 Sommer', pid_2021s))

# === 2023 Winter ===
folder = os.path.join(extract_dir, '2023 Winter')
manual_2023w = [
    ('Fachinformatiker_Anwendungsentwicklung_Planen_eines_Softwareproduktes.pdf', 'GA1', 'Aufgabe'),
    ('Fachinformatiker_Anwendungsentwicklung_Entwicklung_und_Umsetzung.pdf', 'GA2', 'Aufgabe'),
    ('Abschlussprufung_Winter_2023-2024_Teil_1_Losung.pdf', 'GA1', 'Lösung'),
    ('Abschlussprufung_Winter_2023-2024_Teil_2_Losung.pdf', 'GA2', 'Lösung'),
    ('WISOW23_24.pdf', 'WISO', 'Aufgabe'),
    ('WiSo_AP2_Winter23_FiSi_Teil_3_Losung.pdf', 'WISO', 'Lösung'),
    # AP2_1W23_24.pdf = GA1 Aufgabe (already have it?)
    # AP2_2W23_24.pdf = GA2 Aufgabe (already have it?)
]
if os.path.exists(folder):
    for f, bereich, typ in manual_2023w:
        fp = os.path.join(folder, f)
        if os.path.exists(fp):
            imports.append((fp, f, bereich, typ, '2023_24 Winter', pid_2023w))

# === 2023 Sommer FIAE (Lösungen) ===
folder = os.path.join(extract_dir, '2023 Sommer FIAE')
manual_2023sf = [
    ('2023_Sommer_-_FIAE_1.pdf', 'GA1', 'Aufgabe'),
    ('2023_Sommer_-_FIAE_2.pdf', 'GA2', 'Aufgabe'),
    ('2023_Sommer_-_FIAE_Lösungen.pdf', 'GA1', 'Lösung'),  # Combined, mark as GA1
    ('2023_Sommer_WiSo.pdf', 'WISO', 'Aufgabe'),
]
pid_2023s = ordner_to_id.get('2023 Sommer')
if os.path.exists(folder):
    for f, bereich, typ in manual_2023sf:
        fp = os.path.join(folder, f)
        if os.path.exists(fp):
            imports.append((fp, f, bereich, typ, '2023 Sommer', pid_2023s))

print(f"\nZu importieren: {len(imports)} PDFs\n")

# Check existing docs
docs = api_get('/dokumente')
existing = set()
for d in docs:
    existing.add((d.get('pruefung_id'), d.get('pruefungsbereich',''), d.get('typ','')))
existing_names = set(d.get('dateiname','').lower() for d in docs)

ok = 0
skip = 0
err = 0

for pfad, name, bereich, typ, ordner, pid in imports:
    # Duplikat-Check
    if name.lower() in existing_names:
        print(f"SKIP (Dateiname-Dup): {name}")
        skip += 1
        continue
    
    if (pid, bereich, typ) in existing:
        print(f"SKIP (Bereich+Typ exists): {bereich:10} {typ:8} {ordner:20} {name}")
        skip += 1
        continue
    
    size = os.path.getsize(pfad)
    pages = page_count(pfad)
    
    data = {
        'pruefung_id': pid,
        'dateiname': name,
        'pfad': f'zip://IHK_Abschlussprüfungen_AP2 2020-2023.zip/{ordner}/{name}',
        'typ': typ,
        'pruefungsbereich': bereich,
        'dateigroesse': size,
        'seitenanzahl': pages,
    }
    
    resp = api_post('/dokumente', data)
    if 'id' in resp:
        ok += 1
        existing.add((pid, bereich, typ))
        existing_names.add(name.lower())
        print(f"OK [{resp['id']:3d}] {bereich:10} {typ:8} {ordner:20} {pages:2}p {name}")
    else:
        err += 1
        print(f"ERR: {str(resp)[:60]} | {name}")

shutil.rmtree(extract_dir)

print(f"\n{'='*60}")
print(f"Importiert: {ok}, Übersprungen: {skip}, Fehler: {err}")
