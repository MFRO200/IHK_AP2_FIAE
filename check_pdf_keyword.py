#!/usr/bin/env python3
import sys
from pathlib import Path
try:
    import fitz  # PyMuPDF
except Exception:
    print('NO_PYMUPDF')
    sys.exit(2)

def main():
    if len(sys.argv) < 3:
        print('USAGE: check_pdf_keyword.py <pdf_path> <keyword>')
        sys.exit(2)
    pdf = Path(sys.argv[1])
    kw = sys.argv[2].casefold()
    max_pages = 50
    try:
        doc = fitz.open(str(pdf))
        n = min(len(doc), max_pages)
        for i in range(n):
            try:
                text = doc[i].get_text() or ''
            except Exception:
                continue
            if kw in text.casefold():
                print('FOUND')
                sys.exit(0)
        doc.close()
    except Exception:
        sys.exit(3)
    sys.exit(1)

if __name__ == '__main__':
    main()
