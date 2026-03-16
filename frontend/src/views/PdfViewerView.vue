<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { dokumenteApi, versionenApi } from '@/services/api'
import type { Dokument, DokumentVersion } from '@/types'

const route = useRoute()
const router = useRouter()
const dokument = ref<Dokument | null>(null)
const versionen = ref<DokumentVersion[]>([])
const loading = ref(true)
const error = ref('')
const showVersionPanel = ref(false)
const uploading = ref(false)
const uploadLabel = ref('')
const uploadKommentar = ref('')
const activeVersionId = ref<number | null>(null)
const pdfMissing = ref(false)

const id = computed(() => Number(route.params.id))

// Seitenzahl aus Query-Parameter lesen (?page=5)
const page = computed(() => {
  const p = route.query.page
  return p ? Number(p) : null
})

const pdfUrl = computed(() => {
  if (pdfMissing.value) return ''
  // Wenn eine bestimmte Version aktiv ist (nicht Original)
  if (activeVersionId.value) {
    const base = `/api/dokumente/${id.value}/versionen/${activeVersionId.value}/pdf`
    return page.value ? `${base}#page=${page.value}` : base
  }
  const base = `/api/dokumente/${id.value}/pdf`
  return page.value ? `${base}#page=${page.value}` : base
})
const downloadUrl = computed(() => `/api/dokumente/${id.value}/download`)

