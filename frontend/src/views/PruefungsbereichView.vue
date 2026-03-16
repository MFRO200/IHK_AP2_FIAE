<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { dokumenteApi, pruefungenApi, trefferApi, antwortenApi } from '@/services/api'
import type { Dokument, Pruefung, PruefungsbereichStat, BearbeitungsStatus } from '@/types'

const route = useRoute()
const router = useRouter()
const bereich = computed(() => String(route.params.bereich))

const dokumente = ref<Dokument[]>([])
const pruefungen = ref<Pruefung[]>([])
const bereichStat = ref<PruefungsbereichStat | null>(null)
const bearbeitungsStatus = ref<BearbeitungsStatus[]>([])
const loading = ref(true)

/* Upload Dialog */
const showUploadDialog = ref(false)
const uploadFile = ref<File | null>(null)
const uploadPruefungId = ref<number | null>(null)
const uploadTyp = ref('Aufgabe')
const uploading = ref(false)
const snackbar = ref(false)
const snackbarText = ref('')
const snackbarColor = ref('success')

/* Neue Prüfung anlegen */
const showNewPruefungDialog = ref(false)
const newPruefungJahr = ref<number>(new Date().getFullYear())
const newPruefungSemester = ref<string>('Sommer')
const creatingPruefung = ref(false)

/* Dokument verschieben */
const showMoveDialog = ref(false)
const moveDokument = ref<Dokument | null>(null)
const moveTargetPruefungId = ref<number | null>(null)
const moving = ref(false)

const bereichLabels: Record<string, string> = {
  GA1: 'Planen eines Softwareproduktes',
  GA2: 'Entwicklung und Umsetzung von Algorithmen',
  WISO: 'Wirtschafts- und Sozialkunde',
  AP1: 'Einrichten eines IT-gestützten Arbeitsplatzes',
  'GA1 FISI': 'Fachqualifikation Systemintegration',
  'GA1 IK': 'Fachqualifikation Informatikkaufleute',
  'GA1 IT-SE': 'Fachqualifikation IT-System-Elektronik',
  'GA1 IT-SK': 'Fachqualifikation IT-System-Kaufleute',
  Sonstige: 'Sonstige Dokumente',
}
const bereichColors: Record<string, string> = {
  GA1: '#1565C0',
  GA2: '#6A1B9A',
  WISO: '#E65100',
  AP1: '#2E7D32',
  'GA1 FISI': '#0277BD',
  'GA1 IK': '#00838F',
  'GA1 IT-SE': '#4527A0',
  'GA1 IT-SK': '#AD1457',
  Sonstige: '#757575',
}
const bereichIcons: Record<string, string> = {
  GA1: 'mdi-cog-outline',
  GA2: 'mdi-code-braces',
  WISO: 'mdi-scale-balance',
  AP1: 'mdi-desktop-classic',
  'GA1 FISI': 'mdi-server-network',
  'GA1 IK': 'mdi-calculator-variant',
  'GA1 IT-SE': 'mdi-chip',
  'GA1 IT-SK': 'mdi-cart-outline',
  Sonstige: 'mdi-file-document-outline',
}
const bereichGewichtung: Record<string, string> = {
  GA1: '25 %',
  GA2: '25 %',
  WISO: '10 %',
  AP1: '20 %',
  'GA1 FISI': '25 %',
  'GA1 IK': '25 %',
  'GA1 IT-SE': '25 %',
  'GA1 IT-SK': '25 %',
}

const color = computed(() => bereichColors[bereich.value] || '#757575')

/* Dokumente nach Prüfung gruppiert */
interface PruefungGroup {
  pruefung: Pruefung
  dokumente: Dokument[]
}
const groupedByPruefung = computed<PruefungGroup[]>(() => {
  const map = new Map<number, PruefungGroup>()
  for (const d of dokumente.value) {
    if (!d.pruefung) continue
    if (!map.has(d.pruefung.id)) {
      map.set(d.pruefung.id, { pruefung: d.pruefung, dokumente: [] })
    }
    map.get(d.pruefung.id)!.dokumente.push(d)
  }
  return [...map.values()].sort((a, b) => b.pruefung.jahr - a.pruefung.jahr || a.pruefung.semester.localeCompare(b.pruefung.semester))
})

