"""
Durchsucht alle Prüfungs-PDFs nach einem Begriff.
Nutzt PyMuPDF für Text-PDFs, Tesseract-OCR für Bild-PDFs.

Aufruf:
    python search_pruefungen.py "Aktivitätsdiagramm"
    python search_pruefungen.py "SQL" --ordner "2018 Sommer"
    python search_pruefungen.py "Klassendiagramm" --ocr
"""

import os, re, sys, io, argparse, json, hashlib, time
from datetime import datetime
import fitz
import pytesseract
from PIL import Image

# Fix Windows cp1252 encoding for special characters
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

BASE = r'c:\Users\CC-Student\Documents\Neuer Ordner\IHK_AP2\AP_IHK_Anwendungsentwicklung'
SKIP_DIRS = {'Sequenzdiagramme', '_Sonstige'}
OCR_CACHE_FILE = os.path.join(os.path.dirname(__file__), '.ocr_cache.json')
RESULTS_DIR = os.path.join(os.path.dirname(__file__), 'Ergebnisse')


def load_ocr_cache():
    if os.path.exists(OCR_CACHE_FILE):
        with open(OCR_CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_ocr_cache(cache):
    with open(OCR_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False)


def file_key(pdf_path):
    """Unique key: path + file size (fast, avoids full hash)."""
    size = os.path.getsize(pdf_path)
    return f'{pdf_path}|{size}'

# ── ANSI colors ────────────────────────────────────────────────────────────
GREEN  = '\033[92m'
YELLOW = '\033[93m'
CYAN   = '\033[96m'
BOLD   = '\033[1m'
RESET  = '\033[0m'

# ── Umlaut-tolerant pattern ────────────────────────────────────────────────
UMLAUT_MAP = {
    'ä': '[äaá4]', 'Ä': '[ÄAÁ4]',
    'ö': '[öoó0]', 'Ö': '[ÖOÓ0]',
    'ü': '[üuú]',  'Ü': '[ÜUÚ]',
    'ß': '(?:ß|ss|[Bb])',
}


def build_pattern(term):
    """Build a regex pattern that tolerates OCR misreadings of umlauts."""
    parts = []
    for ch in term:
        if ch in UMLAUT_MAP:
            parts.append(UMLAUT_MAP[ch])
        else:
            parts.append(re.escape(ch))
    return re.compile(''.join(parts), re.IGNORECASE)


def extract_text_fast(pdf_path):
    """Extract embedded text from all pages. Returns list of (page_no, text)."""
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        t = page.get_text()
        pages.append((i + 1, t))
    doc.close()
    return pages


def extract_text_ocr(pdf_path, dpi=100, max_pages=30, cache=None):
    """OCR up to max_pages pages. Returns list of (page_no, text). Saves cache per file."""
    key = file_key(pdf_path)
    if cache is not None and key in cache:
        return [(i + 1, t) for i, t in enumerate(cache[key])]

    doc = fitz.open(pdf_path)
    pages = []
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
        img = Image.open(io.BytesIO(pix.tobytes('png')))
        try:
            t = pytesseract.image_to_string(img, lang='eng', timeout=30)
        except RuntimeError:
            t = ''
        pages.append((i + 1, t))
    doc.close()

    if cache is not None:
        cache[key] = [t for _, t in pages]
        save_ocr_cache(cache)   # persist after every file
    return pages


def has_text(pdf_path):
    """True if the PDF contains embedded (non-image) text."""
    doc = fitz.open(pdf_path)
    for page in doc:
        if page.get_text().strip():
            doc.close()
            return True
    doc.close()
    return False


def get_context(text, term, window=80):
    """Return a snippet around the found term."""
    pattern = build_pattern(term)
    match = pattern.search(text)
    if not match:
        return ''
    start = max(0, match.start() - window)
    end   = min(len(text), match.end() + window)
    snippet = text[start:end].replace('\n', ' ').strip()
    # Highlight the term
    snippet = pattern.sub(f'{YELLOW}\\g<0>{RESET}', snippet)
    return '...' + snippet + '...'


def search_pdf(pdf_path, term, use_ocr=False, cache=None):
    """
    Search a PDF for term.
    Returns list of (page_no, context_snippet) for each hit page.
    """
    pattern = build_pattern(term)
    hits = []

    try:
        pages_text = extract_text_fast(pdf_path)
    except Exception:
        if use_ocr:
            try:
                pages_text = extract_text_ocr(pdf_path, cache=cache)
            except Exception:
                return []
        else:
            return []
    is_image_pdf = not any(t.strip() for _, t in pages_text)

    if is_image_pdf and use_ocr:
        try:
            pages_text = extract_text_ocr(pdf_path, cache=cache)
        except Exception:
            return []

    for page_no, text in pages_text:
        if pattern.search(text):
            ctx = get_context(text, term)
            hits.append((page_no, ctx))

    return hits


def main():
    parser = argparse.ArgumentParser(description='Sucht in Prüfungs-PDFs nach einem Begriff.')
    parser.add_argument('suchbegriff', help='Zu suchender Begriff (case-insensitiv)')
    parser.add_argument('--ordner', default=None, help='Nur in diesem Unterordner suchen (z.B. "2018 Sommer")')
    parser.add_argument('--ocr', action='store_true', help='OCR auch für Bild-PDFs aktivieren (langsamer)')
    args = parser.parse_args()

    term = args.suchbegriff
    search_root = os.path.join(BASE, args.ordner) if args.ordner else BASE

    print(f'\n{BOLD}Suche nach: "{CYAN}{term}{RESET}{BOLD}"{RESET}')
    if args.ordner:
        print(f'Ordner: {args.ordner}')
    print(f'OCR: {"ja" if args.ocr else "nein (nur Text-PDFs)"}')
    print('─' * 60)

    total_pdfs  = 0
    total_hits  = 0
    result_list = []
    cache = load_ocr_cache() if args.ocr else {}

    # Collect all PDFs first for progress display
    all_pdfs = []
    for root, dirs, files in os.walk(search_root):
        dirs[:] = sorted([d for d in dirs if d not in SKIP_DIRS])
        for fname in sorted(files):
            if fname.lower().endswith('.pdf'):
                all_pdfs.append((root, fname))
    total_pdfs = len(all_pdfs)

    t_start = time.time()
    ocr_done = 0

    for idx, (root, fname) in enumerate(all_pdfs, 1):
        pdf_path = os.path.join(root, fname)
        rel_folder = os.path.relpath(root, BASE)

        if args.ocr:
            elapsed = time.time() - t_start
            if ocr_done > 0:
                eta_s = int(elapsed / ocr_done * (total_pdfs - idx + 1))
                eta_str = f'  ETA {eta_s // 60}m{eta_s % 60:02d}s'
            else:
                eta_str = ''
            bar_done = int(20 * idx / total_pdfs)
            bar = '#' * bar_done + '-' * (20 - bar_done)
            label = fname[:30].ljust(30)
            cached_flag = ' [cache]' if (file_key(pdf_path) in cache) else ''
            print(f'\r  [{bar}] {idx:3}/{total_pdfs}  {label}{cached_flag}{eta_str}  ', end='', flush=True)

        hits = search_pdf(pdf_path, term, use_ocr=args.ocr, cache=cache)
        if file_key(pdf_path) not in cache or not args.ocr:
            ocr_done += 1
        if hits:
            result_list.append((rel_folder, fname, pdf_path, hits))

    if args.ocr:
        print()  # newline after progress

    # ── Print results ──────────────────────────────────────────────────────
    if not result_list:
        print(f'\n{YELLOW}Keine Treffer gefunden.{RESET}')
    else:
        current_folder = None
        for folder, fname, _path, hits in result_list:
            if folder != current_folder:
                print(f'\n{BOLD}{GREEN}[{folder}/]{RESET}')
                current_folder = folder
            pages_str = ', '.join(str(p) for p, _ in hits)
            print(f'  {CYAN}{fname}{RESET}  [Seite(n): {pages_str}]')
            # Show first context snippet
            _, ctx = hits[0]
            if ctx:
                print(f'    {ctx}')

    print()
    print('─' * 60)
    print(f'Durchsucht: {total_pdfs} PDFs  |  {BOLD}Treffer in: {len(result_list)} Dateien{RESET}')

    # ── Save results to file ───────────────────────────────────────────────
    if result_list:
        save_results(term, result_list, total_pdfs, args.ocr)

    print()


def save_results(term, result_list, total_pdfs, used_ocr):
    """Save search results to Ergebnisse/<term>.html with clickable PDF links."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', term)
    filepath = os.path.join(RESULTS_DIR, f'{safe_name}.html')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    ansi_re = re.compile(r'\033\[[0-9;]*m')

    from html import escape

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
  OCR: {"ja" if used_ocr else "nein"}<br>
  Durchsucht: {total_pdfs} PDFs &mdash; <strong>Treffer in {len(result_list)} Dateien</strong>
</div>
<hr>''')

    current_folder = None
    for folder, fname, pdf_path, hits in result_list:
        if folder != current_folder:
            html.append(f'<div class="folder">[{escape(folder)}/]</div>')
            current_folder = folder
        pages_str = ', '.join(str(p) for p, _ in hits)
        # relative path from Ergebnisse/ to AP_IHK_Anwendungsentwicklung/...
        from urllib.parse import quote
        rel_path = os.path.relpath(pdf_path, RESULTS_DIR).replace('\\', '/')
        rel_url = quote(rel_path, safe='/')
        html.append(f'<div class="hit">')
        html.append(f'  <a href="{rel_url}" target="_blank">{escape(fname)}</a>')
        html.append(f'  <span class="pages">[Seite(n): {pages_str}]</span>')
        for _, ctx in hits:
            if ctx:
                clean = ansi_re.sub('', ctx)
                # highlight the term in context
                highlighted = re.sub(
                    re.escape(term),
                    lambda m: f'<mark>{escape(m.group())}</mark>',
                    escape(clean),
                    flags=re.IGNORECASE
                )
                html.append(f'  <div class="ctx">{highlighted}</div>')
        html.append('</div>')

    html.append('</body></html>')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(html))

    print(f'\n{GREEN}Ergebnisse gespeichert: Ergebnisse/{safe_name}.html{RESET}')


if __name__ == '__main__':
    main()
