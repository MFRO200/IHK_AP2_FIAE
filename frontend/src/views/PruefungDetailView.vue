<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { pruefungenApi, trefferApi, antwortenApi, dokumenteApi } from '@/services/api'
import type { Pruefung, Treffer, Antwort } from '@/types'

const route = useRoute()
const router = useRouter()
const pruefung = ref<Pruefung | null>(null)
const treffer = ref<Treffer[]>([])
const antworten = ref<Antwort[]>([])
const loading = ref(true)
const saving = ref(false)
const snackbar = ref(false)
const snackbarText = ref('')

/* PDF-Lösung Upload */
const showPdfUpload = ref(false)
const uploadFile = ref<File | null>(null)
const uploading = ref(false)

/* Dokumenttyp-Optionen */
const typOptions = ['Aufgabe', 'Lösung', 'Handreichung', 'Belegsatz']
const typColors: Record<string, string> = {
  Aufgabe: 'primary',
  'Lösung': 'success',
  Handreichung: 'warning',
  Belegsatz: 'purple',
}

/* Dokument verschieben */
const showMoveDialog = ref(false)
const moveDokId = ref<number | null>(null)
const moveDokName = ref('')
const moveTargetPruefungId = ref<number | null>(null)
const moving = ref(false)
const allPruefungen = ref<Pruefung[]>([])

/* Neues Antwort-Formular */
const showNewForm = ref(false)
const newAufgabe = ref('')
const newAntwortText = ref('')
const newNotiz = ref('')
const newPunkte = ref<number | null>(null)
const newMaxPunkte = ref<number | null>(null)

/* Inline-Edit */
const editingId = ref<number | null>(null)
const editAntwortText = ref('')
const editNotiz = ref('')
const editPunkte = ref<number | null>(null)
const editMaxPunkte = ref<number | null>(null)

const id = computed(() => Number(route.params.id))

const docHeaders = [
  { title: 'Dateiname', key: 'dateiname' },
  { title: 'Typ', key: 'typ', width: '120px' },
  { title: 'Seiten', key: 'seitenanzahl', width: '80px' },
  { title: 'Größe', key: 'dateigroesse', width: '120px' },
  { title: 'Aktionen', key: 'actions', sortable: false, width: '200px' },
]

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/** Extrahiert die erste Seitenzahl aus "Seite(n): 2, 7" → 2 */
function parseFirstPage(seiten: string | null | undefined): number | undefined {
  if (!seiten) return undefined
  const match = seiten.match(/(\d+)/)
  return match ? Number(match[1]) : undefined
}

interface BegriffTrefferDoc {
  dokument_id: number
  dateiname: string
  typ: string
  seiten: string
  firstPage: number | undefined
}

interface BegriffGroup {
  name: string
  section: string
  count: number
  dokumente: BegriffTrefferDoc[]
}

/* Treffer nach Suchbegriff gruppiert – mit Dokument-Links */
const trefferByBegriff = computed<BegriffGroup[]>(() => {
  const map = new Map<string, BegriffGroup>()
  for (const t of treffer.value) {
    const name = t.suchbegriff?.begriff || `ID ${t.suchbegriff_id}`
    if (!map.has(name)) {
      map.set(name, {
        name,
        section: t.suchbegriff?.section || '?',
        count: 0,
        dokumente: [],
      })
    }
    const group = map.get(name)!
    group.count += 1
    group.dokumente.push({
      dokument_id: t.dokument_id,
      dateiname: t.dokument?.dateiname || '',
      typ: t.dokument?.typ || '',
      seiten: t.seiten || '',
      firstPage: parseFirstPage(t.seiten),
    })
  }
  return [...map.values()].sort((a, b) => b.count - a.count)
})

onMounted(async () => {
  try {
    const [pruefungData, pruefungenList] = await Promise.all([
      pruefungenApi.getById(id.value),
      pruefungenApi.getAll(),
    ])
    pruefung.value = pruefungData
    allPruefungen.value = pruefungenList

    // Treffer für alle Dokumente dieser Prüfung laden
    const antwortenPromise = antwortenApi.getByPruefung(id.value)
    if (pruefung.value?.dokumente) {
      const allTreffer: Treffer[] = []
      for (const doc of pruefung.value.dokumente) {
        const t = await trefferApi.getAll({ dokumentId: doc.id })
        allTreffer.push(...t)
      }
      treffer.value = allTreffer
    }
    antworten.value = await antwortenPromise
  } catch (e) {
    console.error('Prüfung laden fehlgeschlagen:', e)
  } finally {
    loading.value = false
  }
})

