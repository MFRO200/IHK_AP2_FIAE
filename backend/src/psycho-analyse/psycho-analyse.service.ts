import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Injectable()
export class PsychoAnalyseService {
  constructor(private readonly prisma: PrismaService) {}

  /** Alle Analysen mit Prüfungs-Info */
  findAll() {
    return this.prisma.psycho_analyse.findMany({
      include: {
        pruefung: {
          select: { id: true, zeitraum_label: true, jahr: true, semester: true },
        },
      },
      orderBy: [
        { pruefung: { jahr: 'desc' } },
        { pruefung: { semester: 'desc' } },
        { pruefungsbereich: 'asc' },
      ],
    });
  }

  /** Analysen für eine bestimmte Prüfung */
  findByPruefung(pruefungId: number) {
    return this.prisma.psycho_analyse.findMany({
      where: { pruefung_id: pruefungId },
      include: {
        pruefung: {
          select: { id: true, zeitraum_label: true, jahr: true, semester: true },
        },
      },
      orderBy: { pruefungsbereich: 'asc' },
    });
  }

  /** Einzelne Analyse */
  findOne(id: number) {
    return this.prisma.psycho_analyse.findUniqueOrThrow({
      where: { id },
      include: {
        pruefung: {
          select: { id: true, zeitraum_label: true, jahr: true, semester: true },
        },
      },
    });
  }

