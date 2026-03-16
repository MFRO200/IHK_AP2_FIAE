<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { suchbegriffeApi } from '@/services/api'
import type { Suchbegriff } from '@/types'

const router = useRouter()
const suchbegriffe = ref<Suchbegriff[]>([])
const loading = ref(true)
const search = ref('')
const selectedSection = ref<string | null>(null)

const sections = ['A', 'B', 'C', 'D', 'X']

const sectionLabels: Record<string, string> = {
  A: 'A – Fachqualifikation',
  B: 'B – System-Integration',
  C: 'C – Wirtschaft & Soziales',
  D: 'D – Anwendungsentwicklung',
  X: 'X – Nicht zugeordnet',
}

const sectionColors: Record<string, string> = {
  A: 'blue',
  B: 'green',
  C: 'orange',
  D: 'purple',
  X: 'grey',
}

const headers = [
  { title: 'Bereich', key: 'section', width: '120px' },
  { title: 'Begriff', key: 'begriff' },
  { title: 'Treffer', key: 'treffer_anzahl', width: '100px' },
  { title: 'Aktionen', key: 'actions', sortable: false, width: '100px' },
]

const filtered = computed(() => {
  let items = suchbegriffe.value
  if (selectedSection.value) {
    items = items.filter((s) => s.section === selectedSection.value)
  }
  if (search.value) {
    const q = search.value.toLowerCase()
    items = items.filter(
      (s) => s.begriff.toLowerCase().includes(q),
    )
  }
  return items
})

const sectionCounts = computed(() => {
  const counts: Record<string, number> = {}
  for (const s of suchbegriffe.value) {
    counts[s.section] = (counts[s.section] || 0) + 1
  }
  return counts
})

onMounted(async () => {
  try {
    suchbegriffe.value = await suchbegriffeApi.getAll()
  } catch (e) {
    console.error('Suchbegriffe laden fehlgeschlagen:', e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <h1 class="text-h4 mb-6">Suchbegriffe</h1>

    <!-- Section-Filter Chips -->
    <v-card class="mb-4">
      <v-card-text>
        <div class="d-flex align-center flex-wrap ga-2">
          <span class="text-subtitle-2 mr-2">Bereich:</span>
          <v-chip
            :variant="selectedSection === null ? 'flat' : 'outlined'"
            color="primary"
            @click="selectedSection = null"
          >
            Alle ({{ suchbegriffe.length }})
          </v-chip>
          <v-chip
            v-for="sec in sections"
            :key="sec"
            :variant="selectedSection === sec ? 'flat' : 'outlined'"
            :color="sectionColors[sec]"
            @click="selectedSection = selectedSection === sec ? null : sec"
          >
            {{ sec }} ({{ sectionCounts[sec] || 0 }})
          </v-chip>
        </div>
      </v-card-text>
    </v-card>

    <!-- Tabelle -->
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon start>mdi-tag-multiple</v-icon>
        {{ filtered.length }} Suchbegriffe
        <v-spacer />
        <v-text-field
          v-model="search"
          prepend-inner-icon="mdi-magnify"
          label="Name suchen…"
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
        :sort-by="[{ key: 'begriff', order: 'asc' }]"
      >
        <template #item.section="{ item }">
          <v-chip
            :color="sectionColors[item.section] || 'grey'"
            variant="flat"
            size="small"
            label
            class="font-weight-bold"
          >
            {{ item.section }}
          </v-chip>
        </template>

        <template #item.treffer_anzahl="{ item }">
          <v-chip
            :color="item.treffer_anzahl > 0 ? 'success' : 'grey'"
            variant="tonal"
            size="small"
          >
            {{ item.treffer_anzahl }}
          </v-chip>
        </template>

        <template #item.actions="{ item }">
          <v-btn
            icon="mdi-eye"
            size="small"
            variant="text"
            color="primary"
            :disabled="item.treffer_anzahl === 0"
            @click="router.push(`/suchbegriffe/${item.id}`)"
          />
        </template>

        <template #no-data>
          <v-alert type="info" variant="tonal" class="ma-4">
            Keine Suchbegriffe gefunden.
          </v-alert>
        </template>
      </v-data-table>
    </v-card>
  </div>
</template>
