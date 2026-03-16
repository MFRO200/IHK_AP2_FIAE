"""
Adds IHK Punkte section and links to individual HTML result files
throughout Score-Tabelle.html.
"""
import os, re
import html as html_mod

DIR = 'Ergebnisse'
FILE = os.path.join(DIR, 'Score-Tabelle.html')

# ===== PUNKTE DATA =====
punkte_data = [
    ("Pseudocode", 317),
    ("SQL", 200),
    ("SELECT", 155),
    ("Relationales Datenmodell", 141),
    ("Aktivitätsdiagramm", 130),
    ("Klassendiagramm", 79),
    ("ERM", 68),
    ("Sequenzdiagramm", 64),
    ("Zustandsdiagramm", 61),
    ("Objektorientierung", 50),
    ("Use-Case-Diagramm", 46),
    ("Code Coverage", 39),
    ("INSERT", 35),
    ("Vorgehensmodelle", 31),
    ("Schreibtischtest", 28),
    ("Design Patterns", 27),
    ("DELETE", 25),
    ("Mockups", 25),
    ("Stakeholder", 25),
    ("Usability", 25),
    ("Observer", 21),
    ("Verschlüsselung", 21),
    ("Anforderungsanalyse", 20),
    ("XML", 19),
    ("Englisch", 18),
    ("UPDATE", 18),
    ("Dokumentenorientierte Datenbank", 17),
    ("Polymorphie", 17),
    ("Sortieralgorithmen", 17),
    ("Change Management", 16),
    ("Prozessanalyse", 16),
    ("Risikoanalyse", 16),
    ("Tabellenkalkulation", 16),
    ("Unit-Tests", 15),
    ("JSON", 14),
    ("Zertifikate", 14),
    ("Softwarequalität", 13),
    ("Fehler finden", 12),
    ("Projektmanagement", 12),
    ("Ticketsystem", 12),
    ("UNION", 12),
    ("User-Stories", 12),
    ("E-Mail-Sicherheit", 11),
    ("UI-Design", 11),
    ("Qualitätssicherung", 10),
    ("Sicherheitsanforderungen", 10),
    ("Aggregation", 9),
    ("Anomalien", 9),
    ("Datenqualität", 9),
    ("IoT", 9),
    ("Open-Source", 9),
    ("SAN", 9),
    ("Testkonzept", 9),
    ("Barrierefreiheit", 8),
    ("Black-Box-Test", 8),
    ("Machbarkeitsanalyse", 8),
    ("Self-Service", 8),
    ("Transaktionen", 8),
    ("User Experience", 8),
    ("White-Box-Test", 8),
    ("Dateigrößen berechnen", 7),
    ("Funktionale Programmierung", 7),
    ("CI/CD", 6),
    ("Compiler", 6),
    ("CRUD", 6),
    ("Dokumentation", 6),
    ("Ethernet", 6),
    ("HTTP-Methoden", 6),
    ("Interpreter", 6),
    ("KI", 6),
    ("Prototyping", 6),
    ("Schichtenarchitektur", 6),
    ("Single-Sign-On", 6),
    ("Struktogramm", 6),
    ("Umfeldanalyse", 6),
    ("Workshop", 6),
    ("Code-Reviews", 5),
    ("HTTP-Statuscodes", 5),
    ("Änderbarkeit", 4),
    ("Äquivalenzklassen", 4),
    ("Datenimport", 4),
    ("Datenschutz", 4),
    ("Digitale Signatur", 4),
    ("Effizienz", 4),
    ("Fremdvergabe", 4),
    ("Green IT", 4),
    ("Klassenbibliothek", 4),
    ("Kostenarten", 4),
    ("OAuth", 4),
    ("Protokoll anfertigen", 4),
    ("Regressionstests", 4),
    ("Rekursion", 4),
    ("Schwachstellenanalyse", 4),
    ("Versionsverwaltung", 4),
    ("CREATE INDEX", 3),
    ("CREATE TABLE", 3),
    ("Datentypen", 3),
    ("Generische Klassen", 3),
    ("GRANT", 3),
    ("Hashverfahren", 3),
    ("HTTP-Request", 3),
    ("Komposition", 3),
    ("MAC", 3),
    ("REVOKE", 3),
    ("Endpoint-Security", 2),
    ("Fehlerbehandlung", 2),
    ("Index", 2),
    ("Redundanz", 2),
    ("REST", 2),
    ("Stored Procedures", 2),
    ("Testverfahren", 2),
    ("Trigger", 2),
]

# ===== GET AVAILABLE HTML FILES =====
available = {}
for f in os.listdir(DIR):
    if f.endswith('.html') and f != 'Score-Tabelle.html':
        name = f[:-5]
        available[name] = f
available_lower = {k.lower(): v for k, v in available.items()}

