<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { psychoApi } from '@/services/api'
import type { PsychoAnalyse, PsychoStatistik } from '@/types'

/* ── State ── */
const loading = ref(true)
const tab = ref('uebersicht')
const statistik = ref<PsychoStatistik | null>(null)
const analysen = ref<PsychoAnalyse[]>([])
const selectedBereich = ref<string>('alle')
const searchText = ref('')
const expandedPruefung = ref<number | null>(null)

/* ── Farben ── */
const bloomColors: Record<string, string> = {
  wissen: '#42A5F5',
  verstehen: '#66BB6A',
  anwenden: '#FFA726',
  analysieren: '#EF5350',
  bewerten: '#AB47BC',
  erschaffen: '#EC407A',
}
const bloomLabels: Record<string, string> = {
  wissen: 'Wissen (Erinnern)',
  verstehen: 'Verstehen',
  anwenden: 'Anwenden',
  analysieren: 'Analysieren',
  bewerten: 'Bewerten',
  erschaffen: 'Erschaffen',
}
const afbColors = ['#42A5F5', '#FFA726', '#EF5350']
const afbLabels = ['AFB I – Reproduktion', 'AFB II – Transfer', 'AFB III – Reflexion']

const kognitivColors: Record<string, string> = {
  hoch: '#EF5350',
  'mittel-hoch': '#FFA726',
  mittel: '#66BB6A',
  'niedrig-mittel': '#42A5F5',
}

const kompetenzLabels: Record<string, string> = {
  faktenwissen: '📚 Faktenwissen',
  verstehen: '🧩 Verständnis',
  transfer: '🔄 Transfer',
  analytisch: '🔍 Analytisch',
  kommunikation: '💬 Kommunikation',
  kreativ: '🎨 Kreativ',
  handlungskompetenz: '🛠️ Handlung',
  problemlösung: '🧠 Problemlösung',
  kritisches_denken: '⚖️ Kritisches Denken',
  urteilsvermögen: '🎯 Urteilsvermögen',
  argumentation: '📝 Argumentation',
  entscheidungsfähigkeit: '🔔 Entscheidung',
  systemdenken: '🌐 Systemdenken',
  visualisierung: '📊 Visualisierung',
  mathematisch: '🔢 Mathematisch',
  qualitätssicherung: '✅ QS',
  beratungskompetenz: '🤝 Beratung',
  strukturierung: '📋 Strukturierung',
}

/* ── Laden ── */
onMounted(async () => {
  try {
    const [stat, all] = await Promise.all([
      psychoApi.getStatistik(),
      psychoApi.getAll(),
    ])
    statistik.value = stat
    analysen.value = all
  } catch (e) {
    console.error('Fehler beim Laden:', e)
  } finally {
    loading.value = false
  }
})

/* ── Computed ── */
const bereiche = computed(() => {
  const set = new Set(analysen.value.map((a) => a.pruefungsbereich))
  return ['alle', ...Array.from(set).sort()]
})

const gefiltert = computed(() => {
  let result = analysen.value
  if (selectedBereich.value !== 'alle') {
    result = result.filter((a) => a.pruefungsbereich === selectedBereich.value)
  }
  if (searchText.value) {
    const q = searchText.value.toLowerCase()
    result = result.filter(
      (a) =>
        a.pruefung.zeitraum_label.toLowerCase().includes(q) ||
        a.pruefungsbereich.toLowerCase().includes(q) ||
        (a.analyse_text || '').toLowerCase().includes(q),
    )
  }
  return result
})

/** Prüfungen gruppiert */
const gruppiertePruefungen = computed(() => {
  const map = new Map<number, { label: string; jahr: number; analysen: PsychoAnalyse[] }>()
  for (const a of gefiltert.value) {
    if (!map.has(a.pruefung_id)) {
      map.set(a.pruefung_id, {
        label: a.pruefung.zeitraum_label,
        jahr: a.pruefung.jahr,
        analysen: [],
      })
    }
    map.get(a.pruefung_id)!.analysen.push(a)
  }
  return Array.from(map.entries())
    .sort((a, b) => b[1].jahr - a[1].jahr)
    .map(([id, data]) => ({ id, ...data }))
})

