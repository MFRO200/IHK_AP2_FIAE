"""
Extrahiert alle PDFs aus dem ZIP-Archiv und importiert fehlende in die DB.
"""
import zipfile, os, json, subprocess, hashlib, tempfile, shutil

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

# --- DB-Status laden ---
docs = api_get('/dokumente')
pruef = api_get('/pruefungen')
ordner_to_id = {p['ordner_name']: p['id'] for p in pruef}

print(f"DB: {len(docs)} Dokumente, {len(pruef)} Prüfungen\n")

# --- Bestehende Dokumente sammeln (Bereich+Typ pro Prüfung) ---
existing = set()
for d in docs:
    pid = d.get('pruefung_id')
    b = d.get('pruefungsbereich', '')
    t = d.get('typ', '')
    existing.add((pid, b, t))

# Auch Dateinamen hashen für Duplikate
existing_names = set()
for d in docs:
    existing_names.add(d.get('dateiname','').lower())

# --- ZIP-Mapping: Ordner im ZIP -> DB ordner_name ---
zip_to_db = {
    '2019_20 Winter': '2019_20 Winter',
    '2020 Sommer': '2020 Sommer',
    '2020_21 Winter': '2020_21 Winter',
    '2021 Sommer': '2021 Sommer',
    '2021 Winter FIAE AP2': '2021_22 Winter',
    '2022 AP2 Sommer FIAE': '2022 Sommer',
    '2022 Sommer': '2022 Sommer',
    '2022 Winter': '2022_23 Winter',
    '2022 Frühjahr': None,  # AP1 - skip
    '2022 Herbst': None,    # AP1 - skip
    '2023 Frühjahr': None,  # AP1 - skip
    '2023 Herbst': None,    # AP1 - skip
    '2021 Herbst': None,    # AP1 - skip
    '2023 Sommer FIAE': '2023 Sommer',
    '2023 Sommer': '2023 Sommer',
    '2023 Winter': '2023_24 Winter',
}

# --- Bereich + Typ aus Dateiname erkennen ---
def classify(filename, folder):
    fn = filename.lower()
    
    # Typ
    typ = 'Aufgabe'
    if any(x in fn for x in ['lösung', 'loesung', 'losung', 'lsg']):
        typ = 'Lösung'
    
    # Bereich
    bereich = 'Sonstige'
    if any(x in fn for x in ['wiso', 'wirtschaft', 'sozialkunde']):
        bereich = 'WISO'
    elif 'ga2' in fn or '_2.' in fn or 'teil_2' in fn or 'teil2_2' in fn:
        bereich = 'GA2'
    elif 'ga1' in fn or '_1.' in fn or 'teil_1' in fn or 'teil2_1' in fn:
        bereich = 'GA1'
    elif 'fiae' in fn and 'fisi' not in fn:
        # FIAE-spezifisch ohne GA1/GA2 Kennzeichnung
        if 'entwicklung' in fn or 'umsetzung' in fn or 'algorithmen' in fn:
            bereich = 'GA2'
        elif 'planen' in fn or 'softwareprodukt' in fn:
            bereich = 'GA1'
        else:
            bereich = 'GA1'  # Default für FIAE
    elif 'fisi' in fn:
        if 'analyse' in fn or 'netzwerk' in fn:
            bereich = 'GA1 FISI'
        elif 'konzeption' in fn or 'administration' in fn:
            bereich = 'GA2'  # GA2 ist gleich für alle
        else:
            bereich = 'GA1 FISI'
    
    # Spezielle Korrekturen für bekannte Dateinamen
    if 'belegsatz' in fn or 'korrekturhinweis' in fn or 'erlauterung' in fn or 'zusatz' in fn:
        bereich = 'Sonstige'
    
    # IK, IT-SE, IT-SK Professions
    if ' ik ' in fn or '_ik_' in fn or '_ik.' in fn:
        if 'ga1' in fn:
            bereich = 'GA1 IK'
    if ' it-se ' in fn or '_it-se' in fn or ' se ' in fn:
        if 'ga1' in fn or ' se ' in fn:
            bereich = 'GA1 IT-SE'
    if ' it-sk ' in fn or '_it-sk' in fn or ' sk ' in fn:
        if 'ga1' in fn or ' sk ' in fn:
            bereich = 'GA1 IT-SK'
    
    # 2023 Winter spezielle Dateien
    if '2023 Winter' in folder:
        if 'ap2_1' in fn:
            bereich = 'GA1'
            typ = 'Aufgabe'
        elif 'ap2_2' in fn:
            bereich = 'GA2'
            typ = 'Aufgabe'
        elif 'planen' in fn:
            bereich = 'GA1'
        elif 'entwicklung' in fn or 'umsetzung' in fn:
            bereich = 'GA2'
        elif 'teil_1_losung' in fn or 'teil_1_lösung' in fn:
            bereich = 'GA1'
            typ = 'Lösung'
        elif 'teil_2_losung' in fn or 'teil_2_lösung' in fn:
            bereich = 'GA2'
            typ = 'Lösung'
    
    # 2021 Winter spezielle Dateien
    if '2021 Winter' in folder:
        if 'teil2_1' in fn:
            bereich = 'GA1'
        elif 'teil2_2' in fn:
            bereich = 'GA2'
        elif 'teil2_l' in fn.replace('ö','o'):
            # Combined lösung file
            bereich = 'GA1'  # Will handle specially
    
    return bereich, typ

