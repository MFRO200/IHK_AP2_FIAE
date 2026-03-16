#!/usr/bin/env python3
"""
Extrahiert den Lösungsschlüssel aus einer WISO-Lösungs-PDF.
Gibt JSON auf stdout aus: { "1": "4", "2": "1", ... }

Unterstützte Formate:
  - ZPA-Tabelle: Aufgabe/Lösung Spalten mit nummerierten Antworten
  - Peter-Rybarski: "Antwort X" Pattern
  - Einfache Zeilenliste mit Aufgabennummern und Ziffern

Usage:  python extract_wiso_answers.py <dokument_id>
        python extract_wiso_answers.py --file <pdf_path>
"""

import sys
import os
import re
import json
import io

# ── PyMuPDF ──
import fitz

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
STORAGE = os.path.join(WORKSPACE, "storage")

# ── OCR Konfiguration ──
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
OCR_DPI = 250  # höher als bei Scan, da wir Ziffern exakt lesen wollen
OCR_LANG = "eng"  # nur eng traineddata installiert


def extract_text_from_pdf(pdf_path: str) -> tuple[str, bool]:
    """Extrahiert Text aus allen Seiten einer PDF.
    Fallback: OCR via Tesseract für gescannte PDFs.
    Gibt (text, ocr_used) zurück.
    """
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += (page.get_text() or "") + "\n"

    # Prüfe ob genug Text vorhanden (gescannte PDFs haben fast keinen Text)
    total_chars = len(text.strip())
    num_pages = len(doc)
    ocr_used = False

    if total_chars < 50 * max(num_pages, 1):
        # OCR Fallback
        try:
            import pytesseract
            from PIL import Image
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

            print(f"Text zu kurz ({total_chars} Zeichen für {num_pages} Seiten), starte OCR...", file=sys.stderr)
            ocr_text = ""
            for i, page in enumerate(doc):
                try:
                    mat = fitz.Matrix(OCR_DPI / 72, OCR_DPI / 72)
                    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    page_text = pytesseract.image_to_string(
                        img, lang=OCR_LANG, config="--psm 6",
                        timeout=45,
                    )
                    ocr_text += (page_text or "") + "\n"
                    print(f"  Seite {i+1}/{num_pages}: {len(page_text or '')} Zeichen", file=sys.stderr)
                except Exception as e:
                    print(f"  WARN: OCR Seite {i+1} fehlgeschlagen: {e}", file=sys.stderr)
            if len(ocr_text.strip()) > total_chars:
                text = ocr_text
                ocr_used = True
                print(f"OCR fertig: {len(text.strip())} Zeichen extrahiert", file=sys.stderr)
        except ImportError:
            print("WARN: pytesseract nicht installiert, kein OCR möglich", file=sys.stderr)

    doc.close()
    return text, ocr_used


