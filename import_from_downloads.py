"""
Importiert die gefundenen fehlenden PDFs aus Downloads/Documents in die DB.
"""
import os, json, subprocess, re

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

# Manuell zugeordnete Importe aus dem Scan-Ergebnis
# Format: (pfad, dateiname, bereich, typ, ordner_name)
imports = [
    # === TREFFER die Lücken füllen ===
    
    # 2021_22 Winter - WISO Aufgabe fehlt
    ('c:/Users/CC-Student/Downloads/Abschlußprüfung Winter 2021 2022 Wirtschafts und Sozialkunde.pdf',
     'Abschlußprüfung Winter 2021 2022 Wirtschafts und Sozialkunde.pdf',
     'WISO', 'Aufgabe', '2021_22 Winter'),
    
    # 2022 Sommer - GA1 Aufgabe + Lösung, GA2 Aufg + Lös, WISO Aufg + Lös fehlen
    ('c:/Users/CC-Student/Downloads/Telegram Desktop/26. Das Gold des Piraten/IHK-Prüfungen/IHK-Prüfungen/IHK_Abschlussprüfungen_AP2 1999-2023/2022 Sommer/AP S2022 IT GA1 FIAE Lösung.pdf',
     'AP S2022 IT GA1 FIAE Lösung.pdf',
     'GA1', 'Lösung', '2022 Sommer'),
    
    ('c:/Users/CC-Student/Downloads/Telegram Desktop/26. Das Gold des Piraten/IHK-Prüfungen/IHK-Prüfungen/IHK_Abschlussprüfungen_AP2 1999-2023/2022 Sommer/AP S2022 IT GA2 IT-SK.pdf',
     'AP S2022 IT GA2.pdf',  # GA2 ist gleich für alle
     'GA2', 'Aufgabe', '2022 Sommer'),
    
    ('c:/Users/CC-Student/Downloads/Telegram Desktop/26. Das Gold des Piraten/IHK-Prüfungen/IHK-Prüfungen/IHK_Abschlussprüfungen_AP2 1999-2023/2022 Sommer/AP S2022 IT GA2 Lösung.pdf',
     'AP S2022 IT GA2 Lösung.pdf',
     'GA2', 'Lösung', '2022 Sommer'),
    
    ('c:/Users/CC-Student/Downloads/Telegram Desktop/26. Das Gold des Piraten/IHK-Prüfungen/IHK-Prüfungen/IHK_Abschlussprüfungen_AP2 1999-2023/2022 Sommer/AP S2022 IT WiSo.pdf',
     'AP S2022 IT WiSo.pdf',
     'WISO', 'Aufgabe', '2022 Sommer'),
    
    ('c:/Users/CC-Student/Downloads/Telegram Desktop/26. Das Gold des Piraten/IHK-Prüfungen/IHK-Prüfungen/IHK_Abschlussprüfungen_AP2 1999-2023/2022 Sommer/AP S2022 IT WiSo Lösung.pdf',
     'AP S2022 IT WiSo Lösung.pdf',
     'WISO', 'Lösung', '2022 Sommer'),
    
    # "2022" Prüfung - das sind Dateien aus Telegram mit Sommer 2022 Label + Winter 2022
    # Sommer 2022 Aufgaben (aus dem 1999-2023 Archiv)
    ('c:/Users/CC-Student/Downloads/Telegram Desktop/26. Das Gold des Piraten/IHK-Prüfungen/IHK-Prüfungen/IHK_Abschlussprüfungen_AP2 1999-2023/2022 AP2 Sommer FIAE/1.0_FIAE_Pruefung_Sommer_2022_Teil_2_Planen_Softwareprodukt.pdf',
     '1.0_FIAE_Pruefung_Sommer_2022_Teil_2_Planen_Softwareprodukt.pdf',
     'GA1', 'Aufgabe', '2022 Sommer'),
    
    ('c:/Users/CC-Student/Downloads/Telegram Desktop/26. Das Gold des Piraten/IHK-Prüfungen/IHK-Prüfungen/IHK_Abschlussprüfungen_AP2 1999-2023/2022 AP2 Sommer FIAE/2.1_FIAE_Pruefung_Sommer_2022_Teil_2_Entwicklung_Algorithmen.pdf',
     '2.1_FIAE_Pruefung_Sommer_2022_Teil_2_Entwicklung_Algorithmen.pdf',
     'GA2', 'Aufgabe', '2022 Sommer'),
    
    ('c:/Users/CC-Student/Downloads/Telegram Desktop/26. Das Gold des Piraten/IHK-Prüfungen/IHK-Prüfungen/IHK_Abschlussprüfungen_AP2 1999-2023/2022 AP2 Sommer FIAE/3.1_FIAE_Pruefung_Sommer_2022_Teil_2_WISO.pdf',
     '3.1_FIAE_Pruefung_Sommer_2022_Teil_2_WISO.pdf',
     'WISO', 'Aufgabe', '2022 Sommer'),
    
    ('c:/Users/CC-Student/Downloads/Telegram Desktop/26. Das Gold des Piraten/IHK-Prüfungen/IHK-Prüfungen/IHK_Abschlussprüfungen_AP2 1999-2023/2022 AP2 Sommer FIAE/3.3_FIAE_Pruefung_Sommer_2022_Teil_2_WISO_Loesungen.pdf',
     '3.3_FIAE_Pruefung_Sommer_2022_Teil_2_WISO_Loesungen.pdf',
     'WISO', 'Lösung', '2022 Sommer'),
    
    # Winter 2022/23: WISO aus dem 2022 Winter Ordner
    ('c:/Users/CC-Student/Downloads/Telegram Desktop/26. Das Gold des Piraten/IHK-Prüfungen/IHK-Prüfungen/IHK_Abschlussprüfungen_AP2 1999-2023/2022 Winter/2022_Winter_AP2_AO2020_WISO.pdf',
     '2022_Winter_AP2_AO2020_WISO.pdf',
     'WISO', 'Aufgabe', '2022_23 Winter'),  # Zuordnung zu existierender Prüfung
    
    ('c:/Users/CC-Student/Downloads/Telegram Desktop/26. Das Gold des Piraten/IHK-Prüfungen/IHK-Prüfungen/IHK_Abschlussprüfungen_AP2 1999-2023/2022 Winter/2022_Winter_AP2_AO2020_WISO_Loesung.pdf',
     '2022_Winter_AP2_AO2020_WISO_Loesung.pdf',
     'WISO', 'Lösung', '2022_23 Winter'),
    
    # 2023 Sommer - GA1 Aufgabe, GA2 Aufgabe + Lösung, WISO Lösung fehlen
    ('c:/Users/CC-Student/Downloads/Telegram Desktop/26. Das Gold des Piraten/IHK-Prüfungen/IHK-Prüfungen/IHK_Abschlussprüfungen_AP2 1999-2023/2023 Sommer/AP S2023 IT GA1 FIAE.PDF',
     'AP S2023 IT GA1 FIAE.PDF',
     'GA1', 'Aufgabe', '2023 Sommer'),
    
    ('c:/Users/CC-Student/Downloads/Telegram Desktop/26. Das Gold des Piraten/IHK-Prüfungen/IHK-Prüfungen/IHK_Abschlussprüfungen_AP2 1999-2023/2023 Sommer/AP S2023 IT GA2.pdf',
     'AP S2023 IT GA2.pdf',
     'GA2', 'Aufgabe', '2023 Sommer'),
    
    ('c:/Users/CC-Student/Downloads/Telegram Desktop/26. Das Gold des Piraten/IHK-Prüfungen/IHK-Prüfungen/IHK_Abschlussprüfungen_AP2 1999-2023/2023 Sommer/AP S2023 IT GA2 Lösung.pdf',
     'AP S2023 IT GA2 Lösung.pdf',
     'GA2', 'Lösung', '2023 Sommer'),
    
    ('c:/Users/CC-Student/Downloads/Telegram Desktop/26. Das Gold des Piraten/IHK-Prüfungen/IHK-Prüfungen/IHK_Abschlussprüfungen_AP2 1999-2023/2023 Sommer/AP S2023 IT WiSo Lösung.pdf',
     'AP S2023 IT WiSo Lösung.pdf',
     'WISO', 'Lösung', '2023 Sommer'),
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
        print(f"OK [{resp['id']:3d}] {bereich:5} {typ:8} {ordner:20} {name}")
    else:
        err += 1
        print(f"ERR: {str(resp)[:80]} | {name}")

print(f"\n{'='*60}")
print(f"ERGEBNIS: {ok} importiert, {skip} übersprungen, {err} Fehler")
print(f"{'='*60}")