/** Bloom-Gesamtverteilung */
const bloomGesamt = computed(() => {
  if (!statistik.value) return []
  const d = statistik.value.bloom_durchschnitt
  const total = Object.values(d).reduce((s, v) => s + v, 0) || 1
  return Object.entries(d).map(([key, val]) => ({
    key,
    label: bloomLabels[key] || key,
    value: val,
    pct: Math.round((val / total) * 100),
    color: bloomColors[key] || '#999',
  }))
})

/** AFB-Gesamtverteilung */
const afbGesamt = computed(() => {
  if (!statistik.value) return []
  const d = statistik.value.afb_durchschnitt
  return [
    { label: afbLabels[0], value: d.afb1 || 0, color: afbColors[0] },
    { label: afbLabels[1], value: d.afb2 || 0, color: afbColors[1] },
    { label: afbLabels[2], value: d.afb3 || 0, color: afbColors[2] },
  ]
})

/** Bloom für eine einzelne Analyse */
function bloomForAnalyse(a: PsychoAnalyse) {
  const vals = [
    a.bloom_wissen,
    a.bloom_verstehen,
    a.bloom_anwenden,
    a.bloom_analysieren,
    a.bloom_bewerten,
    a.bloom_erschaffen,
  ]
  const total = vals.reduce((s, v) => s + v, 0) || 1
  return Object.keys(bloomColors).map((key, i) => ({
    key,
    label: bloomLabels[key],
    value: vals[i],
    pct: Math.round((vals[i] / total) * 100),
    color: bloomColors[key],
  }))
}

/** AFB für eine einzelne Analyse */
function afbForAnalyse(a: PsychoAnalyse) {
  return [
    { label: 'AFB I', value: Number(a.afb1_prozent), color: afbColors[0] },
    { label: 'AFB II', value: Number(a.afb2_prozent), color: afbColors[1] },
    { label: 'AFB III', value: Number(a.afb3_prozent), color: afbColors[2] },
  ]
}

/** Top-Operatoren sortiert */
function operatorenSorted(ops: Record<string, number>) {
  return Object.entries(ops)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
}

/** Max-Wert für Operator-Balken */
function opsMax(ops: Record<string, number>) {
  return Math.max(...Object.values(ops), 1)
}

/** Kompetenzprofil sortiert */
function kompetenzSorted(profil: Record<string, number>) {
  return Object.entries(profil)
    .sort((a, b) => b[1] - a[1])
    .map(([key, value]) => ({
      key,
      label: kompetenzLabels[key] || key,
      value,
    }))
}

