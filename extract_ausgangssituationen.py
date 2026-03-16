"""
Extrahiert alle Ausgangssituationen aus den IHK-Prüfungs-PDFs.
Die Ausgangssituation steht vor dem 1. Handlungsschritt / 1. Aufgabe.
"""
import json, os, re
from collections import Counter
from datetime import datetime

CACHE_FILE = '.ocr_cache.json'
OUT_FILE = os.path.join('Ergebnisse', 'Ausgangssituationen.html')

# ===== LOAD CACHE =====
print("Lade OCR-Cache...")
with open(CACHE_FILE, 'r', encoding='utf-8') as f:
    cache = json.load(f)
print(f"  {len(cache)} PDFs geladen.")


def extract_semester(path):
    """Extract semester info from path like '2023_24 Winter' or '2024 Sommer'."""
    basename = os.path.basename(path).split('|')[0]
    dirname = os.path.dirname(path)
    
    # Try patterns in filename and dirname
    for text in [basename, dirname]:
        # Pattern: 2023_24 Winter or 2023/24 Winter
        m = re.search(r'(20\d{2})[_/](\d{2})\s*(Winter|Sommer|Herbst|Frühjahr|Fruhjahr|Fruehjahr)', text, re.IGNORECASE)
        if m:
            year = m.group(1)
            suffix = m.group(2)
            season = m.group(3)
            return f"{year}/{suffix} {season}"
        
        # Pattern: Winter 2023/24
        m = re.search(r'(Winter|Sommer|Herbst|Frühjahr|Fruhjahr|Fruehjahr)\s*(20\d{2})[_/](\d{2})', text, re.IGNORECASE)
        if m:
            season = m.group(1)
            year = m.group(2)
            suffix = m.group(3)
            return f"{year}/{suffix} {season}"
        
        # Pattern: 2024 Sommer or Sommer 2024
        m = re.search(r'(20\d{2})\s*(Sommer|Winter|Herbst|Frühjahr|Fruhjahr|Fruehjahr)', text, re.IGNORECASE)
        if m:
            return f"{m.group(1)} {m.group(2)}"
        m = re.search(r'(Sommer|Winter|Herbst|Frühjahr|Fruhjahr|Fruehjahr)\s*(20\d{2})', text, re.IGNORECASE)
        if m:
            return f"{m.group(2)} {m.group(1)}"
        
        # Just year
        m = re.search(r'(20\d{2})', text)
        if m:
            return m.group(1)
    
    return "Unbekannt"


def detect_beruf_from_content(text_data, path=''):
    """Detect the IT profession from the actual PDF content (first 3 pages).
    Falls back to path-based detection if OCR is too poor."""
    if isinstance(text_data, list):
        text = '\n'.join(text_data[:3])
    else:
        text = text_data[:4000]
    
    berufe = []
    
    # FIAE - Anwendungsentwicklung (with OCR tolerance)
    if re.search(r'Anwendungsentwicklung|Fachinformatiker.*?Anwendung', text, re.IGNORECASE | re.DOTALL):
        berufe.append('FIAE')
    
    # FISI - Systemintegration
    if re.search(r'Systemintegration|Fachinformatiker.*?System(?:integration)', text, re.IGNORECASE | re.DOTALL):
        berufe.append('FISI')
    
    # IT-SK - IT-System-Kaufleute (OCR: "T-System-Kauf" without "I")
    if re.search(r'I?T-System-Kaufmann|I?T-System-Kauffrau|Systemkaufmann|Systemkauffrau', text, re.IGNORECASE):
        berufe.append('IT-SK')
    
    # IT-SE - IT-System-Elektroniker (OCR: "T-System-Elek" without "I")
    if re.search(r'I?T-System-Elektronik', text, re.IGNORECASE):
        berufe.append('IT-SE')
    
    # IK - Informatikkaufleute
    if re.search(r'Informatikkaufmann|Informatikkauffrau|Informatikkauf', text, re.IGNORECASE):
        berufe.append('IK')
    
    # If nothing found, try abbreviation patterns in content
    if not berufe:
        if re.search(r'FIAE|FI-AE|FiAe|FIAN|FI.?AN', text):
            berufe.append('FIAE')
        if re.search(r'FISI|FI-SI|FiSi', text):
            berufe.append('FISI')
    
    # Last resort: path-based fallback for bad OCR
    if not berufe and path:
        full = (os.path.basename(path) + ' ' + os.path.dirname(path)).lower()
        if any(x in full for x in ['anwendung', 'fiae', 'fian', 'fi-ae', 'fiae', 'ae_gh', 'ae-', 'awe']):
            berufe.append('FIAE')
        elif any(x in full for x in ['fisi', 'fi-si', 'systemintegration']):
            berufe.append('FISI')
        elif any(x in full for x in ['it-sk', 'systemkauf']):
            berufe.append('IT-SK')
        elif any(x in full for x in ['it-se', 'systemelektronik']):
            berufe.append('IT-SE')
        elif any(x in full for x in ['ik', 'informatikkauf']):
            berufe.append('IK')
    
    # For shared AP1 exams (2021+), mark as shared
    if not berufe:
        if re.search(r'Einrichten\s+eines\s+IT|Teil\s*1\s+der\s+(?:gestreckten\s+)?Abschluss', text, re.IGNORECASE):
            berufe.append('FIAE')
            berufe.append('FISI')
    
    return berufe if berufe else ['Unbekannt']


