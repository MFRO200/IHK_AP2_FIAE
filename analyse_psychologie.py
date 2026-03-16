#!/usr/bin/env python3
"""
Psychologische Analyse der IHK-Abschlussprüfungen (FIAE AP2)

Analysiert OCR-Text aller Aufgaben-Dokumente nach:
- IHK-Operatoren (Handlungsverben) → Bloom'sche Taxonomie
- Anforderungsbereiche (AFB I–III)
- Kognitive Kompetenzprofile
- Psychologische Aspekte der Aufgabenstellung

Speichert Ergebnisse in der Tabelle `psycho_analyse`.
"""

import json
import re
import psycopg
from collections import Counter, defaultdict
from db_config import DB_URL

# ════════════════════════════════════════════════════════════════════
# IHK-OPERATOREN → Bloom-Taxonomie + Anforderungsbereich
# Basierend auf den offiziellen IHK/KMK-Operatorenlisten
# ════════════════════════════════════════════════════════════════════

OPERATOREN = {
    # ── AFB I: Reproduktion (Bloom: Wissen + Verstehen) ──
    "Nennen":       {"bloom": "wissen",     "afb": 1, "kompetenz": ["faktenwissen"]},
    "Angeben":      {"bloom": "wissen",     "afb": 1, "kompetenz": ["faktenwissen"]},
    "Aufzählen":    {"bloom": "wissen",     "afb": 1, "kompetenz": ["faktenwissen"]},
    "Auflisten":    {"bloom": "wissen",     "afb": 1, "kompetenz": ["faktenwissen"]},
    "Aufführen":    {"bloom": "wissen",     "afb": 1, "kompetenz": ["faktenwissen"]},
    "Wiedergeben":  {"bloom": "wissen",     "afb": 1, "kompetenz": ["faktenwissen"]},
    "Definieren":   {"bloom": "wissen",     "afb": 1, "kompetenz": ["faktenwissen"]},
    "Bezeichnen":   {"bloom": "wissen",     "afb": 1, "kompetenz": ["faktenwissen"]},
    "Beschreiben":  {"bloom": "verstehen",  "afb": 1, "kompetenz": ["verstehen", "kommunikation"]},
    "Darstellen":   {"bloom": "verstehen",  "afb": 1, "kompetenz": ["verstehen", "kommunikation"]},
    "Zusammenfassen": {"bloom": "verstehen","afb": 1, "kompetenz": ["verstehen"]},
    "Skizzieren":   {"bloom": "verstehen",  "afb": 1, "kompetenz": ["verstehen", "visualisierung"]},

    # ── AFB II: Reorganisation / Transfer (Bloom: Anwenden + Analysieren) ──
    "Erläutern":    {"bloom": "anwenden",   "afb": 2, "kompetenz": ["transfer", "kommunikation"]},
    "Erklären":     {"bloom": "anwenden",   "afb": 2, "kompetenz": ["transfer", "kommunikation"]},
    "Ermitteln":    {"bloom": "anwenden",   "afb": 2, "kompetenz": ["analytisch", "problemlösung"]},
    "Bestimmen":    {"bloom": "anwenden",   "afb": 2, "kompetenz": ["analytisch"]},
    "Berechnen":    {"bloom": "anwenden",   "afb": 2, "kompetenz": ["analytisch", "mathematisch"]},
    "Erstellen":    {"bloom": "anwenden",   "afb": 2, "kompetenz": ["kreativ", "handlungskompetenz"]},
    "Zeichnen":     {"bloom": "anwenden",   "afb": 2, "kompetenz": ["visualisierung", "handlungskompetenz"]},
    "Ergänzen":     {"bloom": "anwenden",   "afb": 2, "kompetenz": ["transfer"]},
    "Vervollständigen": {"bloom": "anwenden", "afb": 2, "kompetenz": ["transfer"]},
    "Zuordnen":     {"bloom": "anwenden",   "afb": 2, "kompetenz": ["analytisch"]},
    "Anwenden":     {"bloom": "anwenden",   "afb": 2, "kompetenz": ["transfer", "handlungskompetenz"]},
    "Durchführen":  {"bloom": "anwenden",   "afb": 2, "kompetenz": ["handlungskompetenz"]},
    "Formulieren":  {"bloom": "anwenden",   "afb": 2, "kompetenz": ["kommunikation", "handlungskompetenz"]},
    "Vergleichen":  {"bloom": "analysieren","afb": 2, "kompetenz": ["analytisch", "kritisches_denken"]},
    "Unterscheiden":{"bloom": "analysieren","afb": 2, "kompetenz": ["analytisch", "kritisches_denken"]},
    "Analysieren":  {"bloom": "analysieren","afb": 2, "kompetenz": ["analytisch", "kritisches_denken"]},
    "Gegenüberstellen": {"bloom": "analysieren", "afb": 2, "kompetenz": ["analytisch", "kritisches_denken"]},
    "Einordnen":    {"bloom": "analysieren","afb": 2, "kompetenz": ["analytisch"]},
    "Gliedern":     {"bloom": "analysieren","afb": 2, "kompetenz": ["analytisch", "strukturierung"]},
    "Untersuchen":  {"bloom": "analysieren","afb": 2, "kompetenz": ["analytisch", "problemlösung"]},
    "Überprüfen":   {"bloom": "analysieren","afb": 2, "kompetenz": ["analytisch", "qualitätssicherung"]},
    "Prüfen":       {"bloom": "analysieren","afb": 2, "kompetenz": ["analytisch", "qualitätssicherung"]},
    "Implementieren":{"bloom": "anwenden",  "afb": 2, "kompetenz": ["handlungskompetenz", "kreativ"]},
    "Programmieren":{"bloom": "anwenden",   "afb": 2, "kompetenz": ["handlungskompetenz", "kreativ"]},
    "Codieren":     {"bloom": "anwenden",   "afb": 2, "kompetenz": ["handlungskompetenz"]},
    "Umsetzen":     {"bloom": "anwenden",   "afb": 2, "kompetenz": ["handlungskompetenz", "transfer"]},
    "Wandeln":      {"bloom": "anwenden",   "afb": 2, "kompetenz": ["transfer"]},
    "Umwandeln":    {"bloom": "anwenden",   "afb": 2, "kompetenz": ["transfer"]},
    "Konvertieren": {"bloom": "anwenden",   "afb": 2, "kompetenz": ["transfer"]},

    # ── AFB III: Reflexion / Problemlösung (Bloom: Bewerten + Erschaffen) ──
    "Beurteilen":   {"bloom": "bewerten",   "afb": 3, "kompetenz": ["kritisches_denken", "urteilsvermögen"]},
    "Bewerten":     {"bloom": "bewerten",   "afb": 3, "kompetenz": ["kritisches_denken", "urteilsvermögen"]},
    "Begründen":    {"bloom": "bewerten",   "afb": 3, "kompetenz": ["argumentation", "kritisches_denken"]},
    "Stellungnehmen":{"bloom": "bewerten",  "afb": 3, "kompetenz": ["argumentation", "urteilsvermögen"]},
    "Stellung nehmen":{"bloom": "bewerten", "afb": 3, "kompetenz": ["argumentation", "urteilsvermögen"]},
    "Diskutieren":  {"bloom": "bewerten",   "afb": 3, "kompetenz": ["argumentation", "kommunikation"]},
    "Erörtern":     {"bloom": "bewerten",   "afb": 3, "kompetenz": ["argumentation", "kritisches_denken"]},
    "Entscheiden":  {"bloom": "bewerten",   "afb": 3, "kompetenz": ["entscheidungsfähigkeit", "urteilsvermögen"]},
    "Empfehlen":    {"bloom": "bewerten",   "afb": 3, "kompetenz": ["entscheidungsfähigkeit", "beratungskompetenz"]},
    "Vorschlagen":  {"bloom": "bewerten",   "afb": 3, "kompetenz": ["kreativ", "entscheidungsfähigkeit"]},
    "Entwerfen":    {"bloom": "erschaffen", "afb": 3, "kompetenz": ["kreativ", "systemdenken"]},
    "Entwickeln":   {"bloom": "erschaffen", "afb": 3, "kompetenz": ["kreativ", "problemlösung", "systemdenken"]},
    "Konzipieren":  {"bloom": "erschaffen", "afb": 3, "kompetenz": ["kreativ", "systemdenken"]},
    "Gestalten":    {"bloom": "erschaffen", "afb": 3, "kompetenz": ["kreativ"]},
    "Optimieren":   {"bloom": "erschaffen", "afb": 3, "kompetenz": ["problemlösung", "analytisch"]},
    "Planen":       {"bloom": "erschaffen", "afb": 3, "kompetenz": ["systemdenken", "handlungskompetenz"]},
    "Modellieren":  {"bloom": "erschaffen", "afb": 3, "kompetenz": ["kreativ", "systemdenken", "visualisierung"]},
}

