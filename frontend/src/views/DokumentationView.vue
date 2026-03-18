<script setup lang="ts">
import { ref } from 'vue'

const activeTab = ref('uebersicht')
const expandedFaq = ref<string[]>([])

const features = [
  {
    icon: 'mdi-file-document-multiple',
    title: 'Prüfungsarchiv',
    desc: 'Über 50 IHK-Abschlussprüfungen Teil 2 (AP2) aus über 20 Jahren, systematisch kategorisiert nach Halbjahr und Prüfungsbereich (GA1, GA2, WISO).',
    color: 'primary',
  },
  {
    icon: 'mdi-tag-multiple',
    title: 'Suchbegriff-Analyse',
    desc: 'Über 600 Suchbegriffe mit automatischer Häufigkeitsanalyse, Sections (A–D) und Themenblöcken. Erkennen Sie, welche Themen regelmäßig geprüft werden.',
    color: 'success',
  },
  {
    icon: 'mdi-magnify',
    title: 'Volltext-Suche',
    desc: 'Durchsuchen Sie über 2.900 OCR-erkannte Seiten aller Prüfungsdokumente mit Vorschau und direktem PDF-Zugriff.',
    color: 'info',
  },
  {
    icon: 'mdi-robot',
    title: 'KI-Bewertung',
    desc: 'Lassen Sie Ihre Antworten von einer KI bewerten – mit Punktevergabe, detailliertem Feedback und Lösungsvorschlägen bei nicht erreichter Punktzahl.',
    color: 'deep-purple',
  },
  {
    icon: 'mdi-brain',
    title: 'Psychologische Analyse',
    desc: 'KI-basierte Analyse Ihres Lernverhaltens mit Stärken-/Schwächenprofil und personalisierten Empfehlungen für die Prüfungsvorbereitung.',
    color: 'pink',
  },
  {
    icon: 'mdi-school',
    title: 'Trainingsplan',
    desc: 'Intelligenter, personalisierter Trainingsplan basierend auf Ihrem bisherigen Lernfortschritt und Ihren Bewertungsergebnissen.',
    color: 'amber-darken-2',
  },
  {
    icon: 'mdi-auto-fix',
    title: 'Fragen-Extraktion (KI)',
    desc: 'Automatisches Extrahieren aller Prüfungsfragen aus PDF-Dokumenten mithilfe von KI – per Knopfdruck direkt in der App.',
    color: 'teal',
  },
  {
    icon: 'mdi-text-box-check',
    title: 'Lösungen-Extraktion (KI)',
    desc: 'Automatisches Extrahieren der Musterlösungen und erwarteten Antworten aus Handreichungen und Lösungsblättern.',
    color: 'orange',
  },
]

const techStack = [
  { name: 'Vue 3', icon: 'mdi-vuejs', desc: 'Frontend-Framework mit Composition API & TypeScript', color: '#42b883' },
  { name: 'Vuetify 3', icon: 'mdi-material-design', desc: 'Material Design Komponentenbibliothek', color: '#1867C0' },
  { name: 'NestJS', icon: 'mdi-server', desc: 'Backend-Framework (Node.js/TypeScript)', color: '#E0234E' },
  { name: 'PostgreSQL 16', icon: 'mdi-database', desc: 'Relationale Datenbank (Docker)', color: '#336791' },
  { name: 'Prisma 5', icon: 'mdi-relation-many-to-many', desc: 'Type-safe ORM für Datenbankzugriffe', color: '#2D3748' },
  { name: 'Docker', icon: 'mdi-docker', desc: 'Containerisierung der Datenbank', color: '#2496ED' },
  { name: 'Tesseract OCR', icon: 'mdi-text-recognition', desc: 'Optische Zeichenerkennung für PDFs', color: '#5A5A5A' },
  { name: 'LLM-Anbieter', icon: 'mdi-creation', desc: 'Ollama (lokal), OpenAI, Perplexity', color: '#FF6F00' },
]

const workflowSteps = [
  {
    title: '1. Prüfung auswählen',
    icon: 'mdi-file-document-outline',
    color: 'primary',
    desc: 'Wählen Sie eine Prüfung aus dem Archiv. Filtern Sie nach Halbjahr, Berufsgruppe und Prüfungsbereich (GA1, GA2, WISO).',
  },
  {
    title: '2. Fragen extrahieren',
    icon: 'mdi-auto-fix',
    color: 'teal',
    desc: 'Extrahieren Sie automatisch alle Prüfungsfragen aus den Aufgaben-PDFs per KI-Analyse. Die Fragen werden in der Datenbank gespeichert.',
  },
  {
    title: '3. Lösungen extrahieren',
    icon: 'mdi-text-box-check',
    color: 'orange',
    desc: 'Sofern verfügbar, extrahieren Sie die Musterlösungen aus Handreichungen oder Lösungsblättern – ebenfalls per KI.',
  },
  {
    title: '4. Antworten eingeben',
    icon: 'mdi-pencil',
    color: 'indigo',
    desc: 'Bearbeiten Sie die Prüfung: Lesen Sie die Fragestellung, geben Sie Ihre Antwort ein und speichern Sie sie.',
  },
  {
    title: '5. KI-Bewertung starten',
    icon: 'mdi-robot',
    color: 'deep-purple',
    desc: 'Lassen Sie Ihre Antworten automatisch bewerten. Die KI vergibt Punkte, gibt Feedback und zeigt bei Teilpunkten einen Lösungsvorschlag.',
  },
  {
    title: '6. Ergebnisse analysieren',
    icon: 'mdi-chart-line',
    color: 'success',
    desc: 'Nutzen Sie die psychologische Analyse und den Trainingsplan, um gezielt Ihre Schwächen zu erkennen und zu verbessern.',
  },
]

