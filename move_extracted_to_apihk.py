#!/usr/bin/env python3
from pathlib import Path
import shutil

KNOWN_MULTI = ('.tar.gz', '.tgz')
KNOWN_SUFFIXES = {'.zip', '.7z', '.rar', '.tar', '.gz', '.tgz', '.tar.gz'}


def strip_known_extensions(name: str) -> str:
    for ext in KNOWN_MULTI:
        if name.lower().endswith(ext):
            return name[: -len(ext)]
    return name.rsplit('.', 1)[0]


def unique_name(target_dir: Path, name: str) -> str:
    candidate = target_dir / name
    if not candidate.exists():
        return name
    i = 1
    while True:
        nm = f"{name}_{i}"
        if not (target_dir / nm).exists():
            return nm
        i += 1


def main():
    root = Path(r"c:\Users\CC-Student\Documents\Neuer Ordner\IHK_AP2").resolve()
    if not root.exists():
        print('Root nicht gefunden:', root)
        return
    target = root / 'AP_IHK'
    target.mkdir(exist_ok=True)

    # collect archive base names in root (non-recursive)
    bases = set()
    for f in root.iterdir():
        if not f.is_file():
            continue
        name = f.name
        lower = name.lower()
        matched = False
        for ext in KNOWN_MULTI:
            if lower.endswith(ext):
                bases.add(strip_known_extensions(name))
                matched = True
                break
        if matched:
            continue
        if Path(name).suffix.lower() in KNOWN_SUFFIXES:
            bases.add(strip_known_extensions(name))

    moved = []
    skipped = []

    # move directories in root that match any base (exact or base_*)
    for entry in list(root.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name == 'AP_IHK':
            continue
        for base in bases:
            if entry.name == base or entry.name.startswith(base + '_'):
                new_name = unique_name(target, entry.name)
                dest = target / new_name
                print('Verschiebe', entry, '->', dest)
                shutil.move(str(entry), str(dest))
                moved.append(entry.name)
                break

    print('\nFertig. Verschobene Ordner:', len(moved))
    if moved:
        for m in moved:
            print(' -', m)

if __name__ == '__main__':
    main()
