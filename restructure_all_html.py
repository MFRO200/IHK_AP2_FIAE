#!/usr/bin/env python3
"""
Restructure ALL search-result HTML files in Ergebnisse/ to a side-by-side
Aufgabe/Lösung layout grouped by exam period – same as Pseudocode.html.

Skips: Score-Tabelle.html, Ausgangssituationen.html, Pseudocode.html (already done),
       Pseudocode_new.html, and any file with 0 hits.
"""
import re, os, glob, html as html_mod
from urllib.parse import unquote

ERGEBNISSE = 'Ergebnisse'
SKIP = {
    'Score-Tabelle.html',
    'Ausgangssituationen.html',
    'Pseudocode.html',        # already restructured
    'Pseudocode_new.html',
    'Score-Tabelle.html.backup_vor_resort',
}


# ─── Detect exam period from href ───
def detect_exam_period(href, display):
    decoded = unquote(href)

    # Folder like: AP_IHK_Anwendungsentwicklung/2018 Sommer/
    folder_match = re.search(
        r'AP_IHK_Anwendungsentwicklung/(\d{4}(?:_\d{2,4})?\s*(?:Sommer|Winter))',
        decoded)
    if folder_match:
        raw = folder_match.group(1).strip()
        parts = raw.split()
        if len(parts) == 2:
            year_part, season = parts
            return f"{season} {year_part}"

    # Folder like: /2008/ (just year, no season)
    year_folder = re.search(r'AP_IHK_Anwendungsentwicklung/(\d{4})/', decoded)
    if year_folder:
        year = year_folder.group(1)
        combined = display + decoded
        if re.search(r'[Ss]ommer|_So|_S\d{4}', combined):
            return f"Sommer {year}"
        elif re.search(r'[Ww]inter|_Wi|_W\d{4}', combined):
            return f"Winter {year}"
        w_match = re.search(r'[Ww](\d{4})', display)
        s_match = re.search(r'[Ss](\d{4})', display)
        if w_match:
            return f"Winter {year}"
        if s_match:
            return f"Sommer {year}"
        return f"Sommer/Winter {year}"

    # Fallback: try folder name from href
    folder_match2 = re.search(r'/([^/]+)/', decoded)
    if folder_match2:
        return folder_match2.group(1)

    return "Unbekannt"


def is_loesung(display):
    return bool(re.search(r'[Ll]ösu|[Ll]osu|[Ll]öser|[Ll]oser', display))


def period_sort_key(p):
    """Sommer 2018 -> (2018, 0), Winter 2018_19 -> (2018, 1)"""
    m = re.match(r'(Sommer|Winter|Sommer/Winter)\s+(\d{4})', p)
    if m:
        season = m.group(1)
        year = int(m.group(2))
        s = 0 if 'Sommer' in season and 'Winter' not in season else 1
        return (year, s)
    return (9999, 0)


def build_card(hit_list, label):
    if not hit_list:
        return (f'<div class="card card-empty"><div class="card-label">{label}</div>'
                f'<p class="no-data">Keine {label} vorhanden</p></div>')
    parts = [f'<div class="card"><div class="card-label">{label}</div>']
    for h in hit_list:
        parts.append('<div class="pdf-entry">')
        parts.append(f'<a href="{h["href"]}" target="_blank">{h["display"]}</a>')
        parts.append(f' <span class="pages">[{h["pages"]}]</span>')
        for ctx in h['contexts']:
            parts.append(f'<div class="ctx">{ctx}</div>')
        parts.append('</div>')
    parts.append('</div>')
    return '\n'.join(parts)