const apiEndpoints = [
  { method: 'GET', path: '/api/pruefungen', desc: 'Alle Prüfungen abrufen (Filterung nach Fachbereich)' },
  { method: 'GET', path: '/api/pruefungen/:id', desc: 'Details einer Prüfung inkl. Dokumente' },
  { method: 'GET', path: '/api/dokumente/:id/seiten', desc: 'OCR-Seiten eines Dokuments abrufen' },
  { method: 'GET', path: '/api/dokumente/:id/pdf', desc: 'PDF-Datei eines Dokuments streamen' },
  { method: 'GET', path: '/api/suchbegriffe', desc: 'Alle Suchbegriffe mit Statistiken' },
  { method: 'GET', path: '/api/suchbegriffe/:id', desc: 'Detail eines Suchbegriffs mit Treffern' },
  { method: 'GET', path: '/api/treffer/stats', desc: 'Treffer-Statistiken nach Section & Prüfung' },
  { method: 'GET', path: '/api/suche?q=...', desc: 'Volltext-Suche über alle OCR-Seiten' },
  { method: 'POST', path: '/api/antworten', desc: 'Antwort speichern (pruefung_id, aufgabe, antwort_text)' },
  { method: 'GET', path: '/api/antworten/pruefung/:id', desc: 'Alle Antworten einer Prüfung' },
  { method: 'POST', path: '/api/bewertung/start', desc: 'KI-Bewertung einer Antwort starten' },
  { method: 'POST', path: '/api/bewertung/pruefung/:id', desc: 'Alle Antworten einer Prüfung bewerten' },
  { method: 'GET', path: '/api/bewertung/pruefung/:id', desc: 'Bewertungen einer Prüfung abrufen' },
  { method: 'POST', path: '/api/bewertung/extract-fragen/:id', desc: 'Fragen aus Dokument per KI extrahieren' },
  { method: 'POST', path: '/api/bewertung/extract-loesungen/:id', desc: 'Lösungen aus Dokument per KI extrahieren' },
  { method: 'GET', path: '/api/musterloesungen/pruefung/:id', desc: 'Musterlösungen einer Prüfung abrufen' },
  { method: 'POST', path: '/api/bewertung/psycho-analyse', desc: 'Psychologische Lernanalyse starten' },
  { method: 'POST', path: '/api/bewertung/trainingsplan', desc: 'Personalisierten Trainingsplan generieren' },
]

const dbTables = [
  { name: 'pruefungen', desc: 'Prüfungen mit Jahr, Semester (Sommer/Winter), Berufsgruppe', fields: 'id, name, halbjahr, beruf, fachrichtung, erstellt_am' },
  { name: 'pruefungsbereiche', desc: 'Bereiche einer Prüfung (GA1, GA2, WISO)', fields: 'id, pruefung_id, kuerzel, name' },
  { name: 'dokumente', desc: 'PDF-Dokumente zu Prüfungen (Aufgaben, Lösungen, Belegsätze)', fields: 'id, pruefung_id, typ, dateiname, dateipfad, ocr_status' },
  { name: 'seiten', desc: 'OCR-erkannte Textseiten eines Dokuments', fields: 'id, dokument_id, seite_nr, text_inhalt' },
  { name: 'suchbegriffe', desc: 'Katalog der IHK-Suchbegriffe mit Kategorisierung', fields: 'id, begriff, section, themenblock, beschreibung, treffer_anzahl' },
  { name: 'treffer', desc: 'Zuordnung Suchbegriff ↔ Prüfung/Seite', fields: 'id, suchbegriff_id, pruefung_id, dokument_id, seite_id, kontext' },
  { name: 'musterloesungen', desc: 'Erwartete Antworten und Fragestellungen je Aufgabe', fields: 'id, pruefung_id, aufgabe, erwartung_text, max_punkte, hinweise' },
  { name: 'antworten', desc: 'Vom Benutzer eingegebene Antworten', fields: 'id, pruefung_id, aufgabe, antwort_text, erstellt_am, aktualisiert_am' },
  { name: 'bewertungen', desc: 'KI-Bewertungsergebnisse einer Antwort', fields: 'id, antwort_id, punkte, max_punkte, feedback, bewertung_details, llm_provider, llm_model' },
  { name: 'psycho_analysen', desc: 'Psychologische Lernanalyse-Ergebnisse', fields: 'id, pruefung_id, analyse_text, llm_provider, erstellt_am' },
]

