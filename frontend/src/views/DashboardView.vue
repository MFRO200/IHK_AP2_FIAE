<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { pruefungenApi, suchbegriffeApi, trefferApi } from '@/services/api'
import { useSettings } from '@/composables/useSettings'
import type { TrefferStat, TrefferStatPruefung, ThemenblockStat, PruefungsbereichStat, Suchbegriff } from '@/types'

const router = useRouter()
const { istBereichSichtbar, filterAktiv, fachbereichLabel } = useSettings()
const stats = ref<TrefferStat[]>([])
const statsPruefung = ref<TrefferStatPruefung[]>([])
const themenblockStats = ref<ThemenblockStat[]>([])
const pruefungsbereichStats = ref<PruefungsbereichStat[]>([])
const allSuchbegriffe = ref<Suchbegriff[]>([])
const pruefungenCount = ref(0)
const suchbegriffeCount = ref(0)
const loading = ref(true)
const expandedSection = ref<string | null>(null)
const expandedThemenblock = ref<string | null>(null)
const sectionTab = ref<Record<string, string>>({})  // section -> 'pruefungen' | 'begriffe'

const totalTreffer = computed(() =>
  stats.value.reduce((sum, s) => sum + Number(s.treffer), 0),
)
const totalBegriffe = computed(() =>
  stats.value.reduce((sum, s) => sum + Number(s.begriffe), 0),
)

const sectionColors: Record<string, string> = {
  A: '#C62828',   // rot – MUSS
  B: '#F57F17',   // amber – SOLLTE
  C: '#1565C0',   // blau – KANN
  D: '#757575',   // grau – nie geprüft
  X: '#424242',
}

const sectionLabels: Record<string, string> = {
  A: 'A – UNBEDINGT KÖNNEN – regelmäßig geprüft',
  B: 'B – SOLLTE MAN KÖNNEN – kommt regelmäßig vor',
  C: 'C – KENNEN REICHT – 1–2× oder nur Katalog',
  D: 'D – (NOCH) NIE GEPRÜFT',
  X: 'X – Nicht zugeordnet',
}

/** Prüfungen für eine bestimmte Section (sortiert nach Jahr absteigend) */
function pruefungenForSection(section: string) {
  return statsPruefung.value
    .filter((s) => s.section === section)
    .sort((a, b) => b.jahr - a.jahr || a.semester.localeCompare(b.semester))
}

/** Suchbegriffe für eine Section (sortiert nach Treffer absteigend) */
function begriffeForSection(section: string) {
  return allSuchbegriffe.value
    .filter((b) => b.section === section)
    .sort((a, b) => b.treffer_anzahl - a.treffer_anzahl)
}

/** Suchbegriffe für einen Themenblock (sortiert nach Treffer absteigend) */
function begriffeForThemenblock(themenblock: string) {
  return allSuchbegriffe.value
    .filter((b) => b.themenblock === themenblock)
    .sort((a, b) => b.treffer_anzahl - a.treffer_anzahl)
}

/** Total treffer across all themenblocks */
const totalThemenblockTreffer = computed(() =>
  themenblockStats.value.reduce((sum, t) => sum + Number(t.treffer), 0),
)

function toggleSection(section: string) {
  if (expandedSection.value === section) {
    expandedSection.value = null
  } else {
    expandedSection.value = section
    if (!sectionTab.value[section]) sectionTab.value[section] = 'pruefungen'
  }
}

function toggleThemenblock(tb: string) {
  expandedThemenblock.value = expandedThemenblock.value === tb ? null : tb
}

/* ── Prüfungsbereiche ── */
const bereichLabels: Record<string, string> = {
  GA1: 'GA1 – Planen eines Softwareproduktes',
  GA2: 'GA2 – Entwicklung und Umsetzung von Algorithmen',
  WISO: 'WISO – Wirtschafts- und Sozialkunde',
  AP1: 'AP1 – Einrichten eines IT-gestützten Arbeitsplatzes',
  'GA1 FISI': 'GA1 FISI – Fachqualifikation Systemintegration',
  'GA1 IK': 'GA1 IK – Fachqualifikation Informatikkaufleute',
  'GA1 IT-SE': 'GA1 IT-SE – Fachqualifikation IT-System-Elektronik',
  'GA1 IT-SK': 'GA1 IT-SK – Fachqualifikation IT-System-Kaufleute',
  Sonstige: 'Sonstige (Handreichung, Belegsatz etc.)',
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
  Sonstige: '–',
}

