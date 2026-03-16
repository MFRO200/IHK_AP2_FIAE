"""
Bereinigt die Prüfungsdatenbank: NUR FIAE-Prüfungen behalten.

1. Klassifiziert alle PDFs im Cache nach Beruf (Content-basiert)
2. Verschiebt Nicht-FIAE-PDFs in separaten Ordner
3. Bereinigt OCR-Cache (nur FIAE)
4. Durchsucht alle Begriffe NUR gegen FIAE-PDFs
5. Regeneriert ALLE HTML-Ergebnisdateien
6. Aktualisiert Score-Tabelle.html mit neuen Trefferzahlen
"""

import os, re, sys, json, shutil, time
from html import escape
from urllib.parse import quote
from datetime import datetime

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FIAE_DIR = os.path.join(BASE_DIR, 'AP_IHK_Anwendungsentwicklung')
MOVE_DIR = os.path.join(BASE_DIR, 'AP_IHK_Andere_Berufe')
OCR_CACHE_FILE = os.path.join(BASE_DIR, '.ocr_cache.json')
RESULTS_DIR = os.path.join(BASE_DIR, 'Ergebnisse')
SCORE_FILE = os.path.join(RESULTS_DIR, 'Score-Tabelle.html')

# ── Umlaut-tolerant pattern (from search_pruefungen.py) ──
UMLAUT_MAP = {
    'ä': '[äaá4]', 'Ä': '[ÄAÁ4]',
    'ö': '[öoó0]', 'Ö': '[ÖOÓ0]',
    'ü': '[üuú]',  'Ü': '[ÜUÚ]',
    'ß': '(?:ß|ss|[Bb])',
}

def build_pattern(term):
    parts = []
    for ch in term:
        if ch in UMLAUT_MAP:
            parts.append(UMLAUT_MAP[ch])
        else:
            parts.append(re.escape(ch))
    return re.compile(''.join(parts), re.IGNORECASE)


def detect_beruf(text_data, path=''):
    """Detect IT profession from PDF content (first 3 pages) + path fallback."""
    if isinstance(text_data, list):
        text = '\n'.join(text_data[:3])
    else:
        text = text_data[:4000]
    
    berufe = []
    if re.search(r'Anwendungsentwicklung|Fachinformatiker.*?Anwendung', text, re.IGNORECASE | re.DOTALL):
        berufe.append('FIAE')
    if re.search(r'Systemintegration|Fachinformatiker.*?System(?:integration)', text, re.IGNORECASE | re.DOTALL):
        berufe.append('FISI')
    if re.search(r'I?T-System-Kaufmann|I?T-System-Kauffrau|Systemkaufmann|Systemkauffrau', text, re.IGNORECASE):
        berufe.append('IT-SK')
    if re.search(r'I?T-System-Elektronik', text, re.IGNORECASE):
        berufe.append('IT-SE')
    if re.search(r'Informatikkaufmann|Informatikkauffrau|Informatikkauf', text, re.IGNORECASE):
        berufe.append('IK')
    
    # Abbreviation patterns
    if not berufe:
        if re.search(r'FIAE|FI-AE|FiAe|FIAN|FI.?AN', text):
            berufe.append('FIAE')
        if re.search(r'FISI|FI-SI|FiSi', text):
            berufe.append('FISI')
    
    # Path-based fallback for bad OCR
    if not berufe and path:
        full = (os.path.basename(path) + ' ' + os.path.dirname(path)).lower()
        if any(x in full for x in ['anwendung', 'fiae', 'fian', 'fi-ae', 'ae_gh', 'ae-', 'awe']):
            berufe.append('FIAE')
        elif any(x in full for x in ['fisi', 'fi-si', 'systemintegration']):
            berufe.append('FISI')
        elif any(x in full for x in ['it-sk', 'systemkauf']):
            berufe.append('IT-SK')
        elif any(x in full for x in ['it-se', 'systemelektronik']):
            berufe.append('IT-SE')
        elif any(x in full for x in ['informatikkauf']):
            berufe.append('IK')
    
    # Shared AP1 exams (2021+)
    if not berufe:
        if re.search(r'Einrichten\s+eines\s+IT|Teil\s*1\s+der\s+(?:gestreckten\s+)?Abschluss', text, re.IGNORECASE):
            berufe.append('AP1')
    
    return berufe if berufe else ['Unbekannt']