/* ── Antworten CRUD ── */
const gesamtPunkte = computed(() => {
  const bewertet = antworten.value.filter((a) => a.punkte != null && a.max_punkte != null)
  if (!bewertet.length) return null
  const punkte = bewertet.reduce((s, a) => s + Number(a.punkte), 0)
  const max = bewertet.reduce((s, a) => s + Number(a.max_punkte), 0)
  return { punkte, max, prozent: max ? ((punkte / max) * 100).toFixed(1) : '0' }
})

function resetNewForm() {
  newAufgabe.value = ''
  newAntwortText.value = ''
  newNotiz.value = ''
  newPunkte.value = null
  newMaxPunkte.value = null
  showNewForm.value = false
}

async function saveNewAntwort() {
  if (!newAufgabe.value.trim() || !newAntwortText.value.trim()) return
  saving.value = true
  try {
    await antwortenApi.upsert({
      pruefung_id: id.value,
      aufgabe: newAufgabe.value.trim(),
      antwort_text: newAntwortText.value.trim(),
      notiz: newNotiz.value.trim() || undefined,
      punkte: newPunkte.value ?? undefined,
      max_punkte: newMaxPunkte.value ?? undefined,
    })
    antworten.value = await antwortenApi.getByPruefung(id.value)
    resetNewForm()
    snackbarText.value = 'Antwort gespeichert'
    snackbar.value = true
  } catch (e) {
    console.error('Speichern fehlgeschlagen:', e)
    snackbarText.value = 'Fehler beim Speichern'
    snackbar.value = true
  } finally {
    saving.value = false
  }
}

function startEdit(a: Antwort) {
  editingId.value = a.id
  editAntwortText.value = a.antwort_text
  editNotiz.value = a.notiz || ''
  editPunkte.value = a.punkte
  editMaxPunkte.value = a.max_punkte
}

function cancelEdit() {
  editingId.value = null
}

async function saveEdit(a: Antwort) {
  saving.value = true
  try {
    await antwortenApi.update(a.id, {
      antwort_text: editAntwortText.value.trim(),
      notiz: editNotiz.value.trim() || undefined,
      punkte: editPunkte.value ?? undefined,
      max_punkte: editMaxPunkte.value ?? undefined,
    })
    antworten.value = await antwortenApi.getByPruefung(id.value)
    editingId.value = null
    snackbarText.value = 'Antwort aktualisiert'
    snackbar.value = true
  } catch (e) {
    console.error('Update fehlgeschlagen:', e)
    snackbarText.value = 'Fehler beim Aktualisieren'
    snackbar.value = true
  } finally {
    saving.value = false
  }
}

async function deleteAntwort(a: Antwort) {
  if (!confirm(`Antwort "${a.aufgabe}" wirklich löschen?`)) return
  try {
    await antwortenApi.remove(a.id)
    antworten.value = await antwortenApi.getByPruefung(id.value)
    snackbarText.value = 'Antwort gelöscht'
    snackbar.value = true
  } catch (e) {
    console.error('Löschen fehlgeschlagen:', e)
  }
}

/* ── PDF-Lösung Upload ── */
function onPdfChange(files: File[] | File | null) {
  if (Array.isArray(files)) uploadFile.value = files[0] || null
  else uploadFile.value = files
}

async function uploadPdfLoesung() {
  if (!uploadFile.value || !pruefung.value) return
  uploading.value = true
  try {
    await dokumenteApi.upload(
      uploadFile.value,
      pruefung.value.id,
      'Lösung',
      pruefung.value.dokumente?.[0]?.pruefungsbereich || undefined,
    )
    // Prüfung neu laden für aktualisierte Dokumentliste
    pruefung.value = await pruefungenApi.getById(id.value)
    uploadFile.value = null
    showPdfUpload.value = false
    snackbarText.value = 'PDF-Lösung erfolgreich hochgeladen'
    snackbar.value = true
  } catch (e) {
    console.error('Upload fehlgeschlagen:', e)
    snackbarText.value = 'Fehler beim Upload'
    snackbar.value = true
  } finally {
    uploading.value = false
  }
}

