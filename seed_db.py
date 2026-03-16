#!/usr/bin/env python3
"""
seed_db.py — Befüllt die PostgreSQL-Datenbank mit:
  1. Prüfungszeiträume (aus Ordnerstruktur)
  2. Dokumente + OCR-Text pro Seite (aus .ocr_cache.json)
  3. Suchbegriffe mit Section A/B/C/D (aus Score-Tabelle.html)
  4. Treffer mit Seiten + Kontext (aus den HTML-Ergebnisdateien)

Nutzung:
  python seed_db.py          # Volles Seeding (TRUNCATE + INSERT)
  python seed_db.py --check  # Nur Statistik anzeigen
"""
import json, re, os, sys, glob, html as html_mod
from urllib.parse import unquote

# ─── Konfiguration ───
# Liest Secrets aus .env (python-dotenv) oder Umgebungsvariablen
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # ohne python-dotenv: nur Umgebungsvariablen

DB_CONFIG = {
    'host':     os.environ.get('DB_HOST', '127.0.0.1'),
    'port':     int(os.environ.get('DB_PORT', '15432')),
    'dbname':   os.environ.get('POSTGRES_DB', 'ihk_ap2'),
    'user':     os.environ.get('POSTGRES_USER', 'ihk'),
    'password': os.environ.get('POSTGRES_PASSWORD', ''),
}

OCR_CACHE   = '.ocr_cache.json'
SCORE_TABLE = 'Ergebnisse/Score-Tabelle.html'
ERGEBNISSE  = 'Ergebnisse'
PDF_ROOT    = 'AP_IHK_Anwendungsentwicklung'


# ═══════════════════════════════════════════════════════════════
# 1) Prüfungszeiträume + Dokumente aus OCR-Cache parsen
# ═══════════════════════════════════════════════════════════════

def detect_period_from_folder(folder_name):
    """'2018 Sommer' -> (2018, 'Sommer', 'Sommer 2018')
       '2018_19 Winter' -> (2018, 'Winter', 'Winter 2018_19')"""
    m = re.match(r'(\d{4}(?:_\d{2,4})?)\s+(Sommer|Winter)', folder_name)
    if m:
        year_part = m.group(1)
        season = m.group(2)
        year = int(year_part[:4])
        return year, season, f"{season} {year_part}", folder_name
    # Just year folder like '2008'
    m2 = re.match(r'^(\d{4})$', folder_name)
    if m2:
        year = int(m2.group(1))
        return year, 'Unbekannt', f"Unbekannt {year}", folder_name
    return None


def detect_doc_type(filename):
    """Aufgabe / Lösung / Handreichung"""
    fl = filename.lower()
    if any(x in fl for x in ['löser', 'lösung', 'loesung', 'loser', 'lösungen', 'loesungen']):
        return 'Lösung'
    if any(x in fl for x in ['hinweis', 'handreichung']):
        return 'Handreichung'
    return 'Aufgabe'


def parse_ocr_cache():
    """Returns list of dicts: {folder, filename, path, typ, pages: [str], filesize}"""
    with open(OCR_CACHE, 'r', encoding='utf-8') as f:
        cache = json.load(f)

    docs = []
    for key, pages in cache.items():
        parts = key.split('|')
        abs_path = parts[0]
        filesize = int(parts[1]) if len(parts) > 1 else 0

        # Extract folder (exam period) and filename
        # Path: .../AP_IHK_Anwendungsentwicklung/2018 Sommer/file.pdf
        m = re.search(r'AP_IHK_Anwendungsentwicklung[\\/]([^\\/]+)[\\/]([^\\/]+)$', abs_path)
        if not m:
            continue
        folder = m.group(1)
        filename = m.group(2)

        # Relative path from project root
        rel_path = f"{PDF_ROOT}/{folder}/{filename}"

        docs.append({
            'folder':   folder,
            'filename': filename,
            'rel_path': rel_path,
            'typ':      detect_doc_type(filename),
            'pages':    pages if isinstance(pages, list) else [str(pages)],
            'filesize': filesize,
        })

    return docs


# ═══════════════════════════════════════════════════════════════
# 2) Suchbegriffe aus Score-Tabelle parsen
# ═══════════════════════════════════════════════════════════════

