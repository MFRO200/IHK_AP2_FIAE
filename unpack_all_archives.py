#!/usr/bin/env python3
import argparse
import subprocess
import shutil
from pathlib import Path
import zipfile

KNOWN_MULTI = ('.tar.gz', '.tgz')
KNOWN_SUFFIXES = {'.zip', '.7z', '.rar', '.tar', '.gz', '.tgz', '.tar.gz'}


def has_7z():
    # first try to find a command on PATH
    for cmd in ('7z', '7za', '7zr'):
        p = shutil.which(cmd)
        if p:
            return p
    # common Windows install locations
    common = [
        Path(r"C:/Program Files/7-Zip/7z.exe"),
        Path(r"C:/Program Files (x86)/7-Zip/7z.exe"),
    ]
    for p in common:
        if p.exists():
            return str(p)
    return None


def strip_known_extensions(name: str) -> str:
    for ext in KNOWN_MULTI:
        if name.lower().endswith(ext):
            return name[: -len(ext)]
    return name.rsplit('.', 1)[0]


def extract_with_zip(path: Path, dest: Path):
    with zipfile.ZipFile(path, 'r') as z:
        z.extractall(dest)


def extract_with_7z(path: Path, dest: Path, sevenz_cmd: str):
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.check_call([sevenz_cmd, 'x', str(path), f'-o{str(dest)}', '-y'])


def unique_dest_path(dest: Path) -> Path:
    """Return a non-existing path by appending _1, _2, ... if needed."""
    if not dest.exists():
        return dest
    base = str(dest)
    i = 1
    while True:
        candidate = Path(f"{base}_{i}")
        if not candidate.exists():
            return candidate
        i += 1


def main():
    p = argparse.ArgumentParser(description='Entpacke alle Archivdateien direkt im angegebenen Ordner.')
    p.add_argument('root', nargs='?', default='.', help='Root-Ordner (standard: aktuelles Verzeichnis)')
    p.add_argument('-r', '--recursive', action='store_true', help='rekursiv durchsuchen')
    p.add_argument('-d', '--delete', action='store_true', help='Archive nach Entpacken löschen')
    p.add_argument('--conflict', choices=['overwrite', 'skip', 'rename'], default='rename',
                   help='Wie mit vorhandenen Zielordnern umgehen (default: rename)')
    args = p.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print('Root-Ordner existiert nicht oder ist kein Verzeichnis:', root)
        return

    sevenz_cmd = has_7z()
    if not sevenz_cmd:
        print('Hinweis: `7z` nicht gefunden. Nur .zip wird nativ unterstützt; andere Formate benötigen 7z.')

    pattern = '**/*' if args.recursive else '*'
    files = [f for f in root.glob(pattern) if f.is_file()]

    processed = 0
    for f in files:
        suffix = f.suffix.lower()
        # handle .tar.gz/.tgz detection
        full_name = f.name
        matched_multi = False
        for ext in KNOWN_MULTI:
            if full_name.lower().endswith(ext):
                suffix = ext
                matched_multi = True
                break

        if suffix not in KNOWN_SUFFIXES:
            continue

        dest_name = strip_known_extensions(f.name)
        dest = f.parent / dest_name

        # Konfliktbehandlung für vorhandene Zielordner
        if dest.exists():
            if args.conflict == 'overwrite':
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            elif args.conflict == 'skip':
                print('  Überspringe (Ziel existiert):', dest)
                continue
            else:  # rename
                dest = unique_dest_path(dest)

        try:
            print('Entpacke', f, '->', dest)
            if suffix == '.zip':
                dest.mkdir(parents=True, exist_ok=True)
                extract_with_zip(f, dest)
            else:
                if not sevenz_cmd:
                    print('  Überspringe (kein 7z):', f)
                    continue
                extract_with_7z(f, dest, sevenz_cmd)
            processed += 1
            if args.delete:
                f.unlink()
                print('  Archiv gelöscht:', f)
        except Exception as e:
            print('  Fehler beim Entpacken', f, ':', e)

    print('\nFertig. Anzahl entpackter Archive:', processed)


if __name__ == '__main__':
    main()