const faqItems = [
  {
    q: 'Welche Systemvoraussetzungen gibt es?',
    a: 'Sie benötigen Node.js 18+, Docker (für PostgreSQL), und einen modernen Browser. Für die lokale KI-Bewertung mit Ollama wird eine GPU empfohlen, alternativ können OpenAI oder Perplexity als Cloud-Anbieter genutzt werden.',
  },
  {
    q: 'Wie starte ich die App?',
    a: '1. Docker-Container starten: docker-compose up -d\n2. Backend starten: cd backend && npm run start:dev\n3. Frontend starten: cd frontend && npm run dev\n4. App im Browser öffnen: http://localhost:5173',
  },
  {
    q: 'Was ist der Unterschied zwischen den Sections A–D?',
    a: 'Die Sections klassifizieren Suchbegriffe nach Prüfungsrelevanz:\n• A = UNBEDINGT KÖNNEN – wird regelmäßig geprüft\n• B = SOLLTE MAN KÖNNEN – kommt regelmäßig vor\n• C = KENNEN REICHT – 1–2× oder nur im Katalog\n• D = (NOCH) NIE GEPRÜFT',
  },
  {
    q: 'Kann ich mehrere LLM-Anbieter verwenden?',
    a: 'Ja. Die App unterstützt Ollama (lokale Modelle, kostenlos), OpenAI (GPT-4 etc.) und Perplexity. Der Anbieter kann in den Einstellungen der Bewertung gewählt werden.',
  },
  {
    q: 'Wie genau ist die KI-Bewertung?',
    a: 'Die KI-Bewertung orientiert sich an den offiziellen IHK-Musterlösungen und Handreichungen. Sie vergibt Punkte nach dem definierten Bewertungsschema und gibt detailliertes Feedback. Beachten Sie, dass die Bewertung als Trainingstool gedacht ist – die finale Note wird von menschlichen Prüfern vergeben.',
  },
  {
    q: 'Was passiert bei der Fragen-Extraktion?',
    a: 'Die KI analysiert den OCR-Text des Aufgaben-PDFs und identifiziert alle einzelnen Aufgaben (z. B. 1a, 1b, 2a). Jede Aufgabe wird mit Fragetext, maximaler Punktzahl und Aufgabennummer in der Datenbank gespeichert.',
  },
  {
    q: 'Wieso sehe ich bei manchen Prüfungen keine Fragen?',
    a: 'Mögliche Gründe:\n• Die Fragen wurden noch nicht extrahiert → Klicken Sie auf „Fragen extrahieren (KI)"\n• Das PDF hat keinen OCR-Text → Prüfen Sie den OCR-Status im Prüfungsdetail\n• Die Prüfung hat kein Aufgaben-Dokument',
  },
  {
    q: 'Unterstützt die App verschiedene Berufe?',
    a: 'Ja, die App unterstützt FIAE (Fachinformatiker Anwendungsentwicklung), FISI (Fachinformatiker Systemintegration) und weitere IT-Berufe. Der Fachbereich kann in den Einstellungen (Zahnrad-Icon) gewählt werden. WISO-Aufgaben sind berufsübergreifend.',
  },
]

const shortcuts = [
  { keys: 'Strg + S', desc: 'Antwort speichern (in Bearbeiten-Ansicht)' },
  { keys: 'Tab / Shift+Tab', desc: 'Zwischen Aufgaben navigieren' },
  { keys: 'Strg + Enter', desc: 'Bewertung starten' },
]

function getMethodColor(method: string): string {
  switch (method) {
    case 'GET': return 'success'
    case 'POST': return 'primary'
    case 'PUT': return 'warning'
    case 'DELETE': return 'error'
    default: return 'grey'
  }
}
</script>

