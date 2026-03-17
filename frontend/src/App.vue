<script setup lang="ts">
import { ref } from 'vue'
import { routes } from './router'
import { useSettings, fachbereichOptions } from '@/composables/useSettings'

const drawer = ref(true)
const rail = ref(false)
const showSettings = ref(false)

const { fachbereich, fachbereichLabel, fachbereichIcon } = useSettings()

const navItems = routes
  .filter((r) => r.meta?.icon)
  .map((r) => ({
    title: r.meta!.title as string,
    icon: r.meta!.icon as string,
    to: r.path,
  }))
</script>

<template>
  <v-app>
    <!-- App Bar -->
    <v-app-bar color="primary" density="comfortable" elevation="4">
      <v-app-bar-nav-icon @click="drawer = !drawer" />
      <v-app-bar-title class="font-weight-bold">
        IHK AP2 FIAE – Prüfungsanalyse
      </v-app-bar-title>

      <template #append>
        <v-chip
          v-if="fachbereich !== 'alle'"
          :prepend-icon="fachbereichIcon"
          color="white"
          variant="outlined"
          size="small"
          class="mr-2"
          @click="showSettings = true"
        >
          {{ fachbereichLabel }}
        </v-chip>
        <v-btn icon @click="showSettings = true">
          <v-icon>mdi-cog</v-icon>
          <v-tooltip activator="parent" location="bottom">Einstellungen</v-tooltip>
        </v-btn>
      </template>
    </v-app-bar>

    <!-- Navigation Drawer -->
    <v-navigation-drawer v-model="drawer" :rail="rail" permanent>
      <v-list nav density="compact">
        <v-list-item
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          :prepend-icon="item.icon"
          :title="item.title"
          rounded="xl"
          color="primary"
        />
      </v-list>

      <template #append>
        <v-list nav density="compact">
          <v-list-item
            prepend-icon="mdi-cog"
            title="Einstellungen"
            rounded="xl"
            @click="showSettings = true"
          />
          <v-list-item
            :prepend-icon="rail ? 'mdi-chevron-right' : 'mdi-chevron-left'"
            title="Einklappen"
            @click="rail = !rail"
            rounded="xl"
          />
        </v-list>
      </template>
    </v-navigation-drawer>

    <!-- Main content -->
    <v-main>
      <v-container fluid class="pa-6">
        <router-view />
      </v-container>
    </v-main>
    <!-- Einstellungen Dialog -->
    <v-dialog v-model="showSettings" max-width="520" persistent>
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon start color="primary">mdi-cog</v-icon>
          Einstellungen
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" size="small" @click="showSettings = false" />
        </v-card-title>
        <v-divider />
        <v-card-text>
          <div class="text-subtitle-2 mb-2">Fachbereich</div>
          <p class="text-body-2 text-medium-emphasis mb-3">
            Wähle deinen Ausbildungsberuf. Es werden nur die für dich relevanten
            Prüfungsbereiche angezeigt. WISO und Belegsätze sind für alle Berufe sichtbar.
          </p>
          <v-list density="compact" class="pa-0">
            <v-list-item
              v-for="opt in fachbereichOptions"
              :key="opt.value"
              :prepend-icon="opt.icon"
              :title="opt.label"
              :active="fachbereich === opt.value"
              :value="opt.value"
              rounded="lg"
              color="primary"
              @click="fachbereich = opt.value"
            >
              <template #append>
                <v-icon v-if="fachbereich === opt.value" color="primary">mdi-check</v-icon>
              </template>
            </v-list-item>
          </v-list>
        </v-card-text>
        <v-divider />
        <v-card-actions>
          <v-spacer />
          <v-btn color="primary" variant="flat" @click="showSettings = false">Schließen</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-app>
</template>

