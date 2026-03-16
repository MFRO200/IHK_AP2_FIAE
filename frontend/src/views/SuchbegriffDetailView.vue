<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { suchbegriffeApi, trefferApi } from '@/services/api'
import type { Suchbegriff, Treffer } from '@/types'

const route = useRoute()
const router = useRouter()
const suchbegriff = ref<Suchbegriff | null>(null)
const allTreffer = ref<Treffer[]>([])
const loading = ref(true)
const filterTyp = ref<string | null>(null)

const id = computed(() => Number(route.params.id))

const sectionColors: Record<string, string> = {
  A: '#1565C0', B: '#2E7D32', C: '#E65100', D: '#6A1B9A', X: '#757575',
}
const sectionLabels: Record<string, string> = {
  A: 'A – Fachqualifikation',
  B: 'B – System-Integration',
  C: 'C – Wirtschaft & Soziales',
  D: 'D – Anwendungsentwicklung',
  X: 'X – Nicht zugeordnet',
}

/** Extrahiert die erste Seitenzahl aus "Seite(n): 2, 7" → 2 */
function parseFirstPage(seiten: string | null | undefined): number | undefined {
  if (!seiten) return undefined
  const match = seiten.match(/(\d+)/)
  return match ? Number(match[1]) : undefined
}

/* Treffer gruppiert nach Prüfungszeitraum */
const trefferByPruefung = computed(() => {
  const map = new Map<string, {
    zeitraum_label: string
    jahr: number
    semester: string
    pruefung_id: number
    dokumente: {
      id: number
      dateiname: string
      typ: string
      seiten: string
      kontext: string
      seitenanzahl: number
    }[]
  }>()

  for (const t of allTreffer.value) {
    if (!t.dokument?.pruefung) continue
    if (filterTyp.value && t.dokument.typ !== filterTyp.value) continue

    const p = t.dokument.pruefung
    const key = p.zeitraum_label
    if (!map.has(key)) {
      map.set(key, {
        zeitraum_label: p.zeitraum_label,
        jahr: p.jahr,
        semester: p.semester,
        pruefung_id: p.id,
        dokumente: [],
      })
    }
    map.get(key)!.dokumente.push({
      id: t.dokument.id,
      dateiname: t.dokument.dateiname,
      typ: t.dokument.typ,
      seiten: t.seiten || '',
      kontext: t.kontext || '',
      seitenanzahl: t.dokument.seitenanzahl,
    })
  }

  return [...map.values()].sort((a, b) => b.jahr - a.jahr || a.semester.localeCompare(b.semester))
})

const aufgabenCount = computed(() =>
  allTreffer.value.filter((t) => t.dokument?.typ === 'Aufgabe').length,
)
const loesungenCount = computed(() =>
  allTreffer.value.filter((t) => t.dokument?.typ === 'Lösung').length,
)

