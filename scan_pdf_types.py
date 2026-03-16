"""Scan all PDFs in storage/ and check if their DB type matches the actual content.

Classification logic (two-tier):
  Tier 1: Title keywords in first 200 chars of page 1 (strong signal)
  Tier 2: Exclusive keywords anywhere in first 10 pages
  
Priority: Lösung > Handreichung > Aufgabe
"""
import fitz, psycopg, os, re, json
from db_config import DB_URL

WS = os.path.dirname(os.path.abspath(__file__))
conn = psycopg.connect(DB_URL)
cur = conn.cursor()

cur.execute("""
  SELECT d.id, d.dateiname, d.pfad, d.typ, d.pruefungsbereich, p.zeitraum_label, d.pruefung_id
  FROM dokumente d
  JOIN pruefungen p ON d.pruefung_id = p.id
  WHERE d.pfad LIKE 'storage/%%'
  ORDER BY p.zeitraum_label, d.dateiname
""")
rows = cur.fetchall()

# -- Title patterns (checked in first 500 chars of page 1) --
title_loesung = re.compile(
    r"(Lösungshinweis[e]?|Bewertungsschlüssel|Korrekturhinweis[e]?|"
    r"Lösungsvorschlag|Musterlösung|Korrekturanleitung|"
    r"Vorläufige Lösungen|"
    r"Vertraulich.*Prüfungsausschuss)", re.I | re.DOTALL
)
title_aufgabe = re.compile(
    r"(Prüfungsaufgabe|schriftliche Abschlussprüfung|"
    r"Teil \d der Abschlussprüfung)", re.I
)
title_handreichung = re.compile(
    r"(Handreichung|Hinweise für den Prüfungsausschuss)", re.I
)

# -- Strong Lösung-exclusive keywords (anywhere in text, never in Aufgabe docs) --
strong_loesung = re.compile(
    r"(Bewertungsschlüssel|Musterlösung|Korrekturanleitung|Lösungsskizze|"
    r"Lösungsmatrix|Bewertungsraster|Lösungsschlüssel|"
    r"Allgemeine Korrekturhinweise|Lösungs- und Bewertungshinweise|"
    r"Vorläufige Lösungen|"
    r"Vertraulich.*Prüfungsausschuss)", re.I | re.DOTALL
)

# -- Aufgabe keywords (only meaningful if no Lösung keywords found) --
aufgabe_kw = re.compile(
    r"(Prüfungsaufgabe|Ganzheitliche Aufgabe [12I]|"
    r"Ausgangssituation|schriftliche Abschlussprüfung|"
    r"Hinweise für den Prüfungsteilnehmer|"
    r"Teil \d der Abschlussprüfung|Aufgabenstellung|"
    r"Bearbeitungszeit|Hilfsmittel|"
    r"Alle Aufgaben sind zu bearbeiten)", re.I
)

# -- Handreichung keywords --
handreichung_kw = re.compile(
    r"(Handreichung|Bewertungshinweis[e]?|"
    r"Hinweise für (?:den Prüfungsausschuss|die Korrektur))", re.I
)

mismatches = []
errors = []
checked = 0

for doc_id, dateiname, pfad, db_typ, bereich, zeitraum, pruefung_id in rows:
    full_path = os.path.join(WS, pfad)
    if not os.path.isfile(full_path):
        continue

    try:
        doc = fitz.open(full_path)
        # Get page 1 text separately for title detection
        page1_text = ""
        try:
            page1_text = doc[0].get_text()
        except Exception:
            pass
        
        # Get full text (up to 10 pages)
        text = page1_text + " "
        for page_num in range(1, min(10, len(doc))):
            try:
                text += doc[page_num].get_text() + " "
            except Exception:
                pass
        doc.close()
    except Exception as e:
        errors.append((doc_id, dateiname, str(e)))
        continue

    checked += 1

    # Tier 1: Check title (first 500 chars of page 1)
    title_area = page1_text[:500]
    is_title_loesung = bool(title_loesung.search(title_area))
    is_title_aufgabe = bool(title_aufgabe.search(title_area))
    is_title_handreichung = bool(title_handreichung.search(title_area))

    # Tier 2: Strong exclusive keywords anywhere
    has_strong_loesung = bool(strong_loesung.search(text))
    has_aufgabe = bool(aufgabe_kw.search(text))
    has_handreichung = bool(handreichung_kw.search(text))

    # Decision: Title keywords are strongest signal
    detected = None
    if is_title_loesung:
        detected = "Lösung"
    elif is_title_handreichung:
        detected = "Handreichung"
    elif is_title_aufgabe:
        detected = "Aufgabe"
    elif has_strong_loesung:
        detected = "Lösung"
    elif has_handreichung:
        detected = "Handreichung"
    elif has_aufgabe:
        detected = "Aufgabe"

    if detected and detected != db_typ:
        mismatches.append({
            "id": doc_id,
            "dateiname": dateiname,
            "pfad": pfad,
            "db_typ": db_typ,
            "detected": detected,
            "zeitraum": zeitraum,
            "bereich": bereich,
            "pruefung_id": pruefung_id,
            "preview": text[:200].replace("\n", " ").strip(),
        })

# Save results FIRST (before print to avoid encoding crash)
with open(os.path.join(WS, "scan_pdf_types_result.json"), "w", encoding="utf-8") as f:
    json.dump(mismatches, f, ensure_ascii=False, indent=2)

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

print(f"Geprüft: {checked} PDFs")
print(f"Fehler: {len(errors)}")
print(f"Typ-Mismatches: {len(mismatches)}")
print()
for m in mismatches:
    print(f"  ID={m['id']:4d} | {m['zeitraum']:22s} | {m['bereich']:10s} |"
          f" DB={m['db_typ']:14s} -> Inhalt={m['detected']:14s} | {m['dateiname']}")

if errors:
    print(f"\nFehler ({len(errors)}):")
    for e in errors[:10]:
        print(f"  ID={e[0]}: {e[1]} -> {e[2][:60]}")

conn.close()
