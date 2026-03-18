/* ── Typen passend zur NestJS-API / Prisma-Schema ── */

export interface Pruefung {
  id: number
  jahr: number
  semester: string
  zeitraum_label: string
  ordner_name: string
  dokumente?: Dokument[]
}

export interface Dokument {
  id: number
  pruefung_id: number
  dateiname: string
  pfad: string
  typ: string
  pruefungsbereich: string | null
  dateigroesse: number
  seitenanzahl: number
  created_at: string
  seiten?: Seite[]
  treffer?: Treffer[]
  pruefung?: Pruefung
  versionen?: DokumentVersion[]
}

export interface DokumentVersion {
  id: number
  dokument_id: number
  version_nr: number
  label: string
  dateiname: string
  storage_pfad: string
  dateigroesse: number | null
  kommentar: string | null
  erstellt_am: string
}

export interface Seite {
  id: number
  dokument_id: number
  seiten_nr: number
  ocr_text: string
}

export interface Suchbegriff {
  id: number
  begriff: string
  section: string
  themenblock: string | null
  treffer_anzahl: number
}

export interface Treffer {
  id: number
  suchbegriff_id: number
  dokument_id: number
  seiten: string | null
  kontext: string | null
  suchbegriff?: Suchbegriff
  dokument?: Dokument
}

export interface TrefferStat {
  section: string
  begriffe: number | string
  treffer: number | string
}

export interface TrefferStatPruefung {
  pruefung_id: number
  zeitraum_label: string
  jahr: number
  semester: string
  section: string
  begriffe: number
  treffer: number
}

export interface ThemenblockStat {
  themenblock: string
  begriffe: number
  treffer: number
}

export interface PruefungsbereichStat {
  pruefungsbereich: string
  dokumente: number
  seiten: number
  treffer: number
  begriffe: number
}

export interface AntwortBild {
  id: number
  antwort_id: number
  dateiname: string
  storage_pfad: string
  dateigroesse: number | null
  sortierung: number
  erstellt_am: string
}

export interface MeinBild extends AntwortBild {
  aufgabe: string
  durchlauf: number
  antwort_text: string
  punkte: number | null
  max_punkte: number | null
  pruefung_id: number
  zeitraum_label: string
}

export interface Antwort {
  id: number
  pruefung_id: number
  aufgabe: string
  antwort_text: string
  notiz: string | null
  punkte: number | null
  max_punkte: number | null
  durchlauf: number
  dauer_sekunden: number | null
  erstellt_am: string
  updated_am: string
  bilder?: AntwortBild[]
}

export interface DurchlaufStat {
  durchlauf: number
  aufgaben: number
  richtig: number
  falsch: number
  offen: number
  summe_punkte: number
  summe_max: number
  dauer_sekunden: number | null
  datum: string
}

export interface AntwortStat {
  pruefung_id: number
  zeitraum_label: string
  aufgaben: number
  mit_punkte: number
  summe_punkte: number
  summe_max: number
}

export interface BearbeitungsStatus {
  pruefung_id: number
  pruefungsbereich: string
  durchlaeufe: number
  ausgewertet: boolean
  letzte_bearbeitung: string
}

export interface VolltextResult {
  seiten_id: number
  dokument_id: number
  seiten_nr: number
  dateiname: string
  zeitraum_label: string
  typ: string
  headline: string
  rank: number
}

/* ── Psychologische Analyse ── */
export interface PsychoAnalyse {
  id: number
  pruefung_id: number
  pruefungsbereich: string
  bloom_wissen: number
  bloom_verstehen: number
  bloom_anwenden: number
  bloom_analysieren: number
  bloom_bewerten: number
  bloom_erschaffen: number
  operatoren: Record<string, number>
  kompetenz_profil: Record<string, number>
  afb1_prozent: number
  afb2_prozent: number
  afb3_prozent: number
  kognitiver_anspruch: string | null
  transfer_distanz: string | null
  analyse_text: string | null
  schwerpunkte: string[]
  erstellt_am: string
  pruefung: {
    id: number
    zeitraum_label: string
    jahr: number
    semester: string
  }
}

export interface PsychoStatistik {
  anzahl_analysen: number
  bloom_durchschnitt: Record<string, number>
  afb_durchschnitt: Record<string, number>
  top_operatoren: { operator: string; count: number }[]
  details: PsychoAnalyse[]
}

/* ── Trainingsplan ── */
export interface TrainingsPrognose {
  afb1: number
  afb2: number
  afb3: number
  anspruch: string
  topThemen: string[]
}

export interface TrainingsEmpfehlung {
  kategorie: string
  prioritaet: 'hoch' | 'mittel' | 'niedrig'
  titel: string
  beschreibung: string
  uebungen: string[]
}

export interface TrainingsErgebnis {
  pruefung_id: number
  zeitraum_label: string
  punkte: number
  max_punkte: number
  prozent: number
}

export interface SchwacheAufgabe {
  pruefung_id: number
  pruefung: string
  aufgabe: string
  bereich: string
  punkte: number
  max_punkte: number
  prozent: number
  deine_antwort?: string
  korrekte_antwort?: string
  hinweis?: string
}

export interface Trainingsplan {
  prognose: Record<string, TrainingsPrognose>
  topOperatoren: { operator: string; count: number }[]
  ergebnisse: TrainingsErgebnis[]
  schwacheAufgaben: SchwacheAufgabe[]
  empfehlungen: TrainingsEmpfehlung[]
  gesamtErgebnis: {
    pruefungenBearbeitet: number
    durchschnittProzent: number
    schwaechen: number
  }
}

/* ── LLM-Bewertung ── */
export interface Bewertung {
  id: number
  antwort_id: number
  punkte: number | null
  max_punkte: number | null
  feedback: string | null
  bewertung_details: {
    korrekte_aspekte?: string[]
    fehlende_aspekte?: string[]
    loesungsvorschlag?: string | null
    konfidenz?: number
    [key: string]: unknown
  }
  llm_provider: string
  llm_model: string
  prompt_tokens: number | null
  completion_tokens: number | null
  dauer_ms: number | null
  erstellt_am: string
  antwort?: { aufgabe: string; antwort_text: string }
}

export interface Musterloesung {
  id: number
  pruefung_id: number
  aufgabe: string
  erwartung_text: string
  max_punkte: number | null
  hinweise: string | null
}

export interface BewertungResult {
  punkte: number
  max_punkte: number
  feedback: string
  details: Record<string, unknown>
  provider: string
  model: string
  prompt_tokens?: number
  completion_tokens?: number
  dauer_ms: number
}

export interface BewertungPruefungResult {
  pruefung_id: number
  bewertet: number
  fehler: number
  ergebnisse: Array<{ aufgabe: string; punkte: number; feedback: string }>
}

export interface ProviderStatus {
  available: boolean
  models?: string[]
  error?: string
}