# ════════════════════════════════════════════════════════════════════
# PSYCHOLOGISCHE ASPEKTE der Aufgabentypen
# ════════════════════════════════════════════════════════════════════

THEMEN_PSYCHO = {
    "UML":            {"aspekt": "Abstraktion & Modellierung", "beschreibung": "Fähigkeit, reale Systeme in formale Modelle zu übersetzen. Testet visuell-räumliches Denken und Systemverständnis."},
    "Klassendiagramm":{"aspekt": "Objektorientiertes Denken", "beschreibung": "Erkennung von Vererbung, Komposition und Beziehungen. Testet hierarchisches und strukturelles Denken."},
    "Sequenzdiagramm":{"aspekt": "Prozessverständnis", "beschreibung": "Zeitliche Abfolge von Interaktionen visualisieren. Testet sequenzielles Denken und Kommunikationsverständnis."},
    "Aktivitätsdiagramm": {"aspekt": "Algorithmenverständnis", "beschreibung": "Kontrollfluss und Verzweigungen modellieren. Testet logisches und prozessorientiertes Denken."},
    "ER-Diagramm":    {"aspekt": "Datenmodellierung", "beschreibung": "Entitäten und Beziehungen abstrahieren. Testet analytisches Denken und Normalisierungsverständnis."},
    "SQL":            {"aspekt": "Datenmanipulation", "beschreibung": "Daten abfragen und transformieren. Testet logisches, mengenbasiertes Denken."},
    "Pseudocode":     {"aspekt": "Algorithmisches Denken", "beschreibung": "Abstrakte Problemlösung ohne sprachspezifische Syntax. Testet reines logisches Denken."},
    "Programmierung": {"aspekt": "Implementierungskompetenz", "beschreibung": "Konzepte in funktionierenden Code übersetzen. Testet Präzision und systematisches Denken."},
    "Netzplan":       {"aspekt": "Projektplanung", "beschreibung": "Kritischen Pfad und Abhängigkeiten erkennen. Testet planerische Kompetenz und Zeitmanagement."},
    "Testkonzept":    {"aspekt": "Qualitätssicherung", "beschreibung": "Systematisches Testen planen. Testet methodisches Denken und Fehlersensibilität."},
    "User-Story":     {"aspekt": "Anforderungsanalyse", "beschreibung": "Nutzerperspektive einnehmen und formalisieren. Testet Empathie und Kommunikationsfähigkeit."},
    "Use-Case":       {"aspekt": "Systemabgrenzung", "beschreibung": "Systemgrenzen und Akteure identifizieren. Testet Abstraktionsvermögen."},
    "Datenbank":      {"aspekt": "Datenorganisation", "beschreibung": "Strukturierte Datenhaltung planen. Testet systematisches und normatives Denken."},
    "Normalisierung": {"aspekt": "Redundanzerkennung", "beschreibung": "Anomalien erkennen und beseitigen. Testet analytisches Denken und Regelverständnis."},
    "Verschlüsselung":{"aspekt": "Sicherheitsdenken", "beschreibung": "Schutzmechanismen verstehen. Testet abstraktes und sicherheitsorientiertes Denken."},
    "ACID":           {"aspekt": "Transaktionssicherheit", "beschreibung": "Konsistenzgarantien verstehen. Testet formales und theoretisches Denken."},
    "Vererbung":      {"aspekt": "Hierarchisches Denken", "beschreibung": "Generalisierung und Spezialisierung erkennen. Testet Klassifikationsfähigkeit."},
    "Entwurfsmuster": {"aspekt": "Design Pattern Thinking", "beschreibung": "Bewährte Lösungsmuster erkennen und anwenden. Testet Transferfähigkeit und Erfahrungswissen."},
    "Rekursion":      {"aspekt": "Rekursives Denken", "beschreibung": "Selbstbezügliche Problemlösung. Testet abstraktes und meta-kognitives Denken."},
    "Sortierung":     {"aspekt": "Algorithmische Effizienz", "beschreibung": "Optimale Verfahren bewerten. Testet Effizienzdenken und Vergleichskompetenz."},
    "REST":           {"aspekt": "Schnittstellendenken", "beschreibung": "API-Design und Kommunikation. Testet Abstraktions- und Integrationsfähigkeit."},
    "JSON":           {"aspekt": "Datenaustauschformate", "beschreibung": "Strukturierte Datenrepräsentation. Testet Formatverständnis und Transformationsfähigkeit."},
    "Projektmanagement": {"aspekt": "Organisationskompetenz", "beschreibung": "Projekte planen und steuern. Testet Planungsfähigkeit und Verantwortungsbewusstsein."},
    "Scrum":          {"aspekt": "Agile Methodik", "beschreibung": "Iterative Entwicklung verstehen. Testet Flexibilität und Teamorientierung."},
    "Lastenheft":     {"aspekt": "Anforderungsdokumentation", "beschreibung": "Kundenanforderungen formalisieren. Testet Präzision und Stakeholder-Verständnis."},
    "Pflichtenheft":  {"aspekt": "Lösungsspezifikation", "beschreibung": "Technische Umsetzung spezifizieren. Testet Konkretisierungsfähigkeit."},
}


