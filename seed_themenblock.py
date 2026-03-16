#!/usr/bin/env python
"""
Parst die Score-Tabelle.html und weist jedem Suchbegriff in der DB
seinen primären Themenblock zu (aus dem Abschnitt 'Übersicht nach Themenblock').
"""

import os
import re
import html as html_mod
import psycopg2
from db_config import DB_CONF as DB_CFG

SCORE_TABLE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'Ergebnisse', 'Score-Tabelle.html',
)


def parse_themenblock_mapping():
    """
    Returns dict: { begriff_name_lower: themenblock_title }
    Uses the FIRST Themenblock where a term appears (primary mapping).
    """
    with open(SCORE_TABLE, 'r', encoding='utf-8') as f:
        content = f.read()

    themen_start = content.find('id="themen"')
    if themen_start < 0:
        print('FEHLER: id="themen" nicht gefunden in Score-Tabelle.html')
        return {}

    area = content[themen_start:]

    blocks = re.split(r'<h3[^>]*>', area)[1:]  # skip text before first h3
    h3_titles = re.findall(r'<h3[^>]*>(.*?)</h3>', area)

    mapping = {}  # begriff_lower -> themenblock

    for raw_title, block in zip(h3_titles, blocks):
        title = html_mod.unescape(re.sub(r'<[^>]+>', '', raw_title)).strip()

        # Extract all table rows: <tr><td>...</td>
        rows = re.findall(r'<tr><td>(.*?)</td>', block)
        for row in rows:
            term = html_mod.unescape(re.sub(r'<[^>]+>', '', row)).strip()
            if not term or term == 'Begriff':
                continue

            # Handle combined terms like "DDL / DML" or "Blackbox / Whitebox"
            sub_terms = [t.strip() for t in re.split(r'\s*/\s*', term)]
            for st in sub_terms:
                key = st.lower()
                if key not in mapping:
                    mapping[key] = title

    return mapping


def update_db(mapping):
    """Update themenblock for all suchbegriffe in DB."""
    conn = psycopg2.connect(**DB_CFG)
    cur = conn.cursor()

    # Get all suchbegriffe
    cur.execute("SELECT id, begriff FROM suchbegriffe")
    rows = cur.fetchall()

    updated = 0
    not_found = 0

    for sid, begriff in rows:
        key = begriff.strip().lower()
        themenblock = mapping.get(key)

        if not themenblock:
            # Try partial: some DB terms might be substrings or have different forms
            # e.g. "JOIN (alle Typen)" in Score-Tabelle vs "JOIN" in DB
            for mk, mv in mapping.items():
                if mk in key or key in mk:
                    themenblock = mv
                    break

        if themenblock:
            cur.execute(
                "UPDATE suchbegriffe SET themenblock = %s WHERE id = %s",
                (themenblock, sid),
            )
            updated += 1
        else:
            not_found += 1

    conn.commit()
    print(f"Themenblock zugewiesen: {updated} Begriffe")
    print(f"Kein Themenblock gefunden: {not_found} Begriffe")

    # Show stats
    cur.execute("""
        SELECT themenblock, COUNT(*) as cnt
        FROM suchbegriffe
        WHERE themenblock IS NOT NULL
        GROUP BY themenblock
        ORDER BY cnt DESC
    """)
    print("\nThemenblöcke in DB:")
    for tb, cnt in cur.fetchall():
        print(f"  {tb}: {cnt} Begriffe")

    cur.execute("SELECT COUNT(*) FROM suchbegriffe WHERE themenblock IS NULL")
    null_cnt = cur.fetchone()[0]
    print(f"\n  (ohne Themenblock: {null_cnt})")

    cur.close()
    conn.close()


if __name__ == '__main__':
    print(f"Lese Score-Tabelle: {SCORE_TABLE}")
    mapping = parse_themenblock_mapping()
    print(f"Geparst: {len(mapping)} eindeutige Begriffe aus Themenblöcken")
    update_db(mapping)