/* ── Operator-Lookup Helpers ── */
const OPERATOR_MAP: Record<string, { bloom: string; afb: number }> = {
  Nennen: { bloom: 'Wissen', afb: 1 },
  Angeben: { bloom: 'Wissen', afb: 1 },
  Aufzählen: { bloom: 'Wissen', afb: 1 },
  Auflisten: { bloom: 'Wissen', afb: 1 },
  Aufführen: { bloom: 'Wissen', afb: 1 },
  Wiedergeben: { bloom: 'Wissen', afb: 1 },
  Definieren: { bloom: 'Wissen', afb: 1 },
  Bezeichnen: { bloom: 'Wissen', afb: 1 },
  Beschreiben: { bloom: 'Verstehen', afb: 1 },
  Darstellen: { bloom: 'Verstehen', afb: 1 },
  Zusammenfassen: { bloom: 'Verstehen', afb: 1 },
  Skizzieren: { bloom: 'Verstehen', afb: 1 },
  Erläutern: { bloom: 'Anwenden', afb: 2 },
  Erklären: { bloom: 'Anwenden', afb: 2 },
  Ermitteln: { bloom: 'Anwenden', afb: 2 },
  Bestimmen: { bloom: 'Anwenden', afb: 2 },
  Berechnen: { bloom: 'Anwenden', afb: 2 },
  Erstellen: { bloom: 'Anwenden', afb: 2 },
  Zeichnen: { bloom: 'Anwenden', afb: 2 },
  Ergänzen: { bloom: 'Anwenden', afb: 2 },
  Vervollständigen: { bloom: 'Anwenden', afb: 2 },
  Zuordnen: { bloom: 'Anwenden', afb: 2 },
  Anwenden: { bloom: 'Anwenden', afb: 2 },
  Durchführen: { bloom: 'Anwenden', afb: 2 },
  Formulieren: { bloom: 'Anwenden', afb: 2 },
  Implementieren: { bloom: 'Anwenden', afb: 2 },
  Programmieren: { bloom: 'Anwenden', afb: 2 },
  Umsetzen: { bloom: 'Anwenden', afb: 2 },
  Vergleichen: { bloom: 'Analysieren', afb: 2 },
  Unterscheiden: { bloom: 'Analysieren', afb: 2 },
  Analysieren: { bloom: 'Analysieren', afb: 2 },
  Gegenüberstellen: { bloom: 'Analysieren', afb: 2 },
  Einordnen: { bloom: 'Analysieren', afb: 2 },
  Gliedern: { bloom: 'Analysieren', afb: 2 },
  Untersuchen: { bloom: 'Analysieren', afb: 2 },
  Überprüfen: { bloom: 'Analysieren', afb: 2 },
  Prüfen: { bloom: 'Analysieren', afb: 2 },
  Beurteilen: { bloom: 'Bewerten', afb: 3 },
  Bewerten: { bloom: 'Bewerten', afb: 3 },
  Begründen: { bloom: 'Bewerten', afb: 3 },
  Entscheiden: { bloom: 'Bewerten', afb: 3 },
  Empfehlen: { bloom: 'Bewerten', afb: 3 },
  Vorschlagen: { bloom: 'Bewerten', afb: 3 },
  Diskutieren: { bloom: 'Bewerten', afb: 3 },
  Erörtern: { bloom: 'Bewerten', afb: 3 },
  Entwerfen: { bloom: 'Erschaffen', afb: 3 },
  Entwickeln: { bloom: 'Erschaffen', afb: 3 },
  Konzipieren: { bloom: 'Erschaffen', afb: 3 },
  Gestalten: { bloom: 'Erschaffen', afb: 3 },
  Optimieren: { bloom: 'Erschaffen', afb: 3 },
  Planen: { bloom: 'Erschaffen', afb: 3 },
  Modellieren: { bloom: 'Erschaffen', afb: 3 },
}

function getOperatorAfb(op: string): number {
  return OPERATOR_MAP[op]?.afb ?? 2
}
function getOperatorAfbColor(op: string): string {
  const afb = OPERATOR_MAP[op]?.afb ?? 2
  return afb === 1 ? '#42A5F5' : afb === 2 ? '#FFA726' : '#EF5350'
}
function getOperatorBloom(op: string): string {
  return OPERATOR_MAP[op]?.bloom ?? '–'
}
function getOperatorBloomColor(op: string): string {
  const bloom = OPERATOR_MAP[op]?.bloom
  const colors: Record<string, string> = {
    Wissen: '#42A5F5',
    Verstehen: '#66BB6A',
    Anwenden: '#FFA726',
    Analysieren: '#EF5350',
    Bewerten: '#AB47BC',
    Erschaffen: '#EC407A',
  }
  return colors[bloom ?? ''] ?? 'grey'
}
</script>

