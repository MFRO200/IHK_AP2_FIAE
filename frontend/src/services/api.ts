import axios from 'axios'
import type {
  Pruefung,
  Dokument,
  DokumentVersion,
  Suchbegriff,
  Treffer,
  TrefferStat,
  TrefferStatPruefung,
  ThemenblockStat,
  PruefungsbereichStat,
  Antwort,
  AntwortBild,
  MeinBild,
  AntwortStat,
  BearbeitungsStatus,
  DurchlaufStat,
  VolltextResult,
  PsychoAnalyse,
  PsychoStatistik,
  Trainingsplan,
  Bewertung,
  BewertungResult,
  BewertungPruefungResult,
  ProviderStatus,
  Musterloesung,
} from '@/types'

const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

/* ── Prüfungen ── */
export const pruefungenApi = {
  getAll: () => api.get<Pruefung[]>('/pruefungen').then((r) => r.data),
  getById: (id: number) =>
    api.get<Pruefung>(`/pruefungen/${id}`).then((r) => r.data),
  create: (data: { jahr: number; semester: string; zeitraum_label: string; ordner_name: string }) =>
    api.post<Pruefung>('/pruefungen', data).then((r) => r.data),
}

/* ── Dokumente ── */
export const dokumenteApi = {
  getAll: (params?: { pruefungId?: number; typ?: string; pruefungsbereich?: string }) =>
    api.get<Dokument[]>('/dokumente', { params }).then((r) => r.data),
  getById: (id: number) =>
    api.get<Dokument>(`/dokumente/${id}`).then((r) => r.data),
  upload: (file: File, pruefung_id: number, typ: string, pruefungsbereich?: string) => {
    const form = new FormData()
    form.append('file', file)
    form.append('pruefung_id', String(pruefung_id))
    form.append('typ', typ)
    if (pruefungsbereich) form.append('pruefungsbereich', pruefungsbereich)
    return api.post<Dokument>('/dokumente/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000,
    }).then((r) => r.data)
  },
  update: (id: number, data: { pruefung_id?: number; typ?: string; pruefungsbereich?: string }) =>
    api.put<Dokument>(`/dokumente/${id}`, data).then((r) => r.data),
  remove: (id: number) =>
    api.delete(`/dokumente/${id}`).then((r) => r.data),
  extractAnswers: (id: number) =>
    api.get<{ answers: Record<string, string>; count: number; source: string }>(`/dokumente/${id}/extract-answers`).then((r) => r.data),
}

/* ── Suchbegriffe ── */
export const suchbegriffeApi = {
  getAll: (params?: { section?: string; search?: string }) =>
    api.get<Suchbegriff[]>('/suchbegriffe', { params }).then((r) => r.data),
  getById: (id: number) =>
    api.get<Suchbegriff>(`/suchbegriffe/${id}`).then((r) => r.data),
}

/* ── Versionen ── */
export const versionenApi = {
  getAll: (dokumentId: number) =>
    api.get<DokumentVersion[]>(`/dokumente/${dokumentId}/versionen`).then((r) => r.data),
  upload: (dokumentId: number, file: File, label?: string, kommentar?: string) => {
    const form = new FormData()
    form.append('file', file)
    if (label) form.append('label', label)
    if (kommentar) form.append('kommentar', kommentar)
    return api.post<DokumentVersion>(`/dokumente/${dokumentId}/versionen/upload`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data)
  },
  delete: (dokumentId: number, versionId: number) =>
    api.delete(`/dokumente/${dokumentId}/versionen/${versionId}`).then((r) => r.data),
}

/* ── Treffer ── */
export const trefferApi = {
  getAll: (params?: { suchbegriffId?: number; dokumentId?: number }) =>
    api.get<Treffer[]>('/treffer', { params }).then((r) => r.data),
  getStats: () =>
    api.get<TrefferStat[]>('/treffer/stats').then((r) => r.data),
  getStatsPerPruefung: () =>
    api.get<TrefferStatPruefung[]>('/treffer/stats/pruefungen').then((r) => r.data),
  getStatsPerThemenblock: () =>
    api.get<ThemenblockStat[]>('/treffer/stats/themenblock').then((r) => r.data),
  getStatsPerPruefungsbereich: () =>
    api.get<PruefungsbereichStat[]>('/treffer/stats/pruefungsbereich').then((r) => r.data),
}

/* ── Volltext-Suche ── */
export const seitenApi = {
  search: (q: string) =>
    api.get<VolltextResult[]>('/seiten/search', { params: { q } }).then((r) => r.data),
}

