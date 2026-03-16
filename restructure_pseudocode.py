#!/usr/bin/env python3
"""
Liest Pseudocode.html, gruppiert Treffer nach Prüfungszeitraum,
stellt Aufgabe + Lösung nebeneinander dar.
"""
import re, os
from urllib.parse import unquote

HTML_IN  = 'Ergebnisse/Pseudocode.html'
HTML_OUT = 'Ergebnisse/Pseudocode_new.html'  # Erstmal separat

with open(HTML_IN, 'r', encoding='utf-8') as f:
    content = f.read()

# ─── Parse all hit blocks ───
# Split by <div class="hit"> to get each block
hits = []
raw_blocks = re.split(r'<div class="hit">', content)[1:]  # skip before first hit
for block in raw_blocks:
    # Find the end: after all nested </div> tags
    a_m = re.search(r'<a\s+href="([^"]*)"[^>]*>(.*?)</a>', block)
    p_m = re.search(r'<span class="pages">\[(.*?)\]</span>', block)
    if not a_m or not p_m:
        continue
    href = a_m.group(1)
    display = a_m.group(2)
    pages = p_m.group(1)
    ctxs = re.findall(r'<div class="ctx">(.*?)</div>', block, re.DOTALL)

    hits.append({
        'href': href,
        'display': display,
        'pages': pages,
        'contexts': ctxs,
    })

print(f"Hits geparst: {len(hits)}")


# ─── Detect exam period ───
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
        # Fallback: check filename for year patterns
        # GH1-Fian.pdf in /2008/ -> this is Winter 2008_09's GH1
        # Check if there's a season in the filename
        w_match = re.search(r'[Ww](\d{4})', display)
        s_match = re.search(r'[Ss](\d{4})', display)
        if w_match:
            return f"Winter {year}"
        if s_match:
            return f"Sommer {year}"
        return f"Sommer/Winter {year}"

    return "Unbekannt"


def is_loesung(display):
    return bool(re.search(r'[Ll]ösu|[Ll]osu|[Ll]öser|[Ll]oser', display))


# ─── Classify ───
for h in hits:
    h['period'] = detect_exam_period(h['href'], h['display'])
    h['is_loesung'] = is_loesung(h['display'])

# ─── Group by period ───
periods = {}
for h in hits:
    p = h['period']
    periods.setdefault(p, {'aufgaben': [], 'loesungen': []})
    if h['is_loesung']:
        periods[p]['loesungen'].append(h)
    else:
        periods[p]['aufgaben'].append(h)


# ─── Sort periods chronologically ───
def period_sort_key(p):
    """Sommer 2018 -> (2018, 0), Winter 2018_19 -> (2018, 1)"""
    m = re.match(r'(Sommer|Winter|Sommer/Winter)\s+(\d{4})', p)
    if m:
        season = m.group(1)
        year = int(m.group(2))
        s = 0 if 'Sommer' in season and 'Winter' not in season else 1
        return (year, s)
    return (9999, 0)

sorted_periods = sorted(periods.keys(), key=period_sort_key)


# ─── Build hit card HTML ───
def build_card(hit_list, label):
    if not hit_list:
        return f'<div class="card card-empty"><div class="card-label">{label}</div><p class="no-data">Keine {label} vorhanden</p></div>'

    html = f'<div class="card"><div class="card-label">{label}</div>'
    for h in hit_list:
        html += f'<div class="pdf-entry">'
        html += f'<a href="{h["href"]}" target="_blank">{h["display"]}</a>'
        html += f' <span class="pages">[{h["pages"]}]</span>'
        for ctx in h['contexts']:
            html += f'<div class="ctx">{ctx}</div>'
        html += '</div>'
    html += '</div>'
    return html


# ─── Generate new HTML ───
new_html = '''<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>Pseudocode &ndash; Aufgabe &amp; L&ouml;sung nach Pr&uuml;fung</title>
<style>
  body {
    font-family: Segoe UI, Arial, sans-serif;
    margin: 2em;
    background: #1e1e1e;
    color: #d4d4d4;
  }
  h1 { color: #569cd6; margin-bottom: 0.3em; }
  .subtitle { color: #808080; margin-bottom: 1.5em; font-size: 0.95em; }

  /* Prüfungs-Header */
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

  /* Side-by-side Layout */
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

  /* Cards */
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

  /* PDF entries */
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

  /* Navigation */
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
</style>
</head>
<body>
<h1>Pseudocode &ndash; Aufgabe &amp; L&ouml;sung</h1>
<div class="subtitle">
  Alle Pseudocode-Treffer aus 150 FIAE-Pr&uuml;fungs-PDFs, gruppiert nach Pr&uuml;fungszeitraum.<br>
  Aufgabe und L&ouml;sung nebeneinander dargestellt.
</div>
'''

# Stats
total_periods = len(sorted_periods)
with_loesung = sum(1 for p in sorted_periods if periods[p]['loesungen'])
total_hits = len(hits)

new_html += f'''<div class="stats">
  <strong>{total_periods}</strong> Pr&uuml;fungszeitr&auml;ume mit Pseudocode-Treffern &mdash;
  <strong>{total_hits}</strong> PDFs gesamt &mdash;
  <strong>{with_loesung}</strong> davon mit L&ouml;sung
</div>
<hr>
'''

# Navigation
new_html += '<div class="nav"><strong>Springe zu:</strong> '
for p in sorted_periods:
    pid = p.replace(' ', '_').replace('/', '_')
    new_html += f'<a href="#{pid}">{p}</a> '
new_html += '</div>\n'

# Exam sections
for p in sorted_periods:
    pid = p.replace(' ', '_').replace('/', '_')
    data = periods[p]

    # Badge
    if 'Sommer' in p and 'Winter' not in p:
        badge = '<span class="badge-sommer">Sommer</span>'
    elif 'Winter' in p:
        badge = '<span class="badge-winter">Winter</span>'
    else:
        badge = ''

    year_match = re.search(r'(\d{4}(?:_\d{2,4})?)', p)
    year_display = year_match.group(1) if year_match else p

    new_html += f'<div class="exam-header" id="{pid}">{badge} {p}</div>\n'
    new_html += '<div class="exam-row">\n'
    new_html += build_card(data['aufgaben'], 'Aufgabe')
    new_html += build_card(data['loesungen'], 'Lösung')
    new_html += '</div>\n'

new_html += '</body></html>\n'

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(new_html)

print(f"\n✓ {HTML_OUT} neu generiert!")
print(f"  {total_periods} Prüfungen, {total_hits} PDFs, {with_loesung} mit Lösung")
