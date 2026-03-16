#!/usr/bin/env python3
from pathlib import Path
import shutil
import sys

ROOT = Path(r"c:\Users\CC-Student\Documents\Neuer Ordner\IHK_AP2").resolve()
AP_DIR = ROOT / 'AP_IHK'
TARGET = ROOT / 'AP_IHK_Anwendungsentwicklung'
TEXT_EXTS = {'.txt', '.md', '.csv', '.html', '.htm', '.xml', '.json'}
PDF_EXT = '.pdf'

KEYWORDS = ['anwendungsentwicklung', 'anwendungsentwickler', 'fachinformatik', 'fachinformatiker']

# try to import PyPDF2 for PDF text extraction
try:
    import PyPDF2
    pdf_ok = True
except Exception:
    pdf_ok = False


def contains_keywords_text(path: Path) -> bool:
    try:
        s = path.read_text(errors='ignore').casefold()
    except Exception:
        return False
    for k in KEYWORDS:
        if k in s:
            return True
    return False


def contains_keywords_pdf(path: Path) -> bool:
    if not pdf_ok:
        return False
    try:
        with open(path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for p in reader.pages:
                text = p.extract_text() or ''
                if any(k in text.casefold() for k in KEYWORDS):
                    return True
    except Exception:
        return False
    return False


def main():
    if not AP_DIR.exists():
        print('AP_IHK Ordner nicht gefunden:', AP_DIR)
        sys.exit(1)
    TARGET.mkdir(exist_ok=True)

    moved = []
    for path in AP_DIR.rglob('*'):
        if path.is_dir():
            continue
        name_lower = path.name.casefold()
        matched = False
        # filename match
        for k in KEYWORDS:
            if k in name_lower:
                matched = True
                break
        # text file content match
        if not matched and path.suffix.lower() in TEXT_EXTS:
            if contains_keywords_text(path):
                matched = True
        # pdf content match (if PyPDF2 available)
        if not matched and path.suffix.lower() == PDF_EXT:
            if contains_keywords_pdf(path):
                matched = True
        if matched:
            # compute relative path under AP_DIR, move to TARGET preserving relative dirs
            rel = path.relative_to(AP_DIR)
            dest = TARGET / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            print('Verschiebe', path, '->', dest)
            shutil.move(str(path), str(dest))
            moved.append(str(rel))

    print('\nFertig. Verschobene Dateien:', len(moved))
    for m in moved:
        print('-', m)

    if not pdf_ok:
        print('\nHinweis: PyPDF2 nicht installiert — PDFs wurden nur per Dateiname durchsucht.')


if __name__ == '__main__':
    main()