function formatBytes(bytes: number | null): string {
  if (!bytes) return '–'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString('de-DE', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

async function loadVersionen() {
  try {
    versionen.value = await versionenApi.getAll(id.value)
  } catch (e) {
    console.error('Versionen laden fehlgeschlagen:', e)
  }
}

async function switchVersion(versionId: number | null) {
  activeVersionId.value = versionId
}

async function handleUpload(event: Event) {
  const input = event.target as HTMLInputElement
  if (!input.files?.length) return

  uploading.value = true
  try {
    await versionenApi.upload(
      id.value,
      input.files[0],
      uploadLabel.value || undefined,
      uploadKommentar.value || undefined,
    )
    uploadLabel.value = ''
    uploadKommentar.value = ''
    await loadVersionen()
  } catch (e) {
    console.error('Upload fehlgeschlagen:', e)
  } finally {
    uploading.value = false
    input.value = '' // Reset file input
  }
}

async function deleteVersion(version: DokumentVersion) {
  if (!confirm(`Version "${version.label}" wirklich löschen?`)) return
  try {
    await versionenApi.delete(id.value, version.id)
    if (activeVersionId.value === version.id) activeVersionId.value = null
    await loadVersionen()
  } catch (e) {
    console.error('Löschen fehlgeschlagen:', e)
  }
}

onMounted(async () => {
  try {
    dokument.value = await dokumenteApi.getById(id.value)
    await loadVersionen()

    // Check if PDF file actually exists on the server
    try {
      const resp = await fetch(`/api/dokumente/${id.value}/pdf`, { method: 'HEAD' })
      if (!resp.ok) {
        pdfMissing.value = true
        error.value = `Die PDF-Datei "${dokument.value?.dateiname}" wurde nicht auf dem Server gefunden. Die Datei fehlt im Dateisystem.`
      }
    } catch {
      // HEAD not supported or network error - let iframe try
    }
  } catch (e) {
    error.value = 'Dokument nicht gefunden'
    console.error(e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="pdf-viewer-page">
    <!-- Toolbar -->
    <v-card class="mb-2" elevation="2">
      <v-toolbar density="compact" color="primary" flat>
        <v-btn icon="mdi-arrow-left" variant="text" @click="router.back()" />
        <v-toolbar-title v-if="dokument" class="text-body-1">
          {{ dokument.dateiname }}
        </v-toolbar-title>
        <v-spacer />

        <template v-if="dokument">
          <v-chip
            :color="dokument.typ === 'Lösung' ? 'green-lighten-4' : 'blue-lighten-4'"
            variant="flat"
            size="small"
            label
            class="mr-2"
          >
            {{ dokument.typ }}
          </v-chip>
          <v-chip v-if="page" variant="flat" color="amber-lighten-3" size="small" class="mr-2">
            Seite {{ page }}
          </v-chip>
          <v-chip variant="tonal" size="small" class="mr-2">
            {{ dokument.seitenanzahl }} Seiten
          </v-chip>
          <v-chip variant="tonal" size="small" class="mr-2">
            {{ formatBytes(dokument.dateigroesse) }}
          </v-chip>
          <span v-if="dokument.pruefung" class="text-caption mr-3">
            {{ dokument.pruefung.zeitraum_label }}
          </span>
        </template>

        <!-- Prüfung bearbeiten -->
        <v-btn
          v-if="dokument?.pruefung_id"
          color="orange"
          variant="flat"
          size="small"
          prepend-icon="mdi-pencil-box-outline"
          class="mr-2"
          @click="router.push(`/pruefungen/${dokument.pruefung_id}/bearbeiten`)"
        >
          Prüfung bearbeiten
        </v-btn>

        <!-- Versionen-Toggle -->
        <v-btn
          :icon="showVersionPanel ? 'mdi-history-off' : 'mdi-history'"
          variant="text"
          :title="showVersionPanel ? 'Versionen ausblenden' : 'Versionen anzeigen'"
          @click="showVersionPanel = !showVersionPanel"
        >
          <v-icon>{{ showVersionPanel ? 'mdi-close' : 'mdi-history' }}</v-icon>
          <v-badge
            v-if="versionen.length > 1"
            :content="versionen.length"
            color="amber"
            floating
          />
        </v-btn>

        <v-btn
          icon="mdi-open-in-new"
          variant="text"
          :href="pdfUrl"
          target="_blank"
          title="In neuem Tab öffnen"
        />
        <v-btn
          icon="mdi-download"
          variant="text"
          :href="downloadUrl"
          title="PDF herunterladen"
        />
      </v-toolbar>
    </v-card>

    <!-- Error -->
    <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
      {{ error }}
    </v-alert>

    <!-- Loading -->
    <v-progress-linear v-if="loading" indeterminate color="primary" />

    <!-- Content Area mit optionalem Versionen-Panel -->
    <div v-if="!loading && !error" class="content-area">
      <!-- Versionen-Panel (Sidebar) -->
      <v-card v-if="showVersionPanel" class="version-panel mr-2" elevation="1">
        <v-card-title class="text-subtitle-2 py-2 px-3">
          <v-icon start size="small">mdi-history</v-icon>
          Versionen ({{ versionen.length }})
        </v-card-title>

        <v-divider />

        <v-list density="compact" class="version-list">
          <!-- Original anzeigen -->
          <v-list-item
            :active="activeVersionId === null"
            active-color="primary"
            @click="switchVersion(null)"
            class="version-item"
          >
            <template #prepend>
              <v-icon size="small" color="primary">mdi-file-document</v-icon>
            </template>
            <v-list-item-title class="text-body-2 font-weight-medium">
              Original
            </v-list-item-title>
            <v-list-item-subtitle class="text-caption">
              {{ formatBytes(dokument?.dateigroesse ?? null) }}
            </v-list-item-subtitle>
          </v-list-item>

          <!-- Bearbeitete Versionen -->
          <v-list-item
            v-for="v in versionen.filter(v => v.version_nr > 1)"
            :key="v.id"
            :active="activeVersionId === v.id"
            active-color="primary"
            @click="switchVersion(v.id)"
            class="version-item"
          >
            <template #prepend>
              <v-icon size="small" color="amber-darken-2">mdi-pencil</v-icon>
            </template>
            <v-list-item-title class="text-body-2">
              {{ v.label }}
            </v-list-item-title>
            <v-list-item-subtitle class="text-caption">
              {{ formatDate(v.erstellt_am) }} · {{ formatBytes(v.dateigroesse) }}
            </v-list-item-subtitle>
            <template v-if="v.kommentar">
              <div class="text-caption text-medium-emphasis mt-1">
                {{ v.kommentar }}
              </div>
            </template>
            <template #append>
              <v-btn
                icon="mdi-delete"
                size="x-small"
                variant="text"
                color="error"
                @click.stop="deleteVersion(v)"
                title="Version löschen"
              />
            </template>
          </v-list-item>
        </v-list>

        <v-divider />

        <!-- Upload neue Version -->
        <div class="pa-3">
          <p class="text-caption font-weight-medium mb-2">Neue Version hochladen:</p>
          <v-text-field
            v-model="uploadLabel"
            density="compact"
            variant="outlined"
            label="Bezeichnung"
            placeholder="z.B. Mit Notizen"
            hide-details
            class="mb-2"
          />
          <v-text-field
            v-model="uploadKommentar"
            density="compact"
            variant="outlined"
            label="Kommentar"
            placeholder="Optional"
            hide-details
            class="mb-2"
          />
          <v-btn
            block
            size="small"
            color="primary"
            variant="tonal"
            prepend-icon="mdi-upload"
            :loading="uploading"
            @click="($refs.fileInput as HTMLInputElement).click()"
          >
            PDF hochladen
          </v-btn>
          <input
            ref="fileInput"
            type="file"
            accept="application/pdf"
            style="display: none"
            @change="handleUpload"
          />
        </div>
      </v-card>

      <!-- PDF Embed -->
      <div class="pdf-container">
        <iframe
          :src="pdfUrl"
          class="pdf-iframe"
          frameborder="0"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.pdf-viewer-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 100px);
}

.content-area {
  flex: 1;
  min-height: 0;
  display: flex;
}

.version-panel {
  width: 280px;
  min-width: 280px;
  display: flex;
  flex-direction: column;
  max-height: 100%;
  overflow: hidden;
}

.version-list {
  flex: 1;
  overflow-y: auto;
}

.version-item {
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
}

.pdf-container {
  flex: 1;
  min-height: 0;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.pdf-iframe {
  width: 100%;
  height: 100%;
  border: none;
}
</style>
