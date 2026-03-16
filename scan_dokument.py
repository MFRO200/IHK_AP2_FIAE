#!/usr/bin/env python3
"""
scan_dokument.py — Scannt ein einzelnes PDF gegen alle Suchbegriffe in der DB.
Erzeugt treffer-Einträge (seiten + kontext).

Texterkennung:
  1. PyMuPDF get_text() (schnell, für natives PDF)
  2. Fallback: OCR via Tesseract (für gescannte PDFs)

Aufruf:
  python scan_dokument.py <dokument_id> [--pdf <pfad>]

Ohne --pdf wird der Pfad aus der DB gelesen.
Gibt JSON auf stdout aus: { "treffer": [...], "pages_scanned": N, "ocr_used": bool }
"""

import json
import os
import re
import sys
import io
from pathlib import Path

# ─── Config ───
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "127.0.0.1"),
    "port": int(os.environ.get("DB_PORT", "15432")),
    "dbname": os.environ.get("POSTGRES_DB", "ihk_ap2"),
    "user": os.environ.get("POSTGRES_USER", "ihk"),
    "password": os.environ.get("POSTGRES_PASSWORD", ""),
}

TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
OCR_DPI = 200
OCR_LANG = "eng"  # nur eng installiert; deu nicht verfügbar
MAX_PAGES = 80
CONTEXT_CHARS = 120  # Zeichen Kontext um den Treffer

WORKSPACE = Path(__file__).resolve().parent


def get_db():
    import psycopg
    return psycopg.connect(**DB_CONFIG)


def extract_text_pages(pdf_path: str) -> tuple[list[str], bool]:
    """Extrahiert Text pro Seite. Gibt (pages, ocr_used) zurück."""
    import fitz

    doc = fitz.open(pdf_path)
    n = min(len(doc), MAX_PAGES)
    pages: list[str] = []
    ocr_used = False

    # 1. Versuch: PyMuPDF native Textextraktion
    for i in range(n):
        try:
            text = doc[i].get_text() or ""
        except Exception:
            text = ""
        pages.append(text)

    # Prüfe ob genug Text gefunden wurde (< 50 Zeichen pro Seite im Schnitt → gescannt)
    total_chars = sum(len(p) for p in pages)
    if total_chars < 50 * n and n > 0:
        # 2. Fallback: OCR mit Per-Page-Timeout
        try:
            import pytesseract
            from PIL import Image
            import subprocess
            import tempfile

            pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
            ocr_pages: list[str] = []
            for i in range(n):
                try:
                    mat = fitz.Matrix(OCR_DPI / 72, OCR_DPI / 72)
                    pix = doc[i].get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    # Per-Page Timeout: 30 Sekunden
                    text = pytesseract.image_to_string(
                        img, lang=OCR_LANG, config="--psm 3",
                        timeout=30,
                    )
                    ocr_pages.append(text or "")
                except Exception as e:
                    print(f"WARN: OCR Seite {i+1} fehlgeschlagen: {e}", file=sys.stderr)
                    ocr_pages.append("")
            pages = ocr_pages
            ocr_used = True
        except ImportError:
            pass  # Kein pytesseract → bleibe bei leerem Text

    doc.close()
    return pages, ocr_used


def find_matches(pages: list[str], begriffe: list[dict]) -> list[dict]:
    """Sucht alle Suchbegriffe in den Seiten. Gibt Treffer-Liste zurück."""
    results = []
    for bg in begriffe:
        bg_id = bg["id"]
        pattern = re.compile(re.escape(bg["begriff"]), re.IGNORECASE)
        found_pages: list[int] = []
        contexts: list[str] = []

        for page_idx, text in enumerate(pages):
            page_nr = page_idx + 1
            match = pattern.search(text)
            if match:
                found_pages.append(page_nr)
                # Kontext extrahieren
                start = max(0, match.start() - CONTEXT_CHARS)
                end = min(len(text), match.end() + CONTEXT_CHARS)
                snippet = text[start:end].replace("\n", " ").strip()
                if len(contexts) < 3:  # Max 3 Kontext-Snippets
                    contexts.append(f"S.{page_nr}: …{snippet}…")

        if found_pages:
            results.append({
                "suchbegriff_id": bg_id,
                "seiten": ", ".join(str(p) for p in found_pages),
                "kontext": " | ".join(contexts),
            })

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("dokument_id", type=int)
    parser.add_argument("--pdf", type=str, default=None)
    args = parser.parse_args()

    conn = get_db()
    cur = conn.cursor()

    # 1) Dokument-Pfad ermitteln
    if args.pdf:
        pdf_path = args.pdf
    else:
        cur.execute("SELECT pfad FROM dokumente WHERE id = %s", (args.dokument_id,))
        row = cur.fetchone()
        if not row:
            print(json.dumps({"error": f"Dokument {args.dokument_id} nicht gefunden"}))
            sys.exit(1)
        pdf_path = str(WORKSPACE / row[0])

    if not Path(pdf_path).exists():
        print(json.dumps({"error": f"PDF nicht gefunden: {pdf_path}"}))
        sys.exit(1)

    # 2) Alle Suchbegriffe laden
    cur.execute("SELECT id, begriff FROM suchbegriffe ORDER BY id")
    begriffe = [{"id": r[0], "begriff": r[1]} for r in cur.fetchall()]
    if not begriffe:
        print(json.dumps({"error": "Keine Suchbegriffe in der DB", "treffer": [], "pages_scanned": 0}))
        sys.exit(0)

    # 3) Text extrahieren
    pages, ocr_used = extract_text_pages(pdf_path)

    # 4) Begriffe suchen
    matches = find_matches(pages, begriffe)

    # 5) Alte Treffer für dieses Dokument löschen
    cur.execute("DELETE FROM treffer WHERE dokument_id = %s", (args.dokument_id,))

    # 6) Neue Treffer einfügen
    inserted = 0
    for m in matches:
        try:
            cur.execute(
                """INSERT INTO treffer (suchbegriff_id, dokument_id, seiten, kontext)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (suchbegriff_id, dokument_id)
                   DO UPDATE SET seiten = EXCLUDED.seiten, kontext = EXCLUDED.kontext""",
                (m["suchbegriff_id"], args.dokument_id, m["seiten"], m["kontext"]),
            )
            inserted += 1
        except Exception as e:
            print(f"WARN: Treffer-Insert fehlgeschlagen: {e}", file=sys.stderr)

    # 7) treffer_anzahl in suchbegriffe aktualisieren
    cur.execute("""
        UPDATE suchbegriffe s
        SET treffer_anzahl = (SELECT COUNT(*) FROM treffer t WHERE t.suchbegriff_id = s.id)
    """)

    conn.commit()

    result = {
        "dokument_id": args.dokument_id,
        "pages_scanned": len(pages),
        "ocr_used": ocr_used,
        "treffer_count": inserted,
        "treffer": [
            {"suchbegriff_id": m["suchbegriff_id"], "seiten": m["seiten"]}
            for m in matches
        ],
    }
    print(json.dumps(result, ensure_ascii=False))
    conn.close()


if __name__ == "__main__":
    main()
