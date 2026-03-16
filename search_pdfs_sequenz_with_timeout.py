#!/usr/bin/env python3
from pathlib import Path
import subprocess
import shutil
import sys

ROOT = Path(r"c:\Users\CC-Student\Documents\Neuer Ordner\IHK_AP2").resolve()
SRC = ROOT / 'AP_IHK_Anwendungsentwicklung'
TARGET = SRC / 'Sequenzdiagramme'
KEYWORD = 'sequenzdiagramm'

TIMEOUT_S = 12

if not SRC.exists():
    print('Quellordner nicht gefunden:', SRC)
    sys.exit(1)
TARGET.mkdir(parents=True, exist_ok=True)

copied = []
check_script = ROOT / 'check_pdf_keyword.py'
python_exec = sys.executable

for pdf in SRC.rglob('*.pdf'):
    try:
        # call checker with timeout
        res = subprocess.run([python_exec, str(check_script), str(pdf), KEYWORD], capture_output=True, text=True, timeout=TIMEOUT_S)
        out = res.stdout.strip()
        if out == 'FOUND' and res.returncode == 0:
            rel = pdf.relative_to(SRC)
            dest = TARGET / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            print('Kopiere', pdf, '->', dest)
            shutil.copy2(str(pdf), str(dest))
            copied.append(str(rel))
        else:
            # not found or error
            continue
    except subprocess.TimeoutExpired:
        print('Timeout bei', pdf)
        continue
    except Exception as e:
        print('Fehler bei', pdf, ':', e)
        continue

print('\nFertig. Anzahl kopierter PDFs:', len(copied))
for c in copied:
    print('-', c)