CSS = '''
  body {
    font-family: Segoe UI, Arial, sans-serif;
    margin: 2em;
    background: #1e1e1e;
    color: #d4d4d4;
  }
  h1 { color: #569cd6; margin-bottom: 0.3em; }
  .subtitle { color: #808080; margin-bottom: 1.5em; font-size: 0.95em; }

  .exam-header {
    background: #264f78;
    color: #fff;
    padding: 0.5em 1em;
    margin-top: 2em;
    border-radius: 6px 6px 0 0;
    font-size: 1.15em;
    font-weight: bold;
    display: flex;
    align-items: center;
    gap: 0.7em;
  }
  .exam-header .badge-sommer {
    background: #e8a317;
    color: #1e1e1e;
    padding: 2px 10px;
    border-radius: 4px;
    font-size: 0.8em;
    font-weight: 600;
  }
  .exam-header .badge-winter {
    background: #4ec9b0;
    color: #1e1e1e;
    padding: 2px 10px;
    border-radius: 4px;
    font-size: 0.8em;
    font-weight: 600;
  }

  .exam-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1em;
    border: 1px solid #333;
    border-top: none;
    border-radius: 0 0 6px 6px;
    padding: 1em;
    background: #252526;
    margin-bottom: 0.5em;
  }

  .card {
    background: #1e1e1e;
    border: 1px solid #444;
    border-radius: 6px;
    padding: 1em;
    min-height: 80px;
  }
  .card-empty {
    background: #1e1e1e;
    border: 1px dashed #555;
    opacity: 0.6;
  }
  .card-label {
    font-weight: bold;
    font-size: 0.85em;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 0.7em;
    padding-bottom: 0.3em;
    border-bottom: 1px solid #444;
  }
  .card:first-child .card-label { color: #569cd6; }
  .card:last-child .card-label { color: #4ec9b0; }
  .card-empty .card-label { color: #666; }

  .no-data { color: #666; font-style: italic; font-size: 0.9em; }

  .pdf-entry { margin-bottom: 0.8em; }
  .pdf-entry:last-child { margin-bottom: 0; }
  .pdf-entry a {
    color: #dcdcaa;
    text-decoration: none;
    font-size: 0.95em;
  }
  .pdf-entry a:hover { text-decoration: underline; color: #ce9178; }
  .pages { color: #9cdcfe; font-size: 0.85em; }
  .ctx {
    color: #808080;
    font-size: 0.82em;
    margin: 0.2em 0 0.3em 1em;
    white-space: pre-wrap;
    line-height: 1.4;
  }
  mark { background: #4e4e0a; color: #dcdcaa; padding: 1px 2px; }

  .nav { margin: 1em 0 2em 0; }
  .nav a {
    color: #569cd6;
    text-decoration: none;
    margin-right: 0.8em;
    font-size: 0.9em;
  }
  .nav a:hover { text-decoration: underline; }
  .stats { color: #808080; font-size: 0.9em; margin-bottom: 1em; }
  .stats strong { color: #d4d4d4; }
  hr { border: none; border-top: 1px solid #333; margin: 2em 0; }
'''