# --- Extrahieren und analysieren ---
zip_path = 'c:/Users/CC-Student/Downloads/Telegram Desktop/IHK_Abschlussprüfungen_AP2 2020-2023.zip'
extract_dir = 'c:/Users/CC-Student/Documents/Neuer Ordner/IHK_AP2/zip_extract_temp'

if os.path.exists(extract_dir):
    shutil.rmtree(extract_dir)
os.makedirs(extract_dir)

zf = zipfile.ZipFile(zip_path, 'r')
zf.extractall(extract_dir)
zf.close()

print("ZIP extrahiert.\n")

# --- Alle PDFs durchgehen ---
imported = 0
skipped_ap1 = 0
skipped_dup = 0
skipped_sonstige = 0
errors = 0
new_imports = []

for root, dirs, files in os.walk(extract_dir):
    for f in files:
        if not f.lower().endswith('.pdf'):
            continue
        
        fp = os.path.join(root, f)
        rel = os.path.relpath(fp, extract_dir).replace('\\', '/')
        folder = rel.split('/')[0] if '/' in rel else ''
        
        # Ordner-Mapping
        db_ordner = zip_to_db.get(folder)
        if db_ordner is None:
            skipped_ap1 += 1
            continue
        
        pid = ordner_to_id.get(db_ordner)
        if not pid:
            print(f"SKIP (kein DB-Ordner '{db_ordner}'): {rel}")
            skipped_ap1 += 1
            continue
        
        bereich, typ = classify(f, folder)
        
        if bereich == 'Sonstige':
            skipped_sonstige += 1
            continue
        
        # Duplikat-Check
        if (pid, bereich, typ) in existing:
            skipped_dup += 1
            continue
        
        # Dateiname-Check
        if f.lower() in existing_names:
            skipped_dup += 1
            continue
        
        size = os.path.getsize(fp)
        pages = page_count(fp)
        
        data = {
            'pruefung_id': pid,
            'dateiname': f,
            'pfad': f'zip://IHK_Abschlussprüfungen_AP2 2020-2023.zip/{rel}',
            'typ': typ,
            'pruefungsbereich': bereich,
            'dateigroesse': size,
            'seitenanzahl': pages,
        }
        
        resp = api_post('/dokumente', data)
        if 'id' in resp:
            imported += 1
            existing.add((pid, bereich, typ))
            existing_names.add(f.lower())
            print(f"OK [{resp['id']:3d}] {bereich:10} {typ:8} {db_ordner:20} {pages:2}p {f}")
        else:
            errors += 1
            print(f"ERR: {str(resp)[:60]} | {f}")

# Aufräumen
shutil.rmtree(extract_dir)

print(f"\n{'='*60}")
print(f"ERGEBNIS:")
print(f"  Importiert:        {imported}")
print(f"  Duplikate:         {skipped_dup}")
print(f"  AP1/übersprungen:  {skipped_ap1}")
print(f"  Sonstige:          {skipped_sonstige}")
print(f"  Fehler:            {errors}")
print(f"{'='*60}")
