<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { pruefungenApi, antwortenApi, dokumenteApi, bewertungApi } from '@/services/api'
import type { Pruefung, Dokument, DurchlaufStat, AntwortBild, Musterloesung } from '@/types'

const route = useRoute()
const router = useRouter()

const pruefung = ref<Pruefung | null>(null)
const loading = ref(true)
const saving = ref(false)
const snackbar = ref(false)
const snackbarText = ref('')
const snackbarColor = ref('success')

/* Aktives Dokument (PDF links) */
const selectedDocId = ref<number | null>(null)
const pdfPage = ref<number>(1)

/* Lösungs-PDF (unten) */
const showLoesung = ref(false)
const selectedLoesungDocId = ref<number | null>(null)
const loesungPage = ref<number>(1)

/* Aufgaben-Editor */
const aufgaben = ref<AufgabeEntry[]>([])
const newAufgabe = ref('')

/* ══════ Musterloesungen (Fragestellungen) ══════ */
const musterloesungen = ref<Musterloesung[]>([])
const alleAntworten = ref<AufgabeEntry[]>([]) // Alle Antworten (ungefiltert)

/** Prefix für Aufgaben-Namen je nach Prüfungsbereich */
function bereichPrefix(bereich: string | null): string {
  if (!bereich || bereich === 'GA1') return ''
  return bereich + '_'
}

/** Aufgaben-Name mit Bereich-Prefix erzeugen */
function aufgabeWithPrefix(aufgabe: string, bereich: string | null): string {
  const prefix = bereichPrefix(bereich)
  if (prefix && !aufgabe.startsWith(prefix)) return prefix + aufgabe
  return aufgabe
}

/** Aufgaben-Name ohne Bereich-Prefix (für Anzeige) */
function aufgabeDisplayName(aufgabe: string): string {
  // GA2_1a → 1a, WISO_1 → 1
  return aufgabe.replace(/^(GA2|WISO)_/, '')
}

/** Musterloesungen für aktuellen Bereich filtern */
const bereichMusterloesungen = computed<Musterloesung[]>(() => {
  const bereich = activePruefungsbereich.value
  if (!bereich) return musterloesungen.value
  const prefix = bereichPrefix(bereich)
  if (!prefix) {
    // GA1: Aufgaben ohne Prefix (nicht GA2_ und nicht rein numerisch für WISO)
    return musterloesungen.value.filter(m => !m.aufgabe.startsWith('GA2_') && !/^\d+$/.test(m.aufgabe))
  }
  return musterloesungen.value.filter(m => m.aufgabe.startsWith(prefix))
})

/** Fragestellung aus musterloesungen für eine Aufgabe holen */
function getFragestellung(aufgabe: string): string | null {
  const ml = musterloesungen.value.find(m => m.aufgabe === aufgabe)
  return ml?.hinweise || null
}

/** Fragen aus Musterloesungen laden und als leere Aufgaben erstellen */
function loadFragenFromMusterloesungen() {
  const fragen = bereichMusterloesungen.value
  if (!fragen.length) {
    snackbarText.value = 'Keine Fragestellungen für diesen Prüfungsbereich gefunden'
    snackbarColor.value = 'warning'
    snackbar.value = true
    return
  }
  let added = 0
  for (const ml of fragen) {
    if (aufgaben.value.find(a => a.aufgabe === ml.aufgabe)) continue
    aufgaben.value.push({
      id: null,
      aufgabe: ml.aufgabe,
      antwort_text: '',
      notiz: ml.hinweise || '',
      punkte: null,
      max_punkte: ml.max_punkte,
      dirty: true,
      saving: false,
      bilder: [],
      uploadingBild: false,
    })
    added++
  }
  if (added) {
    aufgaben.value.sort((a, b) => a.aufgabe.localeCompare(b.aufgabe, 'de', { numeric: true }))
    snackbarText.value = `${added} Aufgaben für ${activePruefungsbereich.value || 'GA1'} angelegt`
    snackbarColor.value = 'success'
  } else {
    snackbarText.value = 'Alle Aufgaben sind bereits vorhanden'
    snackbarColor.value = 'info'
  }
  snackbar.value = true
}

/* ══════ Durchlauf ══════ */
const aktiverDurchlauf = ref(1)
const durchlaeufe = ref<DurchlaufStat[]>([])
const showDurchlaufStats = ref(false)

/* ══════ Timer ══════ */
const timerSeconds = ref(0)
const timerRunning = ref(false)
let timerInterval: ReturnType<typeof setInterval> | null = null

const timerFormatted = computed(() => {
  const h = Math.floor(timerSeconds.value / 3600)
  const m = Math.floor((timerSeconds.value % 3600) / 60)
  const s = timerSeconds.value % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`
})

function toggleTimer() {
  if (timerRunning.value) {
    stopTimer()
  } else {
    startTimer()
  }
}

function startTimer() {
  if (timerInterval) return
  timerRunning.value = true
  timerInterval = setInterval(() => { timerSeconds.value++ }, 1000)
}

function stopTimer() {
  timerRunning.value = false
  if (timerInterval) { clearInterval(timerInterval); timerInterval = null }
}

function resetTimer() {
  stopTimer()
  timerSeconds.value = 0
}

onUnmounted(() => {
  if (timerInterval) clearInterval(timerInterval)
})

interface AufgabeEntry {
  id: number | null       // null = noch nicht gespeichert
  aufgabe: string
  antwort_text: string
  notiz: string
  punkte: number | null
  max_punkte: number | null
  dirty: boolean          // hat ungespeicherte Änderungen
  saving: boolean
  bilder: AntwortBild[]   // hochgeladene Bilder
  uploadingBild: boolean  // Bild-Upload läuft
}

/* ══════ Bild-Lightbox ══════ */
const lightboxOpen = ref(false)
const lightboxUrl = ref('')
const lightboxTitle = ref('')

/* ══════ Inline-Vorschau (linkes Panel) ══════ */
const previewOpen = ref(false)
const previewUrl = ref('')
const previewTitle = ref('')
const previewIsPdf = ref(false)

function isPdf(bild: AntwortBild): boolean {
  return bild.dateiname.toLowerCase().endsWith('.pdf')
}

/** Klick auf Thumbnail → Inline-Vorschau im linken Panel */
function openLightbox(antwortId: number, bild: AntwortBild) {
  const url = antwortenApi.bildUrl(antwortId, bild.id)
  previewUrl.value = url
  previewTitle.value = bild.dateiname
  previewIsPdf.value = isPdf(bild)
  previewOpen.value = true
}

function closePreview() {
  previewOpen.value = false
  previewUrl.value = ''
  previewTitle.value = ''
}

/** Bild hochladen – Antwort muss vorher gespeichert sein */
async function uploadBild(entry: AufgabeEntry) {
  if (!entry.id) {
    // Erst speichern
    await saveAufgabe(entry)
    if (!entry.id) return
  }
  // File-Picker öffnen
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*,application/pdf'
  input.multiple = true
  input.onchange = async () => {
    if (!input.files?.length) return
    entry.uploadingBild = true
    try {
      for (const file of Array.from(input.files)) {
        const bild = await antwortenApi.uploadBild(entry.id!, file)
        entry.bilder.push(bild)
      }
      snackbarText.value = `${input.files.length} Datei(en) hochgeladen ✓`
      snackbarColor.value = 'success'
      snackbar.value = true
    } catch (e) {
      console.error('Bild-Upload fehlgeschlagen:', e)
      snackbarText.value = 'Fehler beim Bild-Upload'
      snackbarColor.value = 'error'
      snackbar.value = true
    } finally {
      entry.uploadingBild = false
    }
  }
  input.click()
}

/** Bild löschen */
async function deleteBild(entry: AufgabeEntry, bild: AntwortBild) {
  if (!entry.id) return
  try {
    await antwortenApi.deleteBild(entry.id, bild.id)
    entry.bilder = entry.bilder.filter((b) => b.id !== bild.id)
    snackbarText.value = 'Bild gelöscht'
    snackbarColor.value = 'success'
    snackbar.value = true
  } catch (e) {
    console.error('Bild löschen fehlgeschlagen:', e)
    snackbarText.value = 'Fehler beim Löschen'
    snackbarColor.value = 'error'
    snackbar.value = true
  }
}

const id = computed(() => Number(route.params.id))

/* Das Aufgaben-Dokument (bevorzugt 'Aufgabe' Typ, Belegsatz wird ebenfalls angezeigt) */
const aufgabenDocs = computed<Dokument[]>(() => {
  if (!pruefung.value?.dokumente) return []
  return pruefung.value.dokumente.filter((d) => d.typ === 'Aufgabe' || d.typ === 'Belegsatz')
})

/* Prüfungsbereich des aktuell gewählten Dokuments */
const activePruefungsbereich = computed<string | null>(() => {
  if (!selectedDocId.value || !pruefung.value?.dokumente) return null
  const doc = pruefung.value.dokumente.find((d) => d.id === selectedDocId.value)
  return doc?.pruefungsbereich || null
})

/* Lösungs-Dokumente: gefiltert nach dem Prüfungsbereich des Aufgaben-Dokuments */
const loesungsDocs = computed<Dokument[]>(() => {
  if (!pruefung.value?.dokumente) return []
  const lDocs = pruefung.value.dokumente.filter((d) => d.typ === 'L\u00f6sung' || d.typ === 'Handreichung')
  if (!activePruefungsbereich.value) return lDocs
  // Erst nach gleichem Bereich filtern
  const sameBereich = lDocs.filter((d) => d.pruefungsbereich === activePruefungsbereich.value)
  return sameBereich.length ? sameBereich : lDocs
})
const allDocs = computed<Dokument[]>(() => pruefung.value?.dokumente || [])

const pdfUrl = computed(() => {
  if (!selectedDocId.value) return ''
  return `/api/dokumente/${selectedDocId.value}/pdf#page=${pdfPage.value}`
})

const loesungPdfUrl = computed(() => {
  if (!selectedLoesungDocId.value) return ''
  return `/api/dokumente/${selectedLoesungDocId.value}/pdf#page=${loesungPage.value}`
})

/* Gesamtpunkte */
const gesamtPunkte = computed(() => {
  const bewertet = aufgaben.value.filter((a) => a.punkte != null && a.max_punkte != null)
  if (!bewertet.length) return null
  const punkte = bewertet.reduce((s, a) => s + Number(a.punkte || 0), 0)
  const max = bewertet.reduce((s, a) => s + Number(a.max_punkte || 0), 0)
  return { punkte, max, prozent: max ? ((punkte / max) * 100).toFixed(1) : '0' }
})

/* Ungespeicherte Änderungen? */
const hasUnsaved = computed(() => aufgaben.value.some((a) => a.dirty))

/* ══════ OCR-Analyse ══════ */
const ocrAnalysing = ref(false)
const ocrProgress = ref('')

/* ══════ KI-Bewertungen (inline) ══════ */
interface InlineBewertung {
  id: number
  antwort_id: number
  punkte: number
  max_punkte: number
  feedback: string
  bewertung_details: any
  llm_provider: string
  llm_model: string
  dauer_ms: number | null
  erstellt_am: string
}
const inlineBewertungen = ref<InlineBewertung[]>([])
const expandedBewertung = ref<number | null>(null) // aufgabe index with expanded bewertung

function getBewertungForAufgabe(entry: AufgabeEntry): InlineBewertung | null {
  if (!entry.id) return null
  return inlineBewertungen.value.find(b => b.antwort_id === entry.id) || null
}

function toggleBewertungDetail(index: number) {
  expandedBewertung.value = expandedBewertung.value === index ? null : index
}

async function loadBewertungen() {
  try {
    inlineBewertungen.value = await bewertungApi.getByPruefung(id.value)
  } catch {
    // silently ignore if no bewertungen exist yet
    inlineBewertungen.value = []
  }
}

/** Bearbeitete PDF per Tesseract-OCR + KI analysieren und Aufgaben extrahieren */
async function ocrAnalyseDokument() {
  if (!selectedDocId.value) {
    snackbarText.value = 'Bitte zuerst ein Dokument auswählen'
    snackbarColor.value = 'warning'
    snackbar.value = true
    return
  }

  // Warnung bei existierenden Aufgaben
  if (aufgaben.value.length > 0) {
    if (!confirm(`Es sind bereits ${aufgaben.value.length} Aufgaben vorhanden. Die OCR-Analyse wird neue Aufgaben hinzufügen oder bestehende überschreiben. Fortfahren?`)) {
      return
    }
  }

  ocrAnalysing.value = true
  ocrProgress.value = 'PDF wird per Tesseract OCR gescannt...'
  snackbarText.value = 'OCR-Analyse gestartet – das kann bis zu 3 Minuten dauern...'
  snackbarColor.value = 'info'
  snackbar.value = true

  try {
    ocrProgress.value = 'OCR-Text wird per KI analysiert...'

    // OCR + KI-Analyse in einem Schritt
    const result = await bewertungApi.analyseDokument(selectedDocId.value, 'perplexity')

    if (!result.aufgaben || result.aufgaben.length === 0) {
      snackbarText.value = 'Keine Aufgaben im OCR-Text erkannt. Möglicherweise ist die PDF-Qualität zu gering.'
      snackbarColor.value = 'warning'
      snackbar.value = true
      return
    }

    // Aufgaben importieren: bestehende aktualisieren oder neue hinzufügen
    let imported = 0
    let updated = 0

    for (const extracted of result.aufgaben) {
      if (!extracted.aufgabe || !extracted.antwort) continue
      if (extracted.antwort === '(nicht beantwortet)') continue

      // Store original question text in notiz field
      const frageNotiz = extracted.frage ? `📝 Aufgabe: ${extracted.frage}` : ''

      const existing = aufgaben.value.find((a) => a.aufgabe === extracted.aufgabe)
      if (existing) {
        // Nur überschreiben wenn noch leer
        if (!existing.antwort_text.trim() || existing.antwort_text === '(noch nicht beantwortet)') {
          existing.antwort_text = extracted.antwort
          if (extracted.max_punkte) existing.max_punkte = extracted.max_punkte
          if (frageNotiz && !existing.notiz) existing.notiz = frageNotiz
          existing.dirty = true
          updated++
        }
      } else {
        // Neue Aufgabe anlegen
        aufgaben.value.push({
          id: null,
          aufgabe: extracted.aufgabe,
          antwort_text: extracted.antwort,
          notiz: frageNotiz,
          punkte: null,
          max_punkte: extracted.max_punkte || null,
          dirty: true,
          saving: false,
          bilder: [],
          uploadingBild: false,
        })
        imported++
      }
    }

    // Aufgaben sortieren
    aufgaben.value.sort((a, b) => a.aufgabe.localeCompare(b.aufgabe, 'de', { numeric: true }))

    snackbarText.value = `OCR-Analyse fertig! ${imported} neue + ${updated} aktualisierte Aufgaben extrahiert (${result.ocr_chars} Zeichen OCR, ${(result.dauer_ms / 1000).toFixed(1)}s KI-Analyse)`
    snackbarColor.value = 'success'
    snackbar.value = true
  } catch (e: any) {
    console.error('OCR-Analyse fehlgeschlagen:', e)
    snackbarText.value = `OCR-Analyse fehlgeschlagen: ${e.response?.data?.message || e.message || 'Unbekannter Fehler'}`
    snackbarColor.value = 'error'
    snackbar.value = true
  } finally {
    ocrAnalysing.value = false
    ocrProgress.value = ''
  }
}

/** Fragen aus Aufgabe-PDF per KI extrahieren und als Musterlösungen speichern */
const extractingFragen = ref(false)
async function extractFragenFromPdf() {
  if (!selectedDocId.value) {
    snackbarText.value = 'Bitte zuerst ein Aufgabe-PDF auswählen'
    snackbarColor.value = 'warning'
    snackbar.value = true
    return
  }

  extractingFragen.value = true
  snackbarText.value = 'Fragen werden per KI aus dem PDF extrahiert – das kann 1–3 Minuten dauern...'
  snackbarColor.value = 'info'
  snackbar.value = true

  try {
    const result = await bewertungApi.extractFragen(selectedDocId.value, 'perplexity')

    // Musterloesungen aus DB neu laden
    try {
      musterloesungen.value = await bewertungApi.getMusterloesungen(id.value)
    } catch { /* ignore */ }

    // Aufgaben automatisch aus den neuen Musterloesungen anlegen
    loadFragenFromMusterloesungen()

    snackbarText.value = `${result.extracted} Fragen extrahiert und gespeichert (${(result.dauer_ms / 1000).toFixed(1)}s, ${result.provider}:${result.model})${result.skipped ? `, ${result.skipped} übersprungen` : ''}`
    snackbarColor.value = 'success'
    snackbar.value = true
  } catch (e: any) {
    console.error('Fragen-Extraktion fehlgeschlagen:', e)
    snackbarText.value = `Fragen-Extraktion fehlgeschlagen: ${e.response?.data?.message || e.message || 'Unbekannter Fehler'}`
    snackbarColor.value = 'error'
    snackbar.value = true
  } finally {
    extractingFragen.value = false
  }
}