def is_fiae(berufe):
    """Check if this PDF is relevant for FIAE (includes shared AP1 exams)."""
    return 'FIAE' in berufe or 'AP1' in berufe


def get_context(text, term, window=80):
    """Return a snippet around the found term."""
    pattern = build_pattern(term)
    match = pattern.search(text)
    if not match:
        return ''
    start = max(0, match.start() - window)
    end   = min(len(text), match.end() + window)
    snippet = text[start:end].replace('\n', ' ').strip()
    return '...' + snippet + '...'


def extract_semester(path):
    """Extract semester from path like '2018_19 Winter'."""
    m = re.search(r'(\d{4}(?:_\d{2})?\s*(?:Sommer|Winter))', path)
    return m.group(1) if m else ''


def save_result_html(term, result_list, total_pdfs, results_dir):
    """Save search results as HTML (same format as search_pruefungen.py)."""
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', term)
    filepath = os.path.join(results_dir, f'{safe_name}.html')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

    html = []
    html.append(f'''<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>Suche: {escape(term)}</title>
<style>
  body {{ font-family: Segoe UI, Arial, sans-serif; margin: 2em; background: #1e1e1e; color: #d4d4d4; }}
  h1 {{ color: #569cd6; }}
  .meta {{ color: #808080; margin-bottom: 1.5em; }}
  .folder {{ color: #4ec9b0; font-weight: bold; font-size: 1.1em; margin-top: 1.5em; }}
  .hit {{ margin: 0.5em 0 0.5em 1.5em; }}
  .hit a {{ color: #dcdcaa; text-decoration: none; font-size: 1.05em; }}
  .hit a:hover {{ text-decoration: underline; color: #ce9178; }}
  .pages {{ color: #9cdcfe; margin-left: 0.5em; }}
  .ctx {{ color: #808080; font-size: 0.9em; margin: 0.2em 0 0 2em; white-space: pre-wrap; }}
  mark {{ background: #4e4e0a; color: #dcdcaa; padding: 1px 2px; }}
  hr {{ border: none; border-top: 1px solid #333; margin: 2em 0; }}
</style>
</head>
<body>
<h1>Suche: &bdquo;{escape(term)}&ldquo;</h1>
<div class="meta">
  Datum: {timestamp}<br>
  OCR: ja<br>
  Durchsucht: {total_pdfs} PDFs (nur FIAE) &mdash; <strong>Treffer in {len(result_list)} Dateien</strong>
</div>
<hr>''')

    current_folder = None
    for folder, fname, pdf_path, hits in result_list:
        if folder != current_folder:
            html.append(f'<div class="folder">[{escape(folder)}/]</div>')
            current_folder = folder
        pages_str = ', '.join(str(p) for p, _ in hits)
        rel_path = os.path.relpath(pdf_path, results_dir).replace('\\', '/')
        rel_url = quote(rel_path, safe='/')
        html.append(f'<div class="hit">')
        html.append(f'  <a href="{rel_url}" target="_blank">{escape(fname)}</a>')
        html.append(f'  <span class="pages">[Seite(n): {pages_str}]</span>')
        for _, ctx in hits:
            if ctx:
                highlighted = re.sub(
                    re.escape(term),
                    lambda m: f'<mark>{escape(m.group())}</mark>',
                    escape(ctx),
                    flags=re.IGNORECASE
                )
                html.append(f'  <div class="ctx">{highlighted}</div>')
        html.append('</div>')

    html.append('</body></html>')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(html))

    return len(result_list)


def search_term_in_cache(term, fiae_cache):
    """Search a term in FIAE-only cache. Returns (result_list, total_pdfs)."""
    pattern = build_pattern(term)
    result_list = []
    
    for cache_key, text_pages in sorted(fiae_cache.items()):
        # cache_key = "path|size"
        pdf_path = cache_key.split('|')[0]
        fname = os.path.basename(pdf_path)
        folder = os.path.relpath(os.path.dirname(pdf_path), FIAE_DIR) if os.path.dirname(pdf_path).startswith(FIAE_DIR) else os.path.dirname(pdf_path)
        
        hits = []
        for page_no, text in enumerate(text_pages, 1):
            if pattern.search(text):
                ctx = get_context(text, term)
                hits.append((page_no, ctx))
        
        if hits:
            result_list.append((folder, fname, pdf_path, hits))
    
    return result_list, len(fiae_cache)


