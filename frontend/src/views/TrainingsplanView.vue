<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { psychoApi } from '@/services/api'
import type { Trainingsplan } from '@/types'

const loading = ref(true)
const refreshing = ref(false)
const data = ref<Trainingsplan | null>(null)
const tab = ref('prognose')
const lastUpdated = ref<Date | null>(null)

async function loadData(isRefresh = false) {
  if (isRefresh) {
    refreshing.value = true
  } else {
    loading.value = true
  }
  try {
    data.value = await psychoApi.getTrainingsplan()
    lastUpdated.value = new Date()
  } catch (e) {
    console.error('Fehler beim Laden des Trainingsplans:', e)
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

onMounted(() => loadData())

/* ── Helpers ── */
const afbColors = ['#42A5F5', '#FFA726', '#EF5350']
const afbLabels = ['AFB I - Reproduktion', 'AFB II - Transfer', 'AFB III - Reflexion']

const priorityColor = (p: string) => {
  switch (p) {
    case 'hoch': return 'error'
    case 'mittel': return 'warning'
    default: return 'info'
  }
}

const kategorieIcon = (k: string) => {
  switch (k) {
    case 'GA1': return 'mdi-pencil-ruler'
    case 'GA2': return 'mdi-code-braces'
    case 'WISO': return 'mdi-scale-balance'
    case 'Schwäche': return 'mdi-alert-circle'
    default: return 'mdi-lightbulb'
  }
}

const prozentColor = (p: number) => {
  if (p >= 80) return 'success'
  if (p >= 60) return 'warning'
  return 'error'
}

const anspruchColor = (a: string) => {
  switch (a) {
    case 'hoch': return 'error'
    case 'mittel-hoch': return 'warning'
    case 'mittel': return 'success'
    case 'niedrig-mittel': return 'info'
    default: return 'grey'
  }
}

const ergebnisseHeaders = [
  { title: 'Prüfung', key: 'zeitraum_label', sortable: true },
  { title: 'Punkte', key: 'punkte', sortable: true },
  { title: 'Max', key: 'max_punkte', sortable: true },
  { title: '%', key: 'prozent', sortable: true },
]

const schwachHeaders = [
  { title: 'Prüfung', key: 'pruefung', sortable: true },
  { title: 'Bereich', key: 'bereich', sortable: true },
  { title: 'Aufgabe', key: 'aufgabe', sortable: true },
  { title: 'Erreicht', key: 'punkte', sortable: true },
  { title: 'Max', key: 'max_punkte', sortable: true },
  { title: '%', key: 'prozent', sortable: true },
]

const hoheEmpfehlungen = computed(() =>
  data.value?.empfehlungen.filter((e) => e.prioritaet === 'hoch') || []
)
const weitereEmpfehlungen = computed(() =>
  data.value?.empfehlungen.filter((e) => e.prioritaet !== 'hoch') || []
)
</script>

<template>
  <div>
    <div class="d-flex align-center mb-6">
      <v-icon size="32" color="primary" class="mr-3">mdi-school</v-icon>
      <div class="flex-grow-1">
        <h1 class="text-h4 font-weight-bold">Trainingsplan AP2 Sommer 2026</h1>
        <p class="text-subtitle-1 text-medium-emphasis mt-1">
          Prognose, Schwächenanalyse und gezielte Übungsempfehlungen
        </p>
      </div>
      <div class="d-flex flex-column align-end">
        <v-btn
          color="primary"
          variant="flat"
          prepend-icon="mdi-refresh"
          :loading="refreshing"
          :disabled="loading"
          @click="loadData(true)"
        >
          Analyse aktualisieren
        </v-btn>
        <span v-if="lastUpdated" class="text-caption text-medium-emphasis mt-1">
          Zuletzt: {{ lastUpdated.toLocaleTimeString('de-DE') }}
        </span>
      </div>
    </div>

    <v-progress-linear v-if="loading || refreshing" indeterminate color="primary" class="mb-4" />

    <template v-if="data && !loading">
      <!-- ══════ Übersichts-Karten ══════ -->
      <v-row class="mb-4">
        <v-col cols="12" md="4">
          <v-card color="primary" variant="tonal" class="pa-4">
            <div class="text-overline mb-1">Bearbeitete Prüfungen</div>
            <div class="text-h3 font-weight-bold">{{ data.gesamtErgebnis.pruefungenBearbeitet }}</div>
          </v-card>
        </v-col>
        <v-col cols="12" md="4">
          <v-card :color="prozentColor(data.gesamtErgebnis.durchschnittProzent)" variant="tonal" class="pa-4">
            <div class="text-overline mb-1">Durchschnitt</div>
            <div class="text-h3 font-weight-bold">{{ data.gesamtErgebnis.durchschnittProzent }}%</div>
          </v-card>
        </v-col>
        <v-col cols="12" md="4">
          <v-card :color="data.gesamtErgebnis.schwaechen > 0 ? 'error' : 'success'" variant="tonal" class="pa-4">
            <div class="text-overline mb-1">Erkannte Schwächen</div>
            <div class="text-h3 font-weight-bold">{{ data.gesamtErgebnis.schwaechen }}</div>
          </v-card>
        </v-col>
      </v-row>

      <!-- Info-Banner: Wie funktioniert die Analyse? -->
      <v-alert type="info" variant="tonal" class="mb-4" closable density="compact">
        <strong>So funktioniert's:</strong>
        Die <strong>Schwächenanalyse</strong> erkennt alle Aufgaben, in denen du weniger als 50% erreicht hast.
        Die <strong>Trainingsempfehlungen</strong> werden aus der <strong>Prognose</strong> (AFB-Trends der letzten 4 Jahre)
        <em>und</em> deinen erkannten Schwächen generiert.
        Klicke oben auf <strong>„Analyse aktualisieren"</strong>, nachdem du neue Prüfungen bewertet hast.
      </v-alert>

      <!-- ══════ Tabs ══════ -->
      <v-tabs v-model="tab" color="primary" class="mb-4">
        <v-tab value="prognose">
          <v-icon start>mdi-crystal-ball</v-icon>
          Prognose Sommer 2026
        </v-tab>
        <v-tab value="empfehlungen">
          <v-icon start>mdi-target</v-icon>
          Trainingsempfehlungen
        </v-tab>
        <v-tab value="ergebnisse">
          <v-icon start>mdi-chart-line</v-icon>
          Meine Ergebnisse
        </v-tab>
        <v-tab value="schwaechen">
          <v-icon start>mdi-alert</v-icon>
          Schwächenanalyse
        </v-tab>
      </v-tabs>

      <v-tabs-window v-model="tab">
        <!-- ══════ TAB 1: Prognose ══════ -->
        <v-tabs-window-item value="prognose">
          <v-alert type="info" variant="tonal" class="mb-4" closable>
            <strong>Prognose basierend auf Trends der letzten 4 Jahre (2022-2025).</strong>
            Die IHK folgt einem konsistenten Muster: GA1 und GA2 betonen AFB II (Transfer/Anwenden),
            WISO hat steigend AFB III (Beurteilen). Der Schwierigkeitsgrad bleibt stabil bei "mittel-hoch".
          </v-alert>

          <v-row>
            <v-col v-for="(prog, bereich) in data.prognose" :key="bereich" cols="12" md="4">
              <v-card elevation="2" class="pa-4" height="100%">
                <div class="d-flex align-center mb-3">
                  <v-icon :color="anspruchColor(prog.anspruch)" size="28" class="mr-2">
                    {{ kategorieIcon(bereich as string) }}
                  </v-icon>
                  <div>
                    <div class="text-h6 font-weight-bold">{{ bereich }}</div>
                    <v-chip :color="anspruchColor(prog.anspruch)" size="small" variant="flat">
                      {{ prog.anspruch }}
                    </v-chip>
                  </div>
                </div>

                <div class="text-subtitle-2 mb-2">Erwartete AFB-Verteilung:</div>

                <div v-for="(val, idx) in [prog.afb1, prog.afb2, prog.afb3]" :key="idx" class="mb-2">
                  <div class="d-flex justify-space-between text-body-2">
                    <span>{{ afbLabels[idx] }}</span>
                    <strong>{{ val }}%</strong>
                  </div>
                  <v-progress-linear
                    :model-value="val"
                    :color="afbColors[idx]"
                    height="8"
                    rounded
                  />
                </div>

                <v-divider class="my-3" />

                <div class="text-subtitle-2 mb-1">Top-Themenblöcke:</div>
                <v-chip
                  v-for="thema in prog.topThemen"
                  :key="thema"
                  size="small"
                  variant="outlined"
                  class="mr-1 mb-1"
                >
                  {{ thema }}
                </v-chip>
                <div v-if="!prog.topThemen.length" class="text-caption text-medium-emphasis">
                  Keine Themenblock-Daten vorhanden
                </div>
              </v-card>
            </v-col>
          </v-row>

          <!-- Top-Operatoren -->
          <v-card class="mt-4 pa-4" elevation="2">
            <div class="text-h6 font-weight-bold mb-3">
              <v-icon color="primary" class="mr-2">mdi-format-list-bulleted</v-icon>
              Häufigste Operatoren (GA1+GA2, 2022+)
            </div>
            <div class="text-body-2 text-medium-emphasis mb-3">
              Diese Handlungsverben kommen am häufigsten in den Aufgabenstellungen vor. Verstehe genau, was jeder Operator verlangt!
            </div>
            <v-row>
              <v-col v-for="op in data.topOperatoren" :key="op.operator" cols="6" sm="4" md="3" lg="2">
                <v-card variant="outlined" class="pa-3 text-center">
                  <div class="text-h6 font-weight-bold text-primary">{{ op.count }}×</div>
                  <div class="text-body-2">{{ op.operator }}</div>
                </v-card>
              </v-col>
            </v-row>
          </v-card>
        </v-tabs-window-item>

        <!-- ══════ TAB 2: Empfehlungen ══════ -->
        <v-tabs-window-item value="empfehlungen">
          <v-alert v-if="!data.empfehlungen.length" type="info" variant="tonal">
            Bearbeite zuerst einige Prüfungen, damit personalisierte Empfehlungen generiert werden können.
          </v-alert>

          <div v-if="hoheEmpfehlungen.length" class="mb-4">
            <div class="text-h6 font-weight-bold mb-3 d-flex align-center">
              <v-icon color="error" class="mr-2">mdi-alert-circle</v-icon>
              Hohe Priorität
            </div>
            <v-row>
              <v-col v-for="(emp, i) in hoheEmpfehlungen" :key="'h' + i" cols="12" md="6">
                <v-card elevation="2" class="pa-4" height="100%">
                  <div class="d-flex align-center mb-2">
                    <v-icon :color="priorityColor(emp.prioritaet)" class="mr-2">
                      {{ kategorieIcon(emp.kategorie) }}
                    </v-icon>
                    <div class="text-subtitle-1 font-weight-bold">{{ emp.titel }}</div>
                    <v-spacer />
                    <v-chip :color="priorityColor(emp.prioritaet)" size="x-small" variant="flat">
                      {{ emp.prioritaet }}
                    </v-chip>
                  </div>
                  <div class="text-body-2 text-medium-emphasis mb-3">
                    {{ emp.beschreibung }}
                  </div>
                  <v-list density="compact" class="bg-transparent">
                    <v-list-item v-for="(u, j) in emp.uebungen" :key="j" class="px-0">
                      <template #prepend>
                        <v-icon size="18" color="success" class="mr-2">mdi-checkbox-blank-circle-outline</v-icon>
                      </template>
                      <v-list-item-title class="text-body-2">{{ u }}</v-list-item-title>
                    </v-list-item>
                  </v-list>
                </v-card>
              </v-col>
            </v-row>
          </div>

          <div v-if="weitereEmpfehlungen.length">
            <div class="text-h6 font-weight-bold mb-3 d-flex align-center">
              <v-icon color="warning" class="mr-2">mdi-lightbulb</v-icon>
              Weitere Empfehlungen
            </div>
            <v-row>
              <v-col v-for="(emp, i) in weitereEmpfehlungen" :key="'w' + i" cols="12" md="6">
                <v-card elevation="1" variant="outlined" class="pa-4" height="100%">
                  <div class="d-flex align-center mb-2">
                    <v-icon :color="priorityColor(emp.prioritaet)" class="mr-2">
                      {{ kategorieIcon(emp.kategorie) }}
                    </v-icon>
                    <div class="text-subtitle-1 font-weight-bold">{{ emp.titel }}</div>
                    <v-spacer />
                    <v-chip :color="priorityColor(emp.prioritaet)" size="x-small" variant="flat">
                      {{ emp.prioritaet }}
                    </v-chip>
                  </div>
                  <div class="text-body-2 text-medium-emphasis mb-3">
                    {{ emp.beschreibung }}
                  </div>
                  <v-list density="compact" class="bg-transparent">
                    <v-list-item v-for="(u, j) in emp.uebungen" :key="j" class="px-0">
                      <template #prepend>
                        <v-icon size="18" color="success" class="mr-2">mdi-checkbox-blank-circle-outline</v-icon>
                      </template>
                      <v-list-item-title class="text-body-2">{{ u }}</v-list-item-title>
                    </v-list-item>
                  </v-list>
                </v-card>
              </v-col>
            </v-row>
          </div>
        </v-tabs-window-item>

        <!-- ══════ TAB 3: Meine Ergebnisse ══════ -->
        <v-tabs-window-item value="ergebnisse">
          <v-alert v-if="!data.ergebnisse.length" type="info" variant="tonal">
            Noch keine Prüfungsergebnisse vorhanden. Gehe zu einer Prüfung und bearbeite die Aufgaben.
          </v-alert>

          <template v-else>
            <!-- Balkendiagramm -->
            <v-card class="pa-4 mb-4" elevation="2">
              <div class="text-h6 font-weight-bold mb-3">Ergebnisverlauf</div>
              <div style="display: flex; align-items: flex-end; gap: 8px; height: 200px; padding: 0 16px">
                <div
                  v-for="e in data.ergebnisse"
                  :key="e.pruefung_id"
                  style="flex: 1; display: flex; flex-direction: column; align-items: center"
                >
                  <div class="text-caption font-weight-bold mb-1">{{ e.prozent }}%</div>
                  <div
                    :style="{
                      width: '100%',
                      maxWidth: '48px',
                      height: `${Math.max(e.prozent * 1.6, 8)}px`,
                      borderRadius: '4px 4px 0 0',
                      transition: 'height 0.5s ease',
                    }"
                    :class="[
                      e.prozent >= 80 ? 'bg-success' :
                      e.prozent >= 60 ? 'bg-warning' :
                      'bg-error'
                    ]"
                  />
                  <div class="text-caption mt-1 text-center" style="font-size: 9px; line-height: 1.2">
                    {{ e.zeitraum_label.replace('Winter ', 'W').replace('Sommer ', 'S') }}
                  </div>
                </div>
              </div>
              <div class="d-flex justify-center mt-2 ga-4">
                <div class="d-flex align-center"><div class="rounded" style="width:12px;height:12px;background:#4CAF50" /><span class="text-caption ml-1">&ge; 80%</span></div>
                <div class="d-flex align-center"><div class="rounded" style="width:12px;height:12px;background:#FF9800" /><span class="text-caption ml-1">&ge; 60%</span></div>
                <div class="d-flex align-center"><div class="rounded" style="width:12px;height:12px;background:#F44336" /><span class="text-caption ml-1">&lt; 60%</span></div>
              </div>
            </v-card>

            <!-- Tabelle -->
            <v-card elevation="2">
              <v-data-table
                :items="data.ergebnisse"
                :headers="ergebnisseHeaders"
                density="compact"
                items-per-page="-1"
              >
                <template #item.prozent="{ item }">
                  <v-chip :color="prozentColor(item.prozent)" size="small" variant="flat">
                    {{ item.prozent }}%
                  </v-chip>
                </template>
              </v-data-table>
            </v-card>
          </template>
        </v-tabs-window-item>

        <!-- ══════ TAB 4: Schwächenanalyse ══════ -->
        <v-tabs-window-item value="schwaechen">
          <v-alert v-if="!data.schwacheAufgaben.length" type="success" variant="tonal" class="mb-4">
            <v-icon start>mdi-check-circle</v-icon>
            Keine Schwächen erkannt! Alle bearbeiteten Aufgaben liegen über 50%.
          </v-alert>

          <template v-else>
            <v-alert type="warning" variant="tonal" class="mb-4">
              <strong>{{ data.schwacheAufgaben.length }} Aufgaben</strong> mit unter 50% der Punkte erkannt.
              Gezielte Wiederholung empfohlen!
            </v-alert>

            <v-card elevation="2">
              <v-data-table
                :items="data.schwacheAufgaben"
                :headers="schwachHeaders"
                density="compact"
                items-per-page="20"
                sort-by="prozent"
              >
                <template #item.bereich="{ item }">
                  <v-chip
                    :color="item.bereich === 'WISO' ? 'purple' : 'blue'"
                    size="small"
                    variant="tonal"
                  >
                    {{ item.bereich }}
                  </v-chip>
                </template>
                <template #item.prozent="{ item }">
                  <v-chip color="error" size="small" variant="flat">
                    {{ item.prozent }}%
                  </v-chip>
                </template>
                <template #item.punkte="{ item }">
                  {{ item.punkte }} / {{ item.max_punkte }}
                </template>
              </v-data-table>
            </v-card>
          </template>
        </v-tabs-window-item>
      </v-tabs-window>
    </template>

    <!-- Fallback wenn keine Daten -->
    <v-alert v-if="!loading && !data" type="error" variant="tonal">
      Trainingsplan konnte nicht geladen werden. Bitte Backend prüfen.
    </v-alert>
  </div>
</template>