/** Lösungen aus Lösung/Handreichung-PDF per KI extrahieren und in Musterlösungen speichern */
const extractingLoesungen = ref(false)
async function extractLoesungenFromPdf() {
  // Use selectedLoesungDocId (the Lösung PDF) or first loesungsDocs
  const docId = selectedLoesungDocId.value || loesungsDocs.value[0]?.id
  if (!docId) {
    snackbarText.value = 'Kein Lösungs-/Handreichungs-PDF für diesen Prüfungsbereich vorhanden'
    snackbarColor.value = 'warning'
    snackbar.value = true
    return
  }

  extractingLoesungen.value = true
  snackbarText.value = 'Lösungen werden per KI aus dem PDF extrahiert – das kann 1–3 Minuten dauern...'
  snackbarColor.value = 'info'
  snackbar.value = true

  try {
    const result = await bewertungApi.extractLoesungen(docId, 'perplexity')

    // Musterloesungen aus DB neu laden
    try {
      musterloesungen.value = await bewertungApi.getMusterloesungen(id.value)
    } catch { /* ignore */ }

    snackbarText.value = `${result.updated} Lösungen aktualisiert, ${result.created} neu erstellt (${(result.dauer_ms / 1000).toFixed(1)}s, ${result.provider}:${result.model})${result.skipped ? `, ${result.skipped} übersprungen` : ''}`
    snackbarColor.value = 'success'
    snackbar.value = true
  } catch (e: any) {
    console.error('Lösungs-Extraktion fehlgeschlagen:', e)
    snackbarText.value = `Lösungs-Extraktion fehlgeschlagen: ${e.response?.data?.message || e.message || 'Unbekannter Fehler'}`
    snackbarColor.value = 'error'
    snackbar.value = true
  } finally {
    extractingLoesungen.value = false
  }
}

/* ══════ WISO Modus ══════ */
const WISO_PUNKTE = 100 / 30 // ≈ 3.333
const isWiso = computed(() => activePruefungsbereich.value === 'WISO')

interface WisoTask {
  hauptaufgabe: AufgabeEntry
  subTasks: AufgabeEntry[]
  isZuordnung: boolean
}

/** Sub-Index (1-basiert) → Buchstabe a)–z) */
function subIndexToLetter(sub: AufgabeEntry): string {
  const parts = sub.aufgabe.split('.')
  if (parts.length < 2) return sub.aufgabe
  const idx = parseInt(parts[1]) - 1
  return String.fromCharCode(97 + idx) + ')' // a=97
}

/** Maximale Antwort-Zahl für Zuordnung einer Aufgabe (aus Lösungsschlüssel oder Standard 6) */
function zuordnungMaxOption(taskNum: string): number {
  const correct = loesungsschluessel.value[taskNum]
  if (correct && correct.includes('-')) {
    const vals = correct.split('-').map(v => parseInt(v)).filter(n => !isNaN(n))
    if (vals.length) return Math.max(6, ...vals)
  }
  return 6
}

/** Prüft ob die Zuordnung einer Aufgabe Freitext-Werte enthält (Beträge, Daten statt einfache Zahlen) */
function isZuordnungFreitext(taskNum: string): boolean {
  const correct = loesungsschluessel.value[taskNum]
  if (!correct || !correct.includes('-')) return false
  const parts = correct.split('-')
  // Wenn alle Teile reine Ganzzahlen sind → kein Freitext
  return parts.some(p => !/^\d+$/.test(p.trim()))
}

const wisoTasks = computed<WisoTask[]>(() => {
  if (!isWiso.value) return []
  const mainTasks = aufgaben.value
    .filter(a => !a.aufgabe.includes('.'))
    .sort((a, b) => Number(a.aufgabe) - Number(b.aufgabe))
  return mainTasks.map(main => {
    const prefix = main.aufgabe + '.'
    const subs = aufgaben.value
      .filter(a => a.aufgabe.startsWith(prefix))
      .sort((a, b) => Number(a.aufgabe.split('.')[1]) - Number(b.aufgabe.split('.')[1]))
    return { hauptaufgabe: main, subTasks: subs, isZuordnung: subs.length > 0 }
  })
})

const wisoStats = computed(() => {
  if (!wisoTasks.value.length) return null
  let richtig = 0, falsch = 0, offen = 0, punkte = 0
  const max = wisoTasks.value.length * WISO_PUNKTE
  for (const wt of wisoTasks.value) {
    if (wt.isZuordnung) {
      const answered = wt.subTasks.filter(s => s.punkte != null).length
      if (answered === 0) { offen++; continue }
      const correct = wt.subTasks.filter(s => s.punkte != null && s.punkte > 0).length
      punkte += (correct / wt.subTasks.length) * WISO_PUNKTE
      if (correct === wt.subTasks.length) richtig++
      else if (correct === 0) falsch++
    } else {
      if (wt.hauptaufgabe.punkte == null) { offen++; continue }
      if (wt.hauptaufgabe.punkte > 0) { richtig++; punkte += WISO_PUNKTE }
      else falsch++
    }
  }
  return {
    richtig, falsch, offen,
    punkte: Math.round(punkte * 100) / 100,
    max: Math.round(max * 100) / 100,
    prozent: max ? ((punkte / max) * 100).toFixed(1) : '0',
  }
})

/* ── Daten laden ── */
async function loadAntworten(durchlauf: number) {
  const data = await antwortenApi.getByPruefung(id.value, durchlauf)
  alleAntworten.value = data
    .sort((a, b) => a.aufgabe.localeCompare(b.aufgabe, 'de', { numeric: true }))
    .map((a) => ({
      id: a.id,
      aufgabe: a.aufgabe,
      antwort_text: a.antwort_text,
      notiz: a.notiz || '',
      punkte: a.punkte,
      max_punkte: a.max_punkte,
      dirty: false,
      saving: false,
      bilder: a.bilder || [],
      uploadingBild: false,
    }))
  // Aufgaben nach Bereich filtern
  filterAufgabenByBereich()

  // Erkennen ob WISO bereits ausgewertet wurde (Aufgaben mit Punkten vorhanden)
  const wisoMitPunkten = alleAntworten.value.filter(a =>
    /^\d+(\.\d+)?$/.test(a.aufgabe) && a.punkte != null
  )
  wisoAusgewertet.value = wisoMitPunkten.length > 0
  if (wisoMitPunkten.length > 0) showSchluessHints.value = true
}

/** Aufgaben anhand des aktiven Prüfungsbereichs filtern */
function filterAufgabenByBereich() {
  const bereich = activePruefungsbereich.value
  if (!bereich || bereich === 'GA1') {
    // GA1: Aufgaben ohne Prefix (nicht GA2_, nicht rein numerisch WISO)
    aufgaben.value = alleAntworten.value.filter(a =>
      !a.aufgabe.startsWith('GA2_') && a.aufgabe !== 'KEY_META' && !/^\d+(\.\d+)?$/.test(a.aufgabe)
    )
  } else if (bereich === 'GA2') {
    aufgaben.value = alleAntworten.value.filter(a => a.aufgabe.startsWith('GA2_'))
  } else if (bereich === 'WISO') {
    aufgaben.value = alleAntworten.value.filter(a =>
      /^\d+(\.\d+)?$/.test(a.aufgabe) || a.aufgabe === 'KEY_META'
    )
    // Automatisch fehlende WISO-Aufgaben 1-30 ergänzen
    if (aufgaben.value.some(a => /^\d+$/.test(a.aufgabe)) && aufgaben.value.filter(a => /^\d+$/.test(a.aufgabe) && !a.aufgabe.includes('.')).length < 30) {
      generateWisoAufgaben()
    }
  } else {
    aufgaben.value = [...alleAntworten.value]
  }

  // Wenn keine Aufgaben gefunden, aus Musterloesungen erstellen
  if (!aufgaben.value.length && bereichMusterloesungen.value.length) {
    loadFragenFromMusterloesungen()
  }
}

/* Watcher: Wenn der Benutzer das Dokument/Prüfungsbereich wechselt → Aufgaben filtern */
watch(activePruefungsbereich, (newBereich, oldBereich) => {
  if (newBereich === oldBereich) return
  // Unsaved Aufgaben zurück in alleAntworten mergen
  for (const a of aufgaben.value) {
    const idx = alleAntworten.value.findIndex(x => x.aufgabe === a.aufgabe)
    if (idx >= 0) {
      alleAntworten.value[idx] = a
    } else {
      alleAntworten.value.push(a)
    }
  }
  filterAufgabenByBereich()
})

async function loadDurchlaeufe() {
  durchlaeufe.value = await antwortenApi.getDurchlaeufe(id.value)
}

onMounted(async () => {
  loading.value = true
  try {
    pruefung.value = await pruefungenApi.getById(id.value)
    await loadDurchlaeufe()

    // Höchsten Durchlauf als aktiv setzen
    if (durchlaeufe.value.length) {
      aktiverDurchlauf.value = Math.max(...durchlaeufe.value.map(d => d.durchlauf))
    }

    // Musterloesungen (Fragestellungen) VOR Antworten laden
    try {
      musterloesungen.value = await bewertungApi.getMusterloesungen(id.value)
    } catch { musterloesungen.value = [] }

    // Dokument aus Query-Parameter oder erstes Aufgaben-Dokument auswählen
    // (muss VOR loadAntworten gesetzt werden, damit filterAufgabenByBereich richtig filtert)
    const queryDoc = route.query.doc ? Number(route.query.doc) : null
    if (queryDoc && allDocs.value.some((d) => d.id === queryDoc)) {
      selectedDocId.value = queryDoc
    } else if (aufgabenDocs.value.length) {
      selectedDocId.value = aufgabenDocs.value[0].id
    } else if (allDocs.value.length) {
      selectedDocId.value = allDocs.value[0].id
    }
    // Erstes Lösungs-Dokument vorauswählen
    if (loesungsDocs.value.length) {
      selectedLoesungDocId.value = loesungsDocs.value[0].id
    }

    await loadAntworten(aktiverDurchlauf.value)

    // KI-Bewertungen laden (für Inline-Anzeige)
    await loadBewertungen()

    // Gespeicherten Schlüssel aus DB laden
    await loadSavedSchluessel()
  } catch (e) {
    console.error('Laden fehlgeschlagen:', e)
    snackbarText.value = 'Fehler beim Laden'
    snackbarColor.value = 'error'
    snackbar.value = true
  } finally {
    loading.value = false
  }
})