def update_score_tabelle(score_file, new_counts, total_fiae):
    """Update hit counts in Score-Tabelle.html."""
    with open(score_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Update meta: PDF count
    content = re.sub(
        r'Basis: \d+ Prüfungs-PDFs',
        f'Basis: {total_fiae} Prüfungs-PDFs',
        content
    )
    
    # Update subtitle to say FIAE only
    content = re.sub(
        r'IHK AP2 &mdash; .*?<br>',
        'IHK AP2 &mdash; NUR FIAE Anwendungsentwicklung<br>',
        content
    )
    
    # Build lookup: term -> new count 
    # For each <tr><td>TERM</td><td class="treffer">COUNT</td>
    # We need to update COUNT with the new value
    
    def replace_count(m):
        """Replace numeric hit count in table rows."""
        prefix = m.group(1)   # everything before the count
        old_count = m.group(2)  # old count text
        suffix = m.group(3)   # </td> and rest
        
        # Extract the term from the prefix
        # The prefix contains <td>TERM</td> or <td><a href="...">TERM</a></td>
        term_match = re.search(r'<td>(?:<a[^>]*>)?([^<]+)(?:</a>)?(?:\s*/\s*(?:<a[^>]*>)?[^<]+(?:</a>)?)?\s*(?:\([^)]*\))?\s*</td>', prefix)
        if not term_match:
            return m.group(0)
        
        display_term = term_match.group(1).strip()
        
        # Skip non-numeric counts like "viele", "26+", "25 / 13"
        if not old_count.strip().isdigit():
            return m.group(0)
        
        # Look up new count
        if display_term in new_counts:
            new_count = new_counts[display_term]
            return f'{prefix}{new_count}{suffix}'
        
        return m.group(0)
    
    # Pattern to match table rows with numeric hit counts
    # <tr><td>...</td><td class="treffer">NUMBER</td>
    content = re.sub(
        r'(<tr><td>.*?</td><td class="treffer"[^>]*>)(\d+)(</td>)',
        replace_count,
        content
    )
    
    with open(score_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return content


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    print('=' * 70)
    print('  FIAE-ONLY CLEANUP')
    print('  Nur Anwendungsentwicklung-Prüfungen behalten')
    print('=' * 70)
    
    # ── 1. Load cache ─────────────────────────────────────────────
    print('\n[1/6] Lade OCR-Cache...')
    with open(OCR_CACHE_FILE, 'r', encoding='utf-8') as f:
        cache = json.load(f)
    print(f'  {len(cache)} PDFs im Cache')
    
    # ── 2. Classify ───────────────────────────────────────────────
    print('\n[2/6] Klassifiziere PDFs nach Beruf...')
    fiae_cache = {}
    non_fiae_entries = []
    
    for key, text_data in cache.items():
        path = key.split('|')[0]
        berufe = detect_beruf(text_data, path)
        
        if is_fiae(berufe):
            fiae_cache[key] = text_data
        else:
            non_fiae_entries.append((key, path, berufe))
    
    print(f'  FIAE (behalten):    {len(fiae_cache)}')
    print(f'  Nicht-FIAE:         {len(non_fiae_entries)}')
    
    if non_fiae_entries:
        print('\n  Nicht-FIAE PDFs:')
        for _, path, berufe in non_fiae_entries:
            fn = os.path.basename(path)
            print(f'    {",".join(berufe):8s} -> {fn}')
    
    # ── 3. Move non-FIAE PDFs physically ─────────────────────────
    print(f'\n[3/6] Verschiebe Nicht-FIAE-PDFs nach {os.path.basename(MOVE_DIR)}/...')
    moved_count = 0
    for _, path, berufe in non_fiae_entries:
        if os.path.exists(path):
            # Keep the subfolder structure
            rel = os.path.relpath(path, FIAE_DIR)
            dest = os.path.join(MOVE_DIR, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.move(path, dest)
            moved_count += 1
            print(f'    Verschoben: {os.path.basename(path)}')
    
    # Also check for non-cached PDFs in the folder using filename detection
    non_fiae_filename_patterns = re.compile(
        r'(?:FiSi|FISI|FI-SI|IT-SK|IT-SE|IK\b|WiSo|WISO|GA2|Systemintegration|Systemkauf|Informatikkauf)',
        re.IGNORECASE
    )
    for root, dirs, files in os.walk(FIAE_DIR):
        dirs[:] = [d for d in dirs if d not in {'Sequenzdiagramme', '_Sonstige'}]
        for fname in files:
            if not fname.lower().endswith('.pdf'):
                continue
            full_path = os.path.join(root, fname)
            # Check if this file is in cache
            cached = any(full_path in k for k in fiae_cache)
            if not cached and non_fiae_filename_patterns.search(fname):
                rel = os.path.relpath(full_path, FIAE_DIR)
                dest = os.path.join(MOVE_DIR, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.move(full_path, dest)
                moved_count += 1
                print(f'    Verschoben (Dateiname): {fname}')
    
    print(f'  {moved_count} Dateien verschoben')
    
    # ── 4. Save cleaned cache ─────────────────────────────────────
    print('\n[4/6] Speichere bereinigten OCR-Cache...')
    # Backup old cache
    backup_file = OCR_CACHE_FILE + '.backup_all_berufe'
    if not os.path.exists(backup_file):
        shutil.copy2(OCR_CACHE_FILE, backup_file)
        print(f'  Backup: {os.path.basename(backup_file)}')
    
    with open(OCR_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(fiae_cache, f, ensure_ascii=False)
    print(f'  Cache gespeichert: {len(fiae_cache)} FIAE-PDFs')
    
    # ── 5. Re-search all terms ────────────────────────────────────
    print('\n[5/6] Durchsuche alle Begriffe neu (nur FIAE)...')
    
    # Get all search terms from existing HTML files
    html_files = [f for f in os.listdir(RESULTS_DIR) 
                  if f.endswith('.html') and f not in ('Score-Tabelle.html', 'Ausgangssituationen.html')]
    terms = [f[:-5] for f in html_files]  # Remove .html extension
    
    # Reverse the filename sanitization for the actual search term
    # The filenames use safe_name = re.sub(r'[<>:"/\\|?*]', '_', term)
    # Most terms don't need reversal since they don't contain those chars
    
    print(f'  {len(terms)} Begriffe zu durchsuchen...')
    
    new_counts = {}  # term -> hit count (number of PDFs)
    total_fiae = len(fiae_cache)
    t_start = time.time()
    
    for i, term in enumerate(terms):
        # Search
        result_list, _ = search_term_in_cache(term, fiae_cache)
        new_counts[term] = len(result_list)
        
        # Save HTML result file
        if result_list:
            save_result_html(term, result_list, total_fiae, RESULTS_DIR)
        else:
            # Delete empty result files
            filepath = os.path.join(RESULTS_DIR, f'{term}.html')
            # Keep file but with 0 results
            save_result_html(term, [], total_fiae, RESULTS_DIR)
        
        # Progress
        if (i + 1) % 50 == 0 or i + 1 == len(terms):
            elapsed = time.time() - t_start
            eta = int(elapsed / (i + 1) * (len(terms) - i - 1))
            print(f'    {i+1:3d}/{len(terms)}  ({elapsed:.0f}s, ETA {eta}s)')
    
    # ── 6. Update Score-Tabelle ───────────────────────────────────
    print('\n[6/6] Aktualisiere Score-Tabelle.html...')
    update_score_tabelle(SCORE_FILE, new_counts, total_fiae)
    
    # Summary
    hits_with_results = sum(1 for c in new_counts.values() if c > 0)
    hits_zero = sum(1 for c in new_counts.values() if c == 0)
    
    print(f'\n{"=" * 70}')
    print(f'  FERTIG!')
    print(f'  FIAE-PDFs im Cache:      {total_fiae}')
    print(f'  Nicht-FIAE verschoben:   {moved_count}')
    print(f'  Begriffe durchsucht:     {len(terms)}')
    print(f'  Begriffe mit Treffern:   {hits_with_results}')
    print(f'  Begriffe ohne Treffer:   {hits_zero}')
    
    # Show biggest changes
    print(f'\n  Top-20 Treffer (nur FIAE):')
    top = sorted(new_counts.items(), key=lambda x: -x[1])[:20]
    for term, count in top:
        print(f'    {count:3d}  {term}')
    
    print(f'{"=" * 70}')


if __name__ == '__main__':
    main()
