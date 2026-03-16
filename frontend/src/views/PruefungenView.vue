<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { pruefungenApi, antwortenApi } from '@/services/api'
import type { Pruefung, BearbeitungsStatus } from '@/types'

const router = useRouter()
const pruefungen = ref<Pruefung[]>([])
const bearbeitungsStatus = ref<BearbeitungsStatus[]>([])
const loading = ref(true)
const search = ref('')

const headers = [
  { title: 'ID', key: 'id', width: '60px' },
  { title: 'Jahr', key: 'jahr', width: '80px' },
  { title: 'Semester', key: 'semester', width: '100px' },
  { title: 'Zeitraum', key: 'zeitraum_label' },
  { title: 'Geübt', key: 'geubt', sortable: false, width: '160px' },
  { title: 'Ordner', key: 'ordner_name' },
  { title: 'Aktionen', key: 'actions', sortable: false, width: '100px' },
]

const filtered = computed(() => {
  if (!search.value) return pruefungen.value
  const q = search.value.toLowerCase()
  return pruefungen.value.filter(
    (p) =>
      p.zeitraum_label.toLowerCase().includes(q) ||
      p.ordner_name.toLowerCase().includes(q) ||
      String(p.jahr).includes(q) ||
      p.semester.toLowerCase().includes(q),
  )
})

/** Gibt die geübten Bereiche für eine Prüfung zurück */
function getGeubt(pruefungId: number): BearbeitungsStatus[] {
  return bearbeitungsStatus.value.filter(s => s.pruefung_id === pruefungId)
}

const bereichIcons: Record<string, string> = {
  WISO: 'mdi-scale-balance',
  GA1: 'mdi-cog-outline',
  GA2: 'mdi-code-braces',
  AP1: 'mdi-desktop-classic',
}
const bereichColors: Record<string, string> = {
  WISO: 'orange',
  GA1: 'blue',
  GA2: 'purple',
  AP1: 'green',
}

onMounted(async () => {
  try {
    const [p, status] = await Promise.all([
      pruefungenApi.getAll(),
      antwortenApi.getBearbeitungsStatus(),
    ])
    pruefungen.value = p
    bearbeitungsStatus.value = status
  } catch (e) {
    console.error('Prüfungen laden fehlgeschlagen:', e)
  } finally {
    loading.value = false
  }
})

function openDetail(id: number) {
  router.push(`/pruefungen/${id}`)
}
</script>

<template>
  <div>
    <h1 class="text-h4 mb-6">Prüfungen</h1>

    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon start>mdi-file-document-multiple</v-icon>
        {{ pruefungen.length }} Prüfungszeiträume
        <v-spacer />
        <v-text-field
          v-model="search"
          prepend-inner-icon="mdi-magnify"
          label="Filtern…"
          single-line
          hide-details
          density="compact"
          variant="outlined"
          clearable
          style="max-width: 300px"
        />
      </v-card-title>

      <v-data-table
        :headers="headers"
        :items="filtered"
        :loading="loading"
        :items-per-page="25"
        :sort-by="[{ key: 'jahr', order: 'desc' }]"
        class="elevation-0"
      >
        <template #item.semester="{ item }">
          <v-chip
            :color="item.semester === 'Sommer' ? 'orange' : 'blue'"
            variant="tonal"
            size="small"
            label
          >
            {{ item.semester }}
          </v-chip>
        </template>

        <template #item.geubt="{ item }">
          <div class="d-flex ga-1">
            <v-tooltip v-for="s in getGeubt(item.id)" :key="s.pruefungsbereich" :text="`${s.pruefungsbereich} – ${s.durchlaeufe}× ${s.ausgewertet ? 'geübt' : 'beantwortet'}`" location="top">
              <template #activator="{ props }">
                <v-chip
                  v-bind="props"
                  :color="s.ausgewertet ? (bereichColors[s.pruefungsbereich] || 'grey') : 'amber'"
                  :variant="s.ausgewertet ? 'flat' : 'outlined'"
                  size="x-small"
                  label
                  :prepend-icon="s.ausgewertet ? (bereichIcons[s.pruefungsbereich] || 'mdi-check') : 'mdi-pencil-outline'"
                >
                  {{ s.pruefungsbereich }}
                </v-chip>
              </template>
            </v-tooltip>
          </div>
        </template>

        <template #item.actions="{ item }">
          <v-btn
            icon="mdi-eye"
            size="small"
            variant="text"
            color="primary"
            @click="openDetail(item.id)"
          />
        </template>

        <template #no-data>
          <v-alert type="info" variant="tonal" class="ma-4">
            Keine Prüfungen gefunden.
          </v-alert>
        </template>
      </v-data-table>
    </v-card>
  </div>
</template>