def process_file(filepath):
    fname = os.path.basename(filepath)
    if fname in SKIP:
        return None

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract search term from <title>Suche: XXX</title>
    title_m = re.search(r'<title>Suche:\s*(.*?)</title>', content)
    if not title_m:
        # Not a standard search result file — skip
        return None
    search_term = title_m.group(1)

    # Extract hit count
    hit_count_m = re.search(r'Treffer in (\d+) Dateien', content)
    hit_count = int(hit_count_m.group(1)) if hit_count_m else 0

    if hit_count == 0:
        # No hits — keep original (nothing to restructure)
        return None

    # Parse hit blocks
    blocks = re.split(r'<div class="hit">', content)[1:]
    hits = []
    for block in blocks:
        a_m = re.search(r'<a\s+href="([^"]*)"[^>]*>(.*?)</a>', block)
        p_m = re.search(r'<span class="pages">\[(.*?)\]</span>', block)
        if not a_m or not p_m:
            continue
        ctxs = re.findall(r'<div class="ctx">(.*?)</div>', block, re.DOTALL)
        hits.append({
            'href': a_m.group(1),
            'display': a_m.group(2),
            'pages': p_m.group(1),
            'contexts': ctxs,
        })

    if not hits:
        return None

    # Classify
    for h in hits:
        h['period'] = detect_exam_period(h['href'], h['display'])
        h['is_loesung'] = is_loesung(h['display'])

    # Group by period
    periods = {}
    for h in hits:
        p = h['period']
        periods.setdefault(p, {'aufgaben': [], 'loesungen': []})
        if h['is_loesung']:
            periods[p]['loesungen'].append(h)
        else:
            periods[p]['aufgaben'].append(h)

    sorted_periods = sorted(periods.keys(), key=period_sort_key)

    # Stats
    total_periods = len(sorted_periods)
    with_loesung = sum(1 for p in sorted_periods if periods[p]['loesungen'])
    total_hits = len(hits)

    # Build HTML
    out = f'''<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>{html_mod.escape(search_term)} &ndash; Aufgabe &amp; L&ouml;sung nach Pr&uuml;fung</title>
<style>{CSS}</style>
</head>
<body>
<h1>{html_mod.escape(search_term)} &ndash; Aufgabe &amp; L&ouml;sung</h1>
<div class="subtitle">
  Alle &bdquo;{html_mod.escape(search_term)}&ldquo;-Treffer aus 150 FIAE-Pr&uuml;fungs-PDFs, gruppiert nach Pr&uuml;fungszeitraum.<br>
  Aufgabe und L&ouml;sung nebeneinander dargestellt.
</div>
<div class="stats">
  <strong>{total_periods}</strong> Pr&uuml;fungszeitr&auml;ume &mdash;
  <strong>{total_hits}</strong> PDFs gesamt &mdash;
  <strong>{with_loesung}</strong> davon mit L&ouml;sung
</div>
<hr>
'''

    # Navigation
    out += '<div class="nav"><strong>Springe zu:</strong> '
    for p in sorted_periods:
        pid = p.replace(' ', '_').replace('/', '_')
        out += f'<a href="#{pid}">{p}</a> '
    out += '</div>\n'

    # Exam sections
    for p in sorted_periods:
        pid = p.replace(' ', '_').replace('/', '_')
        data = periods[p]

        if 'Sommer' in p and 'Winter' not in p:
            badge = '<span class="badge-sommer">Sommer</span>'
        elif 'Winter' in p:
            badge = '<span class="badge-winter">Winter</span>'
        else:
            badge = ''

        out += f'<div class="exam-header" id="{pid}">{badge} {p}</div>\n'
        out += '<div class="exam-row">\n'
        out += build_card(data['aufgaben'], 'Aufgabe')
        out += '\n'
        out += build_card(data['loesungen'], 'Lösung')
        out += '\n</div>\n'

    out += '</body></html>\n'

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(out)

    return (fname, total_periods, total_hits, with_loesung)


# ─── Main ───
if __name__ == '__main__':
    files = sorted(glob.glob(os.path.join(ERGEBNISSE, '*.html')))
    print(f"Gefunden: {len(files)} HTML-Dateien")

    processed = 0
    skipped = 0
    errors = []

    for fpath in files:
        fname = os.path.basename(fpath)
        try:
            result = process_file(fpath)
            if result:
                name, periods, hits, with_l = result
                processed += 1
                if processed <= 10 or processed % 50 == 0:
                    print(f"  ✓ {name}: {periods} Prüfungen, {hits} PDFs, {with_l} mit Lösung")
            else:
                skipped += 1
        except Exception as e:
            errors.append((fname, str(e)))
            print(f"  ✗ {fname}: {e}")

    print(f"\n{'='*60}")
    print(f"Fertig!")
    print(f"  Umstrukturiert: {processed}")
    print(f"  Übersprungen:   {skipped} (0 Treffer / Spezial-Dateien)")
    if errors:
        print(f"  Fehler:         {len(errors)}")
        for name, err in errors:
            print(f"    - {name}: {err}")
