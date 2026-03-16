<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { antwortenApi } from '@/services/api'
import type { MeinBild } from '@/types'

const router = useRouter()
const loading = ref(true)
const alleBilder = ref<MeinBild[]>([])
const searchQuery = ref('')

/* ══════ Daten laden ══════ */
async function loadData() {
  loading.value = true
  try {
    alleBilder.value = await antwortenApi.getAllBilder()
  } catch (e) {
    console.error('Fehler beim Laden:', e)
  } finally {
    loading.value = false
  }
}

onMounted(loadData)

/* ══════ Gruppierung: Prüfung → Aufgabe → Bilder ══════ */
interface AufgabeGroup {
  aufgabe: string
  durchlauf: number
  antwort_id: number
  antwort_text: string
  punkte: number | null
  max_punkte: number | null
  bilder: MeinBild[]
}
interface PruefungGroup {
  pruefung_id: number
  zeitraum_label: string
  aufgaben: AufgabeGroup[]
  bilderCount: number
}

const grouped = computed<PruefungGroup[]>(() => {
  const filtered = searchQuery.value
    ? alleBilder.value.filter(
        (b) =>
          b.zeitraum_label.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
          b.aufgabe.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
          b.dateiname.toLowerCase().includes(searchQuery.value.toLowerCase()),
      )
    : alleBilder.value

  // Gruppiere nach Prüfung
  const pruefMap = new Map<number, { label: string; entries: MeinBild[] }>()
  for (const b of filtered) {
    let g = pruefMap.get(b.pruefung_id)
    if (!g) {
      g = { label: b.zeitraum_label, entries: [] }
      pruefMap.set(b.pruefung_id, g)
    }
    g.entries.push(b)
  }

  // Sortiere und gruppiere nach Aufgabe innerhalb jeder Prüfung
  const result: PruefungGroup[] = []
  for (const [pid, { label, entries }] of pruefMap) {
    const aufgabeMap = new Map<string, AufgabeGroup>()
    for (const b of entries) {
      const key = `${b.aufgabe}__${b.durchlauf}`
      let ag = aufgabeMap.get(key)
      if (!ag) {
        ag = {
          aufgabe: b.aufgabe,
          durchlauf: b.durchlauf,
          antwort_id: b.antwort_id,
          antwort_text: b.antwort_text,
          punkte: b.punkte,
          max_punkte: b.max_punkte,
          bilder: [],
        }
        aufgabeMap.set(key, ag)
      }
      ag.bilder.push(b)
    }
    result.push({
      pruefung_id: pid,
      zeitraum_label: label,
      aufgaben: Array.from(aufgabeMap.values()).sort((a, b) =>
        a.aufgabe.localeCompare(b.aufgabe, 'de', { numeric: true }),
      ),
      bilderCount: entries.length,
    })
  }
  return result.sort((a, b) => a.zeitraum_label.localeCompare(b.zeitraum_label))
})

const totalBilder = computed(() => alleBilder.value.length)
const totalPruefungen = computed(() => grouped.value.length)

/* ══════ Vorschau / Lightbox ══════ */
const lightboxOpen = ref(false)
const lightboxUrl = ref('')
const lightboxTitle = ref('')
const lightboxIsPdf = ref(false)

function openPreview(bild: MeinBild) {
  const url = antwortenApi.bildUrl(bild.antwort_id, bild.id)
  lightboxUrl.value = url
  lightboxTitle.value = bild.dateiname
  lightboxIsPdf.value = bild.dateiname.toLowerCase().endsWith('.pdf')
  lightboxOpen.value = true
}

/* ══════ Löschen mit Bestätigung ══════ */
const deleteDialog = ref(false)
const bildToDelete = ref<MeinBild | null>(null)
const deleting = ref(false)

function confirmDelete(bild: MeinBild) {
  bildToDelete.value = bild
  deleteDialog.value = true
}

async function executeDelete() {
  if (!bildToDelete.value) return
  deleting.value = true
  try {
    await antwortenApi.deleteBild(bildToDelete.value.antwort_id, bildToDelete.value.id)
    alleBilder.value = alleBilder.value.filter((b) => b.id !== bildToDelete.value!.id)
    snackbarText.value = `"${bildToDelete.value.dateiname}" gelöscht`
    snackbarColor.value = 'success'
    snackbar.value = true
  } catch (e) {
    console.error(e)
    snackbarText.value = 'Fehler beim Löschen'
    snackbarColor.value = 'error'
    snackbar.value = true
  } finally {
    deleting.value = false
    deleteDialog.value = false
    bildToDelete.value = null
  }
}

/* ══════ Snackbar ══════ */
const snackbar = ref(false)
const snackbarText = ref('')
const snackbarColor = ref('success')

/* ══════ Expanded Panels ══════ */
const expandedPanels = ref<number[]>([])

/* ══════ Navigation ══════ */
function goToPruefung(pruefungId: number) {
  router.push(`/pruefungen/${pruefungId}/bearbeiten`)
}

