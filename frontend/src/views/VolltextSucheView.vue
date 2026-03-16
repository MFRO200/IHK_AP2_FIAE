<script setup lang="ts">
import { ref } from 'vue'
import { seitenApi } from '@/services/api'
import type { VolltextResult } from '@/types'

const query = ref('')
const results = ref<VolltextResult[]>([])
const loading = ref(false)
const searched = ref(false)

const headers = [
  { title: 'Zeitraum', key: 'zeitraum_label' },
  { title: 'Datei', key: 'dateiname' },
  { title: 'Typ', key: 'typ', width: '100px' },
  { title: 'Seite', key: 'seiten_nr', width: '80px' },
  { title: 'Relevanz', key: 'rank', width: '100px' },
  { title: 'Fundstelle', key: 'headline' },
]

async function doSearch() {
  if (!query.value.trim()) return
  loading.value = true
  searched.value = true
  try {
    results.value = await seitenApi.search(query.value.trim())
  } catch (e) {
    console.error('Suche fehlgeschlagen:', e)
    results.value = []
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div>
    <h1 class="text-h4 mb-6">Volltext-Suche</h1>

    <!-- Suchformular -->
    <v-card class="mb-6">
      <v-card-text>
        <v-form @submit.prevent="doSearch">
          <v-row align="center">
            <v-col cols="12" md="9">
              <v-text-field
                v-model="query"
                prepend-inner-icon="mdi-magnify"
                label="Suchbegriff eingeben (z.B. Sequenzdiagramm, ACID, Normalform…)"
                variant="outlined"
                hide-details
                clearable
                autofocus
                @keyup.enter="doSearch"
              />
            </v-col>
            <v-col cols="12" md="3">
              <v-btn
                color="primary"
                size="large"
                block
                prepend-icon="mdi-magnify"
                :loading="loading"
                @click="doSearch"
              >
                Suchen
              </v-btn>
            </v-col>
          </v-row>
        </v-form>
        <p class="text-caption text-medium-emphasis mt-2">
          Durchsucht alle OCR-erkannten Seiten mit PostgreSQL Volltextsuche (deutsch).
        </p>
      </v-card-text>
    </v-card>

    <!-- Ergebnisse -->
    <v-card v-if="searched">
      <v-card-title>
        <v-icon start>mdi-format-list-bulleted</v-icon>
        {{ results.length }} Ergebnis{{ results.length !== 1 ? 'se' : '' }}
        <span v-if="query" class="text-medium-emphasis ml-2">
          für „{{ query }}"
        </span>
      </v-card-title>

      <v-data-table
        :headers="headers"
        :items="results"
        :loading="loading"
        :items-per-page="25"
        :sort-by="[{ key: 'rank', order: 'desc' }]"
      >
        <template #item.dateiname="{ item }">
          <span class="font-weight-medium">{{ item.dateiname }}</span>
        </template>

        <template #item.typ="{ item }">
          <v-chip
            :color="item.typ === 'Lösung' ? 'success' : 'primary'"
            variant="tonal"
            size="small"
            label
          >
            {{ item.typ }}
          </v-chip>
        </template>

        <template #item.rank="{ item }">
          <v-progress-linear
            :model-value="item.rank * 100"
            color="primary"
            height="18"
            rounded
          >
            <template #default>
              <span class="text-caption">{{ item.rank.toFixed(2) }}</span>
            </template>
          </v-progress-linear>
        </template>

        <!-- eslint-disable-next-line vue/no-v-html -->
        <template #item.headline="{ item }">
          <div
            class="volltext-headline text-body-2"
            v-html="item.headline"
          />
        </template>

        <template #no-data>
          <v-alert type="info" variant="tonal" class="ma-4">
            Keine Treffer gefunden. Versuche einen anderen Suchbegriff.
          </v-alert>
        </template>
      </v-data-table>
    </v-card>
  </div>
</template>

<style scoped>
.volltext-headline :deep(mark) {
  background-color: #fff59d;
  padding: 1px 3px;
  border-radius: 2px;
  font-weight: bold;
}
</style>