const totalBereichDokumente = computed(() =>
  pruefungsbereichStats.value.reduce((s, b) => s + Number(b.dokumente), 0),
)
const totalBereichTreffer = computed(() =>
  pruefungsbereichStats.value.reduce((s, b) => s + Number(b.treffer), 0),
)

/* FIAE-Hauptbereiche vs. andere Berufe (gefiltert nach Fachbereich) */
const fiaeBereiche = ['GA1', 'GA2', 'WISO', 'AP1', 'Sonstige']
const fiaeStats = computed(() =>
  pruefungsbereichStats.value.filter((b) =>
    filterAktiv.value
      ? istBereichSichtbar(b.pruefungsbereich)
      : fiaeBereiche.includes(b.pruefungsbereich),
  ),
)
const andereBerufeStats = computed(() =>
  filterAktiv.value
    ? [] // Bei aktivem Filter: andere Berufe ausblenden
    : pruefungsbereichStats.value.filter((b) => !fiaeBereiche.includes(b.pruefungsbereich)),
)
const showAndereBerufe = ref(false)

onMounted(async () => {
  try {
    const [s, p, sb, sp, tb, pb] = await Promise.all([
      trefferApi.getStats(),
      pruefungenApi.getAll(),
      suchbegriffeApi.getAll(),
      trefferApi.getStatsPerPruefung(),
      trefferApi.getStatsPerThemenblock(),
      trefferApi.getStatsPerPruefungsbereich(),
    ])
    stats.value = s
    pruefungenCount.value = p.length
    suchbegriffeCount.value = sb.length
    allSuchbegriffe.value = sb
    statsPruefung.value = sp
    themenblockStats.value = tb
    pruefungsbereichStats.value = pb
  } catch (e) {
    console.error('Dashboard laden fehlgeschlagen:', e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <h1 class="text-h4 mb-6">Dashboard</h1>

    <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-4" />

    <!-- KPI-Karten -->
    <v-row v-if="!loading">
      <v-col cols="12" sm="6" md="3">
        <v-card color="primary" variant="flat">
          <v-card-text class="text-center text-white">
            <v-icon size="40" class="mb-2">mdi-file-document-multiple</v-icon>
            <div class="text-h3 font-weight-bold">{{ pruefungenCount }}</div>
            <div class="text-subtitle-1">Prüfungen</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <v-card color="accent" variant="flat">
          <v-card-text class="text-center text-white">
            <v-icon size="40" class="mb-2">mdi-tag-multiple</v-icon>
            <div class="text-h3 font-weight-bold">{{ suchbegriffeCount }}</div>
            <div class="text-subtitle-1">Suchbegriffe</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <v-card color="success" variant="flat">
          <v-card-text class="text-center text-white">
            <v-icon size="40" class="mb-2">mdi-target</v-icon>
            <div class="text-h3 font-weight-bold">{{ totalTreffer }}</div>
            <div class="text-subtitle-1">Treffer gesamt</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <v-card color="info" variant="flat">
          <v-card-text class="text-center text-white">
            <v-icon size="40" class="mb-2">mdi-book-open-variant</v-icon>
            <div class="text-h3 font-weight-bold">{{ totalBegriffe }}</div>
            <div class="text-subtitle-1">Begriffe mit Treffern</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Prüfungsbereiche (IHK AP2 Struktur) -->
    <v-row v-if="!loading && pruefungsbereichStats.length" class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>
            <v-icon start>mdi-school</v-icon>
            Prüfungsbereiche – {{ filterAktiv ? fachbereichLabel : 'Fachinformatiker Anwendungsentwicklung (IHK AP2)' }}
          </v-card-title>
          <v-card-subtitle class="pb-2">
            Verteilung der Dokumente und Treffer nach Prüfungsbereich
          </v-card-subtitle>
          <v-card-text>
            <v-row>
              <v-col
                v-for="b in fiaeStats"
                :key="b.pruefungsbereich"
                cols="12"
                sm="6"
                :md="b.pruefungsbereich === 'Sonstige' ? 12 : 3"
              >
                <v-card
                  :color="bereichColors[b.pruefungsbereich] || '#757575'"
                  variant="tonal"
                  class="pa-3 bereich-card"
                  rounded="lg"
                  @click="router.push(`/pruefungsbereiche/${b.pruefungsbereich}`)"
                >
                  <div class="d-flex align-center mb-2">
                    <v-icon
                      :icon="bereichIcons[b.pruefungsbereich] || 'mdi-file'"
                      size="28"
                      class="mr-2"
                    />
                    <div>
                      <div class="text-subtitle-2 font-weight-bold">
                        {{ b.pruefungsbereich }}
                      </div>
                      <div class="text-caption" style="line-height: 1.2">
                        {{ (bereichLabels[b.pruefungsbereich] || b.pruefungsbereich).replace(/^[^ ]+ – /, '') }}
                      </div>
                    </div>
                    <v-spacer />
                    <v-chip
                      size="x-small"
                      variant="flat"
                      :color="bereichColors[b.pruefungsbereich] || '#757575'"
                      class="text-white font-weight-bold"
                    >
                      {{ bereichGewichtung[b.pruefungsbereich] || '–' }}
                    </v-chip>
                  </div>
                  <v-divider class="mb-2" />
                  <div class="d-flex justify-space-between text-body-2">
                    <span>
                      <v-icon size="14" class="mr-1">mdi-file-pdf-box</v-icon>
                      {{ b.dokumente }} Dok.
                    </span>
                    <span>
                      <v-icon size="14" class="mr-1">mdi-book-open-page-variant</v-icon>
                      {{ b.seiten }} S.
                    </span>
                    <span>
                      <v-icon size="14" class="mr-1">mdi-target</v-icon>
                      {{ b.treffer }} Treffer
                    </span>
                  </div>
                  <v-progress-linear
                    :model-value="totalBereichTreffer ? (Number(b.treffer) / totalBereichTreffer) * 100 : 0"
                    :color="bereichColors[b.pruefungsbereich] || '#757575'"
                    height="6"
                    rounded
                    class="mt-2"
                  />
                </v-card>
              </v-col>
            </v-row>

            <!-- Andere IT-Berufe (einklappbar) -->
            <div v-if="andereBerufeStats.length" class="mt-4">
              <v-btn
                variant="text"
                size="small"
                :prepend-icon="showAndereBerufe ? 'mdi-chevron-up' : 'mdi-chevron-down'"
                @click="showAndereBerufe = !showAndereBerufe"
                class="text-medium-emphasis"
              >
                GA1 anderer IT-Berufe ({{ andereBerufeStats.reduce((s, b) => s + Number(b.dokumente), 0) }} Dok.)
              </v-btn>
              <v-expand-transition>
                <v-row v-if="showAndereBerufe" class="mt-2">
                  <v-col
                    v-for="b in andereBerufeStats"
                    :key="b.pruefungsbereich"
                    cols="12"
                    sm="6"
                    md="3"
                  >
                    <v-card
                      :color="bereichColors[b.pruefungsbereich] || '#757575'"
                      variant="tonal"
                      class="pa-3 bereich-card"
                      rounded="lg"
                      @click="router.push(`/pruefungsbereiche/${b.pruefungsbereich}`)"
                    >
                      <div class="d-flex align-center mb-2">
                        <v-icon
                          :icon="bereichIcons[b.pruefungsbereich] || 'mdi-file'"
                          size="28"
                          class="mr-2"
                        />
                        <div>
                          <div class="text-subtitle-2 font-weight-bold">
                            {{ b.pruefungsbereich }}
                          </div>
                          <div class="text-caption" style="line-height: 1.2">
                            {{ (bereichLabels[b.pruefungsbereich] || b.pruefungsbereich).replace(/^[^ ]+ – /, '') }}
                          </div>
                        </div>
                      </div>
                      <v-divider class="mb-2" />
                      <div class="d-flex justify-space-between text-body-2">
                        <span>
                          <v-icon size="14" class="mr-1">mdi-file-pdf-box</v-icon>
                          {{ b.dokumente }} Dok.
                        </span>
                        <span>
                          <v-icon size="14" class="mr-1">mdi-book-open-page-variant</v-icon>
                          {{ b.seiten }} S.
                        </span>
                      </div>
                    </v-card>
                  </v-col>
                </v-row>
              </v-expand-transition>
            </div>

            <!-- Zusammenfassung -->
            <v-alert type="info" variant="tonal" density="compact" class="mt-4" icon="mdi-information-outline">
              <div class="text-body-2">
                <strong>IHK Abschlussprüfung Teil 2 – Fachinformatiker Anwendungsentwicklung:</strong><br>
                <strong>GA1</strong> (25 %) Planen eines Softwareproduktes &bull;
                <strong>GA2</strong> (25 %) Entwicklung und Umsetzung von Algorithmen &bull;
                <strong>WISO</strong> (10 %) Wirtschafts- und Sozialkunde<br>
                <span class="text-caption text-medium-emphasis">
                  AP1 (20 %) – Einrichten eines IT-gestützten Arbeitsplatzes (gesonderte Prüfung).
                  Gesamtnote: AP1 20 % + GA1 25 % + GA2 25 % + WISO 10 % + Projektarbeit 50 % (abzüglich Sperrklausel).
                </span>
              </div>
            </v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Treffer nach Section -->
    <v-row v-if="!loading" class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>
            <v-icon start>mdi-chart-bar</v-icon>
            Treffer-Statistik nach Prüfungsbereich
          </v-card-title>
          <v-card-text>
            <v-table>
              <thead>
                <tr>
                  <th style="width: 2%"></th>
                  <th>Bereich</th>
                  <th class="text-right">Begriffe</th>
                  <th class="text-right">Treffer</th>
                  <th style="width: 40%">Verteilung</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="s in stats" :key="s.section">
                  <!-- Section Übersichtszeile -->
                  <tr
                    style="cursor: pointer"
                    @click="toggleSection(s.section)"
                    class="section-row"
                  >
                    <td class="text-center px-0">
                      <v-icon size="18">
                        {{ expandedSection === s.section ? 'mdi-chevron-down' : 'mdi-chevron-right' }}
                      </v-icon>
                    </td>
                    <td>
                      <v-chip
                        :color="sectionColors[s.section] || 'grey'"
                        variant="flat"
                        size="small"
                        label
                        class="text-white font-weight-bold"
                      >
                        {{ s.section }}
                      </v-chip>
                      <span class="ml-2">{{ sectionLabels[s.section] || s.section }}</span>
                    </td>
                    <td class="text-right font-weight-medium">
                      {{ Number(s.begriffe) }}
                    </td>
                    <td class="text-right font-weight-medium">
                      {{ Number(s.treffer) }}
                    </td>
                    <td>
                      <v-progress-linear
                        :model-value="
                          totalTreffer
                            ? (Number(s.treffer) / totalTreffer) * 100
                            : 0
                        "
                        :color="sectionColors[s.section] || 'grey'"
                        height="20"
                        rounded
                      >
                        <template #default>
                          <span class="text-caption font-weight-bold">
                            {{
                              totalTreffer
                                ? ((Number(s.treffer) / totalTreffer) * 100).toFixed(1)
                                : 0
                            }}%
                          </span>
                        </template>
                      </v-progress-linear>
                    </td>
                  </tr>
                  <!-- Aufgeklappter Bereich: Tabs (Prüfungen / Begriffe) -->
                  <template v-if="expandedSection === s.section">
                    <tr class="expanded-row">
                      <td colspan="5" class="pa-0">
                        <v-tabs
                          v-model="sectionTab[s.section]"
                          density="compact"
                          :color="sectionColors[s.section] || 'grey'"
                          class="px-4"
                        >
                          <v-tab value="pruefungen" size="small">
                            <v-icon start size="16">mdi-file-document-outline</v-icon>
                            Prüfungen ({{ pruefungenForSection(s.section).length }})
                          </v-tab>
                          <v-tab value="begriffe" size="small">
                            <v-icon start size="16">mdi-tag-multiple</v-icon>
                            Begriffe ({{ begriffeForSection(s.section).length }})
                          </v-tab>
                        </v-tabs>
                      </td>
                    </tr>

                    <!-- Tab: Prüfungen -->
                    <template v-if="sectionTab[s.section] === 'pruefungen'">
                      <tr
                        v-for="p in pruefungenForSection(s.section)"
                        :key="`${s.section}-p-${p.pruefung_id}`"
                        class="expanded-row"
                        style="cursor: pointer"
                        @click="router.push(`/pruefungen/${p.pruefung_id}`)"
                      >
                        <td></td>
                        <td class="pl-10">
                          <v-icon size="14" class="mr-1" color="grey">mdi-file-document-outline</v-icon>
                          {{ p.zeitraum_label }}
                        </td>
                        <td class="text-right">{{ Number(p.begriffe) }}</td>
                        <td class="text-right">{{ Number(p.treffer) }}</td>
                        <td>
                          <v-progress-linear
                            :model-value="
                              Number(s.treffer)
                                ? (Number(p.treffer) / Number(s.treffer)) * 100
                                : 0
                            "
                            :color="sectionColors[s.section] || 'grey'"
                            height="12"
                            rounded
                            bg-opacity="0.15"
                          />
                        </td>
                      </tr>
                    </template>

                    <!-- Tab: Begriffe -->
                    <template v-if="sectionTab[s.section] === 'begriffe'">
                      <tr class="expanded-row">
                        <td colspan="5" class="pa-3">
                          <div class="d-flex flex-wrap ga-1">
                            <v-chip
                              v-for="b in begriffeForSection(s.section)"
                              :key="b.id"
                              size="small"
                              variant="tonal"
                              :color="sectionColors[s.section] || 'grey'"
                              class="clickable-chip"
                              @click="router.push(`/suchbegriffe/${b.id}`)"
                            >
                              {{ b.begriff }}
                              <template #append>
                                <span class="text-caption ml-1 font-weight-bold">
                                  {{ b.treffer_anzahl }}
                                </span>
                              </template>
                            </v-chip>
                          </div>
                        </td>
                      </tr>
                    </template>
                  </template>
                </template>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Treffer nach Themenblock -->
    <v-row v-if="!loading && themenblockStats.length" class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>
            <v-icon start>mdi-view-grid-outline</v-icon>
            Treffer nach Themenblock
            <span class="text-caption text-medium-emphasis ml-2">(Score-Tabelle)</span>
          </v-card-title>
          <v-card-text>
            <v-table>
              <thead>
                <tr>
                  <th style="width: 2%"></th>
                  <th>Themenblock</th>
                  <th class="text-right">Begriffe</th>
                  <th class="text-right">Treffer</th>
                  <th style="width: 40%">Verteilung</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="tb in themenblockStats" :key="tb.themenblock">
                  <tr
                    style="cursor: pointer"
                    @click="toggleThemenblock(tb.themenblock)"
                    class="section-row"
                  >
                    <td class="text-center px-0">
                      <v-icon size="18">
                        {{ expandedThemenblock === tb.themenblock ? 'mdi-chevron-down' : 'mdi-chevron-right' }}
                      </v-icon>
                    </td>
                    <td>
                      <v-icon size="16" class="mr-1" color="teal">mdi-folder-outline</v-icon>
                      {{ tb.themenblock }}
                    </td>
                    <td class="text-right font-weight-medium">{{ Number(tb.begriffe) }}</td>
                    <td class="text-right font-weight-medium">{{ Number(tb.treffer) }}</td>
                    <td>
                      <v-progress-linear
                        :model-value="
                          totalThemenblockTreffer
                            ? (Number(tb.treffer) / totalThemenblockTreffer) * 100
                            : 0
                        "
                        color="teal"
                        height="20"
                        rounded
                      >
                        <template #default>
                          <span class="text-caption font-weight-bold">
                            {{
                              totalThemenblockTreffer
                                ? ((Number(tb.treffer) / totalThemenblockTreffer) * 100).toFixed(1)
                                : 0
                            }}%
                          </span>
                        </template>
                      </v-progress-linear>
                    </td>
                  </tr>
                  <!-- Aufgeklappter Themenblock: Begriffe -->
                  <template v-if="expandedThemenblock === tb.themenblock">
                    <tr class="expanded-row">
                      <td colspan="5" class="pa-3">
                        <div class="d-flex flex-wrap ga-1">
                          <v-chip
                            v-for="b in begriffeForThemenblock(tb.themenblock)"
                            :key="b.id"
                            size="small"
                            variant="tonal"
                            :color="sectionColors[b.section] || 'grey'"
                            class="clickable-chip"
                            @click="router.push(`/suchbegriffe/${b.id}`)"
                          >
                            <v-icon start size="10">
                              {{ b.section === 'A' ? 'mdi-alert-circle' : b.section === 'B' ? 'mdi-alert' : b.section === 'C' ? 'mdi-information' : 'mdi-minus-circle-outline' }}
                            </v-icon>
                            {{ b.begriff }}
                            <template #append>
                              <span class="text-caption ml-1 font-weight-bold">
                                {{ b.treffer_anzahl }}
                              </span>
                            </template>
                          </v-chip>
                        </div>
                      </td>
                    </tr>
                  </template>
                </template>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Erklärung Section-Mapping -->
    <v-row v-if="!loading" class="mt-2">
      <v-col cols="12">
        <v-expansion-panels variant="accordion">
          <v-expansion-panel>
            <v-expansion-panel-title>
              <v-icon start size="small" color="info">mdi-information-outline</v-icon>
              <span class="text-subtitle-2">Wie werden die Prüfungsbereiche zugeordnet?</span>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <div class="text-body-2">
                <p class="mb-2">
                  Die Suchbegriffe werden durch die <strong>Score-Tabelle</strong> nach Prüfungsrelevanz klassifiziert
                  (Basis: 150 Prüfungs-PDFs, 2000–2025, Volltextsuche + OCR):
                </p>
                <v-table density="compact" class="mb-3">
                  <tbody>
                    <tr>
                      <td><v-chip color="#C62828" variant="flat" size="x-small" label class="text-white font-weight-bold">A</v-chip></td>
                      <td class="text-body-2"><strong>MUSS</strong> – kommt regelmäßig in Prüfungen vor, oft mit Punkten direkt abgefragt</td>
                    </tr>
                    <tr>
                      <td><v-chip color="#F57F17" variant="flat" size="x-small" label class="text-white font-weight-bold">B</v-chip></td>
                      <td class="text-body-2"><strong>SOLLTE</strong> – kam mehrfach vor, könnte jederzeit wieder drankommen</td>
                    </tr>
                    <tr>
                      <td><v-chip color="#1565C0" variant="flat" size="x-small" label class="text-white font-weight-bold">C</v-chip></td>
                      <td class="text-body-2"><strong>KANN</strong> – kam 1–2× vor oder steht nur im Prüfungskatalog</td>
                    </tr>
                    <tr>
                      <td><v-chip color="#757575" variant="flat" size="x-small" label class="text-white font-weight-bold">D</v-chip></td>
                      <td class="text-body-2"><strong>UNWAHRSCHEINLICH</strong> – noch nie in einer Prüfung aufgetaucht. Enthält auch per OCR gefundene Begriffe, die nicht explizit in der Score-Tabelle vorkommen.</td>
                    </tr>
                  </tbody>
                </v-table>
                <p class="text-caption text-medium-emphasis">
                  Die Bereiche A–C stammen direkt aus der Score-Tabelle mit verlinkten HTML-Ergebnisdateien.
                  Bereich D umfasst sowohl die in der Score-Tabelle als „nie geprüft" gelisteten Begriffe
                  als auch alle weiteren per OCR gefundenen Begriffe, die keiner anderen Kategorie zugeordnet sind.
                  Da ausschließlich FIAE-Prüfungen (Fachinformatiker Anwendungsentwicklung) analysiert werden,
                  werden nicht zugeordnete Begriffe standardmäßig dem Bereich D zugerechnet.
                </p>
              </div>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-col>
    </v-row>
  </div>
</template>

<style scoped>
.section-row:hover {
  background-color: rgba(var(--v-theme-primary), 0.04);
}
.expanded-row {
  background-color: rgba(0, 0, 0, 0.02);
}
.expanded-row:hover {
  background-color: rgba(var(--v-theme-primary), 0.08);
}
.clickable-chip {
  cursor: pointer;
  transition: transform 0.1s;
}
.clickable-chip:hover {
  transform: scale(1.05);
}
.bereich-card {
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}
.bereich-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.15);
}
</style>