# Manual mappings for terms that don't match filenames directly
MANUAL_MAP = {
    '3-Schichten-Architektur': '3-Schichten.html',
    '3-Schichten': '3-Schichten.html',
    'Single Sign-On': 'Single Sign.html',
    'Schreibtischtest': 'Schreibtischtest.html',
    'Code Coverage': 'Anweisungsüberdeckung.html',
    'Relationales Datenmodell': 'Relationales Datenmodell.html',
    'Use-Case-Diagramm': 'Use-Case-Diagramm.html',
    'Objektorientierung': 'objektorientiert.html',
    'ERM': 'ER-Diagramm.html',
    'Design Patterns': 'Entwurfsmuster.html',
    'Mockups': 'Mock.html',
    'Dokumentenorientierte Datenbank': 'dokumentenorientiert.html',
    'Unit-Tests': 'Unit-Test.html',
    'Anomalien': 'Anomalie.html',
    'Zertifikate': 'Zertifikat.html',
    'Sortieralgorithmen': 'Sortieralgorithmus.html',
    'Regressionstests': 'Regressionstest.html',
    'Black-Box-Test': 'Blackbox.html',
    'White-Box-Test': 'Whitebox.html',
    'Vorgehensmodelle': 'Vorgehensmodell.html',
    'Single-Sign-On': 'Single Sign.html',
    'CI/CD': 'Continuous.html',
    'Prototyping': 'Prototyp.html',
    'Schichtenarchitektur': '3-Schichten.html',
    'Datentypen': 'Datentyp.html',
    'Generische Klassen': 'generisch.html',
    'MAC': 'MAC-Adresse.html',
    'HTTP-Methoden': 'HTTP.html',
    'HTTP-Statuscodes': 'Statuscode.html',
    'HTTP-Request': 'HTTP.html',
    'Code-Reviews': 'Review.html',
    'Benutzerschnittstelle (GUI)': 'Benutzerschnittstelle.html',
    'Entität / Entitätstyp': None,  # handled by split
    'Klassenbibliothek': 'Klassenbibliothek.html',
    'Handbuch / Dokumentation': None,  # handled by split
    'Continuous (CI/CD)': 'Continuous.html',
    'User Experience (UX)': 'User Experience.html',
}


def find_file(term):
    """Find HTML file for a term."""
    # Decode HTML entities
    decoded = html_mod.unescape(term)
    if decoded != term:
        return find_file(decoded)
    # Manual mapping
    if term in MANUAL_MAP:
        return MANUAL_MAP[term]
    # Direct match
    if term in available:
        return available[term]
    # Case-insensitive
    if term.lower() in available_lower:
        return available_lower[term.lower()]
    # German de-pluralization: try removing common endings
    for ending in ['en', 'n', 'e', 's']:
        if term.endswith(ending) and len(term) > len(ending) + 3:
            base = term[:-len(ending)]
            f = available.get(base) or available_lower.get(base.lower())
            if f:
                return f
    return None


def make_link(display_text, filename):
    return f'<a href="{filename}">{display_text}</a>'


def link_term(term):
    """Create linked HTML for a term. Returns linked or original text."""
    if '<a ' in term:
        return term

    # Direct match or manual map
    f = find_file(term)
    if f:
        return make_link(term, f)

    # Split by " / "
    if ' / ' in term:
        parts = term.split(' / ')
        results = []
        found = False
        for part in parts:
            part = part.strip()
            # Remove parenthetical for file lookup
            clean = re.sub(r'\s*\([^)]*\)\s*$', '', part).strip()
            pf = find_file(part)
            if not pf and clean != part:
                pf = find_file(clean)
            if pf:
                results.append(make_link(part, pf))
                found = True
            else:
                results.append(part)
        if found:
            return ' / '.join(results)

    # Remove parenthetical at end
    clean = re.sub(r'\s*\([^)]*\)\s*$', '', term).strip()
    if clean != term:
        f = find_file(clean)
        if f:
            return make_link(term, f)

    return term


# ===== READ FILE =====
with open(FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# ===== 1. ADD NAV LINK =====
nav_marker = '<a href="#webdev">Webentwicklung</a>'
if nav_marker in content and '#punkte' not in content:
    content = content.replace(
        nav_marker,
        nav_marker + '\n  <a href="#punkte">IHK-Punkteverteilung</a>',
        1
    )
    print("[OK] Nav link for Punkte added")

# ===== 2. BUILD PUNKTE SECTION =====
lines = []
lines.append('')
lines.append('<hr>')
lines.append('<h2 id="punkte">IHK-Punkteverteilung nach Thema</h2>')
lines.append('<p class="note">')
lines.append('  Summierte Punkte aller Prüfungsaufgaben, die ein Thema abdecken (Quelle: IHK-Prüfungsauswertung).<br>')
lines.append('  <strong>Achtung:</strong> Häufiges Vorkommen (Score&nbsp;A) bedeutet nicht automatisch viele Punkte &mdash; und umgekehrt!')
lines.append('</p>')
lines.append('<table>')
lines.append('  <tr><th>Thema</th><th class="treffer">Punkte gesamt</th></tr>')

for thema, pts in punkte_data:
    linked = link_term(thema)
    if pts >= 50:
        style = ' style="color:#f44747; font-weight:bold"'
    elif pts >= 20:
        style = ' style="color:#dcdcaa"'
    elif pts >= 10:
        style = ''
    else:
        style = ' style="color:#808080"'
    lines.append(f'  <tr><td>{linked}</td><td class="treffer"{style}>{pts}</td></tr>')

lines.append('</table>')
punkte_section = '\n'.join(lines)

# Insert before Score A section
if 'id="punkte"' not in content:
    idx = content.index('id="score-a"')
    preceding = content.rfind('<!-- ==', 0, idx)
    content = content[:preceding] + punkte_section + '\n\n' + content[preceding:]
    print("[OK] Punkte section inserted")

# ===== 3. ADD LINKS TO ALL <tr><td>TERM</td> PATTERNS =====
link_count = 0
unmatched = set()


def replacer(m):
    global link_count
    term = m.group(1).strip()

    # Skip if already contains a link
    if '<a ' in term:
        return m.group(0)

    linked = link_term(term)
    if linked != term:
        link_count += 1
        return f'<tr><td>{linked}</td>'

    unmatched.add(term)
    return m.group(0)


content = re.sub(r'<tr><td>([^<]+?)</td>', replacer, content)

# ===== 4. WRITE =====
with open(FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\n[OK] Links added: {link_count}")
print(f"Unmatched terms ({len(unmatched)}):")
for t in sorted(unmatched):
    print(f"  - {t}")