<template>
  <div>
    <v-row align="center" class="mb-4">
      <v-col>
        <h1 class="text-h4 font-weight-bold">
          <v-icon class="mr-2" color="deep-purple">mdi-brain</v-icon>
          Psychologische Analyse
        </h1>
        <p class="text-subtitle-1 text-medium-emphasis mt-1">
          Kognitive Anforderungen und Bloom'sche Taxonomie der IHK-Abschlussprüfungen
        </p>
      </v-col>
    </v-row>

    <v-progress-linear v-if="loading" indeterminate color="deep-purple" class="mb-4" />

    <template v-if="!loading && statistik">
      <!-- ═══════════════ TABS ═══════════════ -->
      <v-tabs v-model="tab" color="deep-purple" class="mb-6">
        <v-tab value="uebersicht">
          <v-icon start>mdi-chart-bar</v-icon>
          Gesamtübersicht
        </v-tab>
        <v-tab value="pruefungen">
          <v-icon start>mdi-file-document-multiple</v-icon>
          Pro Prüfung ({{ gefiltert.length }})
        </v-tab>
        <v-tab value="operatoren">
          <v-icon start>mdi-format-list-bulleted</v-icon>
          Operatoren-Ranking
        </v-tab>
      </v-tabs>

      <!-- ═══════════════ TAB: GESAMTÜBERSICHT ═══════════════ -->
      <v-window v-model="tab">
        <v-window-item value="uebersicht">
          <!-- Info-Banner -->
          <v-alert type="info" variant="tonal" class="mb-6" icon="mdi-information">
            <strong>Was ist das?</strong> Die AKA (Aufgabenerstellungskommission) wählt Prüfungsfragen
            bewusst nach psychologischen Gesichtspunkten aus. Die <strong>Bloom'sche Taxonomie</strong>
            unterscheidet 6 kognitive Stufen, die <strong>Anforderungsbereiche (AFB)</strong> gruppieren
            diese in 3 Levels. Diese Analyse extrahiert Operatoren (Handlungsverben) aus allen Aufgaben
            und ordnet sie den Taxonomie-Stufen zu.
          </v-alert>

          <v-row>
            <!-- Bloom-Pyramide -->
            <v-col cols="12" md="6">
              <v-card elevation="3" class="h-100">
                <v-card-title class="bg-deep-purple text-white">
                  <v-icon class="mr-2">mdi-triangle</v-icon>
                  Bloom'sche Taxonomie – Durchschnitt
                </v-card-title>
                <v-card-text class="pa-4">
                  <div class="bloom-pyramid">
                    <div
                      v-for="(level, i) in [...bloomGesamt].reverse()"
                      :key="level.key"
                      class="bloom-level"
                      :style="{
                        width: `${40 + (bloomGesamt.length - 1 - i) * 10}%`,
                        backgroundColor: level.color + '20',
                        borderLeft: `4px solid ${level.color}`,
                      }"
                    >
                      <div class="d-flex align-center justify-space-between">
                        <span class="font-weight-medium">{{ level.label }}</span>
                        <span class="font-weight-bold">{{ level.value.toFixed(1) }}</span>
                      </div>
                      <v-progress-linear
                        :model-value="level.pct"
                        :color="level.color"
                        height="8"
                        rounded
                        class="mt-1"
                      />
                    </div>
                  </div>
                </v-card-text>
              </v-card>
            </v-col>

            <!-- AFB-Verteilung -->
            <v-col cols="12" md="6">
              <v-card elevation="3" class="h-100">
                <v-card-title class="bg-orange-darken-2 text-white">
                  <v-icon class="mr-2">mdi-chart-donut</v-icon>
                  Anforderungsbereiche – Durchschnitt
                </v-card-title>
                <v-card-text class="pa-4">
                  <div v-for="afb in afbGesamt" :key="afb.label" class="mb-4">
                    <div class="d-flex align-center justify-space-between mb-1">
                      <span class="font-weight-medium">{{ afb.label }}</span>
                      <v-chip
                        :color="afb.color"
                        size="small"
                        variant="flat"
                        class="text-white"
                      >
                        {{ afb.value.toFixed(1) }}%
                      </v-chip>
                    </div>
                    <v-progress-linear
                      :model-value="afb.value"
                      :color="afb.color"
                      height="20"
                      rounded
                    >
                      <strong class="text-white text-caption">{{ afb.value.toFixed(1) }}%</strong>
                    </v-progress-linear>
                  </div>

                  <v-divider class="my-4" />

                  <v-alert type="info" variant="tonal" density="compact" class="text-caption">
                    <strong>AFB I</strong> = Wissen wiedergeben |
                    <strong>AFB II</strong> = Wissen auf neue Situationen übertragen |
                    <strong>AFB III</strong> = Eigenständig beurteilen & gestalten
                  </v-alert>
                </v-card-text>
              </v-card>
            </v-col>
          </v-row>

          <!-- Key-Stats -->
          <v-row class="mt-4">
            <v-col cols="12" sm="6" md="3">
              <v-card color="deep-purple" variant="flat" class="text-white text-center pa-4">
                <div class="text-h3 font-weight-bold">{{ statistik.anzahl_analysen }}</div>
                <div class="text-subtitle-2">Analysierte Klausuren</div>
              </v-card>
            </v-col>
            <v-col cols="12" sm="6" md="3">
              <v-card color="blue" variant="flat" class="text-white text-center pa-4">
                <div class="text-h3 font-weight-bold">
                  {{ statistik.top_operatoren.reduce((s, o) => s + o.count, 0) }}
                </div>
                <div class="text-subtitle-2">Operatoren gefunden</div>
              </v-card>
            </v-col>
            <v-col cols="12" sm="6" md="3">
              <v-card color="orange-darken-2" variant="flat" class="text-white text-center pa-4">
                <div class="text-h3 font-weight-bold">
                  {{ statistik.top_operatoren.length }}
                </div>
                <div class="text-subtitle-2">Verschiedene Operatoren</div>
              </v-card>
            </v-col>
            <v-col cols="12" sm="6" md="3">
              <v-card color="red" variant="flat" class="text-white text-center pa-4">
                <div class="text-h3 font-weight-bold">
                  {{ statistik.top_operatoren[0]?.operator || '–' }}
                </div>
                <div class="text-subtitle-2">Häufigster Operator</div>
              </v-card>
            </v-col>
          </v-row>

          <!-- Psychologische Erklärung -->
          <v-row class="mt-4">
            <v-col cols="12">
              <v-card elevation="2">
                <v-card-title class="bg-teal text-white">
                  <v-icon class="mr-2">mdi-head-cog</v-icon>
                  Psychologische Strategie der AKA
                </v-card-title>
                <v-card-text class="pa-4">
                  <v-row>
                    <v-col cols="12" md="4">
                      <h4 class="text-subtitle-1 font-weight-bold mb-2">🎯 Normalverteilung</h4>
                      <p class="text-body-2">
                        Die AKA stimmt mit Arbeitgeberverbänden und Gewerkschaften eine
                        <strong>Notenverteilung</strong> ab. Durch gezielte Mischung der AFB-Stufen
                        wird sichergestellt, dass ~15% sehr gut, ~30% gut und ~5% ungenügend abschneiden.
                      </p>
                    </v-col>
                    <v-col cols="12" md="4">
                      <h4 class="text-subtitle-1 font-weight-bold mb-2">🧩 Prüfbare Kompetenz</h4>
                      <p class="text-body-2">
                        AFB I-Aufgaben (Nennen, Beschreiben) sichern die <strong>"Bestehensgrenze"</strong> –
                        wer Basiswissen hat, besteht. AFB III-Aufgaben (Bewerten, Entwickeln) differenzieren
                        die <strong>Spitzengruppe</strong>.
                      </p>
                    </v-col>
                    <v-col cols="12" md="4">
                      <h4 class="text-subtitle-1 font-weight-bold mb-2">🔄 Transfer als Kerntest</h4>
                      <p class="text-body-2">
                        Durch die <strong>Ausgangssituation</strong> (reales Unternehmen) müssen Prüflinge
                        ihr Wissen auf einen <strong>neuen Kontext</strong> übertragen. Dies testet echte
                        berufliche Handlungskompetenz, nicht nur Auswendiglernen.
                      </p>
                    </v-col>
                  </v-row>
                </v-card-text>
              </v-card>
            </v-col>
          </v-row>
        </v-window-item>

        <!-- ═══════════════ TAB: PRO PRÜFUNG ═══════════════ -->
        <v-window-item value="pruefungen">
          <!-- Filter -->
          <v-row class="mb-4">
            <v-col cols="12" sm="6" md="4">
              <v-text-field
                v-model="searchText"
                density="compact"
                variant="outlined"
                label="Suche..."
                prepend-inner-icon="mdi-magnify"
                clearable
                hide-details
              />
            </v-col>
            <v-col cols="12" sm="6" md="3">
              <v-select
                v-model="selectedBereich"
                :items="bereiche"
                density="compact"
                variant="outlined"
                label="Prüfungsbereich"
                hide-details
              />
            </v-col>
          </v-row>

          <!-- Prüfungen -->
          <template v-if="gruppiertePruefungen.length === 0">
            <v-alert type="info" variant="tonal">Keine Analysen gefunden.</v-alert>
          </template>

          <v-expansion-panels v-model="expandedPruefung" variant="accordion">
            <v-expansion-panel
              v-for="pruefung in gruppiertePruefungen"
              :key="pruefung.id"
              :value="pruefung.id"
            >
              <v-expansion-panel-title>
                <div class="d-flex align-center ga-3 w-100">
                  <v-icon color="deep-purple">mdi-file-document</v-icon>
                  <strong>{{ pruefung.label }}</strong>
                  <v-chip
                    v-for="a in pruefung.analysen"
                    :key="a.id"
                    size="small"
                    variant="tonal"
                    :color="a.pruefungsbereich === 'GA1' ? 'blue' : a.pruefungsbereich === 'GA2' ? 'green' : a.pruefungsbereich === 'AP1' ? 'orange' : 'grey'"
                  >
                    {{ a.pruefungsbereich }}
                  </v-chip>
                  <v-spacer />
                  <v-chip
                    v-if="pruefung.analysen[0]?.kognitiver_anspruch"
                    size="small"
                    :color="kognitivColors[pruefung.analysen[0].kognitiver_anspruch] || 'grey'"
                    variant="flat"
                    class="text-white"
                  >
                    {{ pruefung.analysen[0].kognitiver_anspruch }}
                  </v-chip>
                </div>
              </v-expansion-panel-title>

              <v-expansion-panel-text>
                <div v-for="analyse in pruefung.analysen" :key="analyse.id" class="mb-6">
                  <h3 class="text-h6 mb-3">
                    <v-icon size="small" class="mr-1" color="deep-purple">mdi-bookmark</v-icon>
                    {{ analyse.pruefungsbereich }}
                  </h3>

                  <v-row>
                    <!-- Bloom -->
                    <v-col cols="12" md="4">
                      <v-card variant="outlined" class="h-100">
                        <v-card-subtitle class="font-weight-bold pb-0">Bloom-Taxonomie</v-card-subtitle>
                        <v-card-text>
                          <div v-for="b in bloomForAnalyse(analyse)" :key="b.key" class="mb-2">
                            <div class="d-flex justify-space-between text-caption">
                              <span>{{ b.label }}</span>
                              <span class="font-weight-bold">{{ b.value }} ({{ b.pct }}%)</span>
                            </div>
                            <v-progress-linear
                              :model-value="b.pct"
                              :color="b.color"
                              height="6"
                              rounded
                            />
                          </div>
                        </v-card-text>
                      </v-card>
                    </v-col>

                    <!-- AFB -->
                    <v-col cols="12" md="4">
                      <v-card variant="outlined" class="h-100">
                        <v-card-subtitle class="font-weight-bold pb-0">Anforderungsbereiche</v-card-subtitle>
                        <v-card-text>
                          <div v-for="a in afbForAnalyse(analyse)" :key="a.label" class="mb-3">
                            <div class="d-flex justify-space-between text-caption mb-1">
                              <span>{{ a.label }}</span>
                              <strong>{{ a.value }}%</strong>
                            </div>
                            <v-progress-linear
                              :model-value="a.value"
                              :color="a.color"
                              height="14"
                              rounded
                            >
                              <span class="text-caption text-white">{{ a.value }}%</span>
                            </v-progress-linear>
                          </div>

                          <div class="d-flex ga-2 mt-3 flex-wrap">
                            <v-chip
                              size="small"
                              :color="kognitivColors[analyse.kognitiver_anspruch || 'mittel']"
                              variant="flat"
                              class="text-white"
                            >
                              Kognitiv: {{ analyse.kognitiver_anspruch }}
                            </v-chip>
                            <v-chip size="small" color="teal" variant="flat" class="text-white">
                              Transfer: {{ analyse.transfer_distanz }}
                            </v-chip>
                          </div>
                        </v-card-text>
                      </v-card>
                    </v-col>

                    <!-- Operatoren -->
                    <v-col cols="12" md="4">
                      <v-card variant="outlined" class="h-100">
                        <v-card-subtitle class="font-weight-bold pb-0">Operatoren</v-card-subtitle>
                        <v-card-text>
                          <div
                            v-for="[op, count] in operatorenSorted(analyse.operatoren)"
                            :key="op"
                            class="mb-2"
                          >
                            <div class="d-flex justify-space-between text-caption">
                              <span>{{ op }}</span>
                              <strong>{{ count }}×</strong>
                            </div>
                            <v-progress-linear
                              :model-value="(count / opsMax(analyse.operatoren)) * 100"
                              color="deep-purple-lighten-2"
                              height="5"
                              rounded
                            />
                          </div>
                          <v-alert
                            v-if="Object.keys(analyse.operatoren).length === 0"
                            type="warning"
                            variant="tonal"
                            density="compact"
                            class="text-caption"
                          >
                            Keine Operatoren erkannt (evtl. WISO mit Multiple-Choice)
                          </v-alert>
                        </v-card-text>
                      </v-card>
                    </v-col>
                  </v-row>

                  <!-- Kompetenzprofil -->
                  <v-row class="mt-2" v-if="Object.keys(analyse.kompetenz_profil).length > 0">
                    <v-col cols="12">
                      <v-card variant="outlined">
                        <v-card-subtitle class="font-weight-bold pb-0">Kompetenzprofil</v-card-subtitle>
                        <v-card-text>
                          <div class="d-flex ga-2 flex-wrap">
                            <v-chip
                              v-for="k in kompetenzSorted(analyse.kompetenz_profil)"
                              :key="k.key"
                              :size="k.value > 60 ? 'default' : 'small'"
                              :color="k.value > 80 ? 'deep-purple' : k.value > 50 ? 'blue' : 'grey'"
                              :variant="k.value > 50 ? 'flat' : 'tonal'"
                              :class="k.value > 50 ? 'text-white' : ''"
                            >
                              {{ k.label }} ({{ k.value }}%)
                            </v-chip>
                          </div>
                        </v-card-text>
                      </v-card>
                    </v-col>
                  </v-row>

                  <!-- Analyse-Text -->
                  <v-alert
                    v-if="analyse.analyse_text"
                    type="info"
                    variant="tonal"
                    class="mt-3 text-body-2"
                    icon="mdi-text-box"
                  >
                    {{ analyse.analyse_text }}
                  </v-alert>

                  <!-- Schwerpunkte -->
                  <div v-if="analyse.schwerpunkte?.length" class="mt-2 d-flex ga-2 flex-wrap">
                    <v-chip
                      v-for="s in analyse.schwerpunkte"
                      :key="s"
                      size="small"
                      color="teal"
                      variant="tonal"
                      prepend-icon="mdi-tag"
                    >
                      {{ s }}
                    </v-chip>
                  </div>

                  <v-divider v-if="pruefung.analysen.length > 1" class="mt-4" />
                </div>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </v-window-item>

        <!-- ═══════════════ TAB: OPERATOREN-RANKING ═══════════════ -->
        <v-window-item value="operatoren">
          <v-card elevation="3">
            <v-card-title class="bg-deep-purple text-white">
              <v-icon class="mr-2">mdi-format-list-numbered</v-icon>
              Top-Operatoren über alle Prüfungen
            </v-card-title>
            <v-card-text class="pa-4">
              <v-table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Operator</th>
                    <th class="text-center">Häufigkeit</th>
                    <th>Verteilung</th>
                    <th>AFB</th>
                    <th>Bloom-Stufe</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(op, i) in statistik.top_operatoren" :key="op.operator">
                    <td>
                      <v-avatar :color="i < 3 ? 'deep-purple' : 'grey-lighten-1'" size="28">
                        <span class="text-caption font-weight-bold" :class="i < 3 ? 'text-white' : ''">
                          {{ i + 1 }}
                        </span>
                      </v-avatar>
                    </td>
                    <td class="font-weight-bold">{{ op.operator }}</td>
                    <td class="text-center">
                      <v-chip color="deep-purple" variant="flat" size="small" class="text-white">
                        {{ op.count }}×
                      </v-chip>
                    </td>
                    <td style="min-width: 200px">
                      <v-progress-linear
                        :model-value="(op.count / statistik.top_operatoren[0].count) * 100"
                        color="deep-purple-lighten-2"
                        height="12"
                        rounded
                      />
                    </td>
                    <td>
                      <v-chip
                        size="x-small"
                        :color="getOperatorAfbColor(op.operator)"
                        variant="flat"
                        class="text-white"
                      >
                        AFB {{ getOperatorAfb(op.operator) }}
                      </v-chip>
                    </td>
                    <td>
                      <v-chip
                        size="x-small"
                        :color="getOperatorBloomColor(op.operator)"
                        variant="tonal"
                      >
                        {{ getOperatorBloom(op.operator) }}
                      </v-chip>
                    </td>
                  </tr>
                </tbody>
              </v-table>
            </v-card-text>
          </v-card>

          <!-- Legende -->
          <v-card elevation="2" class="mt-4">
            <v-card-title class="text-subtitle-1 font-weight-bold">
              <v-icon class="mr-2" color="teal">mdi-information</v-icon>
              IHK-Operatoren Legende
            </v-card-title>
            <v-card-text>
              <v-row>
                <v-col cols="12" md="4">
                  <h4 class="text-subtitle-2 mb-2" style="color: #42A5F5">
                    AFB I – Reproduktion
                  </h4>
                  <p class="text-caption text-medium-emphasis">
                    <strong>Nennen, Angeben, Aufzählen, Beschreiben, Darstellen</strong><br />
                    Wissen in erlernter Form wiedergeben. „Was weiß der Prüfling?"
                  </p>
                </v-col>
                <v-col cols="12" md="4">
                  <h4 class="text-subtitle-2 mb-2" style="color: #FFA726">
                    AFB II – Reorganisation & Transfer
                  </h4>
                  <p class="text-caption text-medium-emphasis">
                    <strong>Erläutern, Erklären, Vergleichen, Berechnen, Erstellen</strong><br />
                    Wissen auf neue Situationen anwenden. „Kann der Prüfling transferieren?"
                  </p>
                </v-col>
                <v-col cols="12" md="4">
                  <h4 class="text-subtitle-2 mb-2" style="color: #EF5350">
                    AFB III – Reflexion & Problemlösung
                  </h4>
                  <p class="text-caption text-medium-emphasis">
                    <strong>Begründen, Bewerten, Beurteilen, Entwickeln, Entwerfen</strong><br />
                    Eigenständig reflektieren und Lösungen gestalten. „Kann der Prüfling evaluieren?"
                  </p>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>
        </v-window-item>
      </v-window>
    </template>
  </div>
</template>

<style scoped>
.bloom-pyramid {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.bloom-level {
  padding: 8px 16px;
  border-radius: 6px;
  margin: 0 auto;
}
</style>
