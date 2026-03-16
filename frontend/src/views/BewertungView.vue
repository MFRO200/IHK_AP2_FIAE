<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { bewertungApi, antwortenApi, pruefungenApi } from '@/services/api'
import type {
  Bewertung,
  BewertungResult,
  BewertungPruefungResult,
  ProviderStatus,
  Musterloesung,
  Antwort,
  Pruefung,
} from '@/types'

const route = useRoute()
const pruefungId = computed(() => Number(route.params.pruefungId))

const pruefung = ref<Pruefung | null>(null)
const antworten = ref<Antwort[]>([])
const bewertungen = ref<Bewertung[]>([])
const musterloesungen = ref<Musterloesung[]>([])
const ollamaStatus = ref<ProviderStatus | null>(null)
const openaiStatus = ref<ProviderStatus | null>(null)

const loading = ref(true)
const grading = ref(false)
const gradingSingle = ref<number | null>(null)
const snackbar = ref(false)
const snackbarText = ref('')
const snackbarColor = ref('success')

/* Provider-Auswahl */
const selectedProvider = ref<'ollama' | 'openai'>('ollama')
const selectedModel = ref('')
const availableModels = computed(() => {
  if (selectedProvider.value === 'ollama') return ollamaStatus.value?.models || []
  return openaiStatus.value?.models || []
})
const providerAvailable = computed(() => {
  if (selectedProvider.value === 'ollama') return ollamaStatus.value?.available === true
  return openaiStatus.value?.available === true
})

/* Antworten mit Bewertungs-Status */
const enrichedAntworten = computed(() => {
  return antworten.value
    .filter((a) => a.aufgabe && !a.aufgabe.startsWith('KEY_') && !a.aufgabe.startsWith('BEREICH_'))
    .map((a) => {
      const bew = bewertungen.value.find((b) => b.antwort_id === a.id)
      const ml = musterloesungen.value.find(
        (m) => m.aufgabe === a.aufgabe || m.aufgabe === normalizeAufgabe(a.aufgabe),
      )
      return { ...a, bewertung: bew || null, musterloesung: ml || null }
    })
    .sort((a, b) => (a.aufgabe > b.aufgabe ? 1 : -1))
})

const offeneAntworten = computed(() =>
  enrichedAntworten.value.filter(
    (a) =>
      a.punkte == null &&
      (
        (a.antwort_text && !a.antwort_text.includes('(noch nicht beantwortet)')) ||
        (a.bilder && a.bilder.length > 0)
      ),
  ),
)

const bewerteteAntworten = computed(() =>
  enrichedAntworten.value.filter((a) => a.bewertung),
)

/* Statistik */
const stats = computed(() => {
  const total = enrichedAntworten.value.length
  const bewertet = bewerteteAntworten.value.length
  const pSum = bewerteteAntworten.value.reduce(
    (s, a) => s + Number(a.bewertung?.punkte || 0),
    0,
  )
  const mSum = bewerteteAntworten.value.reduce(
    (s, a) => s + Number(a.bewertung?.max_punkte || 0),
    0,
  )
  return {
    total,
    bewertet,
    offen: offeneAntworten.value.length,
    punkte: pSum,
    maxPunkte: mSum,
    prozent: mSum > 0 ? Math.round((pSum / mSum) * 100) : 0,
  }
})

/* ── Load data ── */
onMounted(async () => {
  try {
    const [p, ant, bew, ml, os, oas] = await Promise.all([
      pruefungenApi.getById(pruefungId.value),
      antwortenApi.getByPruefung(pruefungId.value),
      bewertungApi.getByPruefung(pruefungId.value).catch(() => []),
      bewertungApi.getMusterloesungen(pruefungId.value).catch(() => []),
      bewertungApi.checkProvider('ollama').catch(() => ({ available: false, error: 'Timeout' })),
      bewertungApi.checkProvider('openai').catch(() => ({ available: false, error: 'Timeout' })),
    ])
    pruefung.value = p
    antworten.value = ant
    bewertungen.value = bew
    musterloesungen.value = ml
    ollamaStatus.value = os
    openaiStatus.value = oas

    // Auto-select best available model
    if (os.available && os.models?.length) {
      selectedProvider.value = 'ollama'
      selectedModel.value = os.models.find((m: string) => m.includes('llama')) || os.models[0]
    } else if (oas.available && oas.models?.length) {
      selectedProvider.value = 'openai'
      selectedModel.value = oas.models.find((m: string) => m.includes('gpt-4o')) || oas.models[0]
    }
  } catch (e) {
    snackbarText.value = `Fehler: ${e}`
    snackbarColor.value = 'error'
    snackbar.value = true
  } finally {
    loading.value = false
  }
})