def detect_exam_part(text_data, path):
    """Detect exam part (WISO, GA1, GA2, Teil1, Teil2) from content."""
    if isinstance(text_data, list):
        text = '\n'.join(text_data[:3])
    else:
        text = text_data[:4000]
    
    basename = os.path.basename(path).split('|')[0].lower()
    full = (basename + ' ' + os.path.dirname(path)).lower()
    
    # Check content first
    if re.search(r'Wirtschafts-?\s*und\s*Sozialkunde|WiSo', text, re.IGNORECASE):
        if not re.search(r'Ganzheitliche\s+Aufgabe|Aufgabe\s*1|Handlungsschritt', text, re.IGNORECASE):
            return 'WISO'
    
    # Lösung detection by content
    first_page = text[:1500]
    if re.search(r'L[oö]sungs?hinweis|Korrekturhinweis|Bewertungshinweis|Korrekturhilfe|Musterl[oö]sung', first_page, re.IGNORECASE):
        return 'Lösung'
    
    # Path-based Lösung detection
    if re.search(r'lösung|losung|loesung|löser|loser|loeser|_l\.pdf$', full):
        return 'Lösung'
    
    # GA2 / Kernqualifikationen
    if re.search(r'Ganzheitliche\s+Aufgabe\s*I?I\b|Kernqualifikationen', text, re.IGNORECASE):
        if not re.search(r'Ganzheitliche\s+Aufgabe\s*I\b|Fachqualifikationen', text, re.IGNORECASE):
            return 'GA2'
    
    # Teil 1 (AP1 - neue Prüfungsordnung)
    if re.search(r'Teil\s*1\s+der\s+(?:gestreckten\s+)?Abschluss', text, re.IGNORECASE):
        return 'Teil 1'
    if 'einrichten eines it' in full:
        return 'Teil 1'
    
    # Teil 2
    if re.search(r'Teil\s*2\s+der\s+(?:gestreckten\s+)?Abschluss', text, re.IGNORECASE):
        return 'Teil 2'
    
    # GA1 / Fachqualifikationen (old format)
    if re.search(r'Ganzheitliche\s+Aufgabe\s*I?\b.*?Fachqualifikationen', text, re.IGNORECASE | re.DOTALL):
        return 'GA1'
    if re.search(r'Fachqualifikationen', text, re.IGNORECASE):
        return 'GA1'
    
    # Path-based fallback
    if 'wiso' in full:
        return 'WISO'
    if any(x in full for x in ['belegsatz']):
        return 'Belegsatz'
    if any(x in full for x in ['katalog']):
        return 'Katalog'
    
    return 'Prüfung'


def extract_exam_type(path):
    """Determine exam type: Teil1, Teil2-Planen, Teil2-Algorithmen, AP2, etc."""
    basename = os.path.basename(path).split('|')[0].lower()
    dirname = os.path.dirname(path).lower()
    full = (basename + ' ' + dirname).lower()
    
    if 'wiso' in full:
        return 'WISO'
    if 'lösung' in full or 'losung' in full or 'loesung' in full:
        return 'Lösung'
    if 'teil1' in full or 'teil_1' in full or 'teil 1' in full or 'ap1' in full or 'arbeitsplatz' in full:
        return 'Teil 1'
    if 'teil2' in full or 'teil_2' in full or 'teil 2' in full:
        if 'algorithm' in full or '02' in basename:
            return 'Teil 2 – Algorithmen'
        elif 'planen' in full or '01' in basename:
            return 'Teil 2 – Planen'
        return 'Teil 2'
    if 'ap2' in full or 'ap_2' in full:
        return 'AP2'
    return 'Prüfung'


