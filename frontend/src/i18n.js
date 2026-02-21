import { createI18n } from 'vue-i18n'
import en from './locales/en.js'
import uk from './locales/uk.js'

export default createI18n({
  legacy: false,
  locale: localStorage.getItem('locale') || 'en',
  fallbackLocale: 'en',
  messages: { en, uk },
})
