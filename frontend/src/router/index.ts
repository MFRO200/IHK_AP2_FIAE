import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/DashboardView.vue'),
    meta: { title: 'Dashboard', icon: 'mdi-view-dashboard' },
  },
  {
    path: '/pruefungen',
    name: 'Pruefungen',
    component: () => import('@/views/PruefungenView.vue'),
    meta: { title: 'Prüfungen', icon: 'mdi-file-document-multiple' },
  },
  {
    path: '/pruefungen/:id',
    name: 'PruefungDetail',
    component: () => import('@/views/PruefungDetailView.vue'),
    meta: { title: 'Prüfung Details' },
  },
  {
    path: '/pruefungen/:id/bearbeiten',
    name: 'PruefungBearbeiten',
    component: () => import('@/views/PruefungBearbeitenView.vue'),
    meta: { title: 'Prüfung bearbeiten' },
  },
  {
    path: '/suchbegriffe',
    name: 'Suchbegriffe',
    component: () => import('@/views/SuchbegriffeView.vue'),
    meta: { title: 'Suchbegriffe', icon: 'mdi-tag-multiple' },
  },
  {
    path: '/suchbegriffe/:id',
    name: 'SuchbegriffDetail',
    component: () => import('@/views/SuchbegriffDetailView.vue'),
    meta: { title: 'Suchbegriff Details' },
  },
  {
    path: '/suche',
    name: 'Suche',
    component: () => import('@/views/VolltextSucheView.vue'),
    meta: { title: 'Volltext-Suche', icon: 'mdi-magnify' },
  },
  {
    path: '/meine-loesungen',
    name: 'MeineLoesungen',
    component: () => import('@/views/MeineLoesungenView.vue'),
    meta: { title: 'Meine Lösungen', icon: 'mdi-folder-image' },
  },
  {
    path: '/psycho-analyse',
    name: 'PsychoAnalyse',
    component: () => import('@/views/PsychoAnalyseView.vue'),
    meta: { title: 'Psychologische Analyse', icon: 'mdi-brain' },
  },
  {
    path: '/pruefungsbereiche/:bereich',
    name: 'PruefungsbereichDetail',
    component: () => import('@/views/PruefungsbereichView.vue'),
    meta: { title: 'Prüfungsbereich' },
  },
  {
    path: '/dokumente/:id/pdf',
    name: 'PdfViewer',
    component: () => import('@/views/PdfViewerView.vue'),
    meta: { title: 'PDF Anzeige' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  document.title = `${to.meta.title || 'IHK AP2'} – IHK AP2 FIAE`
})

export default router
export { routes }