<template>
  <div>
    <!-- Hero Header -->
    <v-card
      class="mb-6 overflow-hidden"
      rounded="xl"
      elevation="8"
    >
      <div
        class="d-flex flex-column align-center justify-center pa-10"
        style="background: linear-gradient(135deg, #1565C0 0%, #0D47A1 50%, #1A237E 100%); min-height: 260px;"
      >
        <v-icon size="64" color="white" class="mb-4">mdi-book-open-page-variant</v-icon>
        <h1 class="text-h3 font-weight-bold text-white text-center mb-2">
          IHK AP2 FIAE
        </h1>
        <p class="text-h6 text-white text-center" style="opacity: 0.9;">
          Prüfungsanalyse & KI-gestützte Vorbereitung
        </p>
        <p class="text-body-1 text-white text-center mt-2" style="opacity: 0.75; max-width: 700px;">
          Die umfassende Plattform zur Vorbereitung auf die IHK-Abschlussprüfung Teil 2 für
          Fachinformatiker – mit Prüfungsarchiv, intelligenter Suchbegriff-Analyse,
          KI-Bewertung und personalisiertem Trainingsplan.
        </p>
        <div class="d-flex ga-3 mt-5">
          <v-chip color="white" variant="flat" prepend-icon="mdi-tag" size="small">v1.0</v-chip>
        </div>
      </div>
    </v-card>

    <!-- Tabs -->
    <v-card rounded="xl" elevation="2">
      <v-tabs v-model="activeTab" color="primary" grow show-arrows>
        <v-tab value="uebersicht" prepend-icon="mdi-home">Übersicht</v-tab>
        <v-tab value="features" prepend-icon="mdi-star">Features</v-tab>
        <v-tab value="workflow" prepend-icon="mdi-chart-timeline-variant">Workflow</v-tab>
        <v-tab value="technik" prepend-icon="mdi-code-braces">Technik</v-tab>
        <v-tab value="api" prepend-icon="mdi-api">API</v-tab>
        <v-tab value="datenbank" prepend-icon="mdi-database">Datenbank</v-tab>
        <v-tab value="faq" prepend-icon="mdi-help-circle">FAQ</v-tab>
      </v-tabs>

      <v-divider />

      <v-window v-model="activeTab">
        <!-- ==================== ÜBERSICHT ==================== -->
        <v-window-item value="uebersicht">
          <v-container class="pa-6">
            <v-row>
              <v-col cols="12">
                <h2 class="text-h5 font-weight-bold mb-4">
                  <v-icon start color="primary">mdi-information</v-icon>
                  Über diese Anwendung
                </h2>
                <p class="text-body-1 mb-4">
                  <strong>IHK AP2 FIAE</strong> ist eine spezialisierte Webanwendung zur Vorbereitung auf die
                  IHK-Abschlussprüfung Teil 2 (AP2) für IT-Berufe – insbesondere
                  <strong>Fachinformatiker Anwendungsentwicklung (FIAE)</strong> und
                  <strong>Fachinformatiker Systemintegration (FISI)</strong>.
                </p>
                <p class="text-body-1 mb-6">
                  Die App kombiniert ein umfassendes Prüfungsarchiv mit moderner KI-Technologie:
                  Prüfungsfragen werden automatisch aus PDFs extrahiert, Antworten können direkt in der
                  App eingegeben und von einer KI bewertet werden. Ergänzt wird das Ganze durch eine
                  intelligente Suchbegriff-Analyse, psychologische Lernprofile und einen personalisierten Trainingsplan.
                </p>
              </v-col>
            </v-row>

            <!-- Statistik-Karten -->
            <v-row class="mb-6">
              <v-col v-for="stat in [
                { icon: 'mdi-file-document-multiple', label: 'Prüfungen', value: '53+', color: 'primary' },
                { icon: 'mdi-file-pdf-box', label: 'Dokumente', value: '754', color: 'red' },
                { icon: 'mdi-text-recognition', label: 'OCR-Seiten', value: '2.980', color: 'teal' },
                { icon: 'mdi-tag-multiple', label: 'Suchbegriffe', value: '614', color: 'green' },
                { icon: 'mdi-target', label: 'Treffer', value: '4.137', color: 'orange' },
                { icon: 'mdi-clipboard-check', label: 'Musterlösungen', value: '616', color: 'deep-purple' },
              ]" :key="stat.label" cols="6" sm="4" md="2">
                <v-card
                  variant="tonal"
                  :color="stat.color"
                  rounded="xl"
                  class="text-center pa-4"
                  height="120"
                >
                  <v-icon :color="stat.color" size="28">{{ stat.icon }}</v-icon>
                  <div class="text-h5 font-weight-bold mt-1">{{ stat.value }}</div>
                  <div class="text-caption">{{ stat.label }}</div>
                </v-card>
              </v-col>
            </v-row>

            <!-- Schnellstart -->
            <h2 class="text-h5 font-weight-bold mb-4">
              <v-icon start color="success">mdi-rocket-launch</v-icon>
              Schnellstart
            </h2>
            <v-timeline side="end" density="compact" class="mb-6">
              <v-timeline-item dot-color="primary" size="small" icon="mdi-docker">
                <v-card variant="outlined" rounded="lg" class="pa-3">
                  <div class="font-weight-bold">1. Datenbank starten</div>
                  <code class="text-body-2">docker-compose up -d</code>
                </v-card>
              </v-timeline-item>
              <v-timeline-item dot-color="red" size="small" icon="mdi-server">
                <v-card variant="outlined" rounded="lg" class="pa-3">
                  <div class="font-weight-bold">2. Backend starten</div>
                  <code class="text-body-2">cd backend && npm install && npm run start:dev</code>
                </v-card>
              </v-timeline-item>
              <v-timeline-item dot-color="green" size="small" icon="mdi-vuejs">
                <v-card variant="outlined" rounded="lg" class="pa-3">
                  <div class="font-weight-bold">3. Frontend starten</div>
                  <code class="text-body-2">cd frontend && npm install && npm run dev</code>
                </v-card>
              </v-timeline-item>
              <v-timeline-item dot-color="blue" size="small" icon="mdi-web">
                <v-card variant="outlined" rounded="lg" class="pa-3">
                  <div class="font-weight-bold">4. App öffnen</div>
                  <code class="text-body-2">http://localhost:5173</code>
                </v-card>
              </v-timeline-item>
            </v-timeline>

            <!-- Tastenkürzel -->
            <h2 class="text-h5 font-weight-bold mb-4">
              <v-icon start color="grey-darken-1">mdi-keyboard</v-icon>
              Tastenkürzel
            </h2>
            <v-table density="compact" class="rounded-lg">
              <thead>
                <tr>
                  <th class="font-weight-bold">Tastenkombination</th>
                  <th class="font-weight-bold">Funktion</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="sc in shortcuts" :key="sc.keys">
                  <td><kbd class="px-2 py-1 rounded bg-grey-lighten-3 text-body-2 font-weight-medium">{{ sc.keys }}</kbd></td>
                  <td>{{ sc.desc }}</td>
                </tr>
              </tbody>
            </v-table>
          </v-container>
        </v-window-item>

        <!-- ==================== FEATURES ==================== -->
        <v-window-item value="features">
          <v-container class="pa-6">
            <h2 class="text-h5 font-weight-bold mb-6">
              <v-icon start color="amber">mdi-star</v-icon>
              Funktionen im Überblick
            </h2>
            <v-row>
              <v-col v-for="f in features" :key="f.title" cols="12" sm="6" lg="3">
                <v-card
                  rounded="xl"
                  elevation="2"
                  height="100%"
                  class="d-flex flex-column"
                >
                  <v-card-item>
                    <template #prepend>
                      <v-avatar :color="f.color" variant="tonal" size="48" rounded="lg">
                        <v-icon>{{ f.icon }}</v-icon>
                      </v-avatar>
                    </template>
                    <v-card-title class="text-subtitle-1 font-weight-bold">{{ f.title }}</v-card-title>
                  </v-card-item>
                  <v-card-text class="flex-grow-1 text-body-2">
                    {{ f.desc }}
                  </v-card-text>
                </v-card>
              </v-col>
            </v-row>

            <!-- KI-Bewertung Detail -->
            <v-card class="mt-8" rounded="xl" variant="outlined" color="deep-purple">
              <v-card-item>
                <template #prepend>
                  <v-icon color="deep-purple" size="32">mdi-robot-excited</v-icon>
                </template>
                <v-card-title class="text-h6">KI-Bewertung im Detail</v-card-title>
                <v-card-subtitle>So funktioniert die automatische Bewertung</v-card-subtitle>
              </v-card-item>
              <v-card-text>
                <v-row>
                  <v-col cols="12" md="6">
                    <h4 class="font-weight-bold mb-2">Bewertungsprozess</h4>
                    <v-list density="compact" class="pa-0">
                      <v-list-item prepend-icon="mdi-numeric-1-circle" title="Antwort und Musterlösung werden verglichen" />
                      <v-list-item prepend-icon="mdi-numeric-2-circle" title="Punkte werden nach IHK-Schema vergeben" />
                      <v-list-item prepend-icon="mdi-numeric-3-circle" title="Detailliertes Feedback wird generiert" />
                      <v-list-item prepend-icon="mdi-numeric-4-circle" title="Bei Teilpunkten: Lösungsvorschlag angezeigt" />
                    </v-list>
                  </v-col>
                  <v-col cols="12" md="6">
                    <h4 class="font-weight-bold mb-2">Unterstützte LLM-Anbieter</h4>
                    <v-list density="compact" class="pa-0">
                      <v-list-item prepend-icon="mdi-chip" title="Ollama (lokal)" subtitle="Kostenlos, datenschutzfreundlich, GPU empfohlen" />
                      <v-list-item prepend-icon="mdi-cloud" title="OpenAI" subtitle="GPT-4, GPT-3.5 – hohe Qualität" />
                      <v-list-item prepend-icon="mdi-lightning-bolt" title="Perplexity" subtitle="Schnelle Antworten mit Web-Kontext" />
                    </v-list>
                  </v-col>
                </v-row>
              </v-card-text>
            </v-card>
          </v-container>
        </v-window-item>

        <!-- ==================== WORKFLOW ==================== -->
        <v-window-item value="workflow">
          <v-container class="pa-6">
            <h2 class="text-h5 font-weight-bold mb-6">
              <v-icon start color="success">mdi-chart-timeline-variant</v-icon>
              Arbeitsablauf
            </h2>
            <p class="text-body-1 mb-6">
              Der typische Workflow zur Prüfungsvorbereitung besteht aus sechs aufeinander aufbauenden Schritten:
            </p>

            <v-row>
              <v-col v-for="step in workflowSteps" :key="step.title" cols="12" sm="6" md="4">
                <v-card rounded="xl" elevation="3" height="100%" class="d-flex flex-column">
                  <v-card-item>
                    <template #prepend>
                      <v-avatar :color="step.color" size="44">
                        <v-icon color="white">{{ step.icon }}</v-icon>
                      </v-avatar>
                    </template>
                    <v-card-title class="text-subtitle-1 font-weight-bold">{{ step.title }}</v-card-title>
                  </v-card-item>
                  <v-card-text class="flex-grow-1 text-body-2">
                    {{ step.desc }}
                  </v-card-text>
                </v-card>
              </v-col>
            </v-row>

            <!-- Prüfungsbereiche Erklärung -->
            <v-card class="mt-8" rounded="xl" variant="outlined">
              <v-card-item>
                <template #prepend>
                  <v-icon color="primary" size="28">mdi-format-list-group</v-icon>
                </template>
                <v-card-title>Prüfungsbereiche</v-card-title>
              </v-card-item>
              <v-card-text>
                <v-row>
                  <v-col cols="12" md="4">
                    <v-card variant="tonal" color="blue" rounded="lg" class="pa-4">
                      <h4 class="font-weight-bold mb-2">
                        <v-icon start size="20">mdi-cog</v-icon> GA1 – Ganzheitliche Aufgabe 1
                      </h4>
                      <p class="text-body-2">
                        Fachliche Umsetzung einer betrieblichen Aufgabenstellung. Konzeptionelle und
                        technische Aufgaben zu Softwareentwicklung, Systemintegration oder IT-Sicherheit.
                      </p>
                    </v-card>
                  </v-col>
                  <v-col cols="12" md="4">
                    <v-card variant="tonal" color="green" rounded="lg" class="pa-4">
                      <h4 class="font-weight-bold mb-2">
                        <v-icon start size="20">mdi-chart-bar</v-icon> GA2 – Ganzheitliche Aufgabe 2
                      </h4>
                      <p class="text-body-2">
                        Projektplanung, Kalkulation, Qualitätsmanagement. Beinhaltet oft Belegsätze
                        und kaufmännische Aufgaben wie Netzpläne, Nutzwertanalysen oder SQL-Abfragen.
                      </p>
                    </v-card>
                  </v-col>
                  <v-col cols="12" md="4">
                    <v-card variant="tonal" color="orange" rounded="lg" class="pa-4">
                      <h4 class="font-weight-bold mb-2">
                        <v-icon start size="20">mdi-scale-balance</v-icon> WISO – Wirtschafts- & Sozialkunde
                      </h4>
                      <p class="text-body-2">
                        Multiple-Choice-Aufgaben zu Arbeitsrecht, Sozialversicherung, Betriebsrat,
                        Vertragsrecht und weiteren berufsübergreifenden Themen.
                      </p>
                    </v-card>
                  </v-col>
                </v-row>
              </v-card-text>
            </v-card>
          </v-container>
        </v-window-item>

        <!-- ==================== TECHNIK ==================== -->
        <v-window-item value="technik">
          <v-container class="pa-6">
            <h2 class="text-h5 font-weight-bold mb-6">
              <v-icon start color="blue">mdi-code-braces</v-icon>
              Technologie-Stack
            </h2>

            <v-row class="mb-8">
              <v-col v-for="tech in techStack" :key="tech.name" cols="12" sm="6" md="3">
                <v-card rounded="xl" elevation="2" height="100%">
                  <v-card-item>
                    <template #prepend>
                      <v-avatar :color="tech.color" variant="tonal" size="44" rounded="lg">
                        <v-icon>{{ tech.icon }}</v-icon>
                      </v-avatar>
                    </template>
                    <v-card-title class="text-subtitle-1 font-weight-bold">{{ tech.name }}</v-card-title>
                  </v-card-item>
                  <v-card-text class="text-body-2">
                    {{ tech.desc }}
                  </v-card-text>
                </v-card>
              </v-col>
            </v-row>

            <!-- Architektur-Diagramm -->
            <v-card rounded="xl" variant="outlined" class="mb-6">
              <v-card-item>
                <template #prepend>
                  <v-icon color="primary">mdi-sitemap</v-icon>
                </template>
                <v-card-title>Systemarchitektur</v-card-title>
              </v-card-item>
              <v-card-text>
                <div class="d-flex flex-column align-center pa-4" style="font-family: monospace; font-size: 14px;">
                  <v-card variant="flat" color="green-lighten-4" rounded="lg" class="pa-3 mb-3 text-center" width="280">
                    <v-icon>mdi-monitor</v-icon>
                    <div class="font-weight-bold">Frontend (Vue 3 + Vuetify)</div>
                    <div class="text-caption">Port 5173 • SPA • TypeScript</div>
                  </v-card>

                  <v-icon size="28" color="grey">mdi-arrow-down-bold</v-icon>
                  <div class="text-caption text-grey mb-1">REST API (JSON)</div>

                  <v-card variant="flat" color="red-lighten-4" rounded="lg" class="pa-3 mb-3 text-center" width="280">
                    <v-icon>mdi-server</v-icon>
                    <div class="font-weight-bold">Backend (NestJS)</div>
                    <div class="text-caption">Port 3000 • REST • Prisma ORM</div>
                  </v-card>

                  <div class="d-flex ga-4 align-center">
                    <div class="d-flex flex-column align-center">
                      <v-icon size="28" color="grey">mdi-arrow-down-bold</v-icon>
                      <v-card variant="flat" color="blue-lighten-4" rounded="lg" class="pa-3 text-center" width="200">
                        <v-icon>mdi-database</v-icon>
                        <div class="font-weight-bold">PostgreSQL 16</div>
                        <div class="text-caption">Port 15432 • Docker</div>
                      </v-card>
                    </div>

                    <div class="d-flex flex-column align-center">
                      <v-icon size="28" color="grey">mdi-arrow-down-bold</v-icon>
                      <v-card variant="flat" color="orange-lighten-4" rounded="lg" class="pa-3 text-center" width="200">
                        <v-icon>mdi-creation</v-icon>
                        <div class="font-weight-bold">LLM-Anbieter</div>
                        <div class="text-caption">Ollama / OpenAI / Perplexity</div>
                      </v-card>
                    </div>
                  </div>
                </div>
              </v-card-text>
            </v-card>

            <!-- Projektstruktur -->
            <v-card rounded="xl" variant="outlined">
              <v-card-item>
                <template #prepend>
                  <v-icon color="amber-darken-2">mdi-folder-open</v-icon>
                </template>
                <v-card-title>Projektstruktur</v-card-title>
              </v-card-item>
              <v-card-text>
                <v-row>
                  <v-col cols="12" md="6">
                    <h4 class="font-weight-bold mb-2">Frontend</h4>
                    <pre class="text-body-2 bg-grey-lighten-4 pa-3 rounded-lg" style="overflow-x: auto;">