/* ── Neue Aufgabe hinzufügen ── */
function addAufgabe() {
  let name = newAufgabe.value.trim()
  if (!name) return
  // Automatisch Bereich-Prefix hinzufügen (z.B. GA2_1a)
  name = aufgabeWithPrefix(name, activePruefungsbereich.value)
  // Prüfen ob schon existiert
  if (aufgaben.value.find((a) => a.aufgabe === name)) {
    snackbarText.value = `Aufgabe "${aufgabeDisplayName(name)}" existiert bereits`
    snackbarColor.value = 'warning'
    snackbar.value = true
    return
  }
  aufgaben.value.push({
    id: null,
    aufgabe: name,
    antwort_text: '',
    notiz: '',
    punkte: null,
    max_punkte: null,
    dirty: true,
    saving: false,
    bilder: [],
    uploadingBild: false,
  })
  newAufgabe.value = ''
  // Zur neuen Aufgabe scrollen
  nextTick(() => {
    const el = document.getElementById(`aufgabe-${aufgaben.value.length - 1}`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  })
}

/* Schnell-Aufgaben generieren (1a-1d, 2a-2d, etc.) */
function generateAufgaben(pattern: string) {
  const parts = pattern.split(',').map((p) => p.trim()).filter(Boolean)
  for (const part of parts) {
    if (!aufgaben.value.find((a) => a.aufgabe === part)) {
      aufgaben.value.push({
        id: null,
        aufgabe: part,
        antwort_text: '',
        notiz: '',
        punkte: null,
        max_punkte: null,
        dirty: true,
        saving: false,
        bilder: [],
        uploadingBild: false,
      })
    }
  }
}

/* ── Einzelne Aufgabe speichern ── */
async function saveAufgabe(entry: AufgabeEntry) {
  if (!entry.aufgabe.trim()) return
  entry.saving = true
  try {
    const result = await antwortenApi.upsert({
      pruefung_id: id.value,
      aufgabe: entry.aufgabe.trim(),
      antwort_text: entry.antwort_text.trim() || '(noch nicht beantwortet)',
      notiz: entry.notiz.trim() || undefined,
      punkte: entry.punkte ?? undefined,
      max_punkte: entry.max_punkte ?? undefined,
      durchlauf: aktiverDurchlauf.value,
      dauer_sekunden: timerSeconds.value || undefined,
    })
    entry.id = result.id
    entry.dirty = false
    snackbarText.value = `Aufgabe ${entry.aufgabe} gespeichert ✓`
    snackbarColor.value = 'success'
    snackbar.value = true
  } catch (e) {
    console.error('Speichern fehlgeschlagen:', e)
    snackbarText.value = `Fehler beim Speichern von ${entry.aufgabe}`
    snackbarColor.value = 'error'
    snackbar.value = true
  } finally {
    entry.saving = false
  }
}

/* ── Alle unsaved speichern ── */
async function saveAll() {
  saving.value = true
  const unsaved = aufgaben.value.filter((a) => a.dirty)
  let ok = 0
  let fail = 0
  for (const entry of unsaved) {
    try {
      const result = await antwortenApi.upsert({
        pruefung_id: id.value,
        aufgabe: entry.aufgabe.trim(),
        antwort_text: entry.antwort_text.trim() || '(noch nicht beantwortet)',
        notiz: entry.notiz.trim() || undefined,
        punkte: entry.punkte ?? undefined,
        max_punkte: entry.max_punkte ?? undefined,
        durchlauf: aktiverDurchlauf.value,
        dauer_sekunden: timerSeconds.value || undefined,
      })
      entry.id = result.id
      entry.dirty = false
      ok++
    } catch {
      fail++
    }
  }
  saving.value = false
  snackbarText.value = fail ? `${ok} gespeichert, ${fail} fehlgeschlagen` : `${ok} Aufgaben gespeichert ✓`
  snackbarColor.value = fail ? 'warning' : 'success'
  snackbar.value = true
  // Durchlauf-Stats aktualisieren
  loadDurchlaeufe()
}

/* ── Aufgabe löschen ── */
async function deleteAufgabe(entry: AufgabeEntry, index: number) {
  if (!confirm(`Aufgabe "${entry.aufgabe}" wirklich löschen?`)) return
  if (entry.id) {
    try {
      await antwortenApi.remove(entry.id)
    } catch (e) {
      console.error('Löschen fehlgeschlagen:', e)
      snackbarText.value = 'Fehler beim Löschen'
      snackbarColor.value = 'error'
      snackbar.value = true
      return
    }
  }
  aufgaben.value.splice(index, 1)
  snackbarText.value = `Aufgabe "${entry.aufgabe}" gelöscht`
  snackbarColor.value = 'success'
  snackbar.value = true
}

/* Dirty markieren bei Änderung */
function markDirty(entry: AufgabeEntry) {
  entry.dirty = true
}

/* PDF Seite wechseln */
function goToPage(p: number) {
  pdfPage.value = p
}
function goToLoesungPage(p: number) {
  loesungPage.value = p
}

/* ══════ WISO Funktionen ══════ */
function generateWisoAufgaben() {
  for (let i = 1; i <= 30; i++) {
    const name = String(i)
    if (!aufgaben.value.find(a => a.aufgabe === name)) {
      const entry: AufgabeEntry = {
        id: null, aufgabe: name, antwort_text: '', notiz: '',
        punkte: null, max_punkte: WISO_PUNKTE, dirty: true, saving: false,
        bilder: [], uploadingBild: false,
      }
      aufgaben.value.push(entry)
      // Auch in alleAntworten einfügen, damit es beim Bereich-Wechsel erhalten bleibt
      if (!alleAntworten.value.find(a => a.aufgabe === name)) {
        alleAntworten.value.push(entry)
      }
    }
  }
  // Nach Nummern sortieren
  aufgaben.value.sort((a, b) => {
    const na = Number(a.aufgabe.split('.')[0])
    const nb = Number(b.aufgabe.split('.')[0])
    return na - nb || a.aufgabe.localeCompare(b.aufgabe, 'de', { numeric: true })
  })
}

function setWisoCorrect(entry: AufgabeEntry, correct: boolean) {
  entry.punkte = correct ? WISO_PUNKTE : 0
  entry.max_punkte = WISO_PUNKTE
  entry.dirty = true
}

function setWisoSubCorrect(wt: WisoTask, sub: AufgabeEntry, correct: boolean) {
  const subPunkte = WISO_PUNKTE / wt.subTasks.length
  sub.punkte = correct ? subPunkte : 0
  sub.max_punkte = subPunkte
  sub.dirty = true
  recalcZuordnungParent(wt)
}

function recalcZuordnungParent(wt: WisoTask) {
  const total = wt.subTasks.length
  if (!total) return
  const correct = wt.subTasks.filter(s => s.punkte != null && s.punkte > 0).length
  wt.hauptaufgabe.punkte = (correct / total) * WISO_PUNKTE
  wt.hauptaufgabe.max_punkte = WISO_PUNKTE
  wt.hauptaufgabe.dirty = true
}

function addZuordnung(taskNum: string, count = 5) {
  // Wenn Lösungsschlüssel vorhanden, Anzahl automatisch erkennen
  const correct = loesungsschluessel.value[taskNum]
  if (correct && correct.includes('-')) {
    count = correct.split('-').length
  }
  for (let i = 1; i <= count; i++) {
    const name = `${taskNum}.${i}`
    if (!aufgaben.value.find(a => a.aufgabe === name)) {
      aufgaben.value.push({
        id: null, aufgabe: name, antwort_text: '', notiz: '',
        punkte: null, max_punkte: WISO_PUNKTE / count, dirty: true, saving: false,
        bilder: [], uploadingBild: false,
      })
    }
  }
}

function addZuordnungSub(taskNum: string) {
  const prefix = taskNum + '.'
  const existing = aufgaben.value.filter(a => a.aufgabe.startsWith(prefix)).length
  const nextIdx = existing + 1
  const totalCount = nextIdx
  const name = `${taskNum}.${nextIdx}`
  aufgaben.value.push({
    id: null, aufgabe: name, antwort_text: '', notiz: '',
    punkte: null, max_punkte: WISO_PUNKTE / totalCount, dirty: true, saving: false,
    bilder: [], uploadingBild: false,
  })
  // Max-Punkte aller Subs neu berechnen
  const subs = aufgaben.value.filter(a => a.aufgabe.startsWith(prefix))
  subs.forEach(s => { s.max_punkte = WISO_PUNKTE / subs.length })
}

async function removeLastZuordnungSub(taskNum: string) {
  const prefix = taskNum + '.'
  const subs = aufgaben.value
    .filter(a => a.aufgabe.startsWith(prefix))
    .sort((a, b) => Number(a.aufgabe.split('.')[1]) - Number(b.aufgabe.split('.')[1]))
  if (subs.length <= 1) {
    // Letzte entfernen → gesamte Zuordnung entfernen
    await removeZuordnung(taskNum)
    return
  }
  const last = subs[subs.length - 1]
  if (last.id) {
    try { await antwortenApi.remove(last.id) } catch (e) { console.error(e) }
  }
  aufgaben.value = aufgaben.value.filter(a => a.aufgabe !== last.aufgabe)
  // Max-Punkte aller verbleibenden Subs neu berechnen
  const remaining = aufgaben.value.filter(a => a.aufgabe.startsWith(prefix))
  remaining.forEach(s => { s.max_punkte = WISO_PUNKTE / remaining.length })
}

async function removeZuordnung(taskNum: string) {
  const prefix = taskNum + '.'
  const subs = aufgaben.value.filter(a => a.aufgabe.startsWith(prefix))
  for (const sub of subs) {
    if (sub.id) {
      try { await antwortenApi.remove(sub.id) } catch (e) { console.error(e) }
    }
  }
  aufgaben.value = aufgaben.value.filter(a => !a.aufgabe.startsWith(prefix))
  const parent = aufgaben.value.find(a => a.aufgabe === taskNum)
  if (parent) { parent.punkte = null; parent.dirty = true }
}

function wisoRowClass(entry: AufgabeEntry) {
  if (entry.punkte == null) return 'wiso-neutral'
  return entry.punkte > 0 ? 'wiso-correct' : 'wiso-incorrect'
}

/* ══════ Lösungsschlüssel (MC Auto-Auswertung) ══════ */
const loesungsschluessel = ref<Record<string, string>>({})
const loesungLoading = ref(false)
const hasLoesungsschluessel = computed(() => Object.keys(loesungsschluessel.value).length > 0)

/** Schlüssel-Anzeige ein/aus (Korrekturen, Inline-Key-Edit, richtige Antworten) */
const showSchluessHints = ref(false)

/** WISO wurde ausgewertet → Antworten gesperrt bis neuer Durchlauf */
const wisoAusgewertet = ref(false)

/* ══════ Schlüssel-Editor ══════ */
type AnswerType = 'mc' | 'mc-multi' | 'betrag' | 'datum' | 'zuordnung' | 'zahl'
interface SchluesselEntry {
  type: AnswerType
  mc: string           // MC-Einzelantwort ("3")
  mcMulti: string[]    // MC-Mehrfach (["3","6"])
  betrag: string       // Geldbetrag ("2.992,88")
  datum: string        // Datum ("15.06.13")
  zuordnung: string[]  // Zuordnung pro Buchstabe (["2","1","3"])
  zahl: string         // Einfache Zahl ("42", "17")
}
const showSchluessEditor = ref(false)
const schluesselEntries = ref<Record<string, SchluesselEntry>>({})
const showJsonImport = ref(false)
const jsonImportText = ref('')

/** Speichert den Typ pro Aufgabe (mc/mc-multi/betrag/datum/zuordnung) */
const schluesselTypes = ref<Record<string, AnswerType>>({})

/** Antworttyp für eine Aufgabe ermitteln (gespeicherter Typ oder aus Wert ableiten) */
function getAnswerType(taskNum: string): AnswerType {
  if (schluesselTypes.value[taskNum]) return schluesselTypes.value[taskNum]
  const val = loesungsschluessel.value[taskNum]
  return val ? detectAnswerType(val) : 'mc'
}

/** Ist die Aufgabe ein Freitext-Typ (Betrag/Datum/Zahl), bei dem kein MC-Button angezeigt wird? */
function isFreitextTask(taskNum: string): boolean {
  const t = getAnswerType(taskNum)
  return t === 'betrag' || t === 'datum' || t === 'zahl'
}

function detectAnswerType(val: string): AnswerType {
  if (!val) return 'mc'
  if (val.includes('-')) {
    // Datum erkennen: DD.MM.YY oder DD.MM.YYYY
    if (/^\d{1,2}\.\d{1,2}\.\d{2,4}$/.test(val)) return 'datum'
    return 'zuordnung'
  }
  if (val.includes(';')) return 'mc-multi'
  // Datum mit Punkt-Trennern
  if (/^\d{1,2}\.\d{1,2}\.\d{2,4}$/.test(val)) return 'datum'
  if (/[,.]/.test(val) && /\d/.test(val) && !/^\d+$/.test(val)) return 'betrag'
  // Reine Ganzzahl mit mehr als 1 Stelle → Zahl-Typ (einstellige bleiben MC)
  if (/^\d{2,}$/.test(val)) return 'zahl'
  return 'mc'
}

function makeEmptyEntry(type: AnswerType = 'mc'): SchluesselEntry {
  return { type, mc: '', mcMulti: ['', ''], betrag: '', datum: '', zuordnung: ['', '', '', '', ''], zahl: '' }
}

function parseToEntry(val: string): SchluesselEntry {
  const type = detectAnswerType(val)
  const entry = makeEmptyEntry(type)
  if (type === 'mc') {
    entry.mc = val
  } else if (type === 'mc-multi') {
    entry.mcMulti = val.split(';').map(v => v.trim())
    while (entry.mcMulti.length < 2) entry.mcMulti.push('')
  } else if (type === 'betrag') {
    entry.betrag = val
  } else if (type === 'datum') {
    entry.datum = val
  } else if (type === 'zuordnung') {
    entry.zuordnung = val.split('-').map(v => v.trim())
    while (entry.zuordnung.length < 2) entry.zuordnung.push('')
  } else if (type === 'zahl') {
    entry.zahl = val
  }
  return entry
}

function entryToValue(e: SchluesselEntry): string {
  if (e.type === 'mc') return e.mc.trim()
  if (e.type === 'mc-multi') return e.mcMulti.map(v => v.trim()).filter(Boolean).join(';')
  if (e.type === 'betrag') return e.betrag.trim()
  if (e.type === 'datum') return e.datum.trim()
  if (e.type === 'zuordnung') return e.zuordnung.map(v => v.trim()).filter(Boolean).join('-')
  if (e.type === 'zahl') return e.zahl.trim()
  return ''
}

function openSchluessEditor() {
  const entries: Record<string, SchluesselEntry> = {}
  for (let i = 1; i <= 30; i++) {
    const key = String(i)
    const existing = loesungsschluessel.value[key] || ''
    const entry = parseToEntry(existing)
    // Gespeicherter Typ hat Vorrang
    if (schluesselTypes.value[key]) entry.type = schluesselTypes.value[key]
    entries[key] = entry
  }
  schluesselEntries.value = entries
  showSchluessEditor.value = true
}

function changeEntryType(key: string, newType: AnswerType) {
  const e = schluesselEntries.value[key]
  if (!e) return
  const oldVal = entryToValue(e)
  e.type = newType
  // Wert in neues Format übertragen wenn möglich
  if (newType === 'mc') e.mc = oldVal.replace(/[-;]/g, '') || e.mc
  else if (newType === 'mc-multi') {
    if (e.mcMulti.filter(Boolean).length === 0) e.mcMulti = oldVal ? [oldVal, ''] : ['', '']
  }
  else if (newType === 'betrag') e.betrag = e.betrag || oldVal || ''
  else if (newType === 'datum') e.datum = e.datum || oldVal || ''
  else if (newType === 'zuordnung') {
    if (e.zuordnung.filter(Boolean).length === 0) e.zuordnung = ['', '', '', '', '']
  }
  else if (newType === 'zahl') e.zahl = e.zahl || oldVal || ''
}

function addZuordnungField(key: string) {
  schluesselEntries.value[key]?.zuordnung.push('')
}
function removeZuordnungField(key: string) {
  const arr = schluesselEntries.value[key]?.zuordnung
  if (arr && arr.length > 2) arr.pop()
}
function addMcMultiField(key: string) {
  schluesselEntries.value[key]?.mcMulti.push('')
}
function removeMcMultiField(key: string) {
  const arr = schluesselEntries.value[key]?.mcMulti
  if (arr && arr.length > 2) arr.pop()
}

function applySchluessEdits() {
  const result: Record<string, string> = {}
  const types: Record<string, AnswerType> = {}
  for (const [key, entry] of Object.entries(schluesselEntries.value)) {
    const val = entryToValue(entry)
    if (val) {
      result[key] = val
      types[key] = entry.type
    }
  }
  loesungsschluessel.value = result
  schluesselTypes.value = types
  autoCreateZuordnungen()
  reevaluateAll()
  showSchluessEditor.value = false
  saveSchlussel()
  snackbarText.value = `Schlüssel aktualisiert: ${Object.keys(result).length} Antworten`
  snackbarColor.value = 'success'
  snackbar.value = true
}

/** Einzelnen Schlüsselwert inline ändern (Quick-Edit) */
function updateSchluessInline(taskNum: string, newVal: string) {
  const trimmed = newVal.trim()
  if (trimmed) {
    loesungsschluessel.value[taskNum] = trimmed
    if (!schluesselTypes.value[taskNum]) {
      schluesselTypes.value[taskNum] = detectAnswerType(trimmed)
    }
  } else {
    delete loesungsschluessel.value[taskNum]
    delete schluesselTypes.value[taskNum]
  }
  reevaluateAll()
  saveSchlussel()
}

/** Lösungsschlüssel persistent speichern (Durchlauf 0, Aufgabe KEY_n) */
async function saveSchlussel() {
  try {
    // Alle Schlüsselwerte + Typen als JSON in KEY_META speichern
    const meta = JSON.stringify({
      answers: loesungsschluessel.value,
      types: schluesselTypes.value,
    })
    await antwortenApi.upsert({
      pruefung_id: id.value,
      aufgabe: 'KEY_META',
      antwort_text: meta,
      durchlauf: 0,
    })
  } catch (e) {
    console.error('Schlüssel speichern fehlgeschlagen:', e)
  }
}

/** Gespeicherten Lösungsschlüssel aus DB laden */
async function loadSavedSchluessel() {
  try {
    const data = await antwortenApi.getByPruefung(id.value, 0)
    const meta = data.find(a => a.aufgabe === 'KEY_META')
    if (meta && meta.antwort_text) {
      const parsed = JSON.parse(meta.antwort_text)
      if (parsed.answers && Object.keys(parsed.answers).length > 0) {
        loesungsschluessel.value = parsed.answers
        schluesselTypes.value = parsed.types || {}
        autoCreateZuordnungen()
        reevaluateAll()
      }
    }
  } catch (e) {
    console.error('Gespeicherten Schlüssel laden fehlgeschlagen:', e)
  }
}

function clearSchluessel() {
  loesungsschluessel.value = {}
  schluesselTypes.value = {}
  showSchluessEditor.value = false
  // Alle Punkte zurücksetzen
  for (const wt of wisoTasks.value) {
    wt.hauptaufgabe.punkte = null
    wt.hauptaufgabe.dirty = true
    if (wt.isZuordnung) {
      wt.subTasks.forEach(sub => {
        sub.punkte = null
        sub.dirty = true
      })
    }
  }
  snackbarText.value = 'Lösungsschlüssel gelöscht'
  snackbarColor.value = 'info'
  snackbar.value = true
  // Auch aus DB löschen
  saveSchlussel()
}

/** JSON-Import: Nutzer kann JSON einfügen um Lösungsschlüssel schnell anzulegen */
function importSchluessFromJson() {
  const raw = jsonImportText.value.trim()
  if (!raw) {
    snackbarText.value = 'Bitte JSON einfügen'
    snackbarColor.value = 'warning'
    snackbar.value = true
    return
  }
  try {
    const parsed = JSON.parse(raw)
    // Format: { answers: { "1": "4", ... }, types: { "1": "mc", ... } }
    // oder nur: { "1": "4", "2": "[3;5]", ... } (nur answers ohne types)
    const answers: Record<string, string> = parsed.answers || parsed
    const types: Record<string, AnswerType> = parsed.types || {}

    const resultAnswers: Record<string, string> = {}
    const resultTypes: Record<string, AnswerType> = {}

    for (const [key, rawVal] of Object.entries(answers)) {
      if (typeof rawVal !== 'string') continue
      let val = rawVal.trim()
      // Expliziter Typ aus JSON?
      let type: AnswerType | undefined = types[key] as AnswerType | undefined

      // [3;5] → mc-multi → "3;5"
      const mcMultiMatch = val.match(/^\[(.+)\]$/)
      if (mcMultiMatch) {
        val = mcMultiMatch[1].replace(/;/g, ';')
        if (!type) type = 'mc-multi'
      }

      // Typ auto-erkennen wenn nicht angegeben
      if (!type) type = detectAnswerType(val)

      resultAnswers[key] = val
      resultTypes[key] = type
    }

    const count = Object.keys(resultAnswers).length
    if (count === 0) {
      snackbarText.value = 'Keine Antworten im JSON gefunden'
      snackbarColor.value = 'warning'
      snackbar.value = true
      return
    }

    loesungsschluessel.value = resultAnswers
    schluesselTypes.value = resultTypes
    autoCreateZuordnungen()
    reevaluateAll()
    saveSchlussel()

    // Editor aktualisieren falls offen
    if (showSchluessEditor.value) {
      openSchluessEditor()
    }

    showJsonImport.value = false
    jsonImportText.value = ''
    snackbarText.value = `${count} Antworten aus JSON importiert`
    snackbarColor.value = 'success'
    snackbar.value = true
  } catch (e: any) {
    snackbarText.value = `JSON-Fehler: ${e.message}`
    snackbarColor.value = 'error'
    snackbar.value = true
  }
}

async function loadLoesungsschluessel() {
  // Wenn schon gespeicherte Schlüssel vorhanden → nur Info anzeigen, nicht überschreiben
  if (hasLoesungsschluessel.value) {
    snackbarText.value = `Schlüssel bereits geladen (${Object.keys(loesungsschluessel.value).length} Antworten). Zum Bearbeiten: "Schlüssel bearbeiten" nutzen.`
    snackbarColor.value = 'info'
    snackbar.value = true
    return
  }
  if (!selectedLoesungDocId.value) {
    snackbarText.value = 'Bitte zuerst ein Lösungs-Dokument auswählen'
    snackbarColor.value = 'warning'
    snackbar.value = true
    return
  }
  loesungLoading.value = true
  try {
    const result = await dokumenteApi.extractAnswers(selectedLoesungDocId.value)
    if (result.count === 0) {
      snackbarText.value = 'Keine Antworten in der Lösung gefunden (evtl. Scan-PDF?)'
      snackbarColor.value = 'warning'
      snackbar.value = true
      return
    }
    loesungsschluessel.value = result.answers
    // Typen aus Werten ableiten
    for (const [k, v] of Object.entries(result.answers)) {
      if (!schluesselTypes.value[k]) schluesselTypes.value[k] = detectAnswerType(v)
    }
    snackbarText.value = `${result.count} Antworten geladen aus "${result.source}"`
    snackbarColor.value = 'success'
    snackbar.value = true
    // Zuordnungen automatisch erstellen/anpassen wenn Lösungsschlüssel Dash-Pattern hat
    autoCreateZuordnungen()
    // Bei geladenen Antworten: bestehende MC-Antworten automatisch prüfen
    reevaluateAll()
    // Schlüssel persistent speichern
    saveSchlussel()
  } catch (e: any) {
    console.error('Lösungsschlüssel laden fehlgeschlagen:', e)
    snackbarText.value = 'Fehler beim Laden des Lösungsschlüssels'
    snackbarColor.value = 'error'
    snackbar.value = true
  } finally {
    loesungLoading.value = false
  }
}

/** Automatisch Zuordnungen erstellen wenn der Lösungsschlüssel Dash-Patterns enthält */
function autoCreateZuordnungen() {
  for (const [taskNum, answer] of Object.entries(loesungsschluessel.value)) {
    if (!answer.includes('-')) continue
    const neededCount = answer.split('-').length
    const prefix = taskNum + '.'
    const existing = aufgaben.value.filter(a => a.aufgabe.startsWith(prefix)).length
    if (existing < neededCount) {
      addZuordnung(taskNum, neededCount)
    }
  }
}

function getCorrectAnswer(taskNum: string): string | null {
  return loesungsschluessel.value[taskNum] || null
}

function isAnswerCorrect(taskNum: string, userAnswer: string): boolean {
  const correct = getCorrectAnswer(taskNum)
  if (!correct) return false
  // Unterstützt mehrere gültige: "3;6" = 3 oder 6 ist richtig
  const validAnswers = correct.split(';').map(a => normalizeAnswer(a))
  const normalizedUser = normalizeAnswer(userAnswer)
  return validAnswers.includes(normalizedUser)
}

function selectMcAnswer(entry: AufgabeEntry, answer: string) {
  if (wisoAusgewertet.value) return  // gesperrt nach Auswertung
  const taskNum = entry.aufgabe
  const answerType = getAnswerType(taskNum)

  // MC-Multi: mehrere Antworten togglen (z.B. "3;6")
  if (answerType === 'mc-multi') {
    const current = entry.antwort_text.trim()
    const selected = current ? current.split(';').map(s => s.trim()).filter(Boolean) : []
    const idx = selected.indexOf(answer)
    if (idx >= 0) {
      selected.splice(idx, 1)  // deselektieren
    } else {
      selected.push(answer)    // hinzufügen
    }
    selected.sort((a, b) => Number(a) - Number(b))
    entry.antwort_text = selected.join(';')
    entry.dirty = true
    // Auto-Auswertung
    if (hasLoesungsschluessel.value && showSchluessHints.value) {
      entry.punkte = isMcMultiCorrect(taskNum, selected) ? WISO_PUNKTE : 0
      entry.max_punkte = WISO_PUNKTE
    }
    return
  }

  const currentAnswer = entry.antwort_text.trim()
  // Toggle: gleiche Antwort nochmal klicken → deselektieren
  if (currentAnswer === answer) {
    entry.antwort_text = ''
    entry.punkte = null
    entry.dirty = true
    return
  }
  entry.antwort_text = answer
  entry.dirty = true
  // Auto-Auswertung wenn Lösungsschlüssel vorhanden
  if (hasLoesungsschluessel.value && showSchluessHints.value) {
    const correct = isAnswerCorrect(entry.aufgabe, answer)
    entry.punkte = correct ? WISO_PUNKTE : 0
    entry.max_punkte = WISO_PUNKTE
  }
}

/** Prüft ob alle MC-Multi-Antworten korrekt ausgewählt sind */
function isMcMultiCorrect(taskNum: string, selected: string[]): boolean {
  const correct = getCorrectAnswer(taskNum)
  if (!correct) return false
  const expected = correct.split(';').map(a => normalizeAnswer(a)).sort()
  const userSorted = selected.map(a => normalizeAnswer(a)).sort()
  if (expected.length !== userSorted.length) return false
  return expected.every((v, i) => v === userSorted[i])
}

/** Ausgewählte MC-Antworten (für MC-Multi als Array) */
function selectedMcAnswers(entry: AufgabeEntry): string[] {
  const txt = entry.antwort_text.trim()
  if (!txt) return []
  if (txt.includes(';')) return txt.split(';').map(s => normalizeAnswer(s.trim())).filter(Boolean)
  const single = selectedMcAnswer(entry)
  return single ? [single] : []
}

/** Antwort-Werte normalisieren (führende Nullen entfernen, Datum vereinheitlichen, trimmen) */
function normalizeAnswer(val: string): string {
  const t = val.trim()
  // Reine Ganzzahl → führende Nullen entfernen
  if (/^\d+$/.test(t)) return String(parseInt(t))
  // Datum normalisieren: DD.MM.YY / DD.MM.YYYY → einheitlich DD.MM.YY
  const dm = t.match(/^(\d{1,2})\.(\d{1,2})\.(\d{2,4})$/)
  if (dm) {
    const day = dm[1].padStart(2, '0')
    const month = dm[2].padStart(2, '0')
    let year = dm[3]
    if (year.length === 4) year = year.slice(2) // 2013 → 13
    return `${day}.${month}.${year}`
  }
  // Betrag normalisieren: Leerzeichen/Punkte als Tausender-Trenner entfernen, Komma beibehalten
  const bt = t.replace(/\s/g, '')
  if (/^\d[\d.]*,\d{1,2}$/.test(bt)) {
    return bt.replace(/\./g, '')  // "2.992,88" → "2992,88"
  }
  return t
}

function selectedMcAnswer(entry: AufgabeEntry): string {
  const txt = entry.antwort_text.trim()
  // Exakte positive Ganzzahl (beliebig, nicht nur 1-6)
  if (/^\d+$/.test(txt)) return normalizeAnswer(txt)
  // Auch aus Text extrahieren: z.B. "Antwort 3", "3)", "3."
  const m = txt.match(/^(?:Antwort\s+)?(\d+)(?:[).:\s]|$)/)
  if (m) return normalizeAnswer(m[1])
  return ''
}