def find_operators(text: str) -> Counter:
    """Finde IHK-Operatoren im OCR-Text (nur in Aufgabenstellungen, nicht in Fließtext)."""
    ops = Counter()
    # Suche nach Operatoren am Satz-/Zeilenanfang oder nach Aufzählungszeichen
    # Typische Muster: "Nennen Sie...", "a) Beschreiben Sie...", "Erläutern Sie..."
    for op_name in OPERATOREN:
        # Suche nach dem Operator als eigenständiges Wort, typischerweise gefolgt von "Sie"
        patterns = [
            rf'\b{re.escape(op_name)}(?:n)?\s+Sie\b',          # "Nennen Sie", "Beschreiben Sie"
            rf'(?:^|[.!?\n])\s*{re.escape(op_name)}\b',        # Am Satzanfang
            rf'(?:Punkte\s*\n|Punkte\s+)\s*{re.escape(op_name)}\b',  # Nach Punkteangabe
            rf'[a-z]\)\s*{re.escape(op_name)}\b',              # "a) Nennen..."
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            if matches:
                ops[op_name] += len(matches)
                break  # Nur einmal pro Operator-Typ zählen, um Duplikate zu vermeiden
    return ops


def find_themen(text: str) -> list[str]:
    """Finde technische Themen im Aufgabentext."""
    gefunden = []
    text_lower = text.lower()
    
    themen_keywords = {
        "UML": ["uml", "unified modeling"],
        "Klassendiagramm": ["klassendiagramm", "klassen-diagramm"],
        "Sequenzdiagramm": ["sequenzdiagramm", "sequenz-diagramm"],
        "Aktivitätsdiagramm": ["aktivitätsdiagramm", "aktivitatsdiagramm", "aktivitäts-diagramm"],
        "ER-Diagramm": ["er-diagramm", "entity-relationship", "erm ", "er-modell"],
        "SQL": [" sql ", "sql-", "select ", "insert ", "update ", "delete from"],
        "Pseudocode": ["pseudocode", "struktogramm"],
        "Programmierung": ["programmcode", "quellcode", "java ", "python ", "c# ", "programmieren"],
        "Netzplan": ["netzplan", "kritischer pfad", "kritischen pfad", "netzplantechnik"],
        "Testkonzept": ["testkonzept", "testfall", "testfälle", "teststrategie", "unittest"],
        "User-Story": ["user-story", "user story", "userstory"],
        "Use-Case": ["use-case", "use case", "anwendungsfall", "anwendungsfalldiagramm"],
        "Datenbank": ["datenbank", "tabelle", "relational"],
        "Normalisierung": ["normalisierung", "normalform", "1nf", "2nf", "3nf"],
        "Verschlüsselung": ["verschlüsselung", "verschlusselung", "kryptogra", "tls", "ssl", "zertifikat"],
        "ACID": ["acid", "transaktion", "atomicity", "consistency"],
        "Vererbung": ["vererbung", "inheritance", "polymorphi", "abstrakte klasse", "interface"],
        "Entwurfsmuster": ["entwurfsmuster", "design pattern", "singleton", "observer", "factory", "mvc", "mvvm"],
        "Rekursion": ["rekursion", "rekursiv"],
        "Sortierung": ["sortier", "bubblesort", "quicksort", "mergesort", "insertion"],
        "REST": ["rest-api", "restful", "rest api", "http-methode"],
        "JSON": ["json", "javascript object notation"],
        "Projektmanagement": ["projektmanagement", "projektplanung", "meilenstein", "gantt"],
        "Scrum": ["scrum", "sprint", "backlog", "agil"],
        "Lastenheft": ["lastenheft"],
        "Pflichtenheft": ["pflichtenheft"],
    }
    
    for thema, keywords in themen_keywords.items():
        for kw in keywords:
            if kw in text_lower:
                gefunden.append(thema)
                break
    
    return gefunden


def compute_bloom(ops: Counter) -> dict:
    """Berechne Bloom-Stufen-Verteilung aus gefundenen Operatoren."""
    bloom = {"wissen": 0, "verstehen": 0, "anwenden": 0, "analysieren": 0, "bewerten": 0, "erschaffen": 0}
    for op_name, count in ops.items():
        if op_name in OPERATOREN:
            stufe = OPERATOREN[op_name]["bloom"]
            bloom[stufe] += count
    return bloom


def compute_afb(ops: Counter) -> dict:
    """Berechne Anforderungsbereich-Verteilung."""
    afb = {1: 0, 2: 0, 3: 0}
    total = 0
    for op_name, count in ops.items():
        if op_name in OPERATOREN:
            afb[OPERATOREN[op_name]["afb"]] += count
            total += count
    if total > 0:
        return {k: round(v / total * 100, 1) for k, v in afb.items()}
    return {1: 33.3, 2: 33.3, 3: 33.4}


def compute_kompetenz(ops: Counter) -> dict:
    """Berechne Kompetenzprofil."""
    profil = Counter()
    for op_name, count in ops.items():
        if op_name in OPERATOREN:
            for k in OPERATOREN[op_name]["kompetenz"]:
                profil[k] += count
    # Normalisiere auf 0-100
    if profil:
        max_val = max(profil.values())
        return {k: round(v / max_val * 100) for k, v in profil.most_common()}
    return {}


def cognitive_level(afb_pct: dict) -> str:
    """Bestimme kognitiven Gesamtanspruch."""
    if afb_pct[3] >= 30:
        return "hoch"
    elif afb_pct[2] >= 50:
        return "mittel-hoch"
    elif afb_pct[1] >= 50:
        return "niedrig-mittel"
    else:
        return "mittel"


def transfer_distance(themen: list[str]) -> str:
    """Bestimme Transfer-Distanz basierend auf Themenvielfalt."""
    abstrakt = {"Entwurfsmuster", "ACID", "Rekursion", "Normalisierung", "Verschlüsselung"}
    angewandt = {"SQL", "Programmierung", "Netzplan", "JSON"}
    
    has_abstrakt = bool(set(themen) & abstrakt)
    has_angewandt = bool(set(themen) & angewandt)
    
    if has_abstrakt and has_angewandt:
        return "weit"
    elif has_abstrakt:
        return "mittel-weit"
    elif has_angewandt:
        return "nah-mittel"
    return "mittel"


def generate_analyse_text(ops: Counter, bloom: dict, afb_pct: dict, themen: list, bereich: str) -> str:
    """Generiere psychologischen Analysetext."""
    parts = []
    
    total_ops = sum(ops.values())
    if total_ops == 0:
        return f"Für diesen Prüfungsbereich ({bereich}) konnten keine Operatoren aus dem OCR-Text extrahiert werden."
    
    # AFB-Analyse
    dominant_afb = max(afb_pct, key=afb_pct.get)
    afb_names = {1: "Reproduktion (Wissen abrufen)", 2: "Reorganisation & Transfer (Wissen anwenden)", 3: "Reflexion & Problemlösung (bewerten & gestalten)"}
    parts.append(f"Der Schwerpunkt liegt auf Anforderungsbereich {dominant_afb} – {afb_names[dominant_afb]} ({afb_pct[dominant_afb]:.0f}%).")
    
    # Top-Operatoren
    top_ops = ops.most_common(3)
    if top_ops:
        op_text = ", ".join(f'"{o}" ({c}×)' for o, c in top_ops)
        parts.append(f"Häufigste Operatoren: {op_text}.")
    
    # Bloom-Analyse
    bloom_max = max(bloom, key=bloom.get)
    bloom_names = {
        "wissen": "reines Faktenwissen abgefragt",
        "verstehen": "Verständnis und Zusammenhänge geprüft",
        "anwenden": "praktische Anwendung gefordert",
        "analysieren": "analytisches Denken gefordert",
        "bewerten": "kritische Beurteilung erwartet",
        "erschaffen": "eigenständige Lösungsentwicklung gefordert",
    }
    parts.append(f"Nach Bloom wird primär {bloom_names.get(bloom_max, bloom_max)}.")
    
    # Themen-Analyse
    if themen:
        psycho_aspekte = []
        for t in themen[:5]:
            if t in THEMEN_PSYCHO:
                psycho_aspekte.append(f"{t} ({THEMEN_PSYCHO[t]['aspekt']})")
        if psycho_aspekte:
            parts.append(f"Getestete kognitive Fähigkeiten durch: {', '.join(psycho_aspekte)}.")
    
    # Psychologische Strategie
    if afb_pct[1] >= 40:
        parts.append("⚡ Psychologische Strategie: Hoher Reproduktionsanteil belohnt systematisches Auswendiglernen und schafft eine 'sichere Basis' für Prüflinge – typische AKA-Strategie zur Normalverteilung.")
    if afb_pct[3] >= 25:
        parts.append("🧠 Psychologische Strategie: Signifikanter Reflexionsanteil differenziert zwischen 'gut' und 'sehr gut' – nur wer Zusammenhänge wirklich versteht, kann hier Punkte holen.")
    if afb_pct[2] >= 45:
        parts.append("🔄 Psychologische Strategie: Hoher Transferanteil testet, ob Prüflinge erlerntes Wissen auf neue Situationen übertragen können – die Kernkompetenz eines Fachinformatikers.")
    
    return " ".join(parts)


def generate_schwerpunkte(ops: Counter, themen: list, bereich: str) -> list[str]:
    """Bestimme Hauptschwerpunkte der Klausur."""
    schwerpunkte = []
    
    # Aus Top-Operatoren
    for op, count in ops.most_common(2):
        if op in OPERATOREN:
            afb = OPERATOREN[op]["afb"]
            schwerpunkte.append(f"AFB {afb}: {op}")
    
    # Aus Themen
    for t in themen[:3]:
        if t in THEMEN_PSYCHO:
            schwerpunkte.append(THEMEN_PSYCHO[t]["aspekt"])
    
    return schwerpunkte[:5]


def main():
    conn = psycopg.connect(DB_URL)
    cur = conn.cursor()
    
    # Alle Aufgaben-Dokumente mit OCR-Text laden
    cur.execute("""
        SELECT d.id, d.pruefung_id, d.pruefungsbereich, d.dateiname,
               STRING_AGG(s.ocr_text, E'\n' ORDER BY s.seiten_nr) as full_text
        FROM dokumente d
        JOIN seiten s ON s.dokument_id = d.id
        WHERE d.typ = 'Aufgabe'
          AND d.pruefungsbereich IS NOT NULL
          AND d.pruefung_id IS NOT NULL
        GROUP BY d.id, d.pruefung_id, d.pruefungsbereich, d.dateiname
        ORDER BY d.pruefung_id, d.pruefungsbereich
    """)
    
    docs = cur.fetchall()
    print(f"[INFO] {len(docs)} Aufgaben-Dokumente zum Analysieren")
    
    # Gruppiere nach pruefung_id + pruefungsbereich (ein Dokument kann mehrere Versionen haben)
    gruppen = defaultdict(list)
    for doc_id, pruefung_id, bereich, dateiname, full_text in docs:
        gruppen[(pruefung_id, bereich)].append((doc_id, dateiname, full_text or ""))
    
    print(f"[INFO] {len(gruppen)} Pruefung x Bereich-Kombinationen")
    
    # Alte Analysen löschen
    cur.execute("DELETE FROM psycho_analyse")
    
    inserted = 0
    for (pruefung_id, bereich), doc_list in sorted(gruppen.items()):
        # Texte zusammenführen (bei mehreren Versionen des gleichen Dokuments)
        combined_text = "\n".join(text for _, _, text in doc_list)
        
        if len(combined_text.strip()) < 100:
            continue  # Zu wenig Text
        
        # Analyse
        ops = find_operators(combined_text)
        themen = find_themen(combined_text)
        bloom = compute_bloom(ops)
        afb_pct = compute_afb(ops)
        kompetenz = compute_kompetenz(ops)
        kog_level = cognitive_level(afb_pct)
        trans_dist = transfer_distance(themen)
        analyse_text = generate_analyse_text(ops, bloom, afb_pct, themen, bereich)
        schwerpunkte = generate_schwerpunkte(ops, themen, bereich)
        
        cur.execute("""
            INSERT INTO psycho_analyse (
                pruefung_id, pruefungsbereich,
                bloom_wissen, bloom_verstehen, bloom_anwenden, bloom_analysieren, bloom_bewerten, bloom_erschaffen,
                operatoren, kompetenz_profil,
                afb1_prozent, afb2_prozent, afb3_prozent,
                kognitiver_anspruch, transfer_distanz, analyse_text, schwerpunkte
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (pruefung_id, pruefungsbereich) DO UPDATE SET
                bloom_wissen = EXCLUDED.bloom_wissen,
                bloom_verstehen = EXCLUDED.bloom_verstehen,
                bloom_anwenden = EXCLUDED.bloom_anwenden,
                bloom_analysieren = EXCLUDED.bloom_analysieren,
                bloom_bewerten = EXCLUDED.bloom_bewerten,
                bloom_erschaffen = EXCLUDED.bloom_erschaffen,
                operatoren = EXCLUDED.operatoren,
                kompetenz_profil = EXCLUDED.kompetenz_profil,
                afb1_prozent = EXCLUDED.afb1_prozent,
                afb2_prozent = EXCLUDED.afb2_prozent,
                afb3_prozent = EXCLUDED.afb3_prozent,
                kognitiver_anspruch = EXCLUDED.kognitiver_anspruch,
                transfer_distanz = EXCLUDED.transfer_distanz,
                analyse_text = EXCLUDED.analyse_text,
                schwerpunkte = EXCLUDED.schwerpunkte
        """, (
            pruefung_id, bereich,
            bloom["wissen"], bloom["verstehen"], bloom["anwenden"],
            bloom["analysieren"], bloom["bewerten"], bloom["erschaffen"],
            json.dumps(dict(ops), ensure_ascii=False),
            json.dumps(kompetenz, ensure_ascii=False),
            afb_pct[1], afb_pct[2], afb_pct[3],
            kog_level, trans_dist, analyse_text, schwerpunkte,
        ))
        inserted += 1
        
        dateiname = doc_list[0][1]
        total_ops = sum(ops.values())
        print(f"  [OK] {bereich:5s} | {dateiname[:50]:50s} | {total_ops:3d} Operatoren | AFB: {afb_pct[1]:.0f}/{afb_pct[2]:.0f}/{afb_pct[3]:.0f}")
    
    conn.commit()
    conn.close()
    
    print(f"\n[DONE] {inserted} Analysen in DB gespeichert")


if __name__ == "__main__":
    main()
