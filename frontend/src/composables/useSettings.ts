import { ref, computed, watch } from 'vue'

/**
 * Fachbereich-Einstellungen.
 * Wird in localStorage gespeichert und global verfügbar gemacht.
 *
 * Fachbereiche:
 *  - 'alle'                   → alles sichtbar (kein Filter)
 *  - 'Anwendungsentwicklung'  → GA1, GA2, WISO, AP1, Sonstige (Belegsatz für GA1/GA2)
 *  - 'Systemintegration'      → GA1 FISI, GA2, WISO, AP1, Sonstige
 *  - 'IT-System-Elektroniker' → GA1 IT-SE, GA2, WISO, AP1, Sonstige
 *  - 'IT-System-Kaufleute'    → GA1 IT-SK, GA2, WISO, AP1, Sonstige
 *  - 'Informatikkaufleute'    → GA1 IK, GA2, WISO, AP1, Sonstige
 */

export type Fachbereich =
  | 'alle'
  | 'Anwendungsentwicklung'
  | 'Systemintegration'
  | 'IT-System-Elektroniker'
  | 'IT-System-Kaufleute'
  | 'Informatikkaufleute'

export const fachbereichOptions: { value: Fachbereich; label: string; icon: string }[] = [
  { value: 'alle', label: 'Alle Fachbereiche', icon: 'mdi-all-inclusive' },
  { value: 'Anwendungsentwicklung', label: 'Fachinformatiker Anwendungsentwicklung', icon: 'mdi-code-braces' },
  { value: 'Systemintegration', label: 'Fachinformatiker Systemintegration', icon: 'mdi-server-network' },
  { value: 'IT-System-Elektroniker', label: 'IT-System-Elektroniker', icon: 'mdi-chip' },
  { value: 'IT-System-Kaufleute', label: 'IT-System-Kaufleute', icon: 'mdi-cart-outline' },
  { value: 'Informatikkaufleute', label: 'Informatikkaufleute', icon: 'mdi-calculator-variant' },
]

/**
 * Welche pruefungsbereich-Werte für jeden Fachbereich sichtbar sind.
 * WISO, AP1, Sonstige sind für alle gültig.
 * Belegsatz (typ) ist bei FIAE für GA1 und GA2 gültig.
 */
const fachbereichFilter: Record<Fachbereich, string[]> = {
  alle: [], // leer = kein Filter
  Anwendungsentwicklung: ['GA1', 'GA2', 'WISO', 'AP1', 'Sonstige'],
  Systemintegration: ['GA1 FISI', 'GA2', 'WISO', 'AP1', 'Sonstige'],
  'IT-System-Elektroniker': ['GA1 IT-SE', 'GA2', 'WISO', 'AP1', 'Sonstige'],
  'IT-System-Kaufleute': ['GA1 IT-SK', 'GA2', 'WISO', 'AP1', 'Sonstige'],
  Informatikkaufleute: ['GA1 IK', 'GA2', 'WISO', 'AP1', 'Sonstige'],
}

const STORAGE_KEY = 'ihk_fachbereich'

// Shared reactive state (singleton)
const fachbereich = ref<Fachbereich>(loadFromStorage())

function loadFromStorage(): Fachbereich {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored && fachbereichOptions.some((o) => o.value === stored)) {
      return stored as Fachbereich
    }
  } catch { /* ignore */ }
  return 'alle'
}

// Persist changes
watch(fachbereich, (val) => {
  localStorage.setItem(STORAGE_KEY, val)
})

export function useSettings() {
  /** Erlaubte pruefungsbereich-Werte für den aktuellen Fachbereich */
  const erlaubteBereiche = computed(() => fachbereichFilter[fachbereich.value])

  /** Ist ein Filter aktiv? */
  const filterAktiv = computed(() => fachbereich.value !== 'alle')

  /** Prüft ob ein pruefungsbereich sichtbar ist */
  function istBereichSichtbar(pruefungsbereich: string | null | undefined): boolean {
    if (!filterAktiv.value) return true
    if (!pruefungsbereich) return true // null = zeige es
    return erlaubteBereiche.value.includes(pruefungsbereich)
  }

  /**
   * Prüft ob ein Dokument sichtbar ist.
   * Belegsätze sind bei FIAE für GA1/GA2 gültig → immer sichtbar wenn Fachbereich Anwendungsentwicklung.
   */
  function istDokumentSichtbar(dok: { pruefungsbereich?: string | null; typ?: string | null }): boolean {
    if (!filterAktiv.value) return true
    // Belegsatz ist bei allen Fachbereichen für GA1/GA2 sichtbar
    if (dok.typ === 'Belegsatz') return true
    return istBereichSichtbar(dok.pruefungsbereich)
  }

  /** Aktuelles Fachbereich-Label */
  const fachbereichLabel = computed(() =>
    fachbereichOptions.find((o) => o.value === fachbereich.value)?.label || fachbereich.value,
  )

  /** Aktuelles Fachbereich-Icon */
  const fachbereichIcon = computed(() =>
    fachbereichOptions.find((o) => o.value === fachbereich.value)?.icon || 'mdi-all-inclusive',
  )

  return {
    fachbereich,
    fachbereichOptions,
    erlaubteBereiche,
    filterAktiv,
    istBereichSichtbar,
    istDokumentSichtbar,
    fachbereichLabel,
    fachbereichIcon,
  }
}