function mcButtonColor(entry: AufgabeEntry, num: string): string {
  const answerType = getAnswerType(entry.aufgabe)
  if (answerType === 'mc-multi') {
    const sels = selectedMcAnswers(entry)
    if (!sels.includes(num)) return 'grey-lighten-1'
    if (hasLoesungsschluessel.value && showSchluessHints.value) {
      // Einzelnen Button prüfen: ist er Teil der richtigen Antworten?
      const correct = getCorrectAnswer(entry.aufgabe)
      if (correct) {
        const expected = correct.split(';').map(a => normalizeAnswer(a))
        return expected.includes(normalizeAnswer(num)) ? 'green' : 'red'
      }
    }
    return 'blue'
  }
  const selected = selectedMcAnswer(entry)
  if (selected !== num) return 'grey-lighten-1'
  if (hasLoesungsschluessel.value && showSchluessHints.value) {
    return isAnswerCorrect(entry.aufgabe, num) ? 'green' : 'red'
  }
  return 'blue'
}

function mcButtonVariant(entry: AufgabeEntry, num: string): 'flat' | 'outlined' {
  const answerType = getAnswerType(entry.aufgabe)
  if (answerType === 'mc-multi') {
    return selectedMcAnswers(entry).includes(num) ? 'flat' : 'outlined'
  }
  return selectedMcAnswer(entry) === num ? 'flat' : 'outlined'
}

/** MC-Farbe für Zuordnung Sub-Task (hat eigene korrekte Antwort je Index) */
function mcSubButtonColor(wt: WisoTask, sub: AufgabeEntry, num: string): string {
  const selected = selectedMcAnswer(sub)
  if (selected !== num) return 'grey-lighten-1'
  if (hasLoesungsschluessel.value && showSchluessHints.value) {
    const correctVal = getSubCorrectAnswer(wt.hauptaufgabe.aufgabe, sub)
    if (correctVal != null) {
      return normalizeAnswer(num) === normalizeAnswer(correctVal) ? 'green' : 'red'
    }
  }
  return 'blue'
}

/** MC-Antwort für Zuordnung Sub-Task auswählen */
function selectMcSubAnswer(wt: WisoTask, sub: AufgabeEntry, answer: string) {
  if (wisoAusgewertet.value) return  // gesperrt nach Auswertung
  const currentAnswer = sub.antwort_text.trim()
  if (currentAnswer === answer) {
    sub.antwort_text = ''
    sub.punkte = null
    sub.dirty = true
    recalcZuordnungParent(wt)
    return
  }
  sub.antwort_text = answer
  sub.dirty = true
  // Auto-Auswertung wenn Lösungsschlüssel vorhanden UND Hints sichtbar
  if (hasLoesungsschluessel.value && showSchluessHints.value) {
    const correctVal = getSubCorrectAnswer(wt.hauptaufgabe.aufgabe, sub)
    if (correctVal != null) {
      const subPunkte = WISO_PUNKTE / wt.subTasks.length
      sub.punkte = normalizeAnswer(answer) === normalizeAnswer(correctVal) ? subPunkte : 0
      sub.max_punkte = subPunkte
      recalcZuordnungParent(wt)
    }
  }
}

/** Korrekte Antwort für einen Zuordnung Sub-Task (aus Dash-Pattern) */
function getSubCorrectAnswer(taskNum: string, sub: AufgabeEntry): string | null {
  const correct = getCorrectAnswer(taskNum)
  if (!correct || !correct.includes('-')) return null
  const subAnswers = correct.split('-')
  // Sub-Aufgabe "15.3" → Index 2 (dritte Zuordnung)
  const parts = sub.aufgabe.split('.')
  if (parts.length < 2) return null
  const idx = parseInt(parts[1]) - 1
  return idx >= 0 && idx < subAnswers.length ? subAnswers[idx] : null
}

/** Alle bestehenden MC-Antworten gegen den Lösungsschlüssel prüfen */
function reevaluateAll() {
  for (const wt of wisoTasks.value) {
    const taskNum = wt.hauptaufgabe.aufgabe
    const correct = getCorrectAnswer(taskNum)
    if (!correct) continue

    if (!wt.isZuordnung) {
      const answerType = getAnswerType(taskNum)

      if (answerType === 'mc-multi') {
        // MC-Multi: alle ausgewählten prüfen
        const sels = selectedMcAnswers(wt.hauptaufgabe)
        if (!sels.length) continue
        const isCorrect = isMcMultiCorrect(taskNum, sels)
        const newPunkte = isCorrect ? WISO_PUNKTE : 0
        if (wt.hauptaufgabe.punkte !== newPunkte) {
          wt.hauptaufgabe.punkte = newPunkte
          wt.hauptaufgabe.max_punkte = WISO_PUNKTE
          wt.hauptaufgabe.dirty = true
        }
      } else if (answerType === 'datum' || answerType === 'betrag' || answerType === 'zahl') {
        // Freitext-Typ (Datum/Betrag/Zahl): direkt den Textfeld-Inhalt vergleichen
        const rawText = wt.hauptaufgabe.antwort_text.trim()
        if (!rawText) continue
        const isCorrect = normalizeAnswer(rawText) === normalizeAnswer(correct)
        const newPunkte = isCorrect ? WISO_PUNKTE : 0
        if (wt.hauptaufgabe.punkte !== newPunkte) {
          wt.hauptaufgabe.punkte = newPunkte
          wt.hauptaufgabe.max_punkte = WISO_PUNKTE
          wt.hauptaufgabe.dirty = true
        }
      } else {
        // Einfache MC-Antwort prüfen
        const sel = selectedMcAnswer(wt.hauptaufgabe)
        if (!sel) continue
        const isCorrect = isAnswerCorrect(taskNum, sel)
        const newPunkte = isCorrect ? WISO_PUNKTE : 0
        if (wt.hauptaufgabe.punkte !== newPunkte) {
          wt.hauptaufgabe.punkte = newPunkte
          wt.hauptaufgabe.max_punkte = WISO_PUNKTE
          wt.hauptaufgabe.dirty = true
        }
      }
    } else if (correct.includes('-')) {
      // Zuordnung mit Lösungs-Pattern "2-1-3-2-2" oder "2.992,88-278,34"
      const subAnswers = correct.split('-')
      const freitext = isZuordnungFreitext(taskNum)
      wt.subTasks.forEach((sub, idx) => {
        if (idx >= subAnswers.length) return
        // Bei Freitext-Zuordnungen (Beträge etc.) direkt Textfeld nutzen
        let userVal: string | null = null
        if (!freitext) {
          userVal = selectedMcAnswer(sub)
        }
        if (!userVal) {
          // Fallback: direkter Textfeld-Inhalt nutzen
          userVal = sub.antwort_text.trim()
        }
        if (!userVal) return
        const isCorrect = normalizeAnswer(userVal) === normalizeAnswer(subAnswers[idx])
        const subPunkte = WISO_PUNKTE / wt.subTasks.length
        sub.punkte = isCorrect ? subPunkte : 0
        sub.max_punkte = subPunkte
        sub.dirty = true
      })
      recalcZuordnungParent(wt)
    }
  }
}

/** Bereichs-Marker in DB speichern (damit Prüfungsliste weiß, welcher Bereich geübt wurde) */
async function saveBereichMarker() {
  const bereich = activePruefungsbereich.value
  if (!bereich) return
  try {
    await antwortenApi.upsert({
      pruefung_id: id.value,
      aufgabe: `BEREICH_${bereich}`,
      antwort_text: 'ausgewertet',
      durchlauf: 0,
    })
  } catch (e) {
    console.error('Bereich-Marker speichern fehlgeschlagen:', e)
  }
}