def parse_score_tabelle():
    """Returns list of dicts: {begriff, section, treffer_anzahl, html_file}"""
    with open(SCORE_TABLE, 'r', encoding='utf-8') as f:
        content = f.read()

    terms = []

    for section_letter in ['a', 'b', 'c']:
        marker = f'id="score-{section_letter}"'
        if marker not in content:
            continue
        after = content.split(marker, 1)[1]
        # Cut at next section
        for nl in ['a', 'b', 'c', 'd']:
            if nl == section_letter:
                continue
            nm = f'id="score-{nl}"'
            if nm in after:
                after = after.split(nm, 1)[0]

        # Rows: <a href="X.html">Name</a> ... <td class="treffer">N</td>
        rows = re.findall(
            r'<a\s+href="([^"]+)">([^<]+)</a>.*?<td\s+class="treffer">(\d+)</td>',
            after, re.DOTALL
        )
        for href, name, cnt in rows:
            html_file = os.path.basename(unquote(href))
            terms.append({
                'begriff':         html_mod.unescape(name.strip()),
                'section':         section_letter.upper(),
                'treffer_anzahl':  int(cnt),
                'html_file':       html_file,
            })

    # Section D: no links, no hit counts — derive html_file from term name
    if 'id="score-d"' in content:
        d_area = content.split('id="score-d"', 1)[1]
        if '</body>' in d_area:
            d_area = d_area.split('</body>')[0]
        d_rows = re.findall(r'<tr><td>([^<]+)</td><td>[^<]*</td></tr>', d_area)
        for name in d_rows:
            clean = html_mod.unescape(name.strip())
            # Derive expected HTML filename from term name
            html_file = clean + '.html'
            terms.append({
                'begriff':         clean,
                'section':         'D',
                'treffer_anzahl':  0,
                'html_file':       html_file,
            })

    return terms


# ═══════════════════════════════════════════════════════════════
# 3) Treffer aus HTML-Ergebnisdateien parsen
# ═══════════════════════════════════════════════════════════════

def parse_treffer_from_html():
    """Returns list of dicts: {html_file, dateiname, seiten, kontext}"""
    skip_files = {
        'Score-Tabelle.html', 'Ausgangssituationen.html',
        'Pseudocode_new.html', 'Score-Tabelle.html.backup_vor_resort',
    }
    all_treffer = []

    for fpath in glob.glob(os.path.join(ERGEBNISSE, '*.html')):
        fname = os.path.basename(fpath)
        if fname in skip_files:
            continue

        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for hits
        if 'Treffer in 0 Dateien' in content:
            continue

        # Parse hit blocks (works for both old and new format)
        blocks = re.split(r'<div class="(?:hit|pdf-entry)">', content)[1:]
        for block in blocks:
            a_m = re.search(r'<a\s+href="([^"]*)"[^>]*>(.*?)</a>', block)
            p_m = re.search(r'<span class="pages">\[(.*?)\]</span>', block)
            if not a_m:
                continue

            # Get actual filename from href
            href = unquote(a_m.group(1))
            pdf_name = os.path.basename(href)
            pages = p_m.group(1) if p_m else ''

            # Context snippets
            ctxs = re.findall(r'<div class="ctx">(.*?)</div>', block, re.DOTALL)
            # Strip HTML tags from context
            kontext = '\n'.join(
                re.sub(r'<[^>]+>', '', html_mod.unescape(c)).strip()
                for c in ctxs
            )

            all_treffer.append({
                'html_file':  fname,         # Which HTML file this came from
                'dateiname':  pdf_name,
                'seiten':     pages,
                'kontext':    kontext[:2000] if kontext else None,
            })

    return all_treffer


# ═══════════════════════════════════════════════════════════════
# 4) Datenbank befüllen
# ═══════════════════════════════════════════════════════════════