function formatBytes(bytes: number): string {
  if (!bytes) return '–'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

async function loadData() {
  loading.value = true
  try {
    const [docs, allPruefungen, allStats, status] = await Promise.all([
      dokumenteApi.getAll({ pruefungsbereich: bereich.value }),
      pruefungenApi.getAll(),
      trefferApi.getStatsPerPruefungsbereich(),
      antwortenApi.getBearbeitungsStatus(),
    ])
    dokumente.value = docs
    pruefungen.value = allPruefungen
    bereichStat.value = allStats.find((s) => s.pruefungsbereich === bereich.value) || null
    bearbeitungsStatus.value = status
  } catch (e) {
    console.error('Laden fehlgeschlagen:', e)
  } finally {
    loading.value = false
  }
}

/** Prüft ob eine Prüfung im aktuellen Bereich geübt wurde */
function istGeubt(pruefungId: number): BearbeitungsStatus | undefined {
  return bearbeitungsStatus.value.find(
    s => s.pruefung_id === pruefungId && s.pruefungsbereich === bereich.value
  )
}

function openUploadDialog() {
  uploadFile.value = null
  uploadPruefungId.value = null
  uploadTyp.value = 'Aufgabe'
  showUploadDialog.value = true
}

function onFileChange(files: File[] | File | null) {
  if (Array.isArray(files)) {
    uploadFile.value = files[0] || null
  } else {
    uploadFile.value = files
  }
}

async function doUpload() {
  if (!uploadFile.value || !uploadPruefungId.value) return
  uploading.value = true
  try {
    await dokumenteApi.upload(
      uploadFile.value,
      uploadPruefungId.value,
      uploadTyp.value,
      bereich.value,
    )
    showUploadDialog.value = false
    snackbarText.value = 'PDF erfolgreich hochgeladen'
    snackbarColor.value = 'success'
    snackbar.value = true
    await loadData()
  } catch (e) {
    console.error('Upload fehlgeschlagen:', e)
    snackbarText.value = 'Fehler beim Upload'
    snackbarColor.value = 'error'
    snackbar.value = true
  } finally {
    uploading.value = false
  }
}

async function confirmDelete(doc: Dokument) {
  if (!confirm(`Dokument "${doc.dateiname}" wirklich löschen? Diese Aktion kann nicht rückgängig gemacht werden.`)) return
  try {
    await dokumenteApi.remove(doc.id)
    snackbarText.value = `"${doc.dateiname}" gelöscht`
    snackbarColor.value = 'success'
    snackbar.value = true
    await loadData()
  } catch (e) {
    console.error('Löschen fehlgeschlagen:', e)
    snackbarText.value = 'Fehler beim Löschen'
    snackbarColor.value = 'error'
    snackbar.value = true
  }
}

function openMoveDialog(doc: Dokument) {
  moveDokument.value = doc
  moveTargetPruefungId.value = null
  showMoveDialog.value = true
}

async function doMove() {
  if (!moveDokument.value || !moveTargetPruefungId.value) return
  moving.value = true
  try {
    await dokumenteApi.update(moveDokument.value.id, {
      pruefung_id: moveTargetPruefungId.value,
    })
    showMoveDialog.value = false
    snackbarText.value = `"${moveDokument.value.dateiname}" verschoben`
    snackbarColor.value = 'success'
    snackbar.value = true
    await loadData()
  } catch (e) {
    console.error('Verschieben fehlgeschlagen:', e)
    snackbarText.value = 'Fehler beim Verschieben'
    snackbarColor.value = 'error'
    snackbar.value = true
  } finally {
    moving.value = false
  }
}

onMounted(loadData)

async function createPruefung() {
  const jahr = newPruefungJahr.value
  const semester = newPruefungSemester.value
  if (!jahr || !semester) return

  // Prüfen ob schon vorhanden
  const existing = pruefungen.value.find((p) => p.jahr === jahr && p.semester === semester)
  if (existing) {
    snackbarText.value = `Prüfung ${semester} ${jahr} existiert bereits! Sie können direkt im Upload-Dialog diese Prüfung auswählen.`
    snackbarColor.value = 'warning'
    snackbar.value = true
    return
  }

  creatingPruefung.value = true
  try {
    const zeitraum_label = semester === 'Winter'
      ? `Winter ${jahr}_${String(jahr + 1).slice(2)}`
      : `${semester} ${jahr}`
    const ordner_name = semester === 'Winter'
      ? `${jahr}_${String(jahr + 1).slice(2)} Winter`
      : `${jahr} ${semester}`

    await pruefungenApi.create({ jahr, semester, zeitraum_label, ordner_name })
    showNewPruefungDialog.value = false
    snackbarText.value = `Prüfung ${zeitraum_label} angelegt`
    snackbarColor.value = 'success'
    snackbar.value = true
    await loadData()
  } catch (e) {
    console.error('Erstellen fehlgeschlagen:', e)
    snackbarText.value = 'Fehler beim Erstellen'
    snackbarColor.value = 'error'
    snackbar.value = true
  } finally {
    creatingPruefung.value = false
  }
}
</script>

<template>
  <div>
    <v-btn
      variant="text"
      prepend-icon="mdi-arrow-left"
      class="mb-4"
      @click="router.push('/')"
    >
      Zurück zum Dashboard
    </v-btn>

    <v-progress-linear v-if="loading" indeterminate :color="color" />

    <template v-if="!loading">
      <!-- Header -->
      <div class="d-flex align-center mb-4">
        <v-icon :icon="bereichIcons[bereich] || 'mdi-file'" size="36" :color="color" class="mr-3" />
        <div>
          <h1 class="text-h4">{{ bereich }}</h1>
          <p class="text-subtitle-1 text-medium-emphasis mb-0">
            {{ bereichLabels[bereich] || bereich }}
            <v-chip
              v-if="bereichGewichtung[bereich]"
              size="x-small"
              variant="flat"
              :color="color"
              class="ml-2 text-white font-weight-bold"
            >
              {{ bereichGewichtung[bereich] }}
            </v-chip>
          </p>
        </div>
        <v-spacer />
        <v-btn
          color="primary"
          variant="flat"
          prepend-icon="mdi-upload"
          @click="openUploadDialog"
          class="mr-2"
        >
          PDF hochladen
        </v-btn>
        <v-btn
          color="success"
          variant="tonal"
          prepend-icon="mdi-plus-circle-outline"
          @click="showNewPruefungDialog = true"
        >
          Neue Prüfung
        </v-btn>
      </div>

      <!-- KPI Row -->
      <v-row class="mb-4" v-if="bereichStat">
        <v-col cols="6" sm="3">
          <v-card :color="color" variant="tonal" class="text-center pa-3">
            <div class="text-h5 font-weight-bold">{{ bereichStat.dokumente }}</div>
            <div class="text-caption">Dokumente</div>
          </v-card>
        </v-col>
        <v-col cols="6" sm="3">
          <v-card :color="color" variant="tonal" class="text-center pa-3">
            <div class="text-h5 font-weight-bold">{{ bereichStat.seiten }}</div>
            <div class="text-caption">Seiten</div>
          </v-card>
        </v-col>
        <v-col cols="6" sm="3">
          <v-card :color="color" variant="tonal" class="text-center pa-3">
            <div class="text-h5 font-weight-bold">{{ bereichStat.treffer }}</div>
            <div class="text-caption">Treffer</div>
          </v-card>
        </v-col>
        <v-col cols="6" sm="3">
          <v-card :color="color" variant="tonal" class="text-center pa-3">
            <div class="text-h5 font-weight-bold">{{ bereichStat.begriffe }}</div>
            <div class="text-caption">Begriffe</div>
          </v-card>
        </v-col>
      </v-row>

      <!-- Prüfungen mit Dokumenten -->
      <v-card v-for="group in groupedByPruefung" :key="group.pruefung.id" class="mb-4">
        <v-card-title
          class="d-flex align-center clickable-header"
          @click="router.push(`/pruefungen/${group.pruefung.id}`)"
        >
          <v-icon start size="20" :color="color">mdi-calendar-outline</v-icon>
          {{ group.pruefung.zeitraum_label }}
          <v-chip
            :color="group.pruefung.semester === 'Sommer' ? 'orange' : 'blue'"
            variant="tonal"
            size="x-small"
            label
            class="ml-2"
          >
            {{ group.pruefung.semester }}
          </v-chip>
          <!-- Geübt-Status -->
          <v-tooltip v-if="istGeubt(group.pruefung.id)" :text="`${bereich} – ${istGeubt(group.pruefung.id)!.durchlaeufe}× ${istGeubt(group.pruefung.id)!.ausgewertet ? 'geübt' : 'beantwortet (nicht ausgewertet)'}`" location="top">
            <template #activator="{ props }">
              <v-chip
                v-bind="props"
                :color="istGeubt(group.pruefung.id)!.ausgewertet ? 'green' : 'amber'"
                :variant="istGeubt(group.pruefung.id)!.ausgewertet ? 'flat' : 'outlined'"
                size="x-small"
                label
                class="ml-2"
                :prepend-icon="istGeubt(group.pruefung.id)!.ausgewertet ? 'mdi-check-circle' : 'mdi-pencil-outline'"
              >
                {{ istGeubt(group.pruefung.id)!.durchlaeufe }}× {{ istGeubt(group.pruefung.id)!.ausgewertet ? 'geübt' : 'beantwortet' }}
              </v-chip>
            </template>
          </v-tooltip>
          <v-spacer />
          <v-btn
            color="orange"
            variant="tonal"
            size="small"
            prepend-icon="mdi-pencil-box-outline"
            class="mr-2"
            @click.stop="router.push(`/pruefungen/${group.pruefung.id}`)"
          >
            Lösungen eintragen
          </v-btn>
          <v-chip size="x-small" variant="tonal" :color="color">
            {{ group.dokumente.length }} Dok.
          </v-chip>
        </v-card-title>
        <v-divider />
        <v-list density="compact">
          <v-list-item
            v-for="d in group.dokumente"
            :key="d.id"
            :title="d.dateiname"
            :subtitle="`${d.typ} · ${d.seitenanzahl} Seiten · ${formatBytes(d.dateigroesse)}`"
          >
            <template #prepend>
              <v-icon
                :color="d.typ === 'Lösung' ? 'success' : d.typ === 'Handreichung' ? 'warning' : 'primary'"
                size="20"
              >
                {{ d.typ === 'Lösung' ? 'mdi-check-circle' : d.typ === 'Handreichung' ? 'mdi-information' : 'mdi-file-pdf-box' }}
              </v-icon>
            </template>
            <template #append>
              <v-btn
                icon="mdi-swap-horizontal"
                size="small"
                variant="text"
                color="warning"
                title="In andere Prüfung verschieben"
                @click.stop="openMoveDialog(d)"
              />
              <v-btn
                icon="mdi-file-eye"
                size="small"
                variant="text"
                color="primary"
                title="PDF anzeigen"
                @click.stop="router.push(`/dokumente/${d.id}/pdf`)"
              />
              <v-btn
                icon="mdi-open-in-new"
                size="small"
                variant="text"
                color="secondary"
                title="In neuem Tab"
                :href="`/api/dokumente/${d.id}/pdf`"
                target="_blank"
                @click.stop
              />
              <v-btn
                icon="mdi-delete"
                size="small"
                variant="text"
                color="error"
                title="Dokument löschen"
                @click.stop="confirmDelete(d)"
              />
            </template>
          </v-list-item>
        </v-list>
      </v-card>

      <!-- Leer -->
      <v-alert v-if="!groupedByPruefung.length" type="info" variant="tonal">
        Keine Dokumente in diesem Prüfungsbereich gefunden.
      </v-alert>
    </template>

    <!-- Upload Dialog -->
    <v-dialog v-model="showUploadDialog" max-width="550" persistent>
      <v-card>
        <v-card-title>
          <v-icon start :color="color">mdi-upload</v-icon>
          PDF hochladen – {{ bereich }}
        </v-card-title>
        <v-card-text>
          <v-file-input
            label="PDF-Datei auswählen"
            accept=".pdf"
            prepend-icon="mdi-file-pdf-box"
            variant="outlined"
            density="compact"
            class="mb-3"
            @update:model-value="onFileChange"
          />
          <v-select
            v-model="uploadPruefungId"
            :items="pruefungen"
            item-title="zeitraum_label"
            item-value="id"
            label="Prüfungszeitraum"
            variant="outlined"
            density="compact"
            class="mb-3"
          />
          <v-select
            v-model="uploadTyp"
            :items="['Aufgabe', 'Lösung', 'Handreichung']"
            label="Dokumenttyp"
            variant="outlined"
            density="compact"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showUploadDialog = false" :disabled="uploading">
            Abbrechen
          </v-btn>
          <v-btn
            color="primary"
            variant="flat"
            :disabled="!uploadFile || !uploadPruefungId || uploading"
            :loading="uploading"
            @click="doUpload"
          >
            Hochladen
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar" :timeout="3000" :color="snackbarColor">
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
            <strong>{{ moveDokument?.dateiname }}</strong>
            <br />
            Aktuell: {{ moveDokument?.pruefung?.zeitraum_label || '–' }}
          </v-alert>
          <v-select
            v-model="moveTargetPruefungId"
            :items="pruefungen"
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

    <!-- Neue Prüfung Dialog -->
    <v-dialog v-model="showNewPruefungDialog" max-width="450" persistent>
      <v-card>
        <v-card-title>
          <v-icon start color="success">mdi-plus-circle-outline</v-icon>
          Neue Prüfung anlegen
        </v-card-title>
        <v-card-text>
          <v-text-field
            v-model.number="newPruefungJahr"
            label="Jahr"
            type="number"
            variant="outlined"
            density="compact"
            :min="2000"
            :max="2030"
            class="mb-3"
          />
          <v-select
            v-model="newPruefungSemester"
            :items="['Sommer', 'Winter', 'Frühjahr', 'Herbst']"
            label="Semester / Zeitraum"
            variant="outlined"
            density="compact"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showNewPruefungDialog = false" :disabled="creatingPruefung">
            Abbrechen
          </v-btn>
          <v-btn
            color="success"
            variant="flat"
            :loading="creatingPruefung"
            :disabled="!newPruefungJahr || !newPruefungSemester"
            @click="createPruefung"
          >
            Anlegen
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<style scoped>
.clickable-header {
  cursor: pointer;
  transition: background-color 0.15s;
}
.clickable-header:hover {
  background-color: rgba(var(--v-theme-primary), 0.06);
}
</style>