frontend/
├── src/
│   ├── views/           # Vue-Seiten (Dashboard, Prüfungen, ...)
│   ├── components/      # Wiederverwendbare Komponenten
│   ├── services/api.ts  # Axios API-Client
│   ├── composables/     # Vue Composables (useSettings, ...)
│   ├── types/           # TypeScript Interfaces
│   ├── router/          # Vue Router Konfiguration
│   └── App.vue          # Root-Komponente mit Navigation
├── public/              # Statische Assets
└── package.json         # Dependencies
                    </pre>
                  </v-col>
                  <v-col cols="12" md="6">
                    <h4 class="font-weight-bold mb-2">Backend</h4>
                    <pre class="text-body-2 bg-grey-lighten-4 pa-3 rounded-lg" style="overflow-x: auto;">
backend/
├── src/
│   ├── bewertung/       # KI-Bewertung & Extraktion
│   ├── pruefungen/      # Prüfungsverwaltung
│   ├── dokumente/       # PDF-/OCR-Verwaltung
│   ├── suchbegriffe/    # Suchbegriff-Analyse
│   ├── antworten/       # Antwort-CRUD
│   ├── treffer/         # Treffer-Statistiken
│   ├── prisma/          # Prisma Service
│   └── main.ts          # Bootstrap
├── prisma/schema.prisma # Datenbankschema
└── package.json         # Dependencies
                    </pre>
                  </v-col>
                </v-row>
              </v-card-text>
            </v-card>
          </v-container>
        </v-window-item>

        <!-- ==================== API ==================== -->
        <v-window-item value="api">
          <v-container class="pa-6">
            <h2 class="text-h5 font-weight-bold mb-2">
              <v-icon start color="indigo">mdi-api</v-icon>
              REST API Referenz
            </h2>
            <p class="text-body-2 text-medium-emphasis mb-6">
              Basis-URL: <code>http://localhost:3000</code> — Alle Endpunkte akzeptieren und liefern JSON.
            </p>

            <v-table density="comfortable" class="rounded-lg" hover>
              <thead>
                <tr class="bg-grey-lighten-4">
                  <th style="width: 90px;" class="font-weight-bold">Methode</th>
                  <th class="font-weight-bold">Endpunkt</th>
                  <th class="font-weight-bold">Beschreibung</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="ep in apiEndpoints" :key="ep.path">
                  <td>
                    <v-chip
                      :color="getMethodColor(ep.method)"
                      size="small"
                      variant="flat"
                      label
                      class="font-weight-bold"
                    >
                      {{ ep.method }}
                    </v-chip>
                  </td>
                  <td>
                    <code class="text-body-2">{{ ep.path }}</code>
                  </td>
                  <td class="text-body-2">{{ ep.desc }}</td>
                </tr>
              </tbody>
            </v-table>
          </v-container>
        </v-window-item>

        <!-- ==================== DATENBANK ==================== -->
        <v-window-item value="datenbank">
          <v-container class="pa-6">
            <h2 class="text-h5 font-weight-bold mb-2">
              <v-icon start color="blue-grey">mdi-database</v-icon>
              Datenbankschema
            </h2>
            <p class="text-body-2 text-medium-emphasis mb-6">
              PostgreSQL 16 • Docker-Container <code>ihk_ap2_db</code> • Port <code>15432</code>
            </p>

            <v-row>
              <v-col v-for="table in dbTables" :key="table.name" cols="12" md="6">
                <v-card rounded="xl" variant="outlined" class="mb-4" height="100%">
                  <v-card-item>
                    <template #prepend>
                      <v-icon color="blue-grey" size="24">mdi-table</v-icon>
                    </template>
                    <v-card-title class="text-subtitle-1 font-weight-bold font-italic">
                      {{ table.name }}
                    </v-card-title>
                  </v-card-item>
                  <v-card-text>
                    <p class="text-body-2 mb-2">{{ table.desc }}</p>
                    <v-divider class="mb-2" />
                    <div class="text-caption text-medium-emphasis">
                      <v-icon size="14" class="mr-1">mdi-key</v-icon>
                      <code>{{ table.fields }}</code>
                    </div>
                  </v-card-text>
                </v-card>
              </v-col>
            </v-row>

            <!-- ER-Beziehungen -->
            <v-card rounded="xl" variant="outlined" class="mt-4">
              <v-card-item>
                <template #prepend>
                  <v-icon color="deep-purple">mdi-relation-many-to-many</v-icon>
                </template>
                <v-card-title>Wichtige Beziehungen</v-card-title>
              </v-card-item>
              <v-card-text>
                <v-list density="compact" class="pa-0">
                  <v-list-item
                    prepend-icon="mdi-arrow-right"
                    title="pruefungen → dokumente"
                    subtitle="1:N – Eine Prüfung hat mehrere Dokumente (Aufgabe, Lösung, Belegsatz)"
                  />
                  <v-list-item
                    prepend-icon="mdi-arrow-right"
                    title="dokumente → seiten"
                    subtitle="1:N – Ein Dokument hat mehrere OCR-Seiten"
                  />
                  <v-list-item
                    prepend-icon="mdi-arrow-right"
                    title="pruefungen → musterloesungen"
                    subtitle="1:N – Eine Prüfung hat mehrere Musterlösungen (je Aufgabe)"
                  />
                  <v-list-item
                    prepend-icon="mdi-arrow-right"
                    title="pruefungen → antworten"
                    subtitle="1:N – Benutzerantworten je Prüfung und Aufgabe"
                  />
                  <v-list-item
                    prepend-icon="mdi-arrow-right"
                    title="antworten → bewertungen"
                    subtitle="1:N – Jede Antwort kann mehrfach bewertet werden"
                  />
                  <v-list-item
                    prepend-icon="mdi-arrow-right"
                    title="suchbegriffe → treffer"
                    subtitle="1:N – Treffer verknüpfen Suchbegriffe mit Prüfungsseiten"
                  />
                </v-list>
              </v-card-text>
            </v-card>
          </v-container>
        </v-window-item>

        <!-- ==================== FAQ ==================== -->
        <v-window-item value="faq">
          <v-container class="pa-6">
            <h2 class="text-h5 font-weight-bold mb-6">
              <v-icon start color="amber-darken-2">mdi-help-circle</v-icon>
              Häufig gestellte Fragen
            </h2>

            <v-expansion-panels v-model="expandedFaq" variant="accordion" rounded="xl">
              <v-expansion-panel
                v-for="(item, i) in faqItems"
                :key="i"
                :value="String(i)"
                rounded="xl"
              >
                <v-expansion-panel-title class="font-weight-medium">
                  <v-icon start color="primary" size="20">mdi-chat-question</v-icon>
                  {{ item.q }}
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <div class="text-body-2" style="white-space: pre-line;">{{ item.a }}</div>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>

            <!-- Kontakt/Support -->
            <v-alert
              type="info"
              variant="tonal"
              rounded="xl"
              class="mt-6"
              icon="mdi-information"
            >
              <div class="font-weight-bold mb-1">Weitere Hilfe benötigt?</div>
              Diese Anwendung wird kontinuierlich weiterentwickelt. Bei Fragen oder Problemen
              können Sie den Quellcode einsehen oder ein Issue im Repository erstellen.
            </v-alert>
          </v-container>
        </v-window-item>
      </v-window>
    </v-card>

    <!-- Footer -->
    <v-card class="mt-6 text-center pa-4" rounded="xl" variant="tonal" color="grey-lighten-3">
      <p class="text-body-2 text-medium-emphasis mb-0">
        <v-icon size="16" class="mr-1">mdi-code-tags</v-icon>
        IHK AP2 FIAE – Prüfungsanalyse & KI-gestützte Vorbereitung
        <span class="mx-2">•</span>
        Erstellt mit Vue 3, Vuetify, NestJS & PostgreSQL
        <span class="mx-2">•</span>
        {{ new Date().getFullYear() }}
      </p>
    </v-card>
  </div>
</template>

<style scoped>
pre {
  margin: 0;
  line-height: 1.6;
}

code {
  background: rgba(0, 0, 0, 0.06);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.85em;
}
</style>