/** Auswerten: Schlüssel laden + alle prüfen + speichern */
async function auswerten() {
  if (!hasLoesungsschluessel.value) {
    // Versuche zuerst aus DB zu laden
    await loadSavedSchluessel()
    // Falls immer noch keiner da → aus PDF extrahieren
    if (!hasLoesungsschluessel.value) {
      await loadLoesungsschluessel()
    }
  }
  if (!hasLoesungsschluessel.value) return // Laden fehlgeschlagen
  showSchluessHints.value = true   // Hints einblenden bei Auswertung
  wisoAusgewertet.value = true      // Antworten sperren nach Auswertung
  reevaluateAll()
  // Automatisch alle geänderten speichern
  const dirtyCount = aufgaben.value.filter(a => a.dirty).length
  if (dirtyCount > 0) {
    await saveAll()
  }
  // Bereich-Marker speichern (damit Prüfungsliste den Bereich anzeigt)
  await saveBereichMarker()
  loadDurchlaeufe()
  const stats = wisoStats.value
  if (stats) {
    snackbarText.value = `Auswertung: ${stats.richtig}/${wisoTasks.value.length} richtig – ${stats.punkte.toFixed(1)} / ${stats.max.toFixed(0)} P. (${stats.prozent}%)`
    snackbarColor.value = Number(stats.prozent) >= 50 ? 'success' : 'error'
    snackbar.value = true
  }
}

/* ══════ Durchlauf-Funktionen ══════ */
async function startNeuerDurchlauf() {
  if (hasUnsaved.value) {
    if (!confirm('Es gibt ungespeicherte Änderungen. Trotzdem neuen Durchlauf starten?')) return
  }
  const nextNr = durchlaeufe.value.length ? Math.max(...durchlaeufe.value.map(d => d.durchlauf)) + 1 : 1
  aktiverDurchlauf.value = nextNr
  // Aufgaben-Struktur beibehalten, aber Antworten leeren
  aufgaben.value = aufgaben.value.map(a => ({
    id: 0,
    aufgabe: a.aufgabe,
    antwort_text: '',
    notiz: getFragestellung(a.aufgabe) || '',
    punkte: null,
    max_punkte: a.max_punkte,
    dirty: false,
    saving: false,
    bilder: [],
    uploadingBild: false,
  }))
  showSchluessHints.value = false   // Schlüssel-Anzeige ausblenden bei neuem Durchlauf
  showSchluessEditor.value = false
  wisoAusgewertet.value = false     // Sperre aufheben bei neuem Durchlauf
  resetTimer()
  snackbarText.value = `Durchlauf ${nextNr} gestartet`
  snackbarColor.value = 'info'
  snackbar.value = true
}

async function wechsleDurchlauf(nr: number) {
  if (nr === aktiverDurchlauf.value) return
  if (hasUnsaved.value) {
    if (!confirm('Es gibt ungespeicherte Änderungen. Trotzdem wechseln?')) return
  }
  aktiverDurchlauf.value = nr
  wisoAusgewertet.value = false
  await loadAntworten(nr)
  // Timer auf gespeicherte Dauer setzen
  const dl = durchlaeufe.value.find(d => d.durchlauf === nr)
  resetTimer()
  if (dl?.dauer_sekunden) timerSeconds.value = dl.dauer_sekunden
}