function isPdf(bild: MeinBild): boolean {
  return bild.dateiname.toLowerCase().endsWith('.pdf')
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatSize(bytes: number | null): string {
  if (!bytes) return '–'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
</script>

<template>
  <div>
    <!-- Header -->
    <div class="d-flex align-center mb-4">
      <v-icon size="32" color="primary" class="mr-3">mdi-folder-image</v-icon>
      <div>
        <h1 class="text-h5 font-weight-bold">Meine Lösungen</h1>
        <p class="text-body-2 text-medium-emphasis">
          Alle hochgeladenen Bilder und PDFs zu meinen Prüfungsantworten
        </p>
      </div>
      <v-spacer />
      <v-chip color="primary" variant="tonal" class="mr-2">
        <v-icon start size="16">mdi-image-multiple</v-icon>
        {{ totalBilder }} Dateien
      </v-chip>
      <v-chip color="info" variant="tonal">
        <v-icon start size="16">mdi-file-document-multiple</v-icon>
        {{ totalPruefungen }} Prüfungen
      </v-chip>
    </div>

    <!-- Suchleiste -->
    <v-text-field
      v-model="searchQuery"
      prepend-inner-icon="mdi-magnify"
      label="Suche nach Prüfung, Aufgabe oder Dateiname..."
      variant="outlined"
      density="compact"
      hide-details
      clearable
      class="mb-4"
      style="max-width: 500px"
    />

    <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-4" />

    <!-- Leer-Zustand -->
    <v-card v-if="!loading && !alleBilder.length" variant="outlined" class="pa-8 text-center">
      <v-icon size="80" color="grey-lighten-1">mdi-image-off-outline</v-icon>
      <p class="text-h6 mt-4 text-medium-emphasis">Noch keine Lösungen hochgeladen</p>
      <p class="text-body-2 text-medium-emphasis">
        Öffne eine Prüfung zum Bearbeiten und lade Bilder/PDFs zu deinen Antworten hoch.
      </p>
    </v-card>

    <!-- Gruppierte Anzeige -->
    <v-expansion-panels v-else v-model="expandedPanels" multiple variant="accordion">
      <v-expansion-panel
        v-for="pg in grouped"
        :key="pg.pruefung_id"
      >
        <v-expansion-panel-title>
          <div class="d-flex align-center ga-3 flex-grow-1">
            <v-icon color="orange" size="20">mdi-file-document-outline</v-icon>
            <span class="font-weight-bold">{{ pg.zeitraum_label }}</span>
            <v-chip size="x-small" color="primary" variant="tonal">
              {{ pg.bilderCount }} {{ pg.bilderCount === 1 ? 'Datei' : 'Dateien' }}
            </v-chip>
            <v-chip size="x-small" color="grey" variant="tonal">
              {{ pg.aufgaben.length }} {{ pg.aufgaben.length === 1 ? 'Aufgabe' : 'Aufgaben' }}
            </v-chip>
            <v-spacer />
            <v-btn
              icon="mdi-open-in-new"
              size="x-small"
              variant="text"
              color="primary"
              title="Prüfung öffnen"
              @click.stop="goToPruefung(pg.pruefung_id)"
            />
          </div>
        </v-expansion-panel-title>

        <v-expansion-panel-text>
          <!-- Pro Aufgabe -->
          <div
            v-for="ag in pg.aufgaben"
            :key="`${ag.aufgabe}-${ag.durchlauf}`"
            class="aufgabe-block mb-4"
          >
            <!-- Aufgaben-Header -->
            <div class="d-flex align-center ga-2 mb-2 aufgabe-group-header pa-2 rounded">
              <v-icon size="18" color="orange-darken-1">mdi-pencil-box-outline</v-icon>
              <span class="font-weight-bold text-body-2">{{ ag.aufgabe }}</span>
              <v-chip v-if="ag.durchlauf > 1" size="x-small" color="purple" variant="tonal">
                Durchlauf {{ ag.durchlauf }}
              </v-chip>
              <v-chip
                v-if="ag.punkte != null && ag.max_punkte != null"
                size="x-small"
                :color="Number(ag.punkte) >= Number(ag.max_punkte) * 0.5 ? 'success' : 'warning'"
                variant="tonal"
              >
                {{ ag.punkte }}/{{ ag.max_punkte }} Punkte
              </v-chip>
              <v-spacer />
              <span class="text-caption text-medium-emphasis">
                {{ ag.bilder.length }} {{ ag.bilder.length === 1 ? 'Version' : 'Versionen' }}
              </span>
            </div>

            <!-- Antwort-Text (ausklappbar) -->
            <div v-if="ag.antwort_text" class="mb-2 ml-6">
              <v-expansion-panels variant="accordion" flat>
                <v-expansion-panel>
                  <v-expansion-panel-title class="py-1 text-caption text-medium-emphasis">
                    <v-icon size="14" class="mr-1">mdi-text-box-outline</v-icon>
                    Antwort-Text anzeigen
                  </v-expansion-panel-title>
                  <v-expansion-panel-text>
                    <pre class="text-body-2 antwort-preview">{{ ag.antwort_text }}</pre>
                  </v-expansion-panel-text>
                </v-expansion-panel>
              </v-expansion-panels>
            </div>

            <!-- Bilder/PDFs als Karten -->
            <div class="d-flex flex-wrap ga-3 ml-6">
              <v-card
                v-for="bild in ag.bilder"
                :key="bild.id"
                variant="outlined"
                class="bild-card"
                width="200"
              >
                <!-- Vorschau -->
                <div
                  class="bild-preview-area d-flex align-center justify-center"
                  @click="openPreview(bild)"
                >
                  <v-icon v-if="isPdf(bild)" size="48" color="red-darken-1">
                    mdi-file-pdf-box
                  </v-icon>
                  <v-img
                    v-else
                    :src="antwortenApi.bildUrl(bild.antwort_id, bild.id)"
                    :alt="bild.dateiname"
                    height="130"
                    cover
                  >
                    <template #placeholder>
                      <div class="d-flex align-center justify-center fill-height">
                        <v-progress-circular indeterminate size="24" />
                      </div>
                    </template>
                  </v-img>
                </div>

                <!-- Info -->
                <v-card-text class="pa-2">
                  <p class="text-caption font-weight-bold text-truncate" :title="bild.dateiname">
                    {{ bild.dateiname }}
                  </p>
                  <p class="text-caption text-medium-emphasis">
                    {{ formatSize(bild.dateigroesse) }} · {{ formatDate(bild.erstellt_am) }}
                  </p>
                </v-card-text>

                <!-- Aktionen -->
                <v-card-actions class="pa-1 pt-0">
                  <v-btn
                    size="small"
                    variant="text"
                    color="primary"
                    prepend-icon="mdi-eye"
                    @click="openPreview(bild)"
                  >
                    Ansehen
                  </v-btn>
                  <v-spacer />
                  <v-btn
                    size="small"
                    variant="text"
                    color="primary"
                    icon="mdi-open-in-new"
                    :href="antwortenApi.bildUrl(bild.antwort_id, bild.id)"
                    target="_blank"
                    title="In neuem Tab"
                  />
                  <v-btn
                    size="small"
                    variant="text"
                    color="error"
                    icon="mdi-delete-outline"
                    title="Löschen"
                    @click="confirmDelete(bild)"
                  />
                </v-card-actions>
              </v-card>
            </div>
          </div>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>

    <!-- ══════ Vorschau-Dialog ══════ -->
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
          <iframe
            v-if="lightboxIsPdf"
            :src="lightboxUrl"
            style="width: 100%; height: 80vh; border: none"
            title="PDF Vollansicht"
          />
          <img
            v-else
            :src="lightboxUrl"
            :alt="lightboxTitle"
            style="max-width: 100%; max-height: 80vh; object-fit: contain"
          />
        </v-card-text>
      </v-card>
    </v-dialog>

    <!-- ══════ Lösch-Bestätigung ══════ -->
    <v-dialog v-model="deleteDialog" max-width="450" persistent>
      <v-card>
        <v-card-title class="d-flex align-center ga-2">
          <v-icon color="error">mdi-alert-circle-outline</v-icon>
          Datei löschen?
        </v-card-title>
        <v-card-text v-if="bildToDelete">
          <p>Möchtest du diese Datei wirklich unwiderruflich löschen?</p>
          <v-card variant="outlined" class="mt-3 pa-3 d-flex align-center ga-3">
            <v-icon :color="isPdf(bildToDelete) ? 'red-darken-1' : 'blue'" size="32">
              {{ isPdf(bildToDelete) ? 'mdi-file-pdf-box' : 'mdi-image' }}
            </v-icon>
            <div>
              <p class="font-weight-bold text-body-2">{{ bildToDelete.dateiname }}</p>
              <p class="text-caption text-medium-emphasis">
                {{ bildToDelete.zeitraum_label }} · {{ bildToDelete.aufgabe }}
                · {{ formatSize(bildToDelete.dateigroesse) }}
              </p>
            </div>
          </v-card>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false" :disabled="deleting">
            Abbrechen
          </v-btn>
          <v-btn
            color="error"
            variant="flat"
            :loading="deleting"
            @click="executeDelete"
          >
            Endgültig löschen
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar" :timeout="2500" :color="snackbarColor" location="bottom right">
      {{ snackbarText }}
    </v-snackbar>
  </div>
</template>

<style scoped>
.aufgabe-group-header {
  background: rgba(251, 140, 0, 0.06);
  border-left: 3px solid #fb8c00;
}

.bild-card {
  transition: box-shadow 0.15s, transform 0.15s;
}
.bild-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
  transform: translateY(-1px);
}

.bild-preview-area {
  height: 130px;
  background: #f5f5f5;
  cursor: pointer;
  overflow: hidden;
}
.bild-preview-area:hover {
  opacity: 0.85;
}

.antwort-preview {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  background: rgba(0, 0, 0, 0.02);
  padding: 8px 12px;
  border-radius: 4px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  max-height: 200px;
  overflow-y: auto;
}

.lightbox-card {
  overflow: hidden;
}
</style>
