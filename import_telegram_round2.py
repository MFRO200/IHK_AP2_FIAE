"""
Import klar identifizierter FIAE-PDFs aus Telegram Desktop (2. Runde)
"""
import os, json, subprocess

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

base = 'c:/Users/CC-Student/Downloads/Telegram Desktop'

imports = [
    # === Winter 2024_25 ===
    # GA1 Lösung (1201 1 Lösungshinweise)
    (f'{base}/Abschlussprüfung_Winter_2024_25_Fachinformatiker_Anwendungsentwicklung.pdf',
     'Abschlussprüfung_Winter_2024_25_FIAE_GA1_Lösungshinweise.pdf',
     'GA1', 'Lösung', '2024_25 Winter'),
    
    # GA2 Aufgabe (Algorithmen, Pseudocode - die (2) Version)
    (f'{base}/Abschlussprüfung_Winter_2024_25_Aufgaben_Fachinformatiker_Anwen (2).pdf',
     'Abschlussprüfung_Winter_2024_25_FIAE_GA2_Aufgaben.pdf',
     'GA2', 'Aufgabe', '2024_25 Winter'),
    
    # WISO Aufgabe (Teil 3)
    (f'{base}/Abschlussprüfung_Winter_2024_25_AP2_Teil_3_Wirtschafts_und_Sozialkunde.pdf',
     'Abschlussprüfung_Winter_2024_25_WISO_Aufgaben.pdf',
     'WISO', 'Aufgabe', '2024_25 Winter'),
    
    # WISO Lösung
    (f'{base}/Abschlussprüfung_Winter_2024_25_Vorläufige_Lösungen_IT_Berufe_AP2.pdf',
     'Abschlussprüfung_Winter_2024_25_WISO_Lösungen.pdf',
     'WISO', 'Lösung', '2024_25 Winter'),
    
    # GA2 Lösung (1201 2 Lösungshinweise) - not in gap list but good to have
    (f'{base}/Abschlussprüfung_Winter_2024_25_Fachinformatiker_Anwendungsentwicklung (2).pdf',
     'Abschlussprüfung_Winter_2024_25_FIAE_GA2_Lösungshinweise.pdf',
     'GA2', 'Lösung', '2024_25 Winter'),
    
    # === Sommer 2024 ===
    # GA1 Aufgabe (10 Seiten, wahrscheinlich GA1 = Planen eines Softwareproduktes)
    (f'{base}/Abschlusspruefung_Sommer_2024_Teil_2_Fachinformatiker_Anwendungsentwicklung.pdf',
     'Abschlusspruefung_Sommer_2024_FIAE_GA1_Aufgaben.pdf',
     'GA1', 'Aufgabe', '2024 Sommer'),
    
    # GA2 Aufgabe (7 Seiten, wahrscheinlich GA2 = Entwicklung/Algorithmen)
    (f'{base}/Abschlusspruefung_Sommer_2024_Teil_2_Fachinformatiker_Anwendungsentwicklung (2).pdf',
     'Abschlusspruefung_Sommer_2024_FIAE_GA2_Aufgaben.pdf',
     'GA2', 'Aufgabe', '2024 Sommer'),
    
    # WISO Aufgabe Sommer 2024
    (f'{base}/AP Sommer 2024 Wirtschafts- und Sozialkunde Fragen IT-Berufe.pdf',
     'AP_Sommer_2024_WISO_Aufgaben.pdf',
     'WISO', 'Aufgabe', '2024 Sommer'),
    
    # Lösungshinweise GA1 Sommer 2024 (1201 1)
    (f'{base}/AP_Sommer_2024_Lösungshinweise_Fachinformatiker_Anwendungsentwicklung.pdf',
     'AP_Sommer_2024_FIAE_GA1_Lösungshinweise.pdf',
     'GA1', 'Lösung', '2024 Sommer'),
    
    # Lösungshinweise GA2 Sommer 2024 (1201 2)
    (f'{base}/AP_Sommer_2024_Lösungshinweise_Fachinformatiker_Anwendungsentwicklung (2).pdf',
     'AP_Sommer_2024_FIAE_GA2_Lösungshinweise.pdf',
     'GA2', 'Lösung', '2024 Sommer'),
    
    # WISO Lösung Sommer 2024
    (f'{base}/AP_Sommer_2024_Vorläufige_Lösungen_Wirtschafts_und_Sozialkunde_IT.pdf',
     'AP_Sommer_2024_WISO_Lösungen.pdf',
     'WISO', 'Lösung', '2024 Sommer'),
]

print(f"Importiere {len(imports)} PDFs...\n")
ok = 0
err = 0
skip = 0

for pfad, name, bereich, typ, ordner in imports:
    pid = ordner_to_id.get(ordner)
    if not pid:
        print(f"SKIP (keine Prüfung für '{ordner}'): {name}")
        skip += 1
        continue
    
    if not os.path.exists(pfad):
        print(f"SKIP (Datei nicht gefunden): {pfad}")
        skip += 1
        continue
    
    size = os.path.getsize(pfad)
    pages = page_count(pfad)
    
    data = {
        'pruefung_id': pid,
        'dateiname': name,
        'pfad': pfad.replace('c:/Users/CC-Student/', '~/'),
        'typ': typ,
        'pruefungsbereich': bereich,
        'dateigroesse': size,
        'seitenanzahl': pages,
    }
    
    resp = api_post('/dokumente', data)
    if 'id' in resp:
        ok += 1
        print(f"OK [{resp['id']:3d}] {bereich:5} {typ:8} {ordner:20} {pages:2}p {name}")
    else:
        err += 1
        msg = str(resp).replace('\n',' ')[:80]
        print(f"ERR: {msg} | {name}")

print(f"\n{'='*60}")
print(f"ERGEBNIS: {ok} importiert, {skip} übersprungen, {err} Fehler")