onMounted(async () => {
  try {
    const [sb, treffer] = await Promise.all([
      suchbegriffeApi.getById(id.value),
      trefferApi.getAll({ suchbegriffId: id.value }),
    ])
    suchbegriff.value = sb
    allTreffer.value = treffer
  } catch (e) {
    console.error('Suchbegriff laden fehlgeschlagen:', e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <v-btn
      variant="text"
      prepend-icon="mdi-arrow-left"
      class="mb-4"
      @click="router.push('/suchbegriffe')"
    >
      Zurück zu Suchbegriffe
    </v-btn>

    <v-progress-linear v-if="loading" indeterminate color="primary" />

    <template v-if="suchbegriff && !loading">
      <!-- Header -->
      <div class="d-flex align-center mb-2">
        <v-chip
          :color="sectionColors[suchbegriff.section] || 'grey'"
          variant="flat"
          label
          class="text-white font-weight-bold mr-3"
          size="large"
        >
          {{ suchbegriff.section }}
        </v-chip>
        <h1 class="text-h4">{{ suchbegriff.begriff }}</h1>
      </div>
      <p class="text-subtitle-1 text-medium-emphasis mb-6">
        {{ sectionLabels[suchbegriff.section] || suchbegriff.section }}
        · {{ suchbegriff.treffer_anzahl }} Treffer in {{ trefferByPruefung.length }} Prüfungszeiträumen
      </p>

      <!-- Filter-Chips -->
      <v-card class="mb-4">
        <v-card-text class="d-flex align-center ga-2">
          <span class="text-subtitle-2 mr-2">Filtern:</span>
          <v-chip
            :variant="filterTyp === null ? 'flat' : 'outlined'"
            color="primary"
            @click="filterTyp = null"
          >
            Alle ({{ allTreffer.length }})
          </v-chip>
          <v-chip
            :variant="filterTyp === 'Aufgabe' ? 'flat' : 'outlined'"
            color="primary"
            @click="filterTyp = filterTyp === 'Aufgabe' ? null : 'Aufgabe'"
          >
            Aufgaben ({{ aufgabenCount }})
          </v-chip>
          <v-chip
            :variant="filterTyp === 'Lösung' ? 'flat' : 'outlined'"
            color="success"
            @click="filterTyp = filterTyp === 'Lösung' ? null : 'Lösung'"
          >
            Lösungen ({{ loesungenCount }})
          </v-chip>
        </v-card-text>
      </v-card>

      <!-- Treffer nach Prüfungszeitraum -->
      <v-card
        v-for="group in trefferByPruefung"
        :key="group.zeitraum_label"
        class="mb-4"
      >
        <v-card-title class="d-flex align-center">
          <v-icon start color="primary">mdi-calendar</v-icon>
          {{ group.zeitraum_label }}
          <v-chip size="small" variant="tonal" color="primary" class="ml-2">
            {{ group.dokumente.length }} Dokument{{ group.dokumente.length !== 1 ? 'e' : '' }}
          </v-chip>
          <v-spacer />
          <v-btn
            variant="text"
            size="small"
            prepend-icon="mdi-eye"
            @click="router.push(`/pruefungen/${group.pruefung_id}`)"
          >
            Prüfung ansehen
          </v-btn>
        </v-card-title>

        <v-card-text class="pt-0">
          <v-list density="compact" lines="three">
            <v-list-item
              v-for="doc in group.dokumente"
              :key="doc.id"
              class="px-0"
            >
              <template #prepend>
                <v-icon
                  :color="doc.typ === 'Lösung' ? 'success' : 'primary'"
                  size="large"
                >
                  {{ doc.typ === 'Lösung' ? 'mdi-check-circle' : 'mdi-file-document' }}
                </v-icon>
              </template>

              <v-list-item-title class="font-weight-medium">
                {{ doc.dateiname }}
              </v-list-item-title>

              <v-list-item-subtitle>
                <v-chip
                  :color="doc.typ === 'Lösung' ? 'success' : 'primary'"
                  variant="tonal"
                  size="x-small"
                  label
                  class="mr-2"
                >
                  {{ doc.typ }}
                </v-chip>
                <span class="text-caption">{{ doc.seiten }}</span>
                <span class="text-caption ml-2">· {{ doc.seitenanzahl }} Seiten gesamt</span>
              </v-list-item-subtitle>

              <template #append>
                <v-btn
                  icon="mdi-file-eye"
                  size="small"
                  variant="text"
                  color="primary"
                  title="PDF an Fundstelle öffnen"
                  @click="router.push({ path: `/dokumente/${doc.id}/pdf`, query: { page: parseFirstPage(doc.seiten) || undefined } })"
                />
                <v-btn
                  icon="mdi-open-in-new"
                  size="small"
                  variant="text"
                  :href="parseFirstPage(doc.seiten) ? `/api/dokumente/${doc.id}/pdf#page=${parseFirstPage(doc.seiten)}` : `/api/dokumente/${doc.id}/pdf`"
                  target="_blank"
                  title="In neuem Tab an Fundstelle"
                />
                <v-btn
                  icon="mdi-download"
                  size="small"
                  variant="text"
                  :href="`/api/dokumente/${doc.id}/download`"
                  title="Herunterladen"
                />
              </template>

              <div
                v-if="doc.kontext"
                class="text-body-2 text-medium-emphasis mt-1 kontext-text"
              >
                {{ doc.kontext }}
              </div>
            </v-list-item>
          </v-list>
        </v-card-text>
      </v-card>

      <!-- Keine Treffer -->
      <v-alert
        v-if="!trefferByPruefung.length && !loading"
        type="info"
        variant="tonal"
      >
        Keine Treffer für den gewählten Filter.
      </v-alert>
    </template>
  </div>
</template>

<style scoped>
.kontext-text {
  font-style: italic;
  border-left: 3px solid #e0e0e0;
  padding-left: 12px;
  margin-top: 4px;
  max-width: 800px;
  white-space: pre-line;
}
</style>