async function confirmDeleteDoc(item: any) {
  if (!confirm(`Dokument "${item.dateiname}" wirklich löschen? Diese Aktion kann nicht rückgängig gemacht werden.`)) return
  try {
    await dokumenteApi.remove(item.id)
    snackbarText.value = `"${item.dateiname}" gelöscht`
    snackbar.value = true
    pruefung.value = await pruefungenApi.getById(id.value)
  } catch (e) {
    console.error('Löschen fehlgeschlagen:', e)
    snackbarText.value = 'Fehler beim Löschen'
    snackbar.value = true
  }
}

async function updateDocTyp(docId: number, newTyp: string) {
  try {
    await dokumenteApi.update(docId, { typ: newTyp })
    pruefung.value = await pruefungenApi.getById(id.value)
    snackbarText.value = `Typ geändert zu "${newTyp}"`
    snackbar.value = true
  } catch (e) {
    console.error('Typ-Änderung fehlgeschlagen:', e)
    snackbarText.value = 'Fehler beim Ändern des Typs'
    snackbar.value = true
  }
}

function openMoveDialog(item: any) {
  moveDokId.value = item.id
  moveDokName.value = item.dateiname
  moveTargetPruefungId.value = null
  showMoveDialog.value = true
}

async function doMove() {
  if (!moveDokId.value || !moveTargetPruefungId.value) return
  moving.value = true
  try {
    await dokumenteApi.update(moveDokId.value, {
      pruefung_id: moveTargetPruefungId.value,
    })
    showMoveDialog.value = false
    snackbarText.value = `"${moveDokName.value}" verschoben`
    snackbar.value = true
    // Prüfung neu laden
    pruefung.value = await pruefungenApi.getById(id.value)
  } catch (e) {
    console.error('Verschieben fehlgeschlagen:', e)
    snackbarText.value = 'Fehler beim Verschieben'
    snackbar.value = true
  } finally {
    moving.value = false
  }
}
</script>