def clean_text(text):
    """Clean OCR artifacts from text."""
    # Remove excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove common OCR noise
    text = re.sub(r'Kor[er]?[kc]?tur[ae]?nd|Konelaurand|Korrekturrand|Korekturand|Korrekturend', '', text)
    text = re.sub(r'ZPARANA|ZPARANMS|ZPARANS|ZPAFIANS?|ZPA FIA\w*|ZPA\s+Nord\s*-?\s*West', '', text)
    text = re.sub(r'bitte wenden!', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Koretturard', '', text)
    text = text.strip()
    return text


def is_loesung(path):
    """Check if a PDF is a solution/Lösung file."""
    basename = os.path.basename(path).split('|')[0].lower()
    dirname = os.path.dirname(path).lower()
    full = basename + ' ' + dirname
    markers = ['lösung', 'losung', 'loesung', 'löser', 'loser', 'loeser', 
               'losungshinweis', 'lösungshinweis', 'korrekturhinweis',
               'l-fian', 'l-fisi', '_at.pdf']
    if any(m in full for m in markers):
        return True
    # Files ending with _L.pdf or _L_.pdf
    if re.search(r'_[Ll]\.pdf$', basename):
        return True
    # "GH1_Fian_L" pattern
    if re.search(r'_L[_.]', basename):
        return True
    return False


def is_skip(path):
    """Check if a PDF should be skipped entirely."""
    basename = os.path.basename(path).split('|')[0].lower()
    full = (basename + ' ' + os.path.dirname(path)).lower()
    if 'wiso' in full:
        return 'wiso'
    if is_loesung(path):
        return 'loesung'
    if any(x in full for x in ['belegsatz', 'katalog', 'anlagen']):
        return 'irrelevant'
    return None


def is_loesung_by_content(text):
    """Detect Lösungen by PDF content (not filename)."""
    if isinstance(text, list):
        text = '\n'.join(text[:2])  # Check first 2 pages
    first_part = text[:1500]
    markers = [r'L[oö]sungs?hinweis', r'Korrekturhinweis', r'Bewertungshinweis',
               r'Korrekturhilfe', r'Musterl[oö]sung']
    count = sum(1 for m in markers if re.search(m, first_part, re.IGNORECASE))
    return count >= 1


def is_cover_page_text(text):
    """Check if text is just cover page / exam header info (not a scenario)."""
    cover_markers = [
        r'Ganzheitliche\s+Aufgabe', r'Fachqualifikationen', r'Kernqualifikationen',
        r'Bearbeitungshinweise', r'Priifungszeit', r'Prüfungszeit', r'Punkte\s*$',
        r'Zugelassene\s+Hilfsmittel', r'Wird\s+vom\s+Korrektor', r'Bewertung',
        r'Diese\s+Kopfleiste', r'Familienname', r'Famil[ie]nname',
        r'Abschlusspri?[üu]fung', r'Fachinformatiker',
    ]
    marker_count = sum(1 for m in cover_markers if re.search(m, text, re.IGNORECASE))
    return marker_count >= 3


def find_task_start(text):
    """Find position where the first task/Handlungsschritt begins.
    Returns match object or None."""
    # Try specific markers first (most reliable)
    patterns = [
        r'1[.,]\s*(?:Aufgabe|Handlungsschritt)',
        # "Sie sollen" (with OCR variants: solen, salen, sol en)
        r'Sie\s+s[ao]l[le]?(?:en|n)\s+(?:als\s+Mitarbeiter|im\s+Rahmen|in\s+diesem|vier\s+der|folgende)',
        # Reversed word order: "sollen Sie vier"
        r's[ao]l[le]?(?:en|n)\s+Sie\s+(?:vier\s+der|folgende)',        # Broader "Sie sollen/salen" without specific follow words (fallback)
        r'Sie\s+s[ao]l[le]?(?:en|n)\s*(?:\.{2,}|\n)',        # Numbered items after "erledigen"/"erleigen" line
        r'erledi?gen[:\.]?\s*\n',
        # "Übersicht" / "Obersicht" / "Ubersicht" section divider (OCR: Ü→O or U)
        r'[ÜUO]bersicht\s*\n',
        # "Themen der Handlungsschritte"
        r'Themen\s+der\s+Handlungsschritte',
        # Dash-style task list: "— eine" or "- eine"
        r'[—\-]\s+(?:eine|ein|die|das|den)\s+\w+(?:analyse|funktion|programm|datenbank|software)',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m
    return None


def extract_ausgangssituation(text):
    """
    Extract the Ausgangssituation (scenario description before task 1) from exam text.
    Uses multiple strategies:
    1. Explicit "Ausgangssituation" / "Situation" header
    2. "Sie sind Mitarbeiter" pattern before first task
    3. Company description before first task
    4. General text extraction before first numbered task
    """
    if isinstance(text, list):
        text = '\n'.join(text)
    
    # Find where the first task starts (used by most strategies)
    task_match = find_task_start(text)
    
    # ===== STRATEGY 1: Explicit Ausgangssituation / Situation header =====
    # Build end pattern: either task_match position or broad patterns
    end_patterns = [
        r'1[.,]\s*(?:Aufgabe|Handlungsschritt)',
        r'Sie\s+s[ao]l[le]?(?:en|n)',
        r's[ao]l[le]?(?:en|n)\s+Sie',
        r'[ÜU]bersicht',
        r'Themen\s+der\s+Handlungsschritte',
    ]
    end_re = '|'.join(end_patterns)
    
    # Try "Ausgangssituation" header with OCR-tolerant spelling
    for start_pat in [
        r'(?:beziehen\s+sich\s+auf\s+(?:die\s+)?(?:folgende[n]?\s+)?Ausgangs?situatio\w*[:\s;]*)',
        r'(?:Ausgangs?situatio\w*[:\s;]+)',
    ]:
        m = re.search(start_pat + r'(.*?)(?=' + end_re + r')', text, re.DOTALL | re.IGNORECASE)
        if m:
            situation = clean_text(m.group(1).strip())
            if len(situation) > 30:
                return situation
    
    # Try "Situation" header (newer exams 2021+)
    m = re.search(r'(?:^|\n)\s*Situation\s+(.*?)(?=' + end_re + r')', text, re.DOTALL | re.IGNORECASE)
    if m:
        situation = clean_text(m.group(1).strip())
        if len(situation) > 30:
            return situation
    
    # ===== STRATEGY 2: "Sie sind Mitarbeiter" before first task =====
    # Find end point
    end_pos = task_match.start() if task_match else None
    
    # Also try: "Sie sollen" as end marker (common in older exams)
    sie_sollen = re.search(r'Sie\s+s[ao]l[le]?(?:en|n)\s+(?:als|im|in|vier|folgende)', text, re.IGNORECASE)
    if not sie_sollen:
        sie_sollen = re.search(r's[ao]l[le]?(?:en|n)\s+Sie\s+(?:vier|folgende)', text, re.IGNORECASE)
    
    # Take the earliest reliable end point
    if end_pos is None and sie_sollen:
        end_pos = sie_sollen.start()
    elif sie_sollen and end_pos and sie_sollen.start() < end_pos:
        # If "Sie sollen" comes before task, include it in the scenario
        pass  # keep end_pos as task start
    
    if end_pos is not None:
        text_before = text[:end_pos]
        
        # Look for "Sie sind Mitarbeiter" or "Sie arbeiten" start point
        sie_pats = [
            r'Sie\s+(?:sind|arbeiten)\s+(?:Mitarbeiter|in\s+d|an\s+d)',
            r'Sie\s+(?:sind|arbeiten)\s+\w',
        ]
        for spat in sie_pats:
            sie_match = re.search(spat, text_before, re.IGNORECASE)
            if sie_match:
                situation = text_before[sie_match.start():].strip()
                situation = clean_text(situation)
                if len(situation) > 30 and not is_cover_page_text(situation):
                    return situation
        
        # Look for company description: "Die XYZ GmbH..." or similar
        comp_match = re.search(
            r'((?:Die|Das|Der)\s+[A-ZÄÖÜ][\w\-\.]+(?:\s+[A-ZÄÖÜ&][\w\-\.]+)*\s+(?:GmbH|AG|KG|OHG|SE|UG|GbR|e\.V))',
            text_before, re.IGNORECASE
        )
        if comp_match:
            situation = text_before[comp_match.start():].strip()
            situation = clean_text(situation)
            if len(situation) > 30 and not is_cover_page_text(situation):
                return situation
    
    # ===== STRATEGY 3: General text before numbered task =====
    if end_pos is not None:
        text_before = text[:end_pos]
        # Remove obvious cover page content - search for last cover-page marker
        last_cover = 0
        for marker in [r'Bearbeitungshinweise', r'Alle\s+Rechte\s+vorbehalten', 
                       r'verfolgt\.?\s*[~\-]?\s*©', r'Hilfsmittel',
                       r'Bewertung\s*\n', r'Wird\s+vom\s+Korrektor',
                       r'Korrekturhinweis\w*']:
            for m in re.finditer(marker, text_before, re.IGNORECASE):
                ep = m.end()
                nl = text_before.find('\n', ep)
                if nl > 0:
                    ep = nl + 1
                if ep > last_cover:
                    last_cover = ep
        
        if last_cover > 0:
            scenario_text = text_before[last_cover:].strip()
            scenario_text = clean_text(scenario_text)
            if len(scenario_text) > 50 and not is_cover_page_text(scenario_text):
                return scenario_text
    
    return None


# ===== EXTRACT =====
print("\nExtrahiere Ausgangssituationen...")
results = []
skipped = {'wiso': 0, 'loesung': 0, 'irrelevant': 0, 'no_situation': 0, 'too_short': 0}
no_situation_files = []

for path, text in sorted(cache.items()):
    basename = os.path.basename(path).split('|')[0]
    semester = extract_semester(path)
    
    # Content-based detection: Beruf + Prüfungsteil
    berufe = detect_beruf_from_content(text, path)
    exam_part = detect_exam_part(text, path)
    
    # Skip WISO, Lösungen, GA2, Belegsätze, Kataloge
    if exam_part in ('WISO', ):
        skipped['wiso'] += 1
        continue
    if exam_part in ('Lösung', ):
        skipped['loesung'] += 1
        continue
    if exam_part in ('GA2', 'Belegsatz', 'Katalog'):
        skipped['irrelevant'] += 1
        continue
    
    # Fallback: path-based skip
    skip_reason = is_skip(path)
    if skip_reason:
        skipped[skip_reason] += 1
        continue
    
    # Content-based Lösung detection  
    if is_loesung_by_content(text):
        skipped['loesung'] += 1
        continue
    
    situation = extract_ausgangssituation(text)
    
    if situation:
        if len(situation) < 30:
            skipped['too_short'] += 1
            continue
        
        # Build readable Beruf string
        beruf_str = ' / '.join(berufe)
        
        results.append({
            'semester': semester,
            'exam_type': exam_part,
            'berufe': berufe,
            'beruf_str': beruf_str,
            'filename': basename,
            'situation': situation,
            'path': path,
        })
    else:
        skipped['no_situation'] += 1
        no_situation_files.append(basename)

print(f"\n  Gefunden: {len(results)} Ausgangssituationen")
print(f"  Übersprungen: {skipped}")

# Show breakdown by Beruf
from collections import Counter as _Counter
beruf_counts = _Counter()
for r in results:
    for b in r['berufe']:
        beruf_counts[b] += 1
print(f"\n  Nach Beruf (aus PDF-Inhalt):")
for b, c in beruf_counts.most_common():
    print(f"    {b}: {c}")

if no_situation_files:
    print(f"\n  Ohne Ausgangssituation ({len(no_situation_files)}):")
    for f in no_situation_files:
        print(f"    - {f}")

# ===== ANALYZE KEYWORDS =====
print("\nAnalysiere Schlüsselwörter in Ausgangssituationen...")

# Industry/domain keywords
industry_keywords = {
    'Softwareentwicklung / IT-Dienstleistung': [
        r'Software', r'IT-(?:Dienst|Abteilung|Unternehmen|System)', r'App\b', r'Webanwendung',
        r'Programmier', r'Entwickl', r'Cloud', r'SaaS', r'Datenbank',
    ],
    'Produktion / Fertigung / Industrie': [
        r'Fertigung', r'Produktion', r'Maschine', r'Fabrik', r'Industrie', r'Werkstück',
        r'CNC', r'Steuerung', r'Sensor', r'IoT', r'Kunststoff', r'Bauteile',
    ],
    'Handel / E-Commerce': [
        r'Online-?Shop', r'E-Commerce', r'Webshop', r'Versandh', r'Handel', r'Bestellung',
        r'Warenwirtschaft', r'Lager', r'Logistik', r'Lieferant',
    ],
    'Gesundheit / Medizin': [
        r'Krankenhaus', r'Arztpraxis', r'Patient', r'Medizin', r'Gesundheit', r'Klinik',
        r'Pflege', r'Apotheke',
    ],
    'Energie / Umwelt': [
        r'Energie', r'Solar', r'Photovoltaik', r'Windkraft', r'Umwelt', r'Nachhalt',
        r'Stadtwerke', r'Strom',
    ],
    'Bildung / Verwaltung': [
        r'Schule', r'Universität', r'Bildung', r'Verwaltung', r'Behörde', r'Kommune',
        r'öffentlich',
    ],
    'Landwirtschaft / Lebensmittel': [
        r'Landwirtschaft', r'Weinberg', r'Wein', r'Ernte', r'Anbau', r'Lebensmittel',
        r'Brauerei', r'Bäckerei', r'Mühle',
    ],
    'Transport / Mobilität': [
        r'Transport', r'Spedition', r'Fahrzeug', r'Mobilität', r'Fuhrpark', r'Flotte',
        r'Lieferung', r'Route',
    ],
    'Finanzen / Versicherung': [
        r'Bank', r'Versicherung', r'Finanz', r'Kredit', r'Buchhaltung',
    ],
    'Medien / Kommunikation': [
        r'Medien', r'Verlag', r'Marketing', r'Werbe', r'Kommunikation', r'Event',
        r'Messe',
    ],
}

# Classify each situation
for r in results:
    text = r['situation']
    r['industries'] = []
    for industry, patterns in industry_keywords.items():
        for pat in patterns:
            if re.search(pat, text, re.IGNORECASE):
                r['industries'].append(industry)
                break
    if not r['industries']:
        r['industries'] = ['Sonstige']

# Count industries
industry_counter = Counter()
for r in results:
    for ind in r['industries']:
        industry_counter[ind] += 1

# Extract company names (pattern: "die XYZ GmbH/AG/KG" etc.)
company_counter = Counter()
for r in results:
    companies = re.findall(
        r'(?:der|die|des|bei)\s+([A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]+(?:\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]+)*\s+(?:GmbH|AG|KG|OHG|e\.V\.|SE|UG|GmbH\s*&\s*Co\.\s*KG))',
        r['situation']
    )
    r['companies'] = companies
    for c in companies:
        company_counter[c] += 1

# Also look for common themes
theme_patterns = {
    'Netzwerk / Infrastruktur': r'Netzwerk|Server|Router|Switch|Firewall|WLAN|LAN|VPN|IP-Adress',
    'Datenbank': r'Datenbank|SQL|Tabelle|relational|Entity|Entit',
    'Webentwicklung': r'Website|Webseite|Webanwendung|Web-?App|Homepage|Online-?P|Browser',
    'Mobile App': r'App\b|mobile|Smartphone|Tablet|Android|iOS',
    'ERP / Warenwirtschaft': r'ERP|Warenwirtschaft|SAP|Auftrags|Bestell',
    'Sicherheit': r'Sicherheit|Verschlüsselung|Backup|Datenschutz|Firewall|Zugriff',
    'Automatisierung / IoT': r'Sensor|IoT|Automatisier|Smart|Messung|Drohne|autonom',
    'Kundenverwaltung / CRM': r'Kunde|Kundenverwaltung|CRM|Auftrag|Reklamation',
    'Projektmanagement': r'Projekt|Stakeholder|Scrum|agil|Sprint|Pflichtenheft|Lastenheft',
    'Cloud / Virtualisierung': r'Cloud|virtuell|Container|Docker|Migration|SaaS|IaaS|PaaS',
}

theme_counter = Counter()
for r in results:
    r['themes'] = []
    for theme, pat in theme_patterns.items():
        if re.search(pat, r['situation'], re.IGNORECASE):
            r['themes'].append(theme)
            theme_counter[theme] += 1


# ===== GENERATE HTML =====
print("\nErstelle HTML-Report...")
from html import escape

html = []
html.append('''<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>Ausgangssituationen – IHK AP2 FIAE</title>
<style>
  body { font-family: Segoe UI, Arial, sans-serif; margin: 2em; background: #1e1e1e; color: #d4d4d4; }
  h1 { color: #569cd6; }
  h2 { color: #4ec9b0; margin-top: 2em; border-bottom: 2px solid #4ec9b0; padding-bottom: 0.3em; }
  h3 { color: #9cdcfe; margin-top: 1.5em; }
  .meta { color: #808080; margin-bottom: 1.5em; }
  .toc { background: #252526; padding: 1em 1.5em; border-radius: 8px; margin-bottom: 2em; }
  .toc a { color: #4ec9b0; margin-right: 1em; }
  table { border-collapse: collapse; width: 100%; margin: 0.5em 0 1.5em; }
  th { background: #333; color: #569cd6; text-align: left; padding: 8px 12px; border-bottom: 2px solid #569cd6; }
  td { padding: 6px 12px; border-bottom: 1px solid #333; vertical-align: top; }
  tr:hover { background: #2a2d2e; }
  .treffer { text-align: center; min-width: 3em; }
  .situation-box { background: #252526; border-left: 4px solid #569cd6; padding: 1em 1.5em;
                   margin: 0.5em 0 1.5em; border-radius: 0 8px 8px 0; white-space: pre-wrap;
                   font-size: 0.92em; line-height: 1.5; }
  .tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; margin: 2px; }
  .tag-industry { background: #4e4e0a; color: #dcdcaa; }
  .tag-theme { background: #1a3a4e; color: #9cdcfe; }
  .tag-type { background: #5c1a1a; color: #f44747; }
  .tag-beruf { background: #2a4e2a; color: #6a9955; font-weight: bold; }
  .tag-beruf-fiae { background: #2a4e2a; color: #73c991; }
  .tag-beruf-fisi { background: #1a3a4e; color: #4fc1ff; }
  .tag-beruf-other { background: #4e3a1a; color: #ce9178; }
  .semester { color: #ce9178; font-weight: bold; }
  .company { color: #dcdcaa; }
  a { color: #dcdcaa; text-decoration: none; }
  a:hover { text-decoration: underline; color: #ce9178; }
  .bar { display: inline-block; height: 16px; background: #569cd6; border-radius: 3px; margin-right: 8px; vertical-align: middle; }
  .summary-box { background: #252526; border-left: 4px solid #4ec9b0; padding: 1em 1.5em;
                  margin: 1em 0; border-radius: 0 8px 8px 0; }
  hr { border: none; border-top: 1px solid #333; margin: 2em 0; }
  .note { color: #808080; font-size: 0.9em; }
</style>
</head>
<body>
''')

html.append(f'<h1>Ausgangssituationen der IHK-Prüfungen</h1>')
html.append(f'<div class="meta">IT-Berufe – FIAE, FISI, IT-SK, IT-SE – AP1 &amp; AP2<br>')
html.append(f'Erstellt: {datetime.now().strftime("%Y-%m-%d %H:%M")}<br>')
html.append(f'Basis: {len(cache)} PDFs, davon {len(results)} mit Ausgangssituation</div>')

html.append('<div class="toc"><strong>Schnellnavigation:</strong><br>')
html.append('<a href="#zusammenfassung">Zusammenfassung</a>')
html.append('<a href="#branchen">Branchen</a>')
html.append('<a href="#themen">Themen</a>')
html.append('<a href="#unternehmen">Unternehmen</a>')
html.append('<a href="#berufe">Berufe</a>')
html.append('<a href="#alle">Alle Situationen</a>')
html.append('</div>')

# ===== ZUSAMMENFASSUNG =====
html.append('<h2 id="zusammenfassung">Zusammenfassung</h2>')
html.append('<div class="summary-box">')
html.append(f'<strong>{len(results)}</strong> Ausgangssituationen aus {len(cache)} PDFs extrahiert.<br>')
html.append(f'<strong>Berufserkennung:</strong> Direkt aus dem PDF-Inhalt (nicht Dateiname!)<br><br>')
html.append(f'Übersprungen: {skipped["wiso"]} WISO, {skipped["loesung"]} Lösungen, '
             f'{skipped["irrelevant"]} GA2/Belegsatz/Katalog, '
             f'{skipped["no_situation"]} ohne Ausgangssituation<br><br>')

# Beruf breakdown
beruf_c = Counter()
for r in results:
    for b in r['berufe']:
        beruf_c[b] += 1
html.append('<strong>Nach Beruf (aus PDF-Inhalt erkannt):</strong><br>')
for b, c in beruf_c.most_common():
    html.append(f'  {b}: {c} | ')
html.append('<br><br>')

# Semester overview
semesters = Counter(r['semester'] for r in results)
html.append('<strong>Nach Semester:</strong><br>')
for sem, count in sorted(semesters.items()):
    html.append(f'  {sem}: {count} | ')
html.append('</div>')

# ===== BERUFE =====
html.append('<h2 id="berufe">IT-Berufe in den Pr\u00fcfungen</h2>')
html.append('<p class="note">Erkannt aus dem PDF-Inhalt (Deckblatt), nicht aus dem Dateinamen.</p>')
html.append('<table>')
html.append('<tr><th>Beruf</th><th class="treffer">Anzahl</th><th>Balken</th></tr>')
max_b = max(beruf_c.values()) if beruf_c else 1
for beruf, count in beruf_c.most_common():
    bar_width = int(count / max_b * 300)
    html.append(f'<tr><td>{escape(beruf)}</td><td class="treffer">{count}</td>'
                f'<td><span class="bar" style="width:{bar_width}px"></span></td></tr>')
html.append('</table>')

# ===== BRANCHEN =====
html.append('<h2 id="branchen">Branchen der fiktiven Unternehmen</h2>')
html.append('<p class="note">In welchem Branchenumfeld spielen die Ausgangssituationen?</p>')
html.append('<table>')
html.append('<tr><th>Branche</th><th class="treffer">Anzahl</th><th>Balken</th></tr>')
max_count = max(industry_counter.values()) if industry_counter else 1
for industry, count in industry_counter.most_common():
    bar_width = int(count / max_count * 300)
    html.append(f'<tr><td>{escape(industry)}</td><td class="treffer">{count}</td>'
                f'<td><span class="bar" style="width:{bar_width}px"></span></td></tr>')
html.append('</table>')

# ===== THEMEN =====
html.append('<h2 id="themen">Technische Themen in den Ausgangssituationen</h2>')
html.append('<p class="note">Welche IT-Themen werden in den Szenarien angesprochen?</p>')
html.append('<table>')
html.append('<tr><th>Thema</th><th class="treffer">Anzahl</th><th>Balken</th></tr>')
max_t = max(theme_counter.values()) if theme_counter else 1
for theme, count in theme_counter.most_common():
    bar_width = int(count / max_t * 300)
    html.append(f'<tr><td>{escape(theme)}</td><td class="treffer">{count}</td>'
                f'<td><span class="bar" style="width:{bar_width}px"></span></td></tr>')
html.append('</table>')

# ===== UNTERNEHMEN =====
html.append('<h2 id="unternehmen">Wiederkehrende Unternehmen</h2>')
html.append('<p class="note">Fiktive Firmennamen, die in den Prüfungen vorkommen.</p>')
html.append('<table>')
html.append('<tr><th>Unternehmen</th><th class="treffer">Vorkommen</th></tr>')
for company, count in company_counter.most_common(30):
    html.append(f'<tr><td class="company">{escape(company)}</td><td class="treffer">{count}</td></tr>')
html.append('</table>')

# ===== ALLE SITUATIONEN =====
html.append('<h2 id="alle">Alle Ausgangssituationen</h2>')
html.append('<p class="note">Chronologisch sortiert – neueste zuerst.</p>')

# Sort by semester (newest first)
def sort_key(r):
    s = r['semester']
    # extract year
    m = re.search(r'(20\d{2})', s)
    year = int(m.group(1)) if m else 0
    # Winter > Sommer for same year
    season_order = 1 if 'Sommer' in s or 'Frühjahr' in s or 'Fruhjahr' in s else 2
    return (-year, -season_order, r['exam_type'])

results.sort(key=sort_key)

for i, r in enumerate(results, 1):
    sem = escape(r['semester'])
    etype = escape(r['exam_type'])
    fname = escape(r['filename'])
    situation = escape(r['situation'])
    
    # Beruf tags with color coding
    beruf_tags = ''
    for b in r['berufe']:
        if b == 'FIAE':
            beruf_tags += f' <span class="tag tag-beruf-fiae">{escape(b)}</span>'
        elif b == 'FISI':
            beruf_tags += f' <span class="tag tag-beruf-fisi">{escape(b)}</span>'
        else:
            beruf_tags += f' <span class="tag tag-beruf-other">{escape(b)}</span>'
    
    html.append(f'<h3>{i}. <span class="semester">{sem}</span> – '
                f'<span class="tag tag-type">{etype}</span>'
                f'{beruf_tags} '
                f'<span style="color:#808080; font-size:0.85em">({fname})</span></h3>')
    
    # Tags
    for ind in r['industries']:
        html.append(f'<span class="tag tag-industry">{escape(ind)}</span>')
    for th in r.get('themes', []):
        html.append(f'<span class="tag tag-theme">{escape(th)}</span>')
    
    html.append(f'<div class="situation-box">{situation}</div>')

html.append('</body></html>')

# ===== WRITE =====
os.makedirs('Ergebnisse', exist_ok=True)
with open(OUT_FILE, 'w', encoding='utf-8') as f:
    f.write('\n'.join(html))

print(f"\n[OK] Report gespeichert: {OUT_FILE}")
print(f"     {len(results)} Ausgangssituationen extrahiert")