/* ── Antworten (eigene Lösungen) ── */
export const antwortenApi = {
  getByPruefung: (pruefungId: number, durchlauf?: number) =>
    api.get<Antwort[]>(`/antworten/pruefung/${pruefungId}`, { params: durchlauf != null ? { durchlauf } : {} }).then((r) => r.data),
  getDurchlaeufe: (pruefungId: number) =>
    api.get<DurchlaufStat[]>(`/antworten/pruefung/${pruefungId}/durchlaeufe`).then((r) => r.data),
  getStats: () =>
    api.get<AntwortStat[]>('/antworten/stats').then((r) => r.data),
  getBearbeitungsStatus: () =>
    api.get<BearbeitungsStatus[]>('/antworten/bearbeitungsstatus').then((r) => r.data),
  upsert: (data: { pruefung_id: number; aufgabe: string; antwort_text: string; notiz?: string; punkte?: number; max_punkte?: number; durchlauf?: number; dauer_sekunden?: number }) =>
    api.post<Antwort>('/antworten', data).then((r) => r.data),
  update: (id: number, data: Partial<Antwort>) =>
    api.put<Antwort>(`/antworten/${id}`, data).then((r) => r.data),
  remove: (id: number) =>
    api.delete(`/antworten/${id}`).then((r) => r.data),
  /* Bilder */
  getBilder: (antwortId: number) =>
    api.get<AntwortBild[]>(`/antworten/${antwortId}/bilder`).then((r) => r.data),
  uploadBild: (antwortId: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post<AntwortBild>(`/antworten/${antwortId}/bilder`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000,
    }).then((r) => r.data)
  },
  deleteBild: (antwortId: number, bildId: number) =>
    api.delete(`/antworten/${antwortId}/bilder/${bildId}`).then((r) => r.data),
  bildUrl: (antwortId: number, bildId: number) =>
    `/api/antworten/${antwortId}/bilder/${bildId}/file`,
  getAllBilder: () =>
    api.get<MeinBild[]>('/antworten/alle-bilder').then((r) => r.data),
}

/* ── Psychologische Analyse ── */
export const psychoApi = {
  getAll: () =>
    api.get<PsychoAnalyse[]>('/psycho-analyse').then((r) => r.data),
  getStatistik: () =>
    api.get<PsychoStatistik>('/psycho-analyse/statistik').then((r) => r.data),
  getTrainingsplan: () =>
    api.get<Trainingsplan>('/psycho-analyse/trainingsplan').then((r) => r.data),
  getByPruefung: (pruefungId: number) =>
    api.get<PsychoAnalyse[]>(`/psycho-analyse/pruefung/${pruefungId}`).then((r) => r.data),
  getOne: (id: number) =>
    api.get<PsychoAnalyse>(`/psycho-analyse/${id}`).then((r) => r.data),
}

/* ── LLM-Bewertung ── */
export const bewertungApi = {
  /** Einzelne Antwort bewerten */
  bewerten: (antwortId: number, provider: 'ollama' | 'openai', model?: string, image?: string) =>
    api.post<BewertungResult>('/bewertung/bewerten', { antwortId, provider, model, image }, { timeout: 120000 }).then((r) => r.data),

  /** Alle offenen Antworten einer Prüfung bewerten */
  bewertenPruefung: (pruefungId: number, provider: 'ollama' | 'openai', model?: string) =>
    api.post<BewertungPruefungResult>(`/bewertung/bewerten/pruefung/${pruefungId}?provider=${provider}${model ? `&model=${model}` : ''}`, {}, { timeout: 300000 }).then((r) => r.data),

  /** Bewertungen für eine Antwort */
  getByAntwort: (antwortId: number) =>
    api.get<Bewertung[]>(`/bewertung/antwort/${antwortId}`).then((r) => r.data),

  /** Alle Bewertungen einer Prüfung */
  getByPruefung: (pruefungId: number) =>
    api.get<Bewertung[]>(`/bewertung/pruefung/${pruefungId}`).then((r) => r.data),

  /** Musterlösungen einer Prüfung */
  getMusterloesungen: (pruefungId: number) =>
    api.get<Musterloesung[]>(`/bewertung/musterloesungen/${pruefungId}`).then((r) => r.data),

  /** Provider-Status prüfen */
  checkProvider: (provider: 'ollama' | 'openai') =>
    api.get<ProviderStatus>(`/bewertung/provider/${provider}`).then((r) => r.data),
}