/* ── Grading actions ── */

async function gradeOne(antwortId: number) {
  gradingSingle.value = antwortId
  try {
    const result = await bewertungApi.bewerten(
      antwortId,
      selectedProvider.value,
      selectedModel.value || undefined,
    )
    // Update bewertungen list
    const idx = bewertungen.value.findIndex(
      (b) => b.antwort_id === antwortId && b.llm_provider === selectedProvider.value,
    )
    const newBew: Bewertung = {
      id: 0,
      antwort_id: antwortId,
      punkte: result.punkte,
      max_punkte: result.max_punkte,
      feedback: result.feedback,
      bewertung_details: result.details as any,
      llm_provider: result.provider,
      llm_model: result.model,
      prompt_tokens: result.prompt_tokens || null,
      completion_tokens: result.completion_tokens || null,
      dauer_ms: result.dauer_ms,
      erstellt_am: new Date().toISOString(),
    }
    if (idx >= 0) bewertungen.value[idx] = newBew
    else bewertungen.value.push(newBew)

    // Update antwort punkte
    const ant = antworten.value.find((a) => a.id === antwortId)
    if (ant && ant.punkte == null) {
      ant.punkte = result.punkte
      ant.max_punkte = result.max_punkte
    }

    snackbarText.value = `Aufgabe bewertet: ${result.punkte}/${result.max_punkte} P.`
    snackbarColor.value = 'success'
    snackbar.value = true
  } catch (e) {
    snackbarText.value = `Fehler: ${e}`
    snackbarColor.value = 'error'
    snackbar.value = true
  } finally {
    gradingSingle.value = null
  }
}

async function gradeAll() {
  grading.value = true
  try {
    const result = await bewertungApi.bewertenPruefung(
      pruefungId.value,
      selectedProvider.value,
      selectedModel.value || undefined,
    )
    // Reload bewertungen
    bewertungen.value = await bewertungApi.getByPruefung(pruefungId.value).catch(() => [])
    // Reload antworten
    antworten.value = await antwortenApi.getByPruefung(pruefungId.value)

    snackbarText.value = `${result.bewertet} Aufgaben bewertet, ${result.fehler} Fehler`
    snackbarColor.value = result.fehler > 0 ? 'warning' : 'success'
    snackbar.value = true
  } catch (e) {
    snackbarText.value = `Fehler: ${e}`
    snackbarColor.value = 'error'
    snackbar.value = true
  } finally {
    grading.value = false
  }
}

/* ── Helpers ── */

function normalizeAufgabe(aufgabe: string): string {
  const m = aufgabe.match(/^(\d+)([a-z])$/i)
  if (m) return `${m[1]}.${m[2].toLowerCase()}`
  return aufgabe
}

function punkteColor(punkte: number, max: number): string {
  const pct = max > 0 ? punkte / max : 0
  if (pct >= 0.8) return 'success'
  if (pct >= 0.5) return 'warning'
  return 'error'
}

function konfidenzLabel(k: number | undefined): string {
  if (!k) return ''
  if (k >= 0.8) return 'Hohe Sicherheit'
  if (k >= 0.5) return 'Mittlere Sicherheit'
  return 'Niedrige Sicherheit'
}

/* Expanded detail rows */
const expandedRow = ref<number | null>(null)
function toggleRow(antwortId: number) {
  expandedRow.value = expandedRow.value === antwortId ? null : antwortId
}
</script>