  /** Aggregierte Statistik über alle Prüfungen */
  async statistik() {
    const all = await this.prisma.psycho_analyse.findMany({
      select: {
        pruefungsbereich: true,
        bloom_wissen: true,
        bloom_verstehen: true,
        bloom_anwenden: true,
        bloom_analysieren: true,
        bloom_bewerten: true,
        bloom_erschaffen: true,
        afb1_prozent: true,
        afb2_prozent: true,
        afb3_prozent: true,
        operatoren: true,
        kompetenz_profil: true,
        kognitiver_anspruch: true,
        pruefung: {
          select: { jahr: true, semester: true, zeitraum_label: true },
        },
      },
      orderBy: [{ pruefung: { jahr: 'asc' } }, { pruefung: { semester: 'asc' } }],
    });

    // Aggregiere Bloom-Werte über alle Prüfungen
    const bloomGesamt = { wissen: 0, verstehen: 0, anwenden: 0, analysieren: 0, bewerten: 0, erschaffen: 0 };
    const afbGesamt = { afb1: 0, afb2: 0, afb3: 0 };
    const operatorenGesamt: Record<string, number> = {};

    for (const a of all) {
      bloomGesamt.wissen += a.bloom_wissen;
      bloomGesamt.verstehen += a.bloom_verstehen;
      bloomGesamt.anwenden += a.bloom_anwenden;
      bloomGesamt.analysieren += a.bloom_analysieren;
      bloomGesamt.bewerten += a.bloom_bewerten;
      bloomGesamt.erschaffen += a.bloom_erschaffen;

      afbGesamt.afb1 += Number(a.afb1_prozent);
      afbGesamt.afb2 += Number(a.afb2_prozent);
      afbGesamt.afb3 += Number(a.afb3_prozent);

      const ops = a.operatoren as Record<string, number>;
      for (const [op, count] of Object.entries(ops)) {
        operatorenGesamt[op] = (operatorenGesamt[op] || 0) + count;
      }
    }

    const n = all.length || 1;
    return {
      anzahl_analysen: all.length,
      bloom_durchschnitt: {
        wissen: Math.round(bloomGesamt.wissen / n * 10) / 10,
        verstehen: Math.round(bloomGesamt.verstehen / n * 10) / 10,
        anwenden: Math.round(bloomGesamt.anwenden / n * 10) / 10,
        analysieren: Math.round(bloomGesamt.analysieren / n * 10) / 10,
        bewerten: Math.round(bloomGesamt.bewerten / n * 10) / 10,
        erschaffen: Math.round(bloomGesamt.erschaffen / n * 10) / 10,
      },
      afb_durchschnitt: {
        afb1: Math.round(afbGesamt.afb1 / n * 10) / 10,
        afb2: Math.round(afbGesamt.afb2 / n * 10) / 10,
        afb3: Math.round(afbGesamt.afb3 / n * 10) / 10,
      },
      top_operatoren: Object.entries(operatorenGesamt)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 15)
        .map(([op, count]) => ({ operator: op, count })),
      details: all,
    };
  }

  /**
   * Trainingsplan: Kombiniert Prüfungs-Analysen mit Nutzer-Ergebnissen,
   * erkennt Schwächen und gibt gezielte Empfehlungen.
   */
  async trainingsplan() {
    // 1) Alle psycho-Analysen (Trends)
    const analysen = await this.prisma.psycho_analyse.findMany({
      include: {
        pruefung: { select: { id: true, zeitraum_label: true, jahr: true, semester: true } },
      },
      orderBy: [{ pruefung: { jahr: 'desc' } }, { pruefung: { semester: 'desc' } }],
    });

    // 2) Alle Antworten des Nutzers (nur neuester Durchlauf pro Prüfung+Aufgabe)
    const antworten = await this.prisma.$queryRaw<Array<{
      pruefung_id: number;
      zeitraum_label: string;
      aufgabe: string;
      punkte: number | null;
      max_punkte: number | null;
      durchlauf: number;
      antwort_text: string | null;
      erwartung_text: string | null;
      ml_hinweise: string | null;
      ki_feedback: string | null;
    }>>`
      SELECT a.pruefung_id, p.zeitraum_label, a.aufgabe,
             a.punkte::float, a.max_punkte::float, a.durchlauf,
             a.antwort_text,
             m.erwartung_text,
             m.hinweise AS ml_hinweise,
             bw.feedback AS ki_feedback
      FROM antworten a
      JOIN pruefungen p ON a.pruefung_id = p.id
      JOIN (
        SELECT pruefung_id, aufgabe, MAX(durchlauf) AS max_dl
        FROM antworten
        WHERE durchlauf >= 1
          AND aufgabe NOT LIKE 'BEREICH_%'
          AND aufgabe NOT LIKE 'KEY_%'
        GROUP BY pruefung_id, aufgabe
      ) latest ON a.pruefung_id = latest.pruefung_id
                AND a.aufgabe = latest.aufgabe
                AND a.durchlauf = latest.max_dl
      LEFT JOIN musterloesungen m
        ON a.pruefung_id = m.pruefung_id AND a.aufgabe = m.aufgabe
      LEFT JOIN LATERAL (
        SELECT b.feedback FROM bewertungen b
        WHERE b.antwort_id = a.id
        ORDER BY b.erstellt_am DESC NULLS LAST
        LIMIT 1
      ) bw ON true
      ORDER BY p.zeitraum_label, a.aufgabe
    `;

    // 3) Themen-Treffer: Welche Suchbegriffe kommen in welchen Prüfungen vor?
    const themenTreffer = await this.prisma.$queryRaw<Array<{
      themenblock: string;
      pruefungsbereich: string;
      treffer: number;
    }>>`
      SELECT sb.themenblock, d.pruefungsbereich,
             COUNT(*)::int AS treffer
      FROM treffer t
      JOIN suchbegriffe sb ON t.suchbegriff_id = sb.id
      JOIN dokumente d ON t.dokument_id = d.id
      WHERE sb.themenblock IS NOT NULL
        AND d.pruefungsbereich IS NOT NULL
      GROUP BY sb.themenblock, d.pruefungsbereich
      ORDER BY treffer DESC
    `;

    // ── Berechne Schwächen aus Antworten ──
    // Gruppiere nach Prüfung und berechne Prozent
    const pruefungErgebnisse: Record<string, { punkte: number; max: number; label: string }> = {};
    for (const a of antworten) {
      const key = String(a.pruefung_id);
      if (!pruefungErgebnisse[key]) {
        pruefungErgebnisse[key] = { punkte: 0, max: 0, label: a.zeitraum_label };
      }
      if (a.punkte != null) pruefungErgebnisse[key].punkte += a.punkte;
      if (a.max_punkte != null) pruefungErgebnisse[key].max += a.max_punkte;
    }

    // Aufgaben-Level Schwächen (wo punkte/max_punkte < 50%)
    const schwacheAufgaben = antworten
      .filter((a) => a.punkte != null && a.max_punkte != null && a.max_punkte > 0 && a.punkte / a.max_punkte < 0.5)
      .map((a) => {
        // Bereich-Erkennung: GA2_-Prefix → GA2, rein numerisch/dezimal → WISO, sonst GA1
        let bereich = 'GA1';
        if (a.aufgabe.startsWith('GA2_')) {
          bereich = 'GA2';
        } else if (/^\d+(\.\d+)?$/.test(a.aufgabe)) {
          bereich = 'WISO';
        }

        // Hinweis zusammenbauen: KI-Feedback bevorzugen, dann Musterlösung + Hinweise
        const teile: string[] = [];
        if (a.ki_feedback) {
          teile.push(a.ki_feedback);
        }
        if (a.erwartung_text) {
          teile.push('📋 Erwartete Lösung: ' + a.erwartung_text);
        }
        if (a.ml_hinweise) {
          teile.push('💡 Hinweis: ' + a.ml_hinweise);
        }

        return {
          pruefung_id: a.pruefung_id,
          pruefung: a.zeitraum_label,
          aufgabe: a.aufgabe.replace(/^GA2_/, ''),
          bereich,
          punkte: a.punkte,
          max_punkte: a.max_punkte,
          prozent: Math.round((a.punkte! / a.max_punkte!) * 100),
          deine_antwort: a.antwort_text || '',
          korrekte_antwort: a.erwartung_text || '',
          hinweis: teile.join('\n\n') || 'Keine Hinweise verfügbar – versuche die KI-Bewertung für diese Aufgabe zu nutzen.',
        };
      });

    // ── Trend-Prognose für Sommer 2026 ──
    // Berechne AFB-Durchschnitte der letzten 4 Prüfungen pro Bereich
    const recentByBereich: Record<string, Array<{ afb1: number; afb2: number; afb3: number; anspruch: string | null }>> = {};
    for (const a of analysen) {
      if (a.pruefung.jahr >= 2022) {
        const b = a.pruefungsbereich;
        if (!recentByBereich[b]) recentByBereich[b] = [];
        recentByBereich[b].push({
          afb1: Number(a.afb1_prozent),
          afb2: Number(a.afb2_prozent),
          afb3: Number(a.afb3_prozent),
          anspruch: a.kognitiver_anspruch,
        });
      }
    }

    const prognose: Record<string, { afb1: number; afb2: number; afb3: number; anspruch: string; topThemen: string[] }> = {};
    for (const [bereich, entries] of Object.entries(recentByBereich)) {
      const n = entries.length || 1;
      const avg1 = Math.round(entries.reduce((s, e) => s + e.afb1, 0) / n);
      const avg2 = Math.round(entries.reduce((s, e) => s + e.afb2, 0) / n);
      const avg3 = Math.round(entries.reduce((s, e) => s + e.afb3, 0) / n);

      // Anspruch-Trend
      const anspruchCounts: Record<string, number> = {};
      for (const e of entries) {
        if (e.anspruch) anspruchCounts[e.anspruch] = (anspruchCounts[e.anspruch] || 0) + 1;
      }
      const topAnspruch = Object.entries(anspruchCounts).sort((a, b) => b[1] - a[1])[0]?.[0] || 'mittel-hoch';

      // Top-Themen für diesen Bereich
      const topThemen = themenTreffer
        .filter((t) => t.pruefungsbereich === bereich)
        .slice(0, 5)
        .map((t) => t.themenblock);

      prognose[bereich] = { afb1: avg1, afb2: avg2, afb3: avg3, anspruch: topAnspruch, topThemen };
    }

    // ── Operatoren-Trend (letzte 3 Jahre) ──
    const opTrend: Record<string, number> = {};
    for (const a of analysen) {
      if (a.pruefung.jahr >= 2022 && ['GA1', 'GA2'].includes(a.pruefungsbereich)) {
        const ops = a.operatoren as Record<string, number>;
        for (const [op, count] of Object.entries(ops)) {
          opTrend[op] = (opTrend[op] || 0) + count;
        }
      }
    }
    const topOperatoren = Object.entries(opTrend)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([op, count]) => ({ operator: op, count }));

    // ── Trainingsempfehlungen generieren ──
    const empfehlungen: Array<{ kategorie: string; prioritaet: 'hoch' | 'mittel' | 'niedrig'; titel: string; beschreibung: string; uebungen: string[] }> = [];

    // ── Schwächen-Themen erkennen ──
    // 1) Klassifiziere schwache Aufgaben nach Bereich (Format + Antwort-Inhalt)
    const schwachThemen = new Set<string>();
    const schwachBereichCount: Record<string, number> = {};

    for (const s of schwacheAufgaben) {
      const aufgabe = s.aufgabe;
      const isWiso = /^\d+$/.test(aufgabe); // Rein numerisch = WISO (Multiple-Choice 1-30)

      if (isWiso) {
        schwachThemen.add('WISO');
        schwachBereichCount['WISO'] = (schwachBereichCount['WISO'] || 0) + 1;
      } else {
        // GA1/GA2 Aufgaben: Scan Antwortinhalt nach Themen-Keywords
        const antwort = antworten.find((a) => a.aufgabe === aufgabe && a.zeitraum_label === s.pruefung);
        const text = (antwort?.aufgabe || '').toLowerCase() + ' ' + (s.aufgabe || '').toLowerCase();

        // Versuche aus Musterloesungen/Antworttext Themen zu extrahieren
        const aufgabeLower = aufgabe.toLowerCase();
        if (aufgabeLower.includes('sql') || aufgabeLower.includes('datenbank') || aufgabeLower.includes('db')) {
          schwachThemen.add('SQL & Datenbanken');
        } else if (aufgabeLower.includes('uml') || aufgabeLower.includes('klasse') || aufgabeLower.includes('diagramm') || aufgabeLower.includes('sequenz')) {
          schwachThemen.add('UML-Diagramme');
        } else if (aufgabeLower.includes('netz') || aufgabeLower.includes('projekt') || aufgabeLower.includes('plan')) {
          schwachThemen.add('Projektmanagement');
        } else if (aufgabeLower.includes('code') || aufgabeLower.includes('pseudo') || aufgabeLower.includes('program') || aufgabeLower.includes('algo')) {
          schwachThemen.add('Programmierung');
        } else if (aufgabeLower.includes('test') || aufgabeLower.includes('qualit')) {
          schwachThemen.add('Testen & QS');
        } else if (aufgabeLower.includes('scrum') || aufgabeLower.includes('agil')) {
          schwachThemen.add('Agile Methoden');
        } else if (aufgabeLower.includes('er') || aufgabeLower.includes('normal')) {
          schwachThemen.add('Datenmodellierung');
        } else {
          // Fallback: als allgemeine GA-Schwäche zählen
          schwachThemen.add('GA-Aufgaben (allgemein)');
        }
        schwachBereichCount['GA'] = (schwachBereichCount['GA'] || 0) + 1;
      }
    }

    // Empfehlungen basierend auf Prognose
    if (prognose['GA1']) {
      const ga1 = prognose['GA1'];
      empfehlungen.push({
        kategorie: 'GA1',
        prioritaet: 'hoch',
        titel: 'GA1 – Fachliche Analyse & Entwurf',
        beschreibung: `Erwarteter Schwerpunkt: AFB II (${ga1.afb2}%) mit Anspruch "${ga1.anspruch}". Fokus auf Erstellen, Erläutern und Beschreiben.`,
        uebungen: [
          'UML-Klassendiagramme aus Ausgangssituation erstellen',
          'Sequenzdiagramme für Systeminteraktionen zeichnen',
          'ER-Diagramme entwerfen und normalisieren',
          'Pseudocode für Algorithmen schreiben',
          'Netzpläne berechnen (kritischer Pfad, Pufferzeiten)',
        ],
      });
    }
    if (prognose['GA2']) {
      const ga2 = prognose['GA2'];
      empfehlungen.push({
        kategorie: 'GA2',
        prioritaet: 'hoch',
        titel: 'GA2 – Praktische Umsetzung',
        beschreibung: `Erwarteter Schwerpunkt: AFB II (${ga2.afb2}%) mit "${ga2.anspruch}". Hauptoperator: Erstellen & Implementieren.`,
        uebungen: [
          'SQL-Abfragen (JOINs, Subqueries, GROUP BY) üben',
          'Datenbankschema aus Text-Beschreibung erstellen',
          'Code ergänzen/vervollständigen (Pseudocode/Java)',
          'Testfälle aus Anforderungen ableiten',
          'REST-API-Endpunkte entwerfen und beschreiben',
        ],
      });
    }
    if (prognose['WISO']) {
      const wiso = prognose['WISO'];
      empfehlungen.push({
        kategorie: 'WISO',
        prioritaet: 'mittel',
        titel: 'WISO – Wirtschafts- und Sozialkunde',
        beschreibung: `Trend: ${wiso.afb3}% AFB III (Beurteilen). Multiple-Choice mit Begründung. Anspruch: "${wiso.anspruch}".`,
        uebungen: [
          'Vertragsarten und Kündigungsfristen lernen',
          'Gehaltsabrechnungen berechnen (brutto/netto)',
          'Gesellschaftsformen vergleichen',
          'Datenschutz (DSGVO) und IT-Sicherheit',
          'Arbeitsrecht Fallbeispiele bearbeiten',
        ],
      });
    }

    // Schwächen-basierte Empfehlungen
    for (const thema of schwachThemen) {
      const uebungen: Record<string, string[]> = {
        'SQL & Datenbanken': ['SELECT mit JOIN und Aggregatfunktionen üben', 'Subqueries und Views erstellen', 'INSERT/UPDATE/DELETE Statements sicher beherrschen'],
        'UML-Diagramme': ['Klassendiagramme mit Beziehungen (1:n, m:n) zeichnen', 'Sequenzdiagramme aus Use-Cases ableiten', 'Aktivitätsdiagramme für Geschäftsprozesse erstellen'],
        'Projektmanagement': ['Netzpläne mit FAZ/FEZ/SAZ/SEZ berechnen', 'Gantt-Diagramme erstellen', 'Kritischen Pfad bestimmen'],
        'Programmierung': ['Schleifen, Bedingungen, Rekursion in Pseudocode', 'Sortieralgorithmen implementieren', 'Entwurfsmuster (MVC, Observer) anwenden'],
        'WISO': [
          `${schwachBereichCount['WISO'] || 0} WISO-Aufgaben falsch beantwortet – Multiple-Choice der letzten 5 Jahre durcharbeiten`,
          'Wirtschaftsrechnen (Dreisatz, Prozent) üben',
          'Vertragsrecht und BGB-Grundlagen wiederholen',
          'Arbeitsrecht (Kündigungsfristen, Betriebsrat) lernen',
          'Gesellschaftsformen und Unternehmensrecht vergleichen',
        ],
        'Testen & QS': ['Black-Box vs. White-Box Testverfahren unterscheiden', 'Testfälle aus Äquivalenzklassen ableiten', 'Grenzwertanalyse anwenden'],
        'Agile Methoden': ['Scrum-Rollen und Artefakte lernen', 'Sprint Planning vs. Sprint Review unterscheiden', 'User Stories formulieren (INVEST-Kriterien)'],
        'Datenmodellierung': ['ER-Modell → Relationales Modell übersetzen', 'Normalformen (1NF-3NF) bestimmen und herstellen', 'Anomalien erkennen und beheben'],
        'GA-Aufgaben (allgemein)': ['Aufgaben der letzten 5 Prüfungen gezielt wiederholen', 'Schwache Bereiche identifizieren und gezielt üben', 'Operatoren-Verständnis vertiefen (Erstellen, Erläutern, Beschreiben)'],
      };

      const anzahl = thema === 'WISO' ? (schwachBereichCount['WISO'] || 0) : (schwachBereichCount['GA'] || 0);

      empfehlungen.push({
        kategorie: 'Schwäche',
        prioritaet: 'hoch',
        titel: `Schwäche: ${thema}`,
        beschreibung: `${anzahl} Aufgabe(n) in bisherigen Prüfungen unter 50% erreicht. Gezieltes Training empfohlen.`,
        uebungen: uebungen[thema] || [`${thema}-Aufgaben der letzten 5 Prüfungen wiederholen`],
      });
    }

    // Ergebnisse gruppiert
    const ergebnisListe = Object.entries(pruefungErgebnisse).map(([id, e]) => ({
      pruefung_id: Number(id),
      zeitraum_label: e.label,
      punkte: e.punkte,
      max_punkte: e.max,
      prozent: e.max > 0 ? Math.round((e.punkte / e.max) * 100) : 0,
    })).sort((a, b) => a.zeitraum_label.localeCompare(b.zeitraum_label));

    return {
      prognose,
      topOperatoren,
      ergebnisse: ergebnisListe,
      schwacheAufgaben: schwacheAufgaben.slice(0, 50),
      empfehlungen,
      gesamtErgebnis: {
        pruefungenBearbeitet: ergebnisListe.length,
        durchschnittProzent: ergebnisListe.length > 0
          ? Math.round(ergebnisListe.reduce((s, e) => s + e.prozent, 0) / ergebnisListe.length)
          : 0,
        schwaechen: schwacheAufgaben.length,
      },
    };
  }
}