def find_pdf_path(doc_id: int) -> str:
    """Findet den PDF-Pfad anhand der Dokument-ID aus der DB."""
    import psycopg
    from db_config import DB_URL
    conn = psycopg.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("SELECT pfad FROM dokumente WHERE id = %s", (doc_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise FileNotFoundError(f"Dokument {doc_id} nicht gefunden")
    pfad = row[0]
    # ~/... → absoluten Home-Pfad auflösen
    if pfad.startswith('~/') or pfad.startswith('~\\'):
        expanded = os.path.expanduser(pfad)
        if os.path.isfile(expanded):
            return expanded
    # Prüfe storage/ und Workspace-Root
    for base in [STORAGE, WORKSPACE]:
        full = os.path.join(base, pfad)
        if os.path.isfile(full):
            return full
    raise FileNotFoundError(f"PDF nicht gefunden: {pfad}")


def parse_rybarski_format(text: str) -> dict:
    """
    Format: 'X.\nThema\nAntwort Y' oder 'Antwort 2 – 1 – 3'
    Zeilenbasiertes Parsing.
    """
    answers = {}
    lines = text.split('\n')
    current_num = None

    for i, line in enumerate(lines):
        line = line.strip()
        # Neue Aufgabe erkannt: "1." oder "23."
        m = re.match(r'^(\d{1,2})\.$', line)
        if m:
            current_num = m.group(1)
            continue
        # "Antwort X" in aktueller Aufgabe
        if current_num and re.match(r'^Antwort\b', line):
            raw = re.sub(r'^Antwort\s*', '', line).strip()
            # Alle Ziffern im Antwort-Text sammeln
            digits = re.findall(r'\d', raw)
            if len(digits) == 1:
                # Einfache MC-Antwort: "4"
                answers[current_num] = digits[0]
            elif len(digits) == 2:
                # Zwei gültige Antworten: "3 – 6" → "3;6"
                answers[current_num] = f"{digits[0]};{digits[1]}"
            elif len(digits) >= 3:
                # Zuordnung: "2 – 1 – 3 – 2 – 2" → "2-1-3-2-2"
                answers[current_num] = '-'.join(digits)
            else:
                # Fallback: erste Ziffer
                fm = re.search(r'(\d)', raw)
                if fm:
                    answers[current_num] = fm.group(1)
    return answers


def parse_zpa_table_format(text: str) -> dict:
    """
    Offizielles ZPA-Format: Aufgabe-Lösung Tabelle.
    Zwei Varianten:
    A) Spalten-Tabelle: Alle Aufgabe-Nummern stehen oben, alle Antworten unten
    B) Inline: 'N. Antwort' auf derselben Zeile (OCR-Text)
    """
    answers = {}

    # Finde den WISO-Block
    wiso_start = text.find("Wirtschafts- und Sozialkunde")
    if wiso_start < 0:
        for alt in ["Wirtschafts-", "Sozialkunde", "WiSo"]:
            pos = text.find(alt)
            if pos >= 0:
                wiso_start = pos
                break
        else:
            wiso_start = 0
    relevant = text[wiso_start:]

    lines = relevant.split('\n')
    lines = [l.strip() for l in lines if l.strip()]

    # ── Strategie A: Spalten-Tabelle erkennen ──
    # Sammle Aufgaben-Nummern in Reihenfolge, dann die Antworten danach
    # Unterstützt mehrseitige Tabellen: Tasks → Antworten → Tasks → Antworten
    task_chunks = []     # Liste von chunks: [(task_nums, task_sub_counts), ...]
    answer_chunks = []   # Liste von answer-blocks: [[val1, val2, ...], ...]
    cur_tasks = []
    cur_subs = {}
    cur_answers = []
    in_tasks = True      # Erst Aufgaben, dann Antworten

    for line in lines:
        # "Insgesamt" etc. → nur stoppen wenn wir bereits Antworten haben
        if re.match(r'^(Insgesamt|Teilbewertung|Globalbewertung)', line):
            if not in_tasks and cur_answers:
                # Speichere aktuellen Chunk
                pass  # Wird unten fortgesetzt
            # Einfach überspringen, nicht abbrechen
            continue
        # "Hinweis:" am Anfang überspringen
        if re.match(r'^Hinweis', line):
            continue

        # ── Antwort-Werte zuerst prüfen (VOR Aufgaben-Nummern) ──
        # Damit "15.06.13" nicht als Aufgabe "15." erkannt wird
        # Datum-Pattern: "15.06.13", "01.01.2024"
        dt = re.match(r'^\d{1,2}\.\d{2}\.\d{2,4}$', line)
        if dt and not in_tasks:
            cur_answers.append(line)
            continue
        # Deutsches Zahlenformat: "2.992,88", "246,00", "6.750,00", "7,85"
        # Erkennt Zahlen mit Tausender-Punkt und/oder Dezimalkomma
        dec = re.match(r'^\d{1,3}(?:\.\d{3})*,\d+$', line)
        if dec and not in_tasks:
            cur_answers.append(line)
            continue
        # Brüche: "3/9", "4/7"
        frac = re.match(r'^\d+/\d+$', line)
        if frac and not in_tasks:
            cur_answers.append(line)
            continue
        # [X;Y] mit verschiedenen Klammern
        bracket = re.match(r'^[\[\(\{]([0-9;:,]+)[\]\)\}]$', line)
        if bracket:
            in_tasks = False
            cur_answers.append(re.sub(r'[;:,]', ';', bracket.group(1)))
            continue

        # Aufgaben-Nummer: "1." oder "11.\ta)" oder "28."
        # Aber NUR wenn gefolgt von Tab/Leerzeichen/Sub-Aufgabe oder Ende
        tm = re.match(r'^(\d{1,2})[.]\s*(.*)', line)
        if tm:
            num = int(tm.group(1))
            rest = tm.group(2).strip()
            # Nicht als Aufgabe erkennen wenn Rest wie ein Datum aussieht
            if re.match(r'^\d{2}\.\d{2,4}', rest):
                # Das ist ein Datum wie "15.06.13" → als Antwort behandeln
                if not in_tasks:
                    cur_answers.append(line)
                continue
            # Nicht als Aufgabe erkennen wenn Rest wie eine Zahl aussieht
            # z.B. "2.992,88" → rest="992,88"
            if rest and re.match(r'^\d{2,}', rest):
                if not in_tasks:
                    cur_answers.append(line)
                continue
            # Nur gültige Aufgabennummern (1-30)
            if 1 <= num <= 30:
                # Falls wir gerade Antworten sammelten und jetzt wieder Tasks kommen
                if not in_tasks and cur_answers:
                    task_chunks.append((cur_tasks[:], dict(cur_subs)))
                    answer_chunks.append(cur_answers[:])
                    cur_tasks = []
                    cur_subs = {}
                    cur_answers = []
                    in_tasks = True

                num_str = str(num)
                # Prüfe ob Sub-Aufgabe a)
                if re.match(r'^a\)', rest):
                    cur_tasks.append(num_str)
                    cur_subs[num_str] = 1
                else:
                    cur_tasks.append(num_str)
                    cur_subs[num_str] = 0
                continue

        # Sub-Aufgabe b), c), ... (erhöht Zähler)
        sm = re.match(r'^[b-f]\)', line)
        if sm and in_tasks and cur_tasks:
            last = cur_tasks[-1]
            if last in cur_subs and cur_subs[last] > 0:
                cur_subs[last] += 1
            continue

        # Antwort-Wert: einzelne Ziffer 1-6
        val = _extract_single_answer(line)
        if val is not None:
            in_tasks = False
            cur_answers.append(val)
            continue
        # Zweistellige Zahl als Antwort (z.B. "03", "10") — nur im Antwort-Modus
        two_digit = re.match(r'^(\d{2})$', line)
        if two_digit and not in_tasks:
            cur_answers.append(line)
            continue
        # Dezimal mit Suffix: "278,34 oder", "2.992,88 €"
        dec_suffix = re.match(r'^(\d[\d.,]+)\s+\w', line)
        if dec_suffix and not in_tasks:
            cur_answers.append(dec_suffix.group(1))
            continue

    # Letzten Chunk speichern
    if cur_tasks:
        task_chunks.append((cur_tasks, cur_subs))
    if cur_answers:
        answer_chunks.append(cur_answers)

    # Mappe Aufgaben → Antworten (unter Berücksichtigung von Sub-Tasks)
    for chunk_idx, (tasks, subs) in enumerate(task_chunks):
        if chunk_idx >= len(answer_chunks):
            break
        ans_list = answer_chunks[chunk_idx]
        ans_idx = 0
        for num in tasks:
            sub_count = subs.get(num, 0)
            if sub_count >= 2:
                # Sub-Aufgaben: sammle sub_count Antworten als Zuordnung
                sub_ans = []
                for _ in range(sub_count):
                    if ans_idx < len(ans_list):
                        sub_ans.append(ans_list[ans_idx])
                        ans_idx += 1
                if sub_ans:
                    answers[num] = '-'.join(sub_ans)
            else:
                if ans_idx < len(ans_list):
                    answers[num] = ans_list[ans_idx]
                    ans_idx += 1

    # ── Strategie B: Inline-Format (OCR-Text) ──
    # Wird nur genutzt wenn Strategie A wenig gefunden hat
    if len(answers) < 15:
        inline_answers = _parse_zpa_inline(lines)
        if len(inline_answers) > len(answers):
            answers = inline_answers

    return answers


def _parse_zpa_inline(lines: list[str]) -> dict:
    """
    Parse ZPA table where answer is on the same line as the task number.
    z.B. '1. 3' oder '2. [1;6]' oder '1. a) [1:6]'
    """
    answers = {}
    for i, line in enumerate(lines):
        m = re.match(r'^(\d{1,2})[.,;:]\s*(.*)', line)
        if not m:
            continue
        num = m.group(1)
        rest = m.group(2).strip()

        # Sub-Aufgabe? z.B. "1. a) [1;6]"
        sub_match = re.match(r'^a\)\s*(.*)', rest)
        if sub_match:
            sub_answers = []
            sub_text = sub_match.group(1).strip()
            sub_val = _extract_single_answer(sub_text)
            if sub_val:
                sub_answers.append(sub_val)
            for j in range(i + 1, min(i + 15, len(lines))):
                sl = lines[j].strip()
                sm = re.match(r'^[b-f]\)\s*(.*)', sl)
                if sm:
                    sv = _extract_single_answer(sm.group(1).strip())
                    if sv:
                        sub_answers.append(sv)
                elif re.match(r'^(\d{1,2})[.,;:]', sl):
                    break
            if len(sub_answers) >= 2:
                answers[num] = '-'.join(sub_answers)
            elif len(sub_answers) == 1:
                answers[num] = sub_answers[0]
            continue

        # Inline-Antwort
        val = _extract_single_answer(rest)
        if val:
            answers[num] = val
            continue

        # Nächste Zeile
        for j in range(i + 1, min(i + 5, len(lines))):
            nxt = lines[j].strip()
            if re.match(r'^(\d{1,2})[.,;:]', nxt):
                break
            val = _extract_single_answer(nxt)
            if val:
                answers[num] = val
                break

    return answers


def _extract_single_answer(text: str) -> str | None:
    """
    Extrahiert eine einzelne Antwort aus einem Text-Fragment.
    Unterstützt: Einzelziffern, [X;Y], [X:Y] (OCR), Datumsangaben, Dezimalzahlen.
    """
    text = text.strip()
    if not text:
        return None

    # [X;Y] oder [X:Y] (OCR-Artefakt) → Mehrfachantwort
    bm = re.match(r'^\[?([0-9][;:,][0-9](?:[;:,][0-9])*)\]?$', text)
    if bm:
        raw = bm.group(1)
        # Normalisiere Trennzeichen zu ;
        return re.sub(r'[;:,]', ';', raw)

    # (X;Y) mit runden Klammern (OCR-Fehler für eckige)
    pm = re.match(r'^\(([0-9][;:,][0-9](?:[;:,][0-9])*)\)$', text)
    if pm:
        raw = pm.group(1)
        return re.sub(r'[;:,]', ';', raw)

    # {X;Y} mit geschweiften Klammern (OCR-Fehler für eckige)
    cm = re.match(r'^\{([0-9][;:,][0-9](?:[;:,][0-9])*)\}$', text)
    if cm:
        raw = cm.group(1)
        return re.sub(r'[;:,]', ';', raw)

    # Einzelne Ziffer 1-6
    dm = re.match(r'^([1-6])$', text)
    if dm:
        return dm.group(1)

    return None


def parse_simple_list(text: str) -> dict:
    """
    Fallback: Suche nach Zeilen die nur eine Ziffer enthalten,
    gruppiert nach Aufgabenblöcken.
    """
    answers = {}
    # Suche nach dem Bereich nach "Lösung" oder "Wirtschafts"
    start = max(
        text.find("Lösung"),
        text.find("Wirtschafts"),
        0
    )
    relevant = text[start:]
    lines = relevant.split('\n')
    lines = [l.strip() for l in lines if l.strip()]

    # Sammle alle einzelnen Ziffern in Folge
    digits = []
    for line in lines:
        m = re.match(r'^(\d)$', line)
        bm = re.match(r'^\[([0-9;]+)\]$', line)
        if m:
            digits.append(m.group(1))
        elif bm:
            digits.append(bm.group(1))

    # Wenn wir ~30 Ziffern haben, sind das die Antworten 1-30
    if 25 <= len(digits) <= 35:
        for idx, d in enumerate(digits[:30], 1):
            answers[str(idx)] = d

    return answers


def parse_ocr_loose(text: str) -> dict:
    """
    Sehr lockerer OCR-Parser für schlecht lesbare Fax/Scan-PDFs.
    Sucht nach Pattern: Aufgabennummer gefolgt von einer Antwort-Ziffer,
    auch mitten in der Zeile (z.B. Mehrspalten-Tabelle).
    Pattern: 'N  D  P' wo N=Aufgabennummer, D=Antwort-Ziffer, P=Punkte
    """
    answers = {}

    # WISO-Block finden
    wiso_start = -1
    for marker in ["Wirtschafts- und Sozialkunde", "Wirtschafts-", "Sozialkunde", "WiSo"]:
        pos = text.find(marker)
        if pos >= 0:
            wiso_start = pos
            break
    if wiso_start < 0:
        return {}
    relevant = text[wiso_start:]

    # Suche alle "AufgabenNr Ziffer" Pattern in jeder Zeile
    # Format: "1 3 1" (Aufgabe 1, Lösung 3, 1 Punkt) oder "14 a) 2 2"
    for line in relevant.split('\n'):
        # Pattern 1: "N  D  P" — Aufgabe-Nr + Ziffer + Punkte
        #   z.B. "1 3 1", "6 1 3", "16 2 3"
        for m in re.finditer(r'\b(\d{1,2})\s+([1-6])\s+\d\b', line):
            num = m.group(1)
            ans = m.group(2)
            n = int(num)
            if 1 <= n <= 30 and num not in answers:
                answers[num] = ans

        # Pattern 2: "N  [X;Y]" oder "N  [X:Y]"
        for m in re.finditer(r'\b(\d{1,2})\s+[\[\({]([0-9][;:,][0-9](?:[;:,][0-9])*)[\]\)}]', line):
            num = m.group(1)
            raw = m.group(2)
            n = int(num)
            if 1 <= n <= 30 and num not in answers:
                answers[num] = re.sub(r'[;:,]', ';', raw)

    return answers


def extract_answers(text: str) -> dict:
    """Versucht alle Formate und gibt das beste Ergebnis zurück."""
    results = []

    # Format 1: Peter Rybarski ("Antwort X")
    if "Antwort" in text:
        r = parse_rybarski_format(text)
        if r:
            results.append(("rybarski", r))

    # Format 2: ZPA-Tabelle
    r = parse_zpa_table_format(text)
    if r:
        results.append(("zpa", r))

    # Format 3: OCR loose pattern (Fax-Tabellen)
    r = parse_ocr_loose(text)
    if r:
        results.append(("ocr_loose", r))

    if not results:
        return {}

    # Bestes Ergebnis: das mit den meisten Antworten
    results.sort(key=lambda x: len(x[1]), reverse=True)
    best_format, best = results[0]

    # Nur Aufgaben 1-30 behalten
    filtered = {}
    for k, v in best.items():
        try:
            n = int(k)
            if 1 <= n <= 30:
                filtered[k] = v
        except ValueError:
            pass

    return filtered


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_wiso_answers.py <dokument_id>", file=sys.stderr)
        print("       python extract_wiso_answers.py --file <pdf_path>", file=sys.stderr)
        sys.exit(1)

    if sys.argv[1] == "--file":
        pdf_path = sys.argv[2]
    else:
        doc_id = int(sys.argv[1])
        pdf_path = find_pdf_path(doc_id)

    text, ocr_used = extract_text_from_pdf(pdf_path)
    answers = extract_answers(text)

    result = {
        "answers": answers,
        "count": len(answers),
        "source": os.path.basename(pdf_path),
        "ocr_used": ocr_used,
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
