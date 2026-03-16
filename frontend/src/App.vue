<script setup lang="ts">
import { ref } from 'vue'
import { routes } from './router'

const drawer = ref(true)
const rail = ref(false)

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
  </v-app>
</template>