def seed_database(docs, terms, treffer_list, check_only=False):
    import psycopg

    conn = psycopg.connect(**DB_CONFIG)
    cur = conn.cursor()

    if check_only:
        for tbl in ['pruefungen', 'dokumente', 'seiten', 'suchbegriffe', 'treffer']:
            cur.execute(f"SELECT COUNT(*) FROM {tbl}")
            print(f"  {tbl}: {cur.fetchone()[0]} rows")
        conn.close()
        return

    print("\n=== Seed starten ===")

    # TRUNCATE all tables (CASCADE handles FK)
    print("  TRUNCATE alle Tabellen...")
    cur.execute("""
        TRUNCATE treffer, suchbegriffe, seiten, dokumente, pruefungen
        RESTART IDENTITY CASCADE
    """)

    # ── 1) Prüfungen ──
    print("  Prüfungen einfügen...")
    folders = set(d['folder'] for d in docs)
    pruefung_map = {}  # folder_name -> id
    for folder in sorted(folders):
        result = detect_period_from_folder(folder)
        if not result:
            continue
        year, season, label, ordner = result
        cur.execute("""
            INSERT INTO pruefungen (jahr, semester, zeitraum_label, ordner_name)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (zeitraum_label) DO UPDATE SET ordner_name = EXCLUDED.ordner_name
            RETURNING id
        """, (year, season, label, ordner))
        pruefung_map[folder] = cur.fetchone()[0]
    print(f"    → {len(pruefung_map)} Prüfungszeiträume")

    # ── 2) Dokumente ──
    print("  Dokumente einfügen...")
    doc_map = {}  # filename -> id
    for d in docs:
        p_id = pruefung_map.get(d['folder'])
        if not p_id:
            continue
        cur.execute("""
            INSERT INTO dokumente (pruefung_id, dateiname, pfad, typ, dateigroesse, seitenanzahl)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (p_id, d['filename'], d['rel_path'], d['typ'],
              d['filesize'], len(d['pages'])))
        doc_id = cur.fetchone()[0]
        doc_map[d['filename']] = doc_id

        # ── 2b) Seiten (OCR-Text pro Seite) ──
        for page_nr, page_text in enumerate(d['pages'], 1):
            cur.execute("""
                INSERT INTO seiten (dokument_id, seiten_nr, ocr_text)
                VALUES (%s, %s, %s)
            """, (doc_id, page_nr, page_text))

    print(f"    → {len(doc_map)} Dokumente mit OCR-Text")

    # ── 3) Suchbegriffe ──
    print("  Suchbegriffe einfügen...")
    html_file_map = {}  # html_filename -> suchbegriff_id
    for t in terms:
        cur.execute("""
            INSERT INTO suchbegriffe (begriff, section, treffer_anzahl)
            VALUES (%s, %s, %s)
            ON CONFLICT (begriff) DO UPDATE
                SET section = EXCLUDED.section,
                    treffer_anzahl = EXCLUDED.treffer_anzahl
            RETURNING id
        """, (t['begriff'], t['section'], t['treffer_anzahl']))
        sb_id = cur.fetchone()[0]
        if t.get('html_file'):
            html_file_map[t['html_file']] = sb_id
    print(f"    → {len(html_file_map)} Suchbegriffe (mit HTML-Datei)")

    # ── 4) Treffer ──
    print("  Treffer einfügen...")
    treffer_count = 0
    skipped_count = 0
    auto_created = 0
    for tr in treffer_list:
        b_id = html_file_map.get(tr['html_file'])
        d_id = doc_map.get(tr['dateiname'])

        # Auto-create suchbegriff for HTML files not in Score-Tabelle
        if not b_id and tr['html_file']:
            begriff_name = os.path.splitext(tr['html_file'])[0]  # "API.html" -> "API"
            # Check if this term already exists (e.g. from section D)
            cur.execute("SELECT id FROM suchbegriffe WHERE begriff = %s", (begriff_name,))
            existing = cur.fetchone()
            if existing:
                b_id = existing[0]
            else:
                cur.execute("""
                    INSERT INTO suchbegriffe (begriff, section, treffer_anzahl)
                    VALUES (%s, %s, 0)
                    ON CONFLICT (begriff) DO NOTHING
                    RETURNING id
                """, (begriff_name, 'D'))  # Default to D (Anwendungsentwicklung)
                row = cur.fetchone()
                b_id = row[0] if row else None
                if not b_id:
                    cur.execute("SELECT id FROM suchbegriffe WHERE begriff = %s", (begriff_name,))
                    b_id = cur.fetchone()[0]
            b_id = cur.fetchone()[0]
            html_file_map[tr['html_file']] = b_id
            auto_created += 1

        if not b_id or not d_id:
            skipped_count += 1
            continue
        cur.execute("""
            INSERT INTO treffer (suchbegriff_id, dokument_id, seiten, kontext)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (suchbegriff_id, dokument_id) DO UPDATE
                SET seiten = EXCLUDED.seiten,
                    kontext = EXCLUDED.kontext
        """, (b_id, d_id, tr['seiten'], tr['kontext']))
        treffer_count += 1
    print(f"    → {treffer_count} Treffer ({skipped_count} übersprungen, {auto_created} Begriffe auto-erstellt)")

    conn.commit()
    cur.close()
    conn.close()
    print("\n✓ Seed abgeschlossen!")


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    check_only = '--check' in sys.argv

    print("1) OCR-Cache parsen...")
    docs = parse_ocr_cache()
    print(f"   {len(docs)} Dokumente gefunden")
    type_counts = {}
    for d in docs:
        type_counts[d['typ']] = type_counts.get(d['typ'], 0) + 1
    for t, c in sorted(type_counts.items()):
        print(f"     {t}: {c}")
    total_pages = sum(len(d['pages']) for d in docs)
    print(f"     Gesamtseiten: {total_pages}")

    print("\n2) Score-Tabelle parsen...")
    terms = parse_score_tabelle()
    print(f"   {len(terms)} Suchbegriffe")
    section_counts = {}
    for t in terms:
        section_counts[t['section']] = section_counts.get(t['section'], 0) + 1
    for s in 'ABCD':
        print(f"     Section {s}: {section_counts.get(s, 0)}")

    print("\n3) Treffer aus HTML-Dateien parsen...")
    treffer_list = parse_treffer_from_html()
    print(f"   {len(treffer_list)} Treffer-Einträge")

    if check_only:
        print("\n=== DB-Status ===")
        try:
            import psycopg
            seed_database(docs, terms, treffer_list, check_only=True)
        except Exception as e:
            print(f"   DB nicht erreichbar: {e}")
    else:
        print("\n4) Datenbank befüllen...")
        seed_database(docs, terms, treffer_list)