<template>
  <div>
    <v-btn
      variant="text"
      prepend-icon="mdi-arrow-left"
      class="mb-4"
      @click="router.push('/pruefungen')"
    >
      Zurück zur Übersicht
    </v-btn>

    <v-progress-linear v-if="loading" indeterminate color="primary" />

    <template v-if="pruefung && !loading">
      <div class="d-flex align-center mb-2">
        <h1 class="text-h4">{{ pruefung.zeitraum_label }}</h1>
        <v-spacer />
        <v-btn
          color="orange-darken-2"
          variant="flat"
          size="large"
          prepend-icon="mdi-pencil-box-outline"
          @click="router.push(`/pruefungen/${id}/bearbeiten`)"
        >
          Prüfung bearbeiten
        </v-btn>
      </div>
      <p class="text-subtitle-1 text-medium-emphasis mb-6">
        Ordner: {{ pruefung.ordner_name }}
      </p>

      <!-- Dokumente -->
      <v-card class="mb-6">
        <v-card-title>
          <v-icon start>mdi-file-pdf-box</v-icon>
          Dokumente ({{ pruefung.dokumente?.length || 0 }})
        </v-card-title>
        <v-data-table
          :headers="docHeaders"
          :items="pruefung.dokumente || []"
          :items-per-page="-1"
          hide-default-footer
          density="compact"
        >
          <template #item.typ="{ item }">
            <v-select
              :model-value="item.typ"
              :items="typOptions"
              variant="outlined"
              density="compact"
              hide-details
              style="max-width: 160px"
              @update:model-value="(val: string) => updateDocTyp(item.id, val)"
            >
              <template #selection="{ item: selItem }">
                <v-chip
                  :color="typColors[selItem.value] || 'grey'"
                  variant="tonal"
                  size="small"
                  label
                >
                  {{ selItem.value }}
                </v-chip>
              </template>
            </v-select>
          </template>
          <template #item.dateigroesse="{ item }">
            {{ formatBytes(item.dateigroesse) }}
          </template>
          <template #item.actions="{ item }">
            <v-btn
              icon="mdi-pencil"
              size="small"
              variant="text"
              color="orange"
              title="Dieses Dokument bearbeiten"
              @click="router.push(`/pruefungen/${id}/bearbeiten?doc=${item.id}`)"
            />
            <v-btn
              icon="mdi-file-eye"
              size="small"
              variant="text"
              color="primary"
              title="PDF anzeigen"
              @click="router.push(`/dokumente/${item.id}/pdf`)"
            />
            <v-btn
              icon="mdi-open-in-new"
              size="small"
              variant="text"
              color="secondary"
              title="In neuem Tab öffnen"
              :href="`/api/dokumente/${item.id}/pdf`"
              target="_blank"
            />
            <v-btn
              icon="mdi-download"
              size="small"
              variant="text"
              color="accent"
              title="PDF herunterladen"
              :href="`/api/dokumente/${item.id}/download`"
            />
            <v-btn
              icon="mdi-swap-horizontal"
              size="small"
              variant="text"
              color="warning"
              title="In andere Prüfung verschieben"
              @click="openMoveDialog(item)"
            />
            <v-btn
              icon="mdi-delete"
              size="small"
              variant="text"
              color="error"
              title="Dokument löschen"
              @click="confirmDeleteDoc(item)"
            />
          </template>
        </v-data-table>
      </v-card>

      <!-- ═══ Meine Lösungen ═══ -->
      <v-card class="mb-6" variant="outlined" color="orange">
        <v-card-title class="d-flex align-center">
          <v-icon start color="orange">mdi-pencil-box-outline</v-icon>
          Meine Lösungen ({{ antworten.length }})
          <v-spacer />
          <template v-if="gesamtPunkte">
            <v-chip color="orange" variant="tonal" size="small" class="mr-2">
              {{ gesamtPunkte.punkte }} / {{ gesamtPunkte.max }} Punkte ({{ gesamtPunkte.prozent }}%)
            </v-chip>
          </template>
          <v-btn
            v-if="!showNewForm"
            color="orange"
            variant="tonal"
            size="small"
            prepend-icon="mdi-plus"
            @click="showNewForm = true"
          >
            Aufgabe hinzufügen
          </v-btn>
        </v-card-title>

        <v-card-text>
          <!-- Neue Antwort Formular -->
          <v-card v-if="showNewForm" variant="outlined" color="orange" class="mb-4 pa-3">
            <div class="text-subtitle-2 mb-2">Neue Aufgabe</div>
            <v-row dense>
              <v-col cols="12" sm="3">
                <v-text-field
                  v-model="newAufgabe"
                  label="Aufgabe (z.B. 1a, 2b)"
                  variant="outlined"
                  density="compact"
                  hide-details
                />
              </v-col>
              <v-col cols="6" sm="2">
                <v-text-field
                  v-model.number="newPunkte"
                  label="Punkte"
                  variant="outlined"
                  density="compact"
                  type="number"
                  step="0.5"
                  hide-details
                />
              </v-col>
              <v-col cols="6" sm="2">
                <v-text-field
                  v-model.number="newMaxPunkte"
                  label="Max Punkte"
                  variant="outlined"
                  density="compact"
                  type="number"
                  step="0.5"
                  hide-details
                />
              </v-col>
            </v-row>
            <v-textarea
              v-model="newAntwortText"
              label="Meine Lösung / Antwort"
              variant="outlined"
              density="compact"
              rows="4"
              auto-grow
              class="mt-3"
              hide-details
            />
            <v-text-field
              v-model="newNotiz"
              label="Notiz (optional)"
              variant="outlined"
              density="compact"
              class="mt-2"
              hide-details
            />
            <div class="d-flex ga-2 mt-3">
              <v-btn
                color="orange"
                variant="flat"
                size="small"
                :loading="saving"
                :disabled="!newAufgabe.trim() || !newAntwortText.trim()"
                @click="saveNewAntwort"
              >
                Speichern
              </v-btn>
              <v-btn variant="text" size="small" @click="resetNewForm">Abbrechen</v-btn>
            </div>
          </v-card>

          <!-- Liste der gespeicherten Antworten -->
          <div v-if="!antworten.length && !showNewForm" class="text-center text-medium-emphasis py-4">
            <v-icon size="40" color="grey">mdi-text-box-outline</v-icon>
            <p class="mt-2">Noch keine Lösungen eingetragen.</p>
            <v-btn color="orange" variant="tonal" size="small" @click="showNewForm = true">
              Erste Aufgabe bearbeiten
            </v-btn>
          </div>

          <v-card
            v-for="a in antworten"
            :key="a.id"
            variant="outlined"
            class="mb-3"
          >
            <v-card-title class="d-flex align-center py-2 text-subtitle-1">
              <v-chip color="orange" variant="flat" size="small" label class="mr-2 font-weight-bold">
                {{ a.aufgabe }}
              </v-chip>
              <template v-if="a.punkte != null && a.max_punkte != null">
                <v-chip
                  :color="Number(a.punkte) / Number(a.max_punkte) >= 0.5 ? 'success' : 'error'"
                  variant="tonal"
                  size="small"
                >
                  {{ a.punkte }} / {{ a.max_punkte }} P.
                </v-chip>
              </template>
              <v-spacer />
              <span class="text-caption text-medium-emphasis mr-2">
                {{ new Date(a.updated_am).toLocaleDateString('de-DE') }}
              </span>
              <v-btn
                v-if="editingId !== a.id"
                icon="mdi-pencil"
                size="x-small"
                variant="text"
                color="orange"
                @click="startEdit(a)"
              />
              <v-btn
                icon="mdi-delete"
                size="x-small"
                variant="text"
                color="error"
                @click="deleteAntwort(a)"
              />
            </v-card-title>

            <!-- Ansichtsmodus -->
            <v-card-text v-if="editingId !== a.id" class="pt-0">
              <pre class="antwort-text">{{ a.antwort_text }}</pre>
              <div v-if="a.notiz" class="text-caption text-medium-emphasis mt-2">
                <v-icon size="14" class="mr-1">mdi-note-text</v-icon>{{ a.notiz }}
              </div>
            </v-card-text>

            <!-- Bearbeitungsmodus -->
            <v-card-text v-else class="pt-0">
              <v-row dense class="mb-2">
                <v-col cols="6" sm="3">
                  <v-text-field
                    v-model.number="editPunkte"
                    label="Punkte"
                    variant="outlined"
                    density="compact"
                    type="number"
                    step="0.5"
                    hide-details
                  />
                </v-col>
                <v-col cols="6" sm="3">
                  <v-text-field
                    v-model.number="editMaxPunkte"
                    label="Max Punkte"
                    variant="outlined"
                    density="compact"
                    type="number"
                    step="0.5"
                    hide-details
                  />
                </v-col>
              </v-row>
              <v-textarea
                v-model="editAntwortText"
                label="Lösung"
                variant="outlined"
                density="compact"
                rows="4"
                auto-grow
                hide-details
              />
              <v-text-field
                v-model="editNotiz"
                label="Notiz"
                variant="outlined"
                density="compact"
                class="mt-2"
                hide-details
              />
              <div class="d-flex ga-2 mt-2">
                <v-btn color="orange" variant="flat" size="small" :loading="saving" @click="saveEdit(a)">
                  Speichern
                </v-btn>
                <v-btn variant="text" size="small" @click="cancelEdit">Abbrechen</v-btn>
              </div>
            </v-card-text>
          </v-card>
        </v-card-text>

        <!-- PDF-Lösung hochladen -->
        <v-divider />
        <v-card-text>
          <div class="d-flex align-center">
            <v-icon color="orange" class="mr-2">mdi-file-upload-outline</v-icon>
            <span class="text-subtitle-2">Bearbeitete PDF als Lösung hochladen</span>
            <v-spacer />
            <v-btn
              v-if="!showPdfUpload"
              color="orange"
              variant="tonal"
              size="small"
              prepend-icon="mdi-upload"
              @click="showPdfUpload = true"
            >
              PDF hochladen
            </v-btn>
          </div>
          <v-expand-transition>
            <div v-if="showPdfUpload" class="mt-3">
              <v-file-input
                label="Bearbeitete PDF auswählen"
                accept=".pdf"
                prepend-icon="mdi-file-pdf-box"
                variant="outlined"
                density="compact"
                class="mb-3"
                @update:model-value="onPdfChange"
              />
              <div class="d-flex ga-2">
                <v-btn
                  color="orange"
                  variant="flat"
                  size="small"
                  :loading="uploading"
                  :disabled="!uploadFile"
                  @click="uploadPdfLoesung"
                >
                  Hochladen & Speichern
                </v-btn>
                <v-btn variant="text" size="small" @click="showPdfUpload = false">Abbrechen</v-btn>
              </div>
            </div>
          </v-expand-transition>
        </v-card-text>
      </v-card>

      <!-- Treffer in dieser Prüfung -->
      <v-card v-if="trefferByBegriff.length">
        <v-card-title>
          <v-icon start>mdi-target</v-icon>
          Treffer in dieser Prüfung ({{ treffer.length }})
        </v-card-title>
        <v-card-text>
          <v-table density="compact">
            <thead>
              <tr>
                <th>Bereich</th>
                <th>Suchbegriff</th>
                <th>Fundstellen</th>
                <th class="text-right">Treffer</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in trefferByBegriff" :key="t.name">
                <td>
                  <v-chip size="x-small" label variant="flat" color="primary">
                    {{ t.section }}
                  </v-chip>
                </td>
                <td>{{ t.name }}</td>
                <td>
                  <div class="d-flex flex-wrap ga-1">
                    <v-chip
                      v-for="(doc, i) in t.dokumente"
                      :key="i"
                      size="x-small"
                      variant="tonal"
                      :color="doc.typ === 'Lösung' ? 'success' : doc.typ === 'Belegsatz' ? 'orange' : 'primary'"
                      :prepend-icon="doc.typ === 'Lösung' ? 'mdi-check-circle' : doc.typ === 'Belegsatz' ? 'mdi-receipt-text' : 'mdi-file-document'"
                      class="clickable-chip"
                      @click="router.push({ path: `/dokumente/${doc.dokument_id}/pdf`, query: doc.firstPage ? { page: doc.firstPage } : {} })"
                    >
                      {{ doc.typ }}{{ doc.seiten ? ' S. ' + doc.seiten : '' }}
                    </v-chip>
                  </div>
                </td>
                <td class="text-right">{{ t.count }}</td>
              </tr>
            </tbody>
          </v-table>
        </v-card-text>
      </v-card>

      <!-- Snackbar -->
      <v-snackbar v-model="snackbar" :timeout="2000" color="success">
        {{ snackbarText }}
      </v-snackbar>

      <!-- Verschieben Dialog -->
      <v-dialog v-model="showMoveDialog" max-width="500" persistent>
        <v-card>
          <v-card-title>
            <v-icon start color="warning">mdi-swap-horizontal</v-icon>
            Dokument verschieben
          </v-card-title>
          <v-card-text>
            <v-alert type="info" variant="tonal" density="compact" class="mb-3">
              <strong>{{ moveDokName }}</strong>
              <br />
              Aktuell: {{ pruefung?.zeitraum_label || '–' }}
            </v-alert>
            <v-select
              v-model="moveTargetPruefungId"
              :items="allPruefungen"
              item-title="zeitraum_label"
              item-value="id"
              label="Ziel-Prüfungszeitraum"
              variant="outlined"
              density="compact"
            />
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn variant="text" @click="showMoveDialog = false" :disabled="moving">
              Abbrechen
            </v-btn>
            <v-btn
              color="warning"
              variant="flat"
              :disabled="!moveTargetPruefungId || moving"
              :loading="moving"
              @click="doMove"
            >
              Verschieben
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>
    </template>
  </div>
</template>

<style scoped>
.clickable-chip {
  cursor: pointer;
  transition: transform 0.1s;
}
.clickable-chip:hover {
  transform: scale(1.05);
}
.antwort-text {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'Consolas', 'Fira Code', monospace;
  font-size: 0.875rem;
  background: rgba(0, 0, 0, 0.03);
  padding: 8px 12px;
  border-radius: 6px;
  border-left: 3px solid #fb8c00;
  line-height: 1.6;
}
</style>
