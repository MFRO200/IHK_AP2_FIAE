#!/usr/bin/env python3
"""
ocr_extract_ga_antworten.py — Extrahiert Text aus einer ausgefüllten Prüfungs-PDF mittels OCR.

Verwendung:
  python ocr_extract_ga_antworten.py <dokument_id>
  python ocr_extract_ga_antworten.py --file <pdf_pfad>

Gibt JSON auf stdout aus:
  {
    "pages": [{"page": 1, "text": "..."}],
    "full_text": "...",
    "page_count": N,
    "ocr_used": true/false,
    "total_chars": N
  }
"""

import json
import os
import sys
import io
from pathlib import Path

# ─── Config ───
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
OCR_DPI = 250  # Höhere Auflösung für bessere Texterkennung
OCR_LANG = "deu+eng"  # Deutsch + Englisch für IHK-Prüfungen
MAX_PAGES = 50
WORKSPACE = Path(__file__).resolve().parent
STORAGE = WORKSPACE / "storage"


def get_db():
    """DB-Verbindung herstellen."""
    import psycopg
    DB_CONFIG = {
        "host": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        "port": int(os.environ.get("POSTGRES_PORT", "15432")),
        "dbname": os.environ.get("POSTGRES_DB", "ihk_ap2"),
        "user": os.environ.get("POSTGRES_USER", "ihk"),
        "password": os.environ.get("POSTGRES_PASSWORD", ""),
    }
    return psycopg.connect(**DB_CONFIG)


def find_pdf_path(doc_id: int) -> str:
    """Findet den PDF-Pfad anhand der Dokument-ID aus der DB."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT pfad FROM dokumente WHERE id = %s", (doc_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise FileNotFoundError(f"Dokument {doc_id} nicht gefunden")
    pfad = row[0]

    # ~/... → absoluten Home-Pfad auflösen
    if pfad.startswith("~/") or pfad.startswith("~\\"):
        expanded = os.path.expanduser(pfad)
        if os.path.isfile(expanded):
            return expanded

    # Prüfe storage/ und Workspace-Root
    for base in [STORAGE, WORKSPACE]:
        full = os.path.join(base, pfad)
        if os.path.isfile(full):
            return full

    # Direkt als absoluter Pfad
    if os.path.isfile(pfad):
        return pfad

    raise FileNotFoundError(f"PDF nicht gefunden: {pfad}")


def extract_text(pdf_path: str, force_ocr: bool = False) -> dict:
    """Extrahiert Text aus allen Seiten einer PDF.
    Bei force_ocr=True wird immer OCR verwendet (nötig für bearbeitete PDFs,
    da ausgefüllte Antworten oft als Annotationen/Formularfelder vorliegen
    und von der nativen Textextraktion nicht erfasst werden).
    1. Versuch: natives Text-Embedding (PyMuPDF) - nur wenn nicht force_ocr
    2. Fallback / force: Tesseract OCR für alle Seiten
    """
    import fitz

    doc = fitz.open(pdf_path)
    n = min(len(doc), MAX_PAGES)
    pages = []
    ocr_used = False
    native_text_total = 0

    # 1. Native Textextraktion (immer - als Referenz)
    native_pages = []
    for i in range(n):
        try:
            text = doc[i].get_text() or ""
        except Exception:
            text = ""
        native_pages.append({"page": i + 1, "text": text.strip()})
    native_text_total = sum(len(p["text"]) for p in native_pages)
    total_chars = native_text_total  # Default: Zeichenanzahl von nativem Text
    
    if not force_ocr:
        pages = native_pages

    # 2. OCR wenn force_ocr oder zu wenig nativer Text
    need_ocr = force_ocr or native_text_total < 80 * max(n, 1)
    
    if need_ocr:
        try:
            import pytesseract
            from PIL import Image

            pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
            reason = "force_ocr für bearbeitete PDF" if force_ocr else f"Nativer Text zu kurz ({native_text_total} Zeichen für {n} Seiten)"
            print(
                f"{reason}, starte OCR...",
                file=sys.stderr,
            )

            ocr_pages = []
            for i in range(n):
                try:
                    mat = fitz.Matrix(OCR_DPI / 72, OCR_DPI / 72)
                    pix = doc[i].get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    ocr_text = pytesseract.image_to_string(
                        img,
                        lang=OCR_LANG,
                        config="--psm 3",
                        timeout=45,
                    )
                    # Bei force_ocr: kombiniere nativen Text + OCR für beste Ergebnisse
                    if force_ocr and i < len(native_pages):
                        native_t = native_pages[i]["text"]
                        ocr_t = (ocr_text or "").strip()
                        # Verwende OCR wenn es deutlich mehr Text liefert,
                        # sonst nativen Text (der genauer ist)
                        if len(ocr_t) > len(native_t) * 1.2:
                            final_text = ocr_t
                        else:
                            final_text = native_t if native_t else ocr_t
                    else:
                        final_text = (ocr_text or "").strip()
                    
                    ocr_pages.append({"page": i + 1, "text": final_text})
                    print(
                        f"  Seite {i+1}/{n}: native={len(native_pages[i]['text'] if i < len(native_pages) else '')} / ocr={len(ocr_text or '')} → final={len(final_text)} Zeichen",
                        file=sys.stderr,
                    )
                except Exception as e:
                    print(f"  WARN: OCR Seite {i+1} fehlgeschlagen: {e}", file=sys.stderr)
                    ocr_pages.append({"page": i + 1, "text": ""})

            ocr_total = sum(len(p["text"]) for p in ocr_pages)
            if ocr_total > native_text_total or force_ocr:
                pages = ocr_pages
                total_chars = ocr_total
                ocr_used = True
                print(
                    f"OCR fertig: {total_chars} Zeichen extrahiert",
                    file=sys.stderr,
                )
        except ImportError:
            print("WARN: pytesseract nicht installiert, kein OCR möglich", file=sys.stderr)

    doc.close()

    # Volltext zusammensetzen
    full_text = "\n\n".join(
        f"--- Seite {p['page']} ---\n{p['text']}" for p in pages if p["text"]
    )

    return {
        "pages": pages,
        "full_text": full_text,
        "page_count": n,
        "ocr_used": ocr_used,
        "total_chars": total_chars,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Extrahiert Text aus einer ausgefüllten Prüfungs-PDF"
    )
    parser.add_argument("dokument_id", type=int, nargs="?", default=None)
    parser.add_argument("--file", type=str, default=None, help="Direkter PDF-Pfad")
    parser.add_argument("--force-ocr", action="store_true", default=False,
                        help="Erzwingt Bild-basierte OCR (nötig für bearbeitete PDFs mit Annotationen)")
    args = parser.parse_args()

    try:
        if args.file:
            pdf_path = args.file
        elif args.dokument_id:
            pdf_path = find_pdf_path(args.dokument_id)
        else:
            print(json.dumps({"error": "Bitte dokument_id oder --file angeben"}))
            sys.exit(1)

        if not os.path.isfile(pdf_path):
            print(json.dumps({"error": f"PDF nicht gefunden: {pdf_path}"}))
            sys.exit(1)

        result = extract_text(pdf_path, force_ocr=args.force_ocr)
        print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stdout)
        sys.exit(1)


if __name__ == "__main__":
    main()
