"""
Scannt alle Ordner nach GA1, GA2, WISO-Prüfungen (FIAE + allgemein)
und importiert fehlende PDFs in die DB. Dedupliziert nach Dateiname+Größe.
"""
import json, subprocess, os, re, hashlib

BASE = 'c:/Users/CC-Student/Documents/Neuer Ordner/IHK_AP2'

# ── 1. DB-Stand laden ──
def api_get(path):
    r = subprocess.run(['curl', '-s', f'http://localhost:3000/api{path}'], capture_output=True, text=True)
    return json.loads(r.stdout)

def api_post(path, data):
    r = subprocess.run(
        ['curl', '-s', '-X', 'POST', f'http://localhost:3000/api{path}',
         '-H', 'Content-Type: application/json', '-d', json.dumps(data)],
        capture_output=True, text=True
    )
    return json.loads(r.stdout)

db_docs = api_get('/dokumente')
db_pruefungen = api_get('/pruefungen')
ordner_to_id = {p['ordner_name']: p['id'] for p in db_pruefungen}

# Existierende Dateien: Dateiname (lowercase) + Größe als Duplikat-Key
db_keys = set()
for d in db_docs:
    key = (d['dateiname'].lower().strip(), d.get('dateigroesse', 0))
    db_keys.add(key)
# Auch Pfade merken
db_pfade = set(d['pfad'].replace('\\', '/') for d in db_docs)

print(f"DB: {len(db_docs)} Dokumente, {len(db_pruefungen)} Prüfungen")

# ── 2. Relevanz-Filter ──
# GA1/GH1 (Ganzheitliche Aufgabe I) - für FIAE
# GA2/GH2 (Ganzheitliche Aufgabe II) - für alle (ist berufsspez. für FIAE = Algorithmen)
# WISO - für alle IT-Berufe (gleich)
# NICHT: FISI-GA1 spezifisch (die sind berufsspezifisch), 
#        aber GA2 ist gleich für alle, WISO ist gleich für alle
RELEVANT_PATTERN = re.compile(
    r'(ga[12_]|gh[12_]|ganzheitliche|wiso|wirtschaft|wi.so|teil.?2.?[12]|'
    r'planen.*software|algorithmen|anlag|handreichung)', 
    re.IGNORECASE
)

# FISI-spezifisch EXKLUDIEREN (GA1 ist berufsspezifisch!)
FISI_GA1_PATTERN = re.compile(r'(fi.?si|fisi).*ga1|ga1.*(fi.?si|fisi)', re.IGNORECASE)
# Aber FISI-GA1 Lösungen sind trotzdem nützlich zum Vergleichen... 
# User sagt: GA2 für AE, GA1 für alle (Ganzheitliche Aufgabe I), WISO für alle
# Also: GA1 mit FISI ist OK (Ganzheitliche Aufgabe I ist für alle Berufe identisch!)

# AUSSCHLUSS: nicht-relevante GA1-Dateien für andere Berufe (IT-SE, IT-SK, IK)
# User möchte GA1 = "Ganzheitliche Aufgabe I" - die ist GLEICH für alle IT-Berufe!
# Also IT-SE GA1, IT-SK GA1, FI-SI GA1 sind DERSELBE Inhalt wie FIAE GA1
# → Wir nehmen nur EINE Kopie pro Prüfungszeitraum

def is_relevant(filename, path):
    """Prüft ob die Datei relevant ist (GA1, GA2, WISO, Anlagen)"""
    fn = filename.lower()
    
    # Muss eine relevante Bezeichnung haben
    if not RELEVANT_PATTERN.search(fn):
        # Prüfe auch den Pfad
        if not RELEVANT_PATTERN.search(path.lower()):
            return False
    
    # Definitiv irrelevant: Prüfungskataloge, Sequenzdiagramm-Bearbeitungen
    if 'prüfungskatalog' in fn or 'pruefungskatalog' in fn:
        return False
    if 'bearbeitet' in fn:
        return False  # Eigene Bearbeitungen, keine Originalprüfungen
    if 'konto' in fn or 'auszug' in fn:
        return False  # Bank-Downloads
    
    return True