function formatDauer(sek: number | null): string {
  if (!sek) return '–'
  const h = Math.floor(sek / 3600)
  const m = Math.floor((sek % 3600) / 60)
  const s = sek % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`
}

function toggleLoesung() {
  showLoesung.value = !showLoesung.value
  // Beim Einblenden: passendes Lösungs-Dokument automatisch wählen
  if (showLoesung.value && loesungsDocs.value.length) {
    // Prüfen ob aktuell gewählte Lösung noch im gefilterten Set ist
    if (!loesungsDocs.value.find((d) => d.id === selectedLoesungDocId.value)) {
      selectedLoesungDocId.value = loesungsDocs.value[0].id
    }
  }
}

/* Wenn Aufgaben-Dokument gewechselt wird → Lösung aktualisieren */
watch(selectedDocId, () => {
  if (showLoesung.value && loesungsDocs.value.length) {
    if (!loesungsDocs.value.find((d) => d.id === selectedLoesungDocId.value)) {
      selectedLoesungDocId.value = loesungsDocs.value[0].id
    }
  }
})
</script>

<template>
  <div class="bearbeiten-page">
    <!-- Toolbar -->
    <v-card class="mb-2" elevation="2">
      <v-toolbar density="compact" color="orange-darken-2" flat>
        <v-btn icon="mdi-arrow-left" variant="text" @click="router.push(`/pruefungen/${id}`)" />
        <v-toolbar-title v-if="pruefung" class="text-body-1 font-weight-bold">
          <v-icon class="mr-1">mdi-pencil-box-outline</v-icon>
          {{ pruefung.zeitraum_label }} – Prüfung bearbeiten
        </v-toolbar-title>
        <v-spacer />

        <!-- Punkte-Anzeige -->
        <v-chip v-if="isWiso && wisoStats" color="white" variant="flat" size="small" class="mr-2 font-weight-bold">
          <v-icon start size="16" color="green-lighten-3">mdi-check-bold</v-icon>
          {{ wisoStats.richtig }}/{{ wisoTasks.length }} – {{ wisoStats.punkte.toFixed(1) }} / {{ wisoStats.max.toFixed(0) }} P. ({{ wisoStats.prozent }}%)
        </v-chip>
        <v-chip v-else-if="gesamtPunkte" color="white" variant="flat" size="small" class="mr-2 font-weight-bold">
          {{ gesamtPunkte.punkte }} / {{ gesamtPunkte.max }} P. ({{ gesamtPunkte.prozent }}%)
        </v-chip>

        <!-- Alle speichern -->
        <v-btn
          v-if="hasUnsaved"
          color="white"
          variant="outlined"
          size="small"
          prepend-icon="mdi-content-save-all"
          :loading="saving"
          @click="saveAll"
          class="mr-2"
        >
          Alle speichern ({{ aufgaben.filter(a => a.dirty).length }})
        </v-btn>

        <v-chip variant="tonal" color="white" size="small" class="mr-2">
          {{ aufgaben.length }} Aufgaben
        </v-chip>

        <!-- Timer -->
        <v-chip
          :color="timerRunning ? 'green-lighten-3' : 'white'"
          :variant="timerRunning ? 'flat' : 'outlined'"
          size="small"
          class="mr-2 font-weight-bold timer-chip"
          @click="toggleTimer"
          style="cursor: pointer; min-width: 90px; justify-content: center"
        >
          <v-icon start size="16">{{ timerRunning ? 'mdi-pause' : 'mdi-play' }}</v-icon>
          {{ timerFormatted }}
        </v-chip>
        <v-btn
          v-if="timerSeconds > 0"
          icon="mdi-timer-off-outline"
          size="x-small"
          variant="text"
          color="white"
          title="Timer zurücksetzen"
          @click.stop="resetTimer"
          class="mr-2"
        />

        <!-- KI-Bewertung -->
        <v-btn
          color="white"
          variant="outlined"
          size="small"
          prepend-icon="mdi-robot"
          class="mr-2"
          :to="`/bewertung/${id}`"
        >
          KI-Bewertung
        </v-btn>

        <!-- OCR-Analyse: Bearbeitete PDF auslesen -->
        <v-btn
          v-if="!isWiso && selectedDocId"
          color="amber-lighten-2"
          variant="flat"
          size="small"
          prepend-icon="mdi-text-recognition"
          class="mr-2"
          :loading="ocrAnalysing"
          @click="ocrAnalyseDokument"
        >
          {{ ocrAnalysing ? ocrProgress : 'PDF analysieren (OCR)' }}
        </v-btn>

        <!-- Fragen aus DB laden -->
        <v-btn
          v-if="!isWiso && bereichMusterloesungen.length"
          color="blue-lighten-2"
          variant="flat"
          size="small"
          prepend-icon="mdi-help-circle-outline"
          class="mr-2"
          @click="loadFragenFromMusterloesungen"
        >
          Fragen laden ({{ activePruefungsbereich || 'GA1' }})
        </v-btn>

        <!-- Fragen per KI aus Aufgabe-PDF extrahieren -->
        <v-btn
          v-if="selectedDocId"
          color="teal-lighten-2"
          variant="flat"
          size="small"
          prepend-icon="mdi-brain"
          class="mr-2"
          :loading="extractingFragen"
          @click="extractFragenFromPdf"
        >
          {{ extractingFragen ? 'Fragen werden extrahiert...' : 'Fragen extrahieren (KI)' }}
        </v-btn>

        <!-- Lösungen aus Lösung/Handreichung-PDF per KI extrahieren -->
        <v-btn
          v-if="loesungsDocs.length"
          color="orange-lighten-2"
          variant="flat"
          size="small"
          prepend-icon="mdi-lightbulb-on"
          class="mr-2"
          :loading="extractingLoesungen"
          @click="extractLoesungenFromPdf"
        >
          {{ extractingLoesungen ? 'Lösungen werden extrahiert...' : 'Lösungen extrahieren (KI)' }}
        </v-btn>

        <!-- Lösung einblenden -->
        <v-btn
          v-if="loesungsDocs.length"
          :color="showLoesung ? 'green-lighten-3' : 'white'"
          :variant="showLoesung ? 'flat' : 'outlined'"
          size="small"
          :prepend-icon="showLoesung ? 'mdi-eye-off' : 'mdi-check-circle-outline'"
          @click="toggleLoesung"
        >
          {{ showLoesung ? 'Lösung ausblenden' : 'Lösung einblenden' }}
        </v-btn>
      </v-toolbar>
    </v-card>

    <v-progress-linear v-if="loading" indeterminate color="orange" />

    <!-- Split View -->
    <div v-if="!loading && pruefung" class="split-container">
      <!-- ═══ LINKE SEITE: PDF ═══ -->
      <div class="pdf-panel">
        <!-- Dokument-Auswahl -->
        <div class="pdf-toolbar d-flex align-center ga-2 pa-2">
          <v-select
            v-model="selectedDocId"
            :items="allDocs"
            item-title="dateiname"
            item-value="id"
            label="Dokument"
            variant="outlined"
            density="compact"
            hide-details
            :return-object="false"
            style="max-width: 350px"
          />
          <v-btn
            icon="mdi-open-in-new"
            size="small"
            variant="text"
            color="primary"
            :href="selectedDocId ? `/api/dokumente/${selectedDocId}/pdf` : undefined"
            target="_blank"
            title="PDF in neuem Tab"
          />
          <v-spacer />
          <v-btn icon="mdi-chevron-left" size="small" variant="text" @click="goToPage(Math.max(1, pdfPage - 1))" title="Vorherige Seite" />
          <v-text-field
            v-model.number="pdfPage"
            type="number"
            variant="outlined"
            density="compact"
            hide-details
            style="max-width: 70px"
            min="1"
            class="text-center"
          />
          <v-btn icon="mdi-chevron-right" size="small" variant="text" @click="goToPage(pdfPage + 1)" title="Nächste Seite" />
        </div>
        <!-- PDF iframe: Aufgabe -->
        <iframe
          v-if="selectedDocId"
          :src="pdfUrl"
          class="pdf-iframe"
          :class="{ 'pdf-iframe-half': showLoesung || previewOpen }"
          title="PDF Aufgabe"
        />
        <div v-else class="d-flex align-center justify-center fill-height text-medium-emphasis">
          <div class="text-center">
            <v-icon size="64" color="grey">mdi-file-pdf-box</v-icon>
            <p class="mt-2">Kein Dokument ausgewählt</p>
          </div>
        </div>

        <!-- Lösungs-PDF (untere Hälfte) -->
        <template v-if="showLoesung && loesungsDocs.length">
          <div class="loesung-toolbar d-flex align-center ga-2 pa-2">
            <v-icon color="success" size="20">mdi-check-circle</v-icon>
            <span class="text-subtitle-2 text-success font-weight-bold">Lösung</span>
            <v-select
              v-model="selectedLoesungDocId"
              :items="loesungsDocs"
              item-title="dateiname"
              item-value="id"
              variant="outlined"
              density="compact"
              hide-details
              style="max-width: 300px"
            />
            <v-btn
              icon="mdi-open-in-new"
              size="small"
              variant="text"
              color="success"
              :href="selectedLoesungDocId ? `/api/dokumente/${selectedLoesungDocId}/pdf` : undefined"
              target="_blank"
              title="Lösung in neuem Tab"
            />
            <v-spacer />
            <v-btn icon="mdi-chevron-left" size="small" variant="text" @click="goToLoesungPage(Math.max(1, loesungPage - 1))" />
            <v-text-field
              v-model.number="loesungPage"
              type="number"
              variant="outlined"
              density="compact"
              hide-details
              style="max-width: 60px"
              min="1"
            />
            <v-btn icon="mdi-chevron-right" size="small" variant="text" @click="goToLoesungPage(loesungPage + 1)" />
          </div>
          <iframe
            v-if="selectedLoesungDocId"
            :src="loesungPdfUrl"
            class="pdf-iframe pdf-iframe-half"
            title="PDF Lösung"
          />
        </template>

        <!-- ═══ Meine Lösung Vorschau (untere Hälfte) ═══ -->
        <template v-if="previewOpen">
          <div class="preview-toolbar d-flex align-center ga-2 pa-2">
            <v-icon color="info" size="20">mdi-image-outline</v-icon>
            <span class="text-subtitle-2 text-info font-weight-bold">Meine Lösung</span>
            <span class="text-caption text-medium-emphasis text-truncate" style="max-width: 250px">
              {{ previewTitle }}
            </span>
            <v-btn
              icon="mdi-open-in-new"
              size="small"
              variant="text"
              color="info"
              :href="previewUrl"
              target="_blank"
              title="In neuem Tab öffnen"
            />
            <v-spacer />
            <v-btn
              icon="mdi-fullscreen"
              size="small"
              variant="text"
              color="info"
              title="Vollbild"
              @click="lightboxUrl = previewUrl; lightboxTitle = previewTitle; lightboxOpen = true"
            />
            <v-btn
              icon="mdi-close"
              size="small"
              variant="text"
              color="grey"
              title="Vorschau schließen"
              @click="closePreview"
            />
          </div>
          <!-- PDF-Vorschau -->
          <iframe
            v-if="previewIsPdf"
            :src="previewUrl"
            class="pdf-iframe pdf-iframe-half"
            title="Meine Lösung (PDF)"
          />
          <!-- Bild-Vorschau -->
          <div
            v-else
            class="preview-img-container pdf-iframe-half d-flex align-center justify-center"
          >
            <img
              :src="previewUrl"
              :alt="previewTitle"
              class="preview-img"
              @click="lightboxUrl = previewUrl; lightboxTitle = previewTitle; lightboxOpen = true"
            />
          </div>
        </template>
      </div>

      <!-- ═══ RECHTE SEITE: WISO Editor ═══ -->
      <div v-if="isWiso" class="editor-panel wiso-editor">
        <!-- WISO Toolbar -->
        <div class="pa-3 wiso-toolbar-bar">
          <div class="d-flex align-center ga-2 flex-wrap">
            <v-chip color="purple" variant="flat" size="small" label class="font-weight-bold">
              <v-icon start size="16">mdi-checkbox-marked-circle</v-icon>
              WISO Modus
            </v-chip>

            <!-- Durchlauf-Auswahl -->
            <v-chip
              color="purple-lighten-3"
              variant="flat"
              size="small"
              label
              class="font-weight-bold"
            >
              Durchlauf {{ aktiverDurchlauf }}
            </v-chip>

            <!-- Durchlauf-Wechsel Buttons -->
            <template v-if="durchlaeufe.length > 1">
              <v-btn
                v-for="dl in durchlaeufe"
                :key="dl.durchlauf"
                :color="dl.durchlauf === aktiverDurchlauf ? 'purple' : 'grey'"
                :variant="dl.durchlauf === aktiverDurchlauf ? 'flat' : 'outlined'"
                size="x-small"
                @click="wechsleDurchlauf(dl.durchlauf)"
                class="px-1"
                style="min-width: 28px"
              >
                {{ dl.durchlauf }}
              </v-btn>
            </template>

            <v-chip v-if="wisoStats" color="green" variant="tonal" size="x-small">
              <v-icon start size="14">mdi-check</v-icon> {{ wisoStats.richtig }}
            </v-chip>
            <v-chip v-if="wisoStats" color="red" variant="tonal" size="x-small">
              <v-icon start size="14">mdi-close</v-icon> {{ wisoStats.falsch }}
            </v-chip>
            <v-spacer />

            <v-btn
              v-if="wisoTasks.length < 30"
              color="purple"
              variant="flat"
              size="small"
              prepend-icon="mdi-lightning-bolt"
              @click="generateWisoAufgaben"
            >
              {{ wisoTasks.length === 0 ? '30 Aufgaben' : `Fehlende ergänzen (${30 - wisoTasks.length})` }}
            </v-btn>
            <v-btn
              v-if="hasUnsaved"
              color="purple"
              variant="outlined"
              size="small"
              prepend-icon="mdi-content-save-all"
              :loading="saving"
              @click="saveAll"
            >
              Speichern ({{ aufgaben.filter(a => a.dirty).length }})
            </v-btn>

            <!-- Neuer Durchlauf -->
            <v-btn
              color="purple-darken-1"
              variant="tonal"
              size="small"
              prepend-icon="mdi-replay"
              @click="startNeuerDurchlauf"
            >
              Neuer Durchlauf
            </v-btn>

            <!-- Lösungsschlüssel laden (nur wenn noch kein Schlüssel vorhanden) -->
            <v-btn
              v-if="loesungsDocs.length && !hasLoesungsschluessel"
              color="purple-lighten-1"
              variant="tonal"
              size="small"
              prepend-icon="mdi-key-variant"
              :loading="loesungLoading"
              @click="loadLoesungsschluessel"
            >
              Schlüssel laden
            </v-btn>

            <!-- Schlüssel-Status (wenn bereits geladen) -->
            <v-chip
              v-if="hasLoesungsschluessel"
              color="green"
              size="small"
              prepend-icon="mdi-key-check"
            >
              Schlüssel ✓ ({{ Object.keys(loesungsschluessel).length }})
            </v-chip>

            <!-- Schlüssel bearbeiten -->
            <v-btn
              v-if="hasLoesungsschluessel || wisoTasks.length"
              :color="showSchluessEditor ? 'orange' : 'purple-lighten-2'"
              :variant="showSchluessEditor ? 'flat' : 'tonal'"
              size="small"
              :prepend-icon="showSchluessEditor ? 'mdi-pencil-off' : 'mdi-pencil'"
              @click="showSchluessEditor ? (showSchluessEditor = false) : openSchluessEditor()"
            >
              {{ showSchluessEditor ? 'Editor schließen' : 'Schlüssel bearbeiten' }}
            </v-btn>

            <!-- Auswerten -->
            <v-btn
              v-if="wisoTasks.length && loesungsDocs.length && !wisoAusgewertet"
              color="green-darken-1"
              variant="flat"
              size="small"
              prepend-icon="mdi-check-decagram"
              :loading="loesungLoading"
              @click="auswerten"
            >
              Auswerten
            </v-btn>

            <!-- Gesperrt-Hinweis -->
            <v-chip
              v-if="wisoAusgewertet"
              color="orange"
              variant="flat"
              size="small"
              prepend-icon="mdi-lock"
            >
              Ausgewertet &ndash; gesperrt
            </v-chip>

            <!-- Schlüssel ein-/ausblenden -->
            <v-btn
              v-if="hasLoesungsschluessel"
              :color="showSchluessHints ? 'orange' : 'grey'"
              :variant="showSchluessHints ? 'flat' : 'outlined'"
              size="small"
              :prepend-icon="showSchluessHints ? 'mdi-eye' : 'mdi-eye-off'"
              @click="showSchluessHints = !showSchluessHints"
              :title="showSchluessHints ? 'Lösungen ausblenden' : 'Lösungen einblenden'"
            >
              {{ showSchluessHints ? 'Lösungen ✓' : 'Lösungen' }}
            </v-btn>

            <!-- Statistik -->
            <v-btn
              v-if="durchlaeufe.length > 0"
              :color="showDurchlaufStats ? 'purple' : 'grey'"
              :variant="showDurchlaufStats ? 'flat' : 'outlined'"
              size="small"
              :icon="showDurchlaufStats ? 'mdi-chart-bar' : 'mdi-chart-bar'"
              @click="showDurchlaufStats = !showDurchlaufStats"
              title="Durchlauf-Vergleich"
            />
          </div>
        </div>

        <!-- Lösungsschlüssel-Editor Panel -->
        <div v-if="showSchluessEditor" class="schluessel-editor-panel pa-3">
          <div class="d-flex align-center mb-2">
            <v-icon color="orange" size="20" class="mr-2">mdi-key-variant</v-icon>
            <span class="text-subtitle-2 font-weight-bold text-orange-darken-2">Lösungsschlüssel bearbeiten</span>
            <v-spacer />
            <v-btn
              :color="showJsonImport ? 'blue' : 'blue-grey'"
              :variant="showJsonImport ? 'flat' : 'tonal'"
              size="x-small"
              prepend-icon="mdi-code-json"
              @click="showJsonImport = !showJsonImport"
              title="JSON einfügen"
            >
              JSON
            </v-btn>
            <v-btn
              color="red"
              variant="text"
              size="x-small"
              prepend-icon="mdi-delete"
              @click="clearSchluessel"
              title="Schlüssel löschen"
              class="ml-1"
            >
              Löschen
            </v-btn>
            <v-btn
              color="green"
              variant="flat"
              size="small"
              prepend-icon="mdi-check"
              class="ml-2"
              @click="applySchluessEdits"
            >
              Übernehmen & Auswerten
            </v-btn>
          </div>

          <!-- JSON-Import Bereich -->
          <div v-if="showJsonImport" class="json-import-area mb-3 pa-2 rounded" style="background: #1a237e22; border: 1px solid #3f51b5;">
            <div class="text-caption text-blue-grey-lighten-1 mb-1">
              JSON einfügen — Format: <code>{ "answers": { "1": "4", "2": "[3;5]", ... }, "types": { "1": "mc", ... } }</code>
            </div>
            <v-textarea
              v-model="jsonImportText"
              variant="outlined"
              density="compact"
              rows="6"
              placeholder='{ "answers": { "1": "4", "2": "[3;5]", "3": "15.06.2013" }, "types": { "1": "mc", "2": "mc-multi", "3": "datum" } }'
              hide-details
              class="mb-2"
              style="font-family: monospace; font-size: 12px"
            />
            <div class="d-flex justify-end">
              <v-btn
                color="grey"
                variant="text"
                size="small"
                @click="showJsonImport = false; jsonImportText = ''"
              >
                Abbrechen
              </v-btn>
              <v-btn
                color="blue"
                variant="flat"
                size="small"
                prepend-icon="mdi-import"
                class="ml-2"
                @click="importSchluessFromJson"
              >
                Importieren
              </v-btn>
            </div>
          </div>

          <!-- Aufgaben-Liste mit Typ-Auswahl -->
          <div class="schluessel-list">
            <div
              v-for="n in 30"
              :key="n"
              class="schluessel-row d-flex align-center pa-1 rounded mb-1"
              :class="{ 'schluessel-row-filled': entryToValue(schluesselEntries[String(n)] || { type: 'mc', mc: '', mcMulti: ['',''], betrag: '', zuordnung: ['','','','',''] }) !== '' }"
            >
              <!-- Aufgaben-Nummer -->
              <v-chip
                color="purple"
                variant="flat"
                size="x-small"
                label
                class="font-weight-bold mr-2"
                style="min-width: 28px; justify-content: center"
              >
                {{ n }}
              </v-chip>

              <!-- Typ-Auswahl -->
              <v-btn-toggle
                :model-value="schluesselEntries[String(n)]?.type || 'mc'"
                mandatory
                density="compact"
                divided
                class="mr-2 schluessel-type-toggle"
                @update:model-value="(v: AnswerType) => changeEntryType(String(n), v)"
              >
                <v-btn value="mc" size="x-small" title="MC (1 Antwort)">MC</v-btn>
                <v-btn value="mc-multi" size="x-small" title="MC (mehrere gültig)">MC+</v-btn>
                <v-btn value="betrag" size="x-small" title="Geldbetrag / Text">€</v-btn>
                <v-btn value="datum" size="x-small" title="Datum">📅</v-btn>
                <v-btn value="zahl" size="x-small" title="Zahl (Ganzzahl)">123</v-btn>
                <v-btn value="zuordnung" size="x-small" title="Zuordnung a=Zahl">A=Z</v-btn>
              </v-btn-toggle>

              <!-- Eingabefelder je nach Typ -->
              <div class="schluessel-fields d-flex align-center ga-1 flex-wrap flex-grow-1">
                <!-- MC: Ein Feld -->
                <template v-if="schluesselEntries[String(n)]?.type === 'mc'">
                  <v-text-field
                    v-model="schluesselEntries[String(n)].mc"
                    density="compact"
                    variant="outlined"
                    hide-details
                    placeholder="z.B. 3"
                    class="schluessel-input"
                    @keydown.enter="applySchluessEdits"
                  />
                </template>

                <!-- MC-Multi: Mehrere Felder -->
                <template v-else-if="schluesselEntries[String(n)]?.type === 'mc-multi'">
                  <v-text-field
                    v-for="(_, mi) in schluesselEntries[String(n)].mcMulti"
                    :key="mi"
                    v-model="schluesselEntries[String(n)].mcMulti[mi]"
                    density="compact"
                    variant="outlined"
                    hide-details
                    :placeholder="'Antwort ' + (mi + 1)"
                    class="schluessel-input-sm"
                    @keydown.enter="applySchluessEdits"
                  />
                  <v-btn icon="mdi-plus" size="x-small" variant="text" color="green" density="compact" @click="addMcMultiField(String(n))" />
                  <v-btn icon="mdi-minus" size="x-small" variant="text" color="red" density="compact" @click="removeMcMultiField(String(n))" v-if="(schluesselEntries[String(n)]?.mcMulti.length || 0) > 2" />
                </template>

                <!-- Betrag: Ein Freitextfeld -->
                <template v-else-if="schluesselEntries[String(n)]?.type === 'betrag'">
                  <v-text-field
                    v-model="schluesselEntries[String(n)].betrag"
                    density="compact"
                    variant="outlined"
                    hide-details
                    placeholder="z.B. 2.992,88"
                    class="schluessel-input-lg"
                    @keydown.enter="applySchluessEdits"
                  />
                </template>

                <!-- Datum: Textfeld für Datum -->
                <template v-else-if="schluesselEntries[String(n)]?.type === 'datum'">
                  <v-text-field
                    v-model="schluesselEntries[String(n)].datum"
                    density="compact"
                    variant="outlined"
                    hide-details
                    placeholder="z.B. 15.06.13"
                    class="schluessel-input-lg"
                    @keydown.enter="applySchluessEdits"
                  >
                    <template #prepend-inner>
                      <v-icon size="14" color="grey">mdi-calendar</v-icon>
                    </template>
                  </v-text-field>
                </template>

                <!-- Zahl: Ein numerisches Freitextfeld -->
                <template v-else-if="schluesselEntries[String(n)]?.type === 'zahl'">
                  <v-text-field
                    v-model="schluesselEntries[String(n)].zahl"
                    density="compact"
                    variant="outlined"
                    hide-details
                    placeholder="z.B. 42"
                    class="schluessel-input"
                    @keydown.enter="applySchluessEdits"
                  >
                    <template #prepend-inner>
                      <v-icon size="14" color="grey">mdi-numeric</v-icon>
                    </template>
                  </v-text-field>
                </template>

                <!-- Zuordnung: Ein Feld pro Buchstabe -->
                <template v-else-if="schluesselEntries[String(n)]?.type === 'zuordnung'">
                  <div
                    v-for="(_, zi) in schluesselEntries[String(n)].zuordnung"
                    :key="zi"
                    class="d-flex align-center"
                  >
                    <span class="text-caption font-weight-bold text-purple mr-1">{{ String.fromCharCode(97 + zi) }})</span>
                    <v-text-field
                      v-model="schluesselEntries[String(n)].zuordnung[zi]"
                      density="compact"
                      variant="outlined"
                      hide-details
                      placeholder="Nr / Betrag"
                      class="schluessel-input-xs"
                      style="min-width: 80px"
                      @keydown.enter="applySchluessEdits"
                    />
                  </div>
                  <v-btn icon="mdi-plus" size="x-small" variant="text" color="green" density="compact" @click="addZuordnungField(String(n))" />
                  <v-btn icon="mdi-minus" size="x-small" variant="text" color="red" density="compact" @click="removeZuordnungField(String(n))" v-if="(schluesselEntries[String(n)]?.zuordnung.length || 0) > 2" />
                </template>
              </div>
            </div>
          </div>
        </div>

        <!-- Durchlauf-Vergleich Panel -->
        <div v-if="showDurchlaufStats && durchlaeufe.length" class="durchlauf-stats-panel pa-3">
          <div class="d-flex align-center mb-2">
            <v-icon color="purple" size="20" class="mr-2">mdi-chart-timeline-variant-shimmer</v-icon>
            <span class="text-subtitle-2 font-weight-bold text-purple">Durchlauf-Vergleich</span>
          </div>
          <v-table density="compact" class="durchlauf-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Richtig</th>
                <th>Falsch</th>
                <th>Punkte</th>
                <th>%</th>
                <th>Dauer</th>
                <th>Datum</th>
                <th>Trend</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(dl, idx) in durchlaeufe"
                :key="dl.durchlauf"
                :class="{
                  'durchlauf-active': dl.durchlauf === aktiverDurchlauf,
                  'cursor-pointer': true,
                }"
                @click="wechsleDurchlauf(dl.durchlauf)"
              >
                <td class="font-weight-bold">{{ dl.durchlauf }}</td>
                <td>
                  <span class="text-green font-weight-bold">{{ dl.richtig }}</span>
                  <span class="text-grey"> / {{ dl.aufgaben }}</span>
                </td>
                <td>
                  <span class="text-red font-weight-bold">{{ dl.falsch }}</span>
                </td>
                <td class="font-weight-bold">
                  {{ dl.summe_punkte.toFixed(1) }} / {{ dl.summe_max.toFixed(0) }}
                </td>
                <td>
                  <v-chip
                    :color="dl.summe_max ? (dl.summe_punkte / dl.summe_max >= 0.5 ? 'green' : 'red') : 'grey'"
                    variant="tonal"
                    size="x-small"
                    class="font-weight-bold"
                  >
                    {{ dl.summe_max ? ((dl.summe_punkte / dl.summe_max) * 100).toFixed(0) : 0 }}%
                  </v-chip>
                </td>
                <td class="text-caption">{{ formatDauer(dl.dauer_sekunden) }}</td>
                <td class="text-caption">{{ new Date(dl.datum).toLocaleDateString('de-DE') }}</td>
                <td>
                  <template v-if="idx > 0">
                    <v-icon
                      v-if="dl.richtig > durchlaeufe[idx - 1].richtig"
                      color="green"
                      size="18"
                    >mdi-trending-up</v-icon>
                    <v-icon
                      v-else-if="dl.richtig < durchlaeufe[idx - 1].richtig"
                      color="red"
                      size="18"
                    >mdi-trending-down</v-icon>
                    <v-icon v-else color="grey" size="18">mdi-trending-neutral</v-icon>
                    <span
                      class="text-caption ml-1 font-weight-bold"
                      :class="dl.richtig >= durchlaeufe[idx - 1].richtig ? 'text-green' : 'text-red'"
                    >
                      {{ dl.richtig >= durchlaeufe[idx - 1].richtig ? '+' : '' }}{{ dl.richtig - durchlaeufe[idx - 1].richtig }}
                    </span>
                  </template>
                  <span v-else class="text-caption text-grey">–</span>
                </td>
              </tr>
            </tbody>
          </v-table>
        </div>

        <!-- WISO Aufgaben-Liste -->
        <div class="aufgaben-list">
          <!-- Sperr-Hinweis nach Auswertung -->
          <v-alert
            v-if="wisoAusgewertet && wisoTasks.length"
            type="info"
            variant="tonal"
            density="compact"
            class="mx-3 mb-3"
            prepend-icon="mdi-lock"
          >
            <strong>Antworten gesperrt.</strong>
            Die Auswertung ist abgeschlossen. Um erneut zu üben, starte einen <strong>neuen Durchlauf</strong>.
          </v-alert>

          <div v-if="!wisoTasks.length" class="text-center text-medium-emphasis pa-8">
            <v-icon size="48" color="purple-lighten-2">mdi-checkbox-marked-circle-outline</v-icon>
            <p class="mt-3">Keine WISO-Aufgaben vorhanden.</p>
            <p class="text-caption">Klicke oben auf "30 Aufgaben" um die Standard-Aufgaben zu generieren.</p>
          </div>

          <div
            v-for="wt in wisoTasks"
            :key="wt.hauptaufgabe.aufgabe"
            class="wiso-task mx-3 mb-2"
          >
            <!-- Hauptaufgabe -->
            <div
              class="wiso-row d-flex align-center pa-2 rounded"
              :class="wisoRowClass(wt.hauptaufgabe)"
            >
              <v-chip
                color="purple"
                variant="flat"
                size="x-small"
                label
                class="font-weight-bold mr-2"
                style="min-width: 32px; justify-content: center"
              >
                {{ wt.hauptaufgabe.aufgabe }}
              </v-chip>

              <!-- Richtig / Falsch Toggle ODER MC-Buttons (nur wenn KEINE Zuordnung) -->
              <template v-if="!wt.isZuordnung">
                <!-- MC-Buttons 1–6 (nur bei MC-Typen anzeigen) -->
                <div v-if="!isFreitextTask(wt.hauptaufgabe.aufgabe)" class="d-flex align-center ga-1">
                  <v-btn
                    v-for="n in 6"
                    :key="n"
                    :color="mcButtonColor(wt.hauptaufgabe, String(n))"
                    :variant="mcButtonVariant(wt.hauptaufgabe, String(n))"
                    size="x-small"
                    class="mc-btn"
                    :disabled="wisoAusgewertet"
                    @click="selectMcAnswer(wt.hauptaufgabe, String(n))"
                  >
                    {{ n }}
                  </v-btn>
                </div>
                <!-- Freitext-Typ-Hinweis (Betrag/Datum/Zahl) -->
                <v-chip
                  v-if="isFreitextTask(wt.hauptaufgabe.aufgabe)"
                  :color="getAnswerType(wt.hauptaufgabe.aufgabe) === 'datum' ? 'blue-lighten-3' : getAnswerType(wt.hauptaufgabe.aufgabe) === 'zahl' ? 'teal-lighten-3' : 'amber-lighten-3'"
                  variant="tonal"
                  size="x-small"
                  label
                  class="mr-1"
                >
                  {{ getAnswerType(wt.hauptaufgabe.aufgabe) === 'datum' ? '📅 Datum' : getAnswerType(wt.hauptaufgabe.aufgabe) === 'zahl' ? '🔢 Zahl' : '€ Betrag' }}
                </v-chip>
                <!-- Korrekte Antwort anzeigen wenn Schlüssel geladen UND sichtbar -->
                <v-chip
                  v-if="showSchluessHints && hasLoesungsschluessel && getCorrectAnswer(wt.hauptaufgabe.aufgabe) && wt.hauptaufgabe.punkte != null"
                  :color="wt.hauptaufgabe.punkte > 0 ? 'green' : 'red'"
                  variant="tonal"
                  size="x-small"
                  class="ml-1 font-weight-bold"
                  :title="wt.hauptaufgabe.punkte > 0 ? 'Richtig!' : 'Richtige Antwort: ' + getCorrectAnswer(wt.hauptaufgabe.aufgabe)"
                >
                  <template v-if="wt.hauptaufgabe.punkte > 0">✓</template>
                  <template v-else>→ {{ getCorrectAnswer(wt.hauptaufgabe.aufgabe) }}</template>
                </v-chip>
              </template>

              <!-- Punkte -->
              <span
                class="text-caption ml-2 font-weight-bold"
                :class="{
                  'text-green': wt.hauptaufgabe.punkte != null && wt.hauptaufgabe.punkte > 0,
                  'text-red': wt.hauptaufgabe.punkte != null && wt.hauptaufgabe.punkte === 0,
                  'text-grey': wt.hauptaufgabe.punkte == null,
                }"
              >
                {{ wt.hauptaufgabe.punkte != null ? Number(wt.hauptaufgabe.punkte).toFixed(1) + ' P.' : '–' }}
              </span>

              <v-spacer />

              <!-- Antwort-Feld (adaptiver Placeholder je nach Typ) -->
              <v-text-field
                v-model="wt.hauptaufgabe.antwort_text"
                :placeholder="isFreitextTask(wt.hauptaufgabe.aufgabe) ? (getAnswerType(wt.hauptaufgabe.aufgabe) === 'datum' ? 'TT.MM.JJ' : getAnswerType(wt.hauptaufgabe.aufgabe) === 'zahl' ? 'Zahl eingeben' : 'Betrag eingeben') : 'Antwort / Notiz'"
                variant="plain"
                density="compact"
                hide-details
                :readonly="wisoAusgewertet"
                class="wiso-answer mx-2"
                @update:model-value="markDirty(wt.hauptaufgabe)"
                @blur="isFreitextTask(wt.hauptaufgabe.aufgabe) ? reevaluateAll() : undefined"
              />

              <!-- Inline Schlüssel Anzeige (readonly, nur sichtbar wenn Hints aktiv) -->
              <v-chip
                v-if="showSchluessHints && hasLoesungsschluessel && loesungsschluessel[wt.hauptaufgabe.aufgabe]"
                size="x-small"
                color="orange"
                variant="outlined"
                class="mx-1"
                prepend-icon="mdi-key-variant"
                :title="'Schlüssel: ' + loesungsschluessel[wt.hauptaufgabe.aufgabe]"
              >
                {{ loesungsschluessel[wt.hauptaufgabe.aufgabe] }}
              </v-chip>

              <!-- Zuordnung-Button -->
              <v-btn
                :icon="wt.isZuordnung ? 'mdi-chevron-up' : 'mdi-format-list-group'"
                size="x-small"
                variant="text"
                :color="wt.isZuordnung ? 'purple' : 'grey'"
                :title="wt.isZuordnung ? 'Zuordnung einklappen' : 'Zuordnung (a=1, b=2, ...)'"
                @click="wt.isZuordnung ? removeZuordnung(wt.hauptaufgabe.aufgabe) : addZuordnung(wt.hauptaufgabe.aufgabe)"
              />

              <!-- Status -->
              <v-icon v-if="wt.hauptaufgabe.dirty" color="orange" size="14" class="ml-1">mdi-circle-small</v-icon>
              <v-icon v-else-if="wt.hauptaufgabe.id" color="green" size="14" class="ml-1">mdi-check-circle</v-icon>
            </div>

            <!-- Zuordnung Sub-Tasks -->
            <div v-if="wt.isZuordnung" class="wiso-subs pl-7 mt-1">
              <div
                v-for="sub in wt.subTasks"
                :key="sub.aufgabe"
                class="wiso-sub-row d-flex align-center pa-1 rounded mb-1"
                :class="wisoRowClass(sub)"
              >
                <v-chip color="purple-lighten-3" variant="tonal" size="x-small" label class="font-weight-bold mr-2" style="min-width: 26px; justify-content: center">
                  {{ subIndexToLetter(sub) }}
                </v-chip>
                <!-- MC-Buttons für Sub-Tasks (nur bei reinen Zahlen-Zuordnungen) -->
                <div v-if="!isZuordnungFreitext(wt.hauptaufgabe.aufgabe)" class="d-flex align-center ga-1 flex-wrap">
                  <v-btn
                    v-for="n in zuordnungMaxOption(wt.hauptaufgabe.aufgabe)"
                    :key="n"
                    :color="mcSubButtonColor(wt, sub, String(n))"
                    :variant="mcButtonVariant(sub, String(n))"
                    size="x-small"
                    class="mc-btn"
                    :disabled="wisoAusgewertet"
                    @click="selectMcSubAnswer(wt, sub, String(n))"
                  >
                    {{ n }}
                  </v-btn>
                </div>
                <!-- Korrekte Antwort bei Zuordnung Sub-Tasks (nur wenn Hints sichtbar) -->
                <v-chip
                  v-if="showSchluessHints && hasLoesungsschluessel && getSubCorrectAnswer(wt.hauptaufgabe.aufgabe, sub) != null && sub.punkte != null"
                  :color="sub.punkte > 0 ? 'green' : 'red'"
                  variant="tonal"
                  size="x-small"
                  class="ml-1 font-weight-bold"
                >
                  <template v-if="sub.punkte > 0">✓</template>
                  <template v-else>→ {{ getSubCorrectAnswer(wt.hauptaufgabe.aufgabe, sub) }}</template>
                </v-chip>
                <v-spacer />
                <v-text-field
                  v-model="sub.antwort_text"
                  :placeholder="isZuordnungFreitext(wt.hauptaufgabe.aufgabe) ? 'Betrag / Wert' : 'Zuordnung'"
                  variant="plain"
                  density="compact"
                  hide-details
                  :readonly="wisoAusgewertet"
                  class="wiso-answer mx-2"
                  :style="isZuordnungFreitext(wt.hauptaufgabe.aufgabe) ? 'max-width: 160px' : 'max-width: 80px'"
                  @update:model-value="markDirty(sub)"
                />
                <v-icon v-if="sub.dirty" color="orange" size="14">mdi-circle-small</v-icon>
              </div>
              <div class="d-flex align-center justify-space-between pr-2 mt-1">
                <div class="d-flex align-center ga-1">
                  <v-btn
                    icon="mdi-minus"
                    size="x-small"
                    variant="text"
                    color="red"
                    density="compact"
                    title="Zuordnung entfernen"
                    @click="removeLastZuordnungSub(wt.hauptaufgabe.aufgabe)"
                  />
                  <v-btn
                    icon="mdi-plus"
                    size="x-small"
                    variant="text"
                    color="green"
                    density="compact"
                    title="Zuordnung hinzufügen"
                    @click="addZuordnungSub(wt.hauptaufgabe.aufgabe)"
                  />
                </div>
                <span class="text-caption text-purple">
                  {{ wt.subTasks.filter(s => s.punkte != null && s.punkte > 0).length }} / {{ wt.subTasks.length }} richtig
                </span>
              </div>
            </div>
          </div>

          <!-- WISO Gesamtübersicht -->
          <v-card v-if="wisoStats && wisoTasks.length" class="mx-3 mt-4 mb-3" variant="outlined" color="purple">
            <div class="pa-3">
              <div class="d-flex align-center justify-space-between">
                <span class="text-subtitle-2 font-weight-bold text-purple">Gesamtergebnis</span>
                <span class="text-h6 font-weight-bold text-purple">
                  {{ wisoStats.punkte.toFixed(1) }} / {{ wisoStats.max.toFixed(0) }} Punkte
                </span>
              </div>
              <v-progress-linear
                :model-value="Number(wisoStats.prozent)"
                color="purple"
                height="8"
                rounded
                class="mt-2"
              />
              <div class="d-flex ga-4 mt-2 text-caption">
                <span class="text-green font-weight-bold">✓ {{ wisoStats.richtig }} richtig</span>
                <span class="text-red font-weight-bold">✗ {{ wisoStats.falsch }} falsch</span>
                <span class="text-grey">{{ wisoStats.offen }} offen</span>
                <v-spacer />
                <span class="font-weight-bold">{{ wisoStats.prozent }}%</span>
              </div>
            </div>
          </v-card>
        </div>
      </div>

      <!-- ═══ RECHTE SEITE: Aufgaben-Editor ═══ -->
      <div v-else class="editor-panel">
        <!-- Durchlauf-Toolbar (GA1/GA2) -->
        <div class="pa-3 d-flex align-center ga-2 flex-wrap" style="border-bottom: 1px solid rgba(0,0,0,0.08)">
          <v-chip
            color="orange"
            variant="flat"
            size="small"
            label
            class="font-weight-bold"
          >
            Durchlauf {{ aktiverDurchlauf }}
          </v-chip>

          <!-- Durchlauf-Wechsel Buttons -->
          <template v-if="durchlaeufe.length > 1">
            <v-btn
              v-for="dl in durchlaeufe"
              :key="dl.durchlauf"
              :color="dl.durchlauf === aktiverDurchlauf ? 'orange' : 'grey'"
              :variant="dl.durchlauf === aktiverDurchlauf ? 'flat' : 'outlined'"
              size="x-small"
              @click="wechsleDurchlauf(dl.durchlauf)"
              class="px-1"
              style="min-width: 28px"
            >
              {{ dl.durchlauf }}
            </v-btn>
          </template>

          <v-spacer />

          <v-btn
            v-if="hasUnsaved"
            color="orange"
            variant="outlined"
            size="small"
            prepend-icon="mdi-content-save-all"
            :loading="saving"
            @click="saveAll"
          >
            Speichern ({{ aufgaben.filter(a => a.dirty).length }})
          </v-btn>

          <v-btn
            color="orange-darken-2"
            variant="tonal"
            size="small"
            prepend-icon="mdi-replay"
            @click="startNeuerDurchlauf"
          >
            Neuer Durchlauf
          </v-btn>
        </div>

        <!-- Aufgabe hinzufügen -->
        <div class="pa-3 add-bar">
          <div class="d-flex align-center ga-2">
            <v-text-field
              v-model="newAufgabe"
              label="Aufgabe hinzufügen (z.B. 1a)"
              variant="outlined"
              density="compact"
              hide-details
              @keydown.enter="addAufgabe"
              style="max-width: 220px"
            />
            <v-btn
              color="orange"
              variant="flat"
              size="small"
              prepend-icon="mdi-plus"
              :disabled="!newAufgabe.trim()"
              @click="addAufgabe"
            >
              Hinzufügen
            </v-btn>
            <v-menu>
              <template #activator="{ props: menuProps }">
                <v-btn
                  v-bind="menuProps"
                  variant="tonal"
                  size="small"
                  prepend-icon="mdi-lightning-bolt"
                  color="orange"
                >
                  Schnell
                </v-btn>
              </template>
              <v-list density="compact">
                <v-list-item @click="generateAufgaben('1a, 1b, 1c, 1d')">
                  <v-list-item-title>1a – 1d</v-list-item-title>
                </v-list-item>
                <v-list-item @click="generateAufgaben('1a, 1b, 1c, 1d, 2a, 2b, 2c, 2d')">
                  <v-list-item-title>1a – 2d</v-list-item-title>
                </v-list-item>
                <v-list-item @click="generateAufgaben('1a, 1b, 1c, 1d, 2a, 2b, 2c, 2d, 3a, 3b, 3c, 3d')">
                  <v-list-item-title>1a – 3d</v-list-item-title>
                </v-list-item>
                <v-list-item @click="generateAufgaben('1, 2, 3, 4, 5')">
                  <v-list-item-title>1 – 5</v-list-item-title>
                </v-list-item>
                <v-list-item @click="generateAufgaben('1, 2, 3, 4, 5, 6, 7, 8, 9, 10')">
                  <v-list-item-title>1 – 10</v-list-item-title>
                </v-list-item>
              </v-list>
            </v-menu>
          </div>
        </div>

        <!-- Aufgaben-Liste -->
        <div class="aufgaben-list">
          <div v-if="!aufgaben.length" class="text-center text-medium-emphasis pa-8">
            <v-icon size="48" color="grey">mdi-text-box-plus-outline</v-icon>
            <p class="mt-3">Noch keine Aufgaben angelegt.</p>
            <p class="text-caption">Füge oben Aufgaben hinzu (z.B. 1a, 1b, 2a) und schreibe deine Lösungen.</p>
          </div>

          <v-card
            v-for="(entry, index) in aufgaben"
            :key="entry.aufgabe"
            :id="`aufgabe-${index}`"
            class="aufgabe-card mb-3 mx-3"
            :class="{ 'aufgabe-dirty': entry.dirty }"
            variant="outlined"
          >
            <!-- Aufgaben-Header -->
            <div class="aufgabe-header d-flex align-center pa-2 px-3">
              <v-chip
                color="orange"
                variant="flat"
                size="small"
                label
                class="font-weight-bold mr-2"
              >
                {{ aufgabeDisplayName(entry.aufgabe) }}
              </v-chip>

              <!-- Punkte inline -->
              <v-text-field
                v-model.number="entry.punkte"
                type="number"
                variant="plain"
                density="compact"
                hide-details
                placeholder="Pkt"
                step="0.5"
                style="max-width: 55px"
                class="punkte-input"
                @update:model-value="markDirty(entry)"
              />
              <span class="text-body-2 mx-1">/</span>
              <v-text-field
                v-model.number="entry.max_punkte"
                type="number"
                variant="plain"
                density="compact"
                hide-details
                placeholder="Max"
                step="0.5"
                style="max-width: 55px"
                class="punkte-input"
                @update:model-value="markDirty(entry)"
              />

              <v-spacer />

              <v-chip
                v-if="entry.dirty"
                color="orange"
                variant="tonal"
                size="x-small"
                class="mr-1"
              >
                geändert
              </v-chip>
              <v-chip
                v-else-if="entry.id"
                color="success"
                variant="tonal"
                size="x-small"
                class="mr-1"
              >
                gespeichert
              </v-chip>

              <!-- Speichern -->
              <v-btn
                icon="mdi-content-save"
                size="x-small"
                variant="text"
                :color="entry.dirty ? 'orange' : 'grey'"
                :loading="entry.saving"
                title="Aufgabe speichern"
                @click="saveAufgabe(entry)"
              />
              <!-- Löschen -->
              <v-btn
                icon="mdi-delete-outline"
                size="x-small"
                variant="text"
                color="error"
                title="Aufgabe löschen"
                @click="deleteAufgabe(entry, index)"
              />
            </div>

            <!-- Antwort-Textarea -->
            <div class="px-3 pb-2">
              <!-- Fragestellung aus Musterlösung anzeigen -->
              <div
                v-if="getFragestellung(entry.aufgabe)"
                class="fragestellung-box mb-2 pa-2 rounded text-body-2"
                style="background: #e3f2fd; border-left: 3px solid #1976d2; color: #1565c0"
              >
                <v-icon size="16" color="#1976d2" class="mr-1">mdi-help-circle-outline</v-icon>
                <strong>Fragestellung:</strong> {{ getFragestellung(entry.aufgabe) }}
              </div>
              <v-textarea
                v-model="entry.antwort_text"
                :label="`Lösung für Aufgabe ${aufgabeDisplayName(entry.aufgabe)}`"
                variant="outlined"
                density="compact"
                rows="3"
                auto-grow
                hide-details
                @update:model-value="markDirty(entry)"
              />
              <v-text-field
                v-model="entry.notiz"
                label="Notiz (optional)"
                variant="plain"
                density="compact"
                hide-details
                class="mt-1 notiz-input"
                prepend-inner-icon="mdi-note-text-outline"
                @update:model-value="markDirty(entry)"
              />

              <!-- ═══ Manuelle Punktevergabe ═══ -->
              <div class="d-flex align-center ga-2 mt-2">
                <v-text-field
                  v-model.number="entry.punkte"
                  label="Punkte"
                  type="number"
                  variant="outlined"
                  density="compact"
                  hide-details
                  style="max-width: 100px"
                  :min="0"
                  :max="entry.max_punkte || 100"
                  step="0.5"
                  prepend-inner-icon="mdi-star"
                  @update:model-value="markDirty(entry)"
                />
                <span class="text-body-2 text-grey">/</span>
                <v-text-field
                  v-model.number="entry.max_punkte"
                  label="Max"
                  type="number"
                  variant="outlined"
                  density="compact"
                  hide-details
                  style="max-width: 100px"
                  :min="0"
                  step="0.5"
                  @update:model-value="markDirty(entry)"
                />
                <v-chip
                  v-if="entry.punkte != null && entry.max_punkte"
                  size="small"
                  :color="Number(entry.punkte) / Number(entry.max_punkte) >= 0.5 ? 'success' : 'error'"
                  variant="tonal"
                >
                  {{ ((Number(entry.punkte) / Number(entry.max_punkte)) * 100).toFixed(0) }}%
                </v-chip>
              </div>

              <!-- ═══ Bilder (Fotos / Scans) ═══ -->
              <div class="mt-2 bilder-section">
                <!-- Thumbnail-Galerie -->
                <div v-if="entry.bilder?.length" class="d-flex flex-wrap ga-2 mb-2">
                  <div
                    v-for="bild in entry.bilder"
                    :key="bild.id"
                    class="bild-thumb-wrapper"
                  >
                    <!-- PDF-Thumbnail -->
                    <div
                      v-if="isPdf(bild)"
                      class="pdf-thumb rounded d-flex flex-column align-center justify-center"
                      @click="openLightbox(entry.id!, bild)"
                    >
                      <v-icon size="36" color="red-darken-1">mdi-file-pdf-box</v-icon>
                      <span class="text-caption text-truncate px-1" style="max-width: 110px">
                        {{ bild.dateiname }}
                      </span>
                    </div>
                    <!-- Bild-Thumbnail -->
                    <v-img
                      v-else
                      :src="antwortenApi.bildUrl(entry.id!, bild.id)"
                      :alt="bild.dateiname"
                      width="120"
                      height="90"
                      cover
                      class="bild-thumb rounded"
                      @click="openLightbox(entry.id!, bild)"
                    >
                      <template #placeholder>
                        <div class="d-flex align-center justify-center fill-height">
                          <v-progress-circular indeterminate size="24" />
                        </div>
                      </template>
                    </v-img>
                  </div>
                </div>
                <!-- Upload-Button -->
                <v-btn
                  size="small"
                  variant="tonal"
                  color="primary"
                  prepend-icon="mdi-upload"
                  :loading="entry.uploadingBild"
                  @click="uploadBild(entry)"
                >
                  Bild / PDF hochladen
                </v-btn>
              </div>

              <!-- ═══ KI-Bewertung (inline) ═══ -->
              <template v-if="getBewertungForAufgabe(entry)">
                <v-divider class="mt-3 mb-2" />
                <div
                  class="d-flex align-center ga-2 cursor-pointer"
                  @click="toggleBewertungDetail(index)"
                >
                  <v-icon size="18" color="deep-purple">mdi-robot</v-icon>
                  <span class="text-caption font-weight-bold text-deep-purple">KI-Bewertung</span>
                  <v-chip
                    size="x-small"
                    :color="Number(getBewertungForAufgabe(entry)!.punkte) / Number(getBewertungForAufgabe(entry)!.max_punkte || 1) >= 0.5 ? 'success' : 'error'"
                    variant="tonal"
                  >
                    {{ getBewertungForAufgabe(entry)!.punkte }} / {{ getBewertungForAufgabe(entry)!.max_punkte }} P.
                  </v-chip>
                  <v-chip size="x-small" variant="outlined" color="grey">
                    {{ getBewertungForAufgabe(entry)!.llm_provider }} · {{ getBewertungForAufgabe(entry)!.llm_model }}
                  </v-chip>
                  <v-chip size="x-small" variant="outlined" color="grey">
                    {{ new Date(getBewertungForAufgabe(entry)!.erstellt_am).toLocaleDateString('de-DE') }}
                  </v-chip>
                  <v-spacer />
                  <v-icon size="18">
                    {{ expandedBewertung === index ? 'mdi-chevron-up' : 'mdi-chevron-down' }}
                  </v-icon>
                </div>
                <div v-if="expandedBewertung === index" class="mt-2 pa-2 rounded" style="background: rgba(103,58,183,0.06)">
                  <div class="text-body-2" style="white-space: pre-wrap">{{ getBewertungForAufgabe(entry)!.feedback }}</div>
                </div>
              </template>
            </div>
          </v-card>
        </div>
      </div>
    </div>

    <!-- ══════ Bild-/PDF-Lightbox ══════ -->
    <v-dialog v-model="lightboxOpen" max-width="95vw" max-height="95vh" scrim="black">
      <v-card class="lightbox-card" color="grey-darken-4">
        <v-toolbar density="compact" color="transparent" flat>
          <v-toolbar-title class="text-body-2 text-white">{{ lightboxTitle }}</v-toolbar-title>
          <v-spacer />
          <v-btn
            icon="mdi-open-in-new"
            variant="text"
            color="white"
            size="small"
            :href="lightboxUrl"
            target="_blank"
            title="In neuem Tab öffnen"
          />
          <v-btn icon="mdi-close" variant="text" color="white" @click="lightboxOpen = false" />
        </v-toolbar>
        <v-card-text class="d-flex align-center justify-center pa-0" style="min-height: 400px; max-height: 80vh">
          <!-- PDF in Lightbox -->
          <iframe
            v-if="lightboxTitle.toLowerCase().endsWith('.pdf')"
            :src="lightboxUrl"
            style="width: 100%; height: 80vh; border: none"
            title="PDF Vollansicht"
          />
          <!-- Bild in Lightbox -->
          <img
            v-else
            :src="lightboxUrl"
            :alt="lightboxTitle"
            class="lightbox-img"
          />
        </v-card-text>
      </v-card>
    </v-dialog>

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar" :timeout="2500" :color="snackbarColor" location="bottom right">
      {{ snackbarText }}
    </v-snackbar>
  </div>
</template>

<style scoped>
.bearbeiten-page {
  height: calc(100vh - 80px);
  display: flex;
  flex-direction: column;
}

.split-container {
  flex: 1;
  display: flex;
  gap: 8px;
  min-height: 0;
}

/* ── PDF Panel (links) ── */
.pdf-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 8px;
  background: #f5f5f5;
}

.pdf-toolbar {
  background: white;
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
  flex-shrink: 0;
  position: relative;
  z-index: 10;
}

.pdf-iframe {
  flex: 1;
  width: 100%;
  border: none;
  position: relative;
  z-index: 1;
}
.pdf-iframe-half {
  flex: 1;
  min-height: 0;
}

.loesung-toolbar {
  background: #e8f5e9;
  border-top: 2px solid #4caf50;
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
  flex-shrink: 0;
}

.preview-toolbar {
  background: #e3f2fd;
  border-top: 2px solid #2196f3;
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
  flex-shrink: 0;
}
.preview-img-container {
  background: #fafafa;
  overflow: auto;
  padding: 8px;
}
.preview-img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  cursor: zoom-in;
  border-radius: 4px;
}

/* ── Editor Panel (rechts) ── */
.editor-panel {
  width: 480px;
  min-width: 380px;
  max-width: 560px;
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 8px;
  overflow: hidden;
  background: white;
}

.add-bar {
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
  background: #fff8e1;
  flex-shrink: 0;
}

.aufgaben-list {
  flex: 1;
  overflow-y: auto;
  padding-top: 12px;
  padding-bottom: 12px;
}

/* ── Aufgabe Card ── */
.aufgabe-card {
  transition: border-color 0.2s, box-shadow 0.2s;
}
.aufgabe-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}
.aufgabe-dirty {
  border-color: #fb8c00 !important;
  border-left: 3px solid #fb8c00 !important;
}

.aufgabe-header {
  background: rgba(251, 140, 0, 0.04);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.punkte-input :deep(input) {
  text-align: center;
  font-size: 0.85rem;
}

.notiz-input {
  font-size: 0.8rem;
  opacity: 0.7;
}
.notiz-input:focus-within {
  opacity: 1;
}

/* Responsive: untereinander auf kleinen Bildschirmen */
@media (max-width: 960px) {
  .split-container {
    flex-direction: column;
  }
  .pdf-panel {
    height: 50vh;
  }
  .editor-panel {
    width: 100%;
    max-width: 100%;
    min-width: 0;
  }
}

/* ── WISO Modus ── */
.wiso-toolbar-bar {
  border-bottom: 2px solid #9c27b0;
  background: #f3e5f5;
  flex-shrink: 0;
}

/* ── Schlüssel-Editor ── */
.schluessel-editor-panel {
  background: #fff8e1;
  border-bottom: 2px solid rgba(255, 152, 0, 0.3);
  flex-shrink: 0;
  max-height: 500px;
  overflow-y: auto;
}
.schluessel-list {
  display: flex;
  flex-direction: column;
}
.schluessel-row {
  min-height: 36px;
  border: 1px solid transparent;
  transition: background 0.15s;
}
.schluessel-row:hover {
  background: rgba(255, 152, 0, 0.06);
}
.schluessel-row-filled {
  background: rgba(255, 152, 0, 0.04);
}
.schluessel-type-toggle {
  height: 26px !important;
}
.schluessel-type-toggle .v-btn {
  font-size: 0.65rem !important;
  min-width: 32px !important;
  height: 26px !important;
  padding: 0 4px !important;
  letter-spacing: 0;
}
.schluessel-input {
  max-width: 80px;
}
.schluessel-input-sm {
  max-width: 60px;
}
.schluessel-input-lg {
  max-width: 140px;
}
.schluessel-input-xs {
  max-width: 42px;
}
.schluessel-input :deep(input),
.schluessel-input-sm :deep(input),
.schluessel-input-lg :deep(input),
.schluessel-input-xs :deep(input) {
  font-size: 0.8rem;
  padding: 2px 6px !important;
  min-height: 26px !important;
}
.schluessel-input :deep(.v-field),
.schluessel-input-sm :deep(.v-field),
.schluessel-input-lg :deep(.v-field),
.schluessel-input-xs :deep(.v-field) {
  min-height: 26px !important;
}
.schluessel-input :deep(.v-field__input),
.schluessel-input-sm :deep(.v-field__input),
.schluessel-input-lg :deep(.v-field__input),
.schluessel-input-xs :deep(.v-field__input) {
  min-height: 26px !important;
  padding: 0 6px !important;
}

.durchlauf-stats-panel {
  background: #faf0ff;
  border-bottom: 1px solid rgba(156, 39, 176, 0.2);
  flex-shrink: 0;
  max-height: 260px;
  overflow-y: auto;
}
.durchlauf-table th {
  font-size: 0.72rem !important;
  white-space: nowrap;
  padding: 4px 8px !important;
}
.durchlauf-table td {
  font-size: 0.78rem !important;
  padding: 4px 8px !important;
  white-space: nowrap;
}
.durchlauf-active {
  background: rgba(156, 39, 176, 0.08) !important;
}
.cursor-pointer {
  cursor: pointer;
}

.wiso-row {
  transition: background 0.15s;
  border: 1px solid transparent;
}
.wiso-row:hover {
  background: rgba(0, 0, 0, 0.02);
}
.wiso-correct {
  background: rgba(76, 175, 80, 0.08) !important;
  border-color: rgba(76, 175, 80, 0.2);
}
.wiso-incorrect {
  background: rgba(244, 67, 54, 0.06) !important;
  border-color: rgba(244, 67, 54, 0.15);
}
.wiso-neutral {
  background: transparent;
}
.wiso-answer :deep(input) {
  font-size: 0.82rem;
}
.wiso-sub-row {
  border: 1px solid transparent;
  transition: background 0.15s;
}
.wiso-sub-row:hover {
  background: rgba(0, 0, 0, 0.02);
}

/* ── MC Buttons ── */
.mc-btn {
  min-width: 28px !important;
  width: 28px !important;
  height: 26px !important;
  padding: 0 !important;
  font-size: 0.75rem !important;
  font-weight: bold !important;
  letter-spacing: 0;
}

/* ── Inline Schlüssel Quick-Edit ── */
.schluessel-inline-edit {
  max-width: 70px;
  flex-shrink: 0;
}
.schluessel-inline-edit :deep(input) {
  font-size: 0.72rem;
  padding: 1px 4px !important;
  min-height: 24px !important;
}
.schluessel-inline-edit :deep(.v-field) {
  min-height: 24px !important;
  border-color: rgba(255, 152, 0, 0.3);
}
.schluessel-inline-edit :deep(.v-field__input) {
  min-height: 24px !important;
  padding: 0 4px !important;
}

/* ══════ Bilder-Section ══════ */
.bilder-section {
  border-top: 1px solid rgba(var(--v-border-color), 0.08);
  padding-top: 8px;
}
.bild-thumb-wrapper {
  position: relative;
  display: inline-block;
  border-radius: 6px;
  overflow: hidden;
  cursor: pointer;
  transition: box-shadow 0.15s;
}
.bild-thumb-wrapper:hover {
  box-shadow: 0 0 0 2px rgb(var(--v-theme-primary));
}
.bild-thumb-wrapper:hover .bild-delete-btn {
  opacity: 1;
}
.bild-delete-btn {
  position: absolute;
  top: 2px;
  right: 2px;
  opacity: 0;
  transition: opacity 0.15s;
}
.pdf-thumb {
  width: 120px;
  height: 90px;
  background: rgba(var(--v-theme-surface-variant), 0.35);
  cursor: pointer;
}

/* ══════ Lightbox ══════ */
.lightbox-card {
  overflow: hidden;
}
.lightbox-img {
  max-width: 100%;
  max-height: 80vh;
  object-fit: contain;
}
</style>