<template>
  <v-container fluid class="pa-4">
    <!-- Header -->
    <v-row>
      <v-col>
        <div class="d-flex align-center mb-4">
          <v-btn icon="mdi-arrow-left" variant="text" :to="`/pruefungen/${pruefungId}`" />
          <h1 class="text-h5 ml-2">
            <v-icon start color="deep-purple">mdi-robot</v-icon>
            KI-Bewertung
            <span v-if="pruefung" class="text-grey-darken-1">
              – {{ pruefung.zeitraum_label }}
            </span>
          </h1>
        </div>
      </v-col>
    </v-row>

    <v-progress-linear v-if="loading" indeterminate color="deep-purple" />

    <template v-if="!loading">
      <!-- Provider Selection + Statistik -->
      <v-row>
        <v-col cols="12" md="6">
          <v-card variant="outlined">
            <v-card-title class="text-subtitle-1">
              <v-icon start>mdi-brain</v-icon>
              LLM-Provider
            </v-card-title>
            <v-card-text>
              <div class="d-flex ga-3 mb-3">
                <!-- Ollama -->
                <v-chip
                  :color="selectedProvider === 'ollama' ? 'deep-purple' : undefined"
                  :variant="selectedProvider === 'ollama' ? 'flat' : 'outlined'"
                  @click="selectedProvider = 'ollama'"
                  prepend-icon="mdi-server"
                >
                  Ollama (Lokal)
                  <template #append>
                    <v-icon
                      :color="ollamaStatus?.available ? 'success' : 'error'"
                      size="14"
                    >
                      {{ ollamaStatus?.available ? 'mdi-check-circle' : 'mdi-close-circle' }}
                    </v-icon>
                  </template>
                </v-chip>

                <!-- OpenAI -->
                <v-chip
                  :color="selectedProvider === 'openai' ? 'blue' : undefined"
                  :variant="selectedProvider === 'openai' ? 'flat' : 'outlined'"
                  @click="selectedProvider = 'openai'"
                  prepend-icon="mdi-cloud"
                >
                  OpenAI
                  <template #append>
                    <v-icon
                      :color="openaiStatus?.available ? 'success' : 'error'"
                      size="14"
                    >
                      {{ openaiStatus?.available ? 'mdi-check-circle' : 'mdi-close-circle' }}
                    </v-icon>
                  </template>
                </v-chip>
              </div>

              <!-- Model selection -->
              <v-select
                v-if="availableModels.length > 0"
                v-model="selectedModel"
                :items="availableModels"
                label="Modell"
                density="compact"
                variant="outlined"
                hide-details
              />
              <v-alert
                v-else-if="!providerAvailable"
                type="warning"
                density="compact"
                variant="tonal"
                class="mt-2"
              >
                {{ selectedProvider === 'ollama'
                  ? 'Ollama nicht erreichbar. Starte mit: docker run -d -p 11434:11434 ollama/ollama'
                  : 'OpenAI API-Key nicht konfiguriert. Setze OPENAI_API_KEY in backend/.env'
                }}
              </v-alert>
            </v-card-text>
          </v-card>
        </v-col>

        <v-col cols="12" md="6">
          <v-card variant="outlined">
            <v-card-title class="text-subtitle-1">
              <v-icon start>mdi-chart-box</v-icon>
              Übersicht
            </v-card-title>
            <v-card-text>
              <div class="d-flex ga-4 flex-wrap">
                <v-chip color="primary" variant="tonal">
                  {{ stats.total }} Aufgaben
                </v-chip>
                <v-chip color="success" variant="tonal">
                  {{ stats.bewertet }} bewertet
                </v-chip>
                <v-chip v-if="stats.offen > 0" color="warning" variant="tonal">
                  {{ stats.offen }} offen
                </v-chip>
                <v-chip
                  v-if="stats.bewertet > 0"
                  :color="punkteColor(stats.punkte, stats.maxPunkte)"
                  variant="tonal"
                >
                  {{ stats.punkte }}/{{ stats.maxPunkte }} P. ({{ stats.prozent }}%)
                </v-chip>
              </div>

              <!-- Alle bewerten Button -->
              <v-btn
                v-if="offeneAntworten.length > 0"
                class="mt-4"
                color="deep-purple"
                variant="flat"
                prepend-icon="mdi-play-circle"
                :loading="grading"
                :disabled="!providerAvailable"
                @click="gradeAll"
              >
                Alle {{ offeneAntworten.length }} offenen Aufgaben bewerten
              </v-btn>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Musterlösungen Info -->
      <v-row v-if="musterloesungen.length > 0" class="mt-1">
        <v-col>
          <v-alert type="info" variant="tonal" density="compact">
            <v-icon start>mdi-book-check</v-icon>
            {{ musterloesungen.length }} Musterlösungen verfügbar für diese Prüfung
          </v-alert>
        </v-col>
      </v-row>

      <!-- Antworten-Tabelle -->
      <v-row class="mt-2">
        <v-col>
          <v-card variant="outlined">
            <v-card-title class="text-subtitle-1">
              <v-icon start>mdi-format-list-checks</v-icon>
              Antworten & Bewertungen
            </v-card-title>

            <v-table density="compact" hover>
              <thead>
                <tr>
                  <th style="width: 80px">Aufgabe</th>
                  <th>Antwort (Auszug)</th>
                  <th style="width: 100px">Punkte</th>
                  <th style="width: 120px">KI-Bewertung</th>
                  <th style="width: 100px">Musterlsg.</th>
                  <th style="width: 60px"></th>
                </tr>
              </thead>
              <tbody>
                <template v-for="a in enrichedAntworten" :key="a.id">
                  <tr
                    :class="{ 'bg-grey-lighten-4': expandedRow === a.id }"
                    style="cursor: pointer"
                    @click="toggleRow(a.id)"
                  >
                    <td class="font-weight-bold">{{ a.aufgabe }}</td>
                    <td class="text-truncate" style="max-width: 300px">
                      {{ a.antwort_text?.substring(0, 80) || '—' }}
                    </td>
                    <td>
                      <v-chip
                        v-if="a.punkte != null"
                        :color="punkteColor(Number(a.punkte), Number(a.max_punkte || 10))"
                        size="small"
                        variant="tonal"
                      >
                        {{ a.punkte }}/{{ a.max_punkte }}
                      </v-chip>
                      <span v-else class="text-grey">—</span>
                    </td>
                    <td>
                      <template v-if="a.bewertung">
                        <v-chip
                          :color="punkteColor(Number(a.bewertung.punkte), Number(a.bewertung.max_punkte || 10))"
                          size="small"
                          variant="flat"
                        >
                          <v-icon start size="14">mdi-robot</v-icon>
                          {{ a.bewertung.punkte }}/{{ a.bewertung.max_punkte }}
                        </v-chip>
                      </template>
                      <v-btn
                        v-else-if="(a.antwort_text && !a.antwort_text.includes('(noch nicht')) || (a.bilder && a.bilder.length > 0)"
                        size="x-small"
                        variant="tonal"
                        color="deep-purple"
                        :loading="gradingSingle === a.id"
                        :disabled="!providerAvailable"
                        @click.stop="gradeOne(a.id)"
                      >
                        <v-icon start size="14">{{ a.bilder?.length ? 'mdi-image-search' : 'mdi-robot' }}</v-icon>
                        {{ a.bilder?.length ? 'Bild bewerten' : 'Bewerten' }}
                      </v-btn>
                      <span v-else class="text-grey">—</span>
                    </td>
                    <td>
                      <v-icon
                        v-if="a.musterloesung"
                        color="success"
                        size="20"
                        title="Musterlösung vorhanden"
                      >
                        mdi-book-check
                      </v-icon>
                      <v-icon v-else color="grey" size="20" title="Keine Musterlösung">
                        mdi-book-remove
                      </v-icon>
                    </td>
                    <td>
                      <v-icon size="20">
                        {{ expandedRow === a.id ? 'mdi-chevron-up' : 'mdi-chevron-down' }}
                      </v-icon>
                    </td>
                  </tr>

                  <!-- Expanded detail row -->
                  <tr v-if="expandedRow === a.id">
                    <td colspan="6" class="pa-4 bg-grey-lighten-5">
                      <v-row>
                        <!-- Antwort -->
                        <v-col cols="12" md="6">
                          <div class="text-subtitle-2 mb-1">
                            <v-icon start size="16" color="primary">mdi-account-edit</v-icon>
                            Deine Antwort
                          </div>
                          <div
                            class="text-body-2 pa-2 rounded"
                            style="
                              background: white;
                              border: 1px solid #e0e0e0;
                              white-space: pre-wrap;
                              max-height: 300px;
                              overflow-y: auto;
                            "
                          >
                            {{ a.antwort_text || '(leer)' }}
                          </div>
                          <!-- Hochgeladene Bilder / Scans -->
                          <div v-if="a.bilder?.length" class="mt-2">
                            <v-chip size="x-small" color="info" variant="tonal" class="mb-1">
                              <v-icon start size="12">mdi-image-multiple</v-icon>
                              {{ a.bilder.length }} Bild(er) / Scan(s) hochgeladen
                            </v-chip>
                            <div class="d-flex flex-wrap ga-2">
                              <v-img
                                v-for="bild in a.bilder.filter((b: any) => !b.dateiname.toLowerCase().endsWith('.pdf'))"
                                :key="bild.id"
                                :src="`/api/antworten/${a.id}/bilder/${bild.id}/file`"
                                width="120"
                                height="90"
                                cover
                                class="rounded border"
                              />
                              <v-chip
                                v-for="bild in a.bilder.filter((b: any) => b.dateiname.toLowerCase().endsWith('.pdf'))"
                                :key="bild.id"
                                size="small"
                                color="red"
                                variant="tonal"
                              >
                                <v-icon start size="14">mdi-file-pdf-box</v-icon>
                                {{ bild.dateiname }}
                              </v-chip>
                            </div>
                          </div>
                        </v-col>

                        <!-- Musterlösung -->
                        <v-col cols="12" md="6">
                          <div class="text-subtitle-2 mb-1">
                            <v-icon start size="16" color="success">mdi-book-check</v-icon>
                            Musterlösung
                          </div>
                          <div
                            v-if="a.musterloesung"
                            class="text-body-2 pa-2 rounded"
                            style="
                              background: #f1f8e9;
                              border: 1px solid #c5e1a5;
                              white-space: pre-wrap;
                              max-height: 300px;
                              overflow-y: auto;
                            "
                          >
                            {{ a.musterloesung.erwartung_text }}
                          </div>
                          <v-alert v-else type="info" variant="tonal" density="compact">
                            Keine Musterlösung für diese Aufgabe gefunden
                          </v-alert>
                        </v-col>
                      </v-row>

                      <!-- KI-Feedback -->
                      <v-row v-if="a.bewertung" class="mt-2">
                        <v-col>
                          <v-card variant="tonal" color="deep-purple" density="compact">
                            <v-card-title class="text-subtitle-2">
                              <v-icon start size="16">mdi-robot</v-icon>
                              KI-Feedback
                              <v-chip
                                class="ml-2"
                                size="x-small"
                                variant="flat"
                                :color="
                                  punkteColor(
                                    Number(a.bewertung.punkte),
                                    Number(a.bewertung.max_punkte || 10),
                                  )
                                "
                              >
                                {{ a.bewertung.punkte }}/{{ a.bewertung.max_punkte }} P.
                              </v-chip>
                              <v-chip class="ml-1" size="x-small" variant="outlined">
                                {{ a.bewertung.llm_provider }}:{{ a.bewertung.llm_model }}
                              </v-chip>
                              <v-chip
                                v-if="a.bewertung.dauer_ms"
                                class="ml-1"
                                size="x-small"
                                variant="outlined"
                              >
                                {{ (a.bewertung.dauer_ms / 1000).toFixed(1) }}s
                              </v-chip>
                            </v-card-title>
                            <v-card-text>
                              <p class="mb-2">{{ a.bewertung.feedback }}</p>

                              <!-- Korrekte / Fehlende Aspekte -->
                              <div
                                v-if="a.bewertung.bewertung_details?.korrekte_aspekte?.length"
                                class="mb-2"
                              >
                                <span class="text-caption font-weight-bold text-success">
                                  Korrekt:
                                </span>
                                <v-chip
                                  v-for="(asp, i) in a.bewertung.bewertung_details.korrekte_aspekte"
                                  :key="i"
                                  size="x-small"
                                  color="success"
                                  variant="tonal"
                                  class="ma-1"
                                >
                                  {{ asp }}
                                </v-chip>
                              </div>

                              <div
                                v-if="a.bewertung.bewertung_details?.fehlende_aspekte?.length"
                              >
                                <span class="text-caption font-weight-bold text-error">
                                  Fehlend:
                                </span>
                                <v-chip
                                  v-for="(asp, i) in a.bewertung.bewertung_details.fehlende_aspekte"
                                  :key="i"
                                  size="x-small"
                                  color="error"
                                  variant="tonal"
                                  class="ma-1"
                                >
                                  {{ asp }}
                                </v-chip>
                              </div>

                              <!-- Konfidenz -->
                              <div
                                v-if="a.bewertung.bewertung_details?.konfidenz"
                                class="mt-2 text-caption text-grey"
                              >
                                <v-icon size="12">mdi-shield-check</v-icon>
                                {{ konfidenzLabel(a.bewertung.bewertung_details.konfidenz as number) }}
                                ({{ ((a.bewertung.bewertung_details.konfidenz as number) * 100).toFixed(0) }}%)
                              </div>
                            </v-card-text>
                          </v-card>
                        </v-col>
                      </v-row>

                      <!-- Grade button in expanded view -->
                      <v-row v-if="!a.bewertung && a.antwort_text && !a.antwort_text.includes('(noch nicht')" class="mt-2">
                        <v-col>
                          <v-btn
                            color="deep-purple"
                            variant="flat"
                            prepend-icon="mdi-robot"
                            :loading="gradingSingle === a.id"
                            :disabled="!providerAvailable"
                            @click="gradeOne(a.id)"
                          >
                            Jetzt mit KI bewerten
                          </v-btn>
                        </v-col>
                      </v-row>
                    </td>
                  </tr>
                </template>
              </tbody>
            </v-table>
          </v-card>
        </v-col>
      </v-row>
    </template>

    <v-snackbar v-model="snackbar" :color="snackbarColor" timeout="4000">
      {{ snackbarText }}
    </v-snackbar>
  </v-container>
</template>