def get_zeitraum(path):
    """Extrahiert den Prüfungszeitraum aus dem Pfad."""
    # Typische Ordnernamen: "2001_02 Winter", "2003 Sommer", etc.
    m = re.search(r'(\d{4}(?:_\d{2})?\s+(?:Winter|Sommer))', path)
    if m:
        return m.group(1).strip()
    # Auch: "Winter2001", "Sommer2002" im Dateinamen
    m = re.search(r'(Winter|Sommer)\s*(\d{4})', path, re.IGNORECASE)
    if m:
        sem = m.group(1).capitalize()
        jahr = int(m.group(2))
        if sem == 'Winter':
            return f"{jahr}_{str(jahr+1)[-2:]} Winter"
        return f"{jahr} {sem}"
    # S2016, W2017
    m = re.search(r'[SW](\d{4})', os.path.basename(path))
    if m:
        jahr = int(m.group(1))
        prefix = path[path.index(m.group(0))]
        if prefix == 'W':
            return f"{jahr}_{str(jahr+1)[-2:]} Winter"
        return f"{jahr} Sommer"
    return None

def classify(filename, path):
    """Bestimmt Typ und Prüfungsbereich."""
    fn = filename.lower()
    
    # Typ
    typ = 'Aufgabe'
    if any(k in fn for k in ['lösung', 'loesung', 'löser', 'lösungen', 'lösungshinweis']):
        typ = 'Lösung'
    if any(k in fn for k in ['handreichung', 'hinweise_zur_projekt']):
        typ = 'Handreichung'
    if 'anlage' in fn or 'anlag' in fn:
        typ = 'Aufgabe'  # Anlagen gehören zur Aufgabe
    
    # Prüfungsbereich
    bereich = None
    if 'ga2' in fn or 'gh2' in fn or 'teil2_2' in fn or 'teil 2' in fn or 'algorithmen' in fn or 'ganzheitliche aufgabe 2' in fn or 'ganzheitliche aufgabe ii' in fn or 'gh_2' in fn or 'fq_anw' in fn:
        bereich = 'GA2'
    elif 'wiso' in fn or 'wirtschaft' in fn or 'wi_so' in fn or 'wi so' in fn or 'wi.so' in fn or 'teil 3' in fn or 'teil2_wiso' in fn or 'teil_3' in fn:
        bereich = 'WISO'
    elif 'ga1' in fn or 'gh1' in fn or 'teil2_1' in fn or 'ganzheitliche aufgabe 1' in fn or 'ganzheitliche aufgabe i' in fn or 'gh_1' in fn or 'planen' in fn:
        bereich = 'GA1'
    elif 'ap1' in fn or 'teil 1' in fn or 'teil1' in fn or 'arbeitsplatz' in fn:
        bereich = 'AP1'
    
    if not bereich:
        # Fallback nach Pfad
        path_l = path.lower()
        if 'ga2' in path_l or 'gh2' in path_l:
            bereich = 'GA2'
        elif 'wiso' in path_l:
            bereich = 'WISO'
        elif 'ga1' in path_l or 'gh1' in path_l:
            bereich = 'GA1'
        else:
            bereich = 'Sonstige'
    
    return typ, bereich

def get_page_count(filepath):
    try:
        import fitz
        doc = fitz.open(filepath)
        count = len(doc)
        doc.close()
        return count
    except:
        return 0

# ── 3. Alle relevanten PDFs sammeln ──
print("\nScanning...")
candidates = []
for root, dirs, files in os.walk(BASE):
    # Skip irrelevante Ordner
    rel_root = os.path.relpath(root, BASE).replace('\\', '/')
    if any(rel_root.startswith(skip) for skip in ['.git', '.venv', 'backend', 'frontend', 'prisma', 'db', '__pycache__', 'node_modules', 'Ergebnisse']):
        continue
    
    for f in files:
        if not f.lower().endswith('.pdf'):
            continue
        
        full = os.path.join(root, f)
        rel = os.path.relpath(full, BASE).replace('\\', '/')
        
        if not is_relevant(f, rel):
            continue
        
        size = os.path.getsize(full)
        candidates.append({
            'dateiname': f,
            'pfad': rel,
            'full': full,
            'size': size,
            'key': (f.lower().strip(), size),
        })

