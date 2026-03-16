#!/usr/bin/env python3
"""
Sortiert alle Begriffe in Score A/B/C/D nach den aktuellen FIAE-Trefferzahlen neu ein.
    A: >= 10 Treffer
    B: 4-9 Treffer
    C: 1-3 Treffer
    D: 0 Treffer (nie geprüft)
Innerhalb jeder Sektion: absteigend nach Trefferzahl.
"""
import re, shutil

FILE = 'Ergebnisse/Score-Tabelle.html'

# ─── Backup ───
shutil.copy2(FILE, FILE + '.backup_vor_resort')

with open(FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# ─── Section boundaries ───
sec_ids = ['score-a', 'score-b', 'score-c', 'score-d']
boundaries = {}
for sid in sec_ids:
    boundaries[sid] = content.find(f'id="{sid}"')
themen = content.find('id="themen"')


def parse_rows(block):
    """Extract all data <tr> rows from a section block."""
    rows = []
    for m in re.finditer(r'  (<tr><td>.*?</tr>)', block):
        row_html = m.group(1)
        tds = re.findall(r'<td[^>]*>(.*?)</td>', row_html)
        rows.append({'html': row_html, 'tds': tds})
    return rows


def parse_treffer(raw):
    """Parse treffer string into numeric value for sorting."""
    v = raw.strip()
    if 'viele' in v.lower():
        return 9999
    if '/' in v:
        return sum(int(x) for x in re.findall(r'\d+', v))
    if '+' in v:
        return int(v.replace('+', ''))
    if v.startswith('~'):
        return int(v.replace('~', ''))
    try:
        return int(v)
    except ValueError:
        return 0


# ─── Parse all sections ───
a_block = content[boundaries['score-a']:boundaries['score-b']]
b_block = content[boundaries['score-b']:boundaries['score-c']]
c_block = content[boundaries['score-c']:boundaries['score-d']]
d_block = content[boundaries['score-d']:themen]

abc_rows = []
for block, old_sec in [(a_block, 'A'), (b_block, 'B'), (c_block, 'C')]:
    for row in parse_rows(block):
        term_html = row['tds'][0]
        treffer_raw = row['tds'][1]
        bemerkung = row['tds'][2] if len(row['tds']) >= 3 else ''
        treffer_num = parse_treffer(treffer_raw)
        abc_rows.append({
            'term_html': term_html,
            'treffer_raw': treffer_raw,
            'treffer_num': treffer_num,
            'bemerkung': bemerkung,
            'old_sec': old_sec,
            'row_html': row['html']
        })

d_existing = parse_rows(d_block)

print(f"Geparst: A/B/C = {len(abc_rows)}, D = {len(d_existing)}")

# ─── Classify ───
new_a = []
new_b = []
new_c = []
new_d_from_abc = []

moves = {}

for r in abc_rows:
    n = r['treffer_num']
    if n >= 10:
        new_sec = 'A'
        new_a.append(r)
    elif n >= 4:
        new_sec = 'B'
        new_b.append(r)
    elif n >= 1:
        new_sec = 'C'
        new_c.append(r)
    else:
        new_sec = 'D'
        new_d_from_abc.append(r)

    if r['old_sec'] != new_sec:
        key = f"{r['old_sec']}->{new_sec}"
        term_clean = re.sub(r'<[^>]+>', '', r['term_html']).strip()
        moves.setdefault(key, []).append(f"{term_clean} ({r['treffer_raw']})")

# Sort each section descending by treffer
new_a.sort(key=lambda x: x['treffer_num'], reverse=True)
new_b.sort(key=lambda x: x['treffer_num'], reverse=True)
new_c.sort(key=lambda x: x['treffer_num'], reverse=True)

print(f"\nVerschiebungen:")
for key in sorted(moves):
    print(f"  {key}: {len(moves[key])} Begriffe")
    for item in moves[key]:
        print(f"    {item}")

print(f"\nNeue Verteilung: A={len(new_a)}, B={len(new_b)}, C={len(new_c)}, "
      f"D={len(d_existing) + len(new_d_from_abc)}")

# ─── Build new table rows ───
def build_abc_row(r):
    """Build a 3-column row for A/B/C sections."""
    return f'  <tr><td>{r["term_html"]}</td><td class="treffer">{r["treffer_raw"]}</td><td>{r["bemerkung"]}</td></tr>'


def build_d_row_from_abc(r):
    """Build a 2-column row for D section from an A/B/C term."""
    return f'  <tr><td>{r["term_html"]}</td><td>{r["bemerkung"]} &mdash; <em>0 Treffer in FIAE</em></td></tr>'


# ─── Replace section contents ───
# Strategy: find the <table>...</table> within each section and replace its rows

def replace_section_rows(content, sec_id, next_marker, new_rows_html, header_row):
    """Replace all data rows in a section's table."""
    sec_start = content.find(f'id="{sec_id}"')
    sec_end = content.find(next_marker, sec_start + 1) if next_marker else content.find('id="themen"', sec_start + 1)

    block = content[sec_start:sec_end]

    # Find table
    table_start = block.find('<table>')
    table_end = block.find('</table>') + len('</table>')
    old_table = block[table_start:table_end]

    # Build new table
    new_table = '<table>\n'
    new_table += f'  {header_row}\n'
    for row in new_rows_html:
        new_table += row + '\n'
    new_table += '</table>'

    new_block = block[:table_start] + new_table + block[table_end:]
    return content[:sec_start] + new_block + content[sec_end:]


abc_header = '<tr><th>Begriff</th><th class="treffer">Treffer</th><th>Typische Aufgabenstellung / Kontext</th></tr>'
bc_header = '<tr><th>Begriff</th><th class="treffer">Treffer</th><th>Bemerkung</th></tr>'
d_header = '<tr><th>Begriff</th><th>Themenblock</th></tr>'

# Build row HTML
a_html = [build_abc_row(r) for r in new_a]
b_html = [build_abc_row(r) for r in new_b]
c_html = [build_abc_row(r) for r in new_c]

# D: existing rows + new from ABC
d_existing_html = [r['html'] for r in d_existing]
d_new_html = [build_d_row_from_abc(r) for r in new_d_from_abc]
d_all_html = d_existing_html + d_new_html

# Apply replacements (reverse order to preserve positions)
content = replace_section_rows(content, 'score-d', None, d_all_html, d_header)
content = replace_section_rows(content, 'score-c', 'id="score-d"', c_html, bc_header)
content = replace_section_rows(content, 'score-b', 'id="score-c"', b_html, bc_header)
content = replace_section_rows(content, 'score-a', 'id="score-b"', a_html, abc_header)

# ─── Update section descriptions ───
# Update subtitle with new counts
# Update Basis info too
old_basis = re.search(r'(Basis:.*?152 PDFs.*?Anwendungsentwicklung)', content)
if old_basis:
    print(f"\nBasis bleibt: {old_basis.group(1)[:80]}...")

# Update D note
old_d_note = '198 analysierten Prüfungen'
if old_d_note in content:
    content = content.replace(old_d_note, '152 analysierten FIAE-Prüfungen')

with open(FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\n✓ Score-Tabelle neu sortiert und gespeichert!")
print(f"  Backup: {FILE}.backup_vor_resort")
