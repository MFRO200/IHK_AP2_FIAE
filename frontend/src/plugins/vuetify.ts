import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'

export default createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: 'ihkTheme',
    themes: {
      ihkTheme: {
        dark: false,
        colors: {
          primary: '#1565C0',
          secondary: '#424242',
          accent: '#FF6F00',
          error: '#D32F2F',
          info: '#0288D1',
          success: '#388E3C',
          warning: '#F9A825',
          background: '#F5F5F5',
          surface: '#FFFFFF',
        },
      },
    },
  },
  defaults: {
    VDataTable: {
      density: 'comfortable',
      hover: true,
    },
    VCard: {
      elevation: 2,
    },
    VBtn: {
      variant: 'flat',
    },
  },
})