print(f"Relevante PDFs gefunden: {len(candidates)}")

# ── 4. Deduplizieren: Gleicher Dateiname + gleiche Größe = Duplikat ──
# Wir behalten die kürzeste Pfad-Variante (bevorzugt AP_IHK_Anwendungsentwicklung)
unique = {}
for c in candidates:
    key = c['key']
    if key not in unique:
        unique[key] = c
    else:
        # Bevorzuge AP_IHK_Anwendungsentwicklung > AP_IHK_Andere_Berufe > AP_IHK > rest
        existing = unique[key]
        def priority(p):
            if p.startswith('AP_IHK_Anwendungsentwicklung/'): return 0
            if p.startswith('AP_IHK_Andere_Berufe/'): return 1
            if p.startswith('WISO '): return 2
            if p.startswith('Lösungen '): return 3
            if p.startswith('AP_IHK/'): return 4
            return 5
        if priority(c['pfad']) < priority(existing['pfad']):
            unique[key] = c

print(f"Nach Deduplizierung: {len(unique)} unique PDFs")

# ── 5. Gegen DB prüfen ──
to_import = []
already_in_db = 0
for key, c in unique.items():
    if key in db_keys or c['pfad'] in db_pfade:
        already_in_db += 1
        continue
    to_import.append(c)

print(f"Bereits in DB: {already_in_db}")
print(f"Zu importieren: {len(to_import)}")

# ── 6. Prüfungs-ID zuordnen ──
for c in to_import:
    zeitraum = get_zeitraum(c['pfad'])
    c['zeitraum'] = zeitraum
    c['pruefung_id'] = ordner_to_id.get(zeitraum)
    typ, bereich = classify(c['dateiname'], c['pfad'])
    c['typ'] = typ
    c['bereich'] = bereich
    c['pages'] = get_page_count(c['full'])

# ── 7. Fehlende Prüfungszeiträume anlegen ──
missing_zeitraeume = set()
for c in to_import:
    if not c['pruefung_id'] and c['zeitraum']:
        missing_zeitraeume.add(c['zeitraum'])

for zt in sorted(missing_zeitraeume):
    # Parse
    m = re.match(r'(\d{4})(?:_(\d{2}))?\s+(Winter|Sommer)', zt)
    if m:
        jahr = int(m.group(1))
        semester = m.group(3)
        zeitraum_label = f"{semester} {zt.split()[0]}"
        print(f"  Erstelle Prüfung: {zt} → {zeitraum_label}")
        resp = api_post('/pruefungen', {
            'jahr': jahr,
            'semester': semester,
            'zeitraum_label': zeitraum_label,
            'ordner_name': zt,
        })
        if 'id' in resp:
            ordner_to_id[zt] = resp['id']
            print(f"    → ID {resp['id']}")
        else:
            print(f"    FEHLER: {resp}")

# Update Prüfungs-IDs
for c in to_import:
    if not c['pruefung_id'] and c['zeitraum']:
        c['pruefung_id'] = ordner_to_id.get(c['zeitraum'])

# ── 8. Import ──
print(f"\n{'='*60}")
print(f"Importiere {len(to_import)} PDFs...")
print(f"{'='*60}")

imported = 0
skipped = 0
errors = 0

for c in sorted(to_import, key=lambda x: x['pfad']):
    if not c['pruefung_id']:
        print(f"SKIP (keine Prüfung): {c['pfad']}")
        skipped += 1
        continue
    
    payload = {
        'pruefung_id': c['pruefung_id'],
        'dateiname': c['dateiname'],
        'pfad': c['pfad'],
        'typ': c['typ'],
        'pruefungsbereich': c['bereich'],
        'dateigroesse': c['size'],
        'seitenanzahl': c['pages'],
    }
    
    resp = api_post('/dokumente', payload)
    if 'id' in resp:
        imported += 1
        print(f"OK [{resp['id']:3d}] {c['bereich']:5} {c['typ']:10} {c['pfad']}")
    else:
        errors += 1
        print(f"ERR: {str(resp)[:80]} | {c['pfad']}")

print(f"\n{'='*60}")
print(f"ERGEBNIS: {imported} importiert, {skipped} übersprungen, {errors} Fehler")
print(f"{'='*60}")
