#!/usr/bin/env python3
from pathlib import Path
import shutil
import sys

ROOT = Path(r"c:\Users\CC-Student\Documents\Neuer Ordner\IHK_AP2").resolve()
SRC = ROOT / 'AP_IHK_Anwendungsentwicklung'
TARGET = SRC / 'Sequenzdiagramme'
TEXT_EXTS = {'.txt', '.md', '.csv', '.html', '.htm', '.xml', '.json'}
PDF_EXT = '.pdf'
KEYWORD = 'sequenzdiagramm'

# We use a fast raw-bytes search for PDFs to avoid heavy parsing
pdf_ok = False


def contains_keywords_text(path: Path) -> bool:
    try:
        s = path.read_text(errors='ignore').casefold()
    except Exception:
        return False
    return KEYWORD in s


def contains_keywords_pdf(path: Path) -> bool:
    # Fast raw-byte search (UTF-8 / Latin-1) — avoids parsing the PDF structure
    try:
        data = path.read_bytes()
        low = data.lower()
        if KEYWORD.encode('utf-8') in low or KEYWORD.encode('latin-1') in low:
            return True
    except Exception:
        return False
    return False


def main():
    if not SRC.exists():
        print('Quellordner nicht gefunden:', SRC)
        sys.exit(1)
    TARGET.mkdir(parents=True, exist_ok=True)

    copied = []
    for path in SRC.rglob('*'):
        if path.is_dir():
            continue
        name_lower = path.name.casefold()
        matched = False
        # filename match
        if KEYWORD in name_lower:
            matched = True
        # text file content
        if not matched and path.suffix.lower() in TEXT_EXTS:
            if contains_keywords_text(path):
                matched = True
        # pdf content
        if not matched and path.suffix.lower() == PDF_EXT:
            if contains_keywords_pdf(path):
                matched = True
        if matched:
            rel = path.relative_to(SRC)
            dest = TARGET / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            print('Kopiere', path, '->', dest)
            shutil.copy2(str(path), str(dest))
            copied.append(str(rel))

    print('\nFertig. Anzahl kopierter Dateien:', len(copied))
    for c in copied:
        print('-', c)

    if not pdf_ok:
        print('\nHinweis: PyPDF2 nicht verfügbar — PDFs wurden nicht inhaltlich durchsucht.')

if __name__ == '__main__':
    main()
