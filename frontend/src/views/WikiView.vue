<template>
  <div>
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px">
      <router-link to=".." @click.prevent="$router.go(-1)" style="color:#1e3a5f;text-decoration:none;font-size:.9em">{{ t('wiki.back') }}</router-link>
      <h2 style="margin:0">{{ t('wiki.title') }}</h2>
    </div>
    <div v-if="loading" style="color:#888">{{ t('common.loading') }}</div>
    <div v-else-if="notFound" style="color:#888;padding:20px">{{ t('wiki.notFound') }}</div>
    <div
      v-else
      class="wiki-content"
      v-html="html"
    />
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { marked } from 'marked'

const route = useRoute()
const { t, locale } = useI18n()

const html = ref('')
const loading = ref(true)
const notFound = ref(false)

async function fetchPage() {
  loading.value = true
  notFound.value = false
  html.value = ''
  const page = route.params.page
  const lang = locale.value
  try {
    const res = await fetch(`/wiki/${lang}/${page}.md`)
    if (!res.ok) {
      // fallback to English
      const fallback = await fetch(`/wiki/en/${page}.md`)
      if (!fallback.ok) { notFound.value = true; return }
      html.value = marked.parse(await fallback.text())
    } else {
      html.value = marked.parse(await res.text())
    }
  } catch {
    notFound.value = true
  } finally {
    loading.value = false
  }
}

onMounted(fetchPage)
watch(() => route.params.page, fetchPage)
watch(locale, fetchPage)
</script>

<style scoped>
.wiki-content {
  background: #fff;
  border-radius: 8px;
  padding: 24px 32px;
  box-shadow: 0 1px 4px rgba(0,0,0,.1);
  line-height: 1.7;
  max-width: 800px;
}
.wiki-content :deep(h1) { font-size: 1.6em; margin-bottom: 16px; color: #1e3a5f; }
.wiki-content :deep(h2) { font-size: 1.2em; margin-top: 24px; margin-bottom: 8px; color: #1e3a5f; border-bottom: 1px solid #e0e0e0; padding-bottom: 4px; }
.wiki-content :deep(h3) { font-size: 1em; margin-top: 16px; color: #333; }
.wiki-content :deep(p) { margin-bottom: 12px; color: #444; }
.wiki-content :deep(ul), .wiki-content :deep(ol) { margin: 8px 0 12px 24px; color: #444; }
.wiki-content :deep(li) { margin-bottom: 4px; }
.wiki-content :deep(code) { background: #f0f4f8; padding: 2px 5px; border-radius: 3px; font-size: .9em; }
.wiki-content :deep(pre) { background: #f0f4f8; padding: 12px 16px; border-radius: 6px; overflow-x: auto; margin-bottom: 12px; }
.wiki-content :deep(table) { border-collapse: collapse; margin-bottom: 12px; width: 100%; }
.wiki-content :deep(th) { background: #f0f4f8; padding: 6px 10px; text-align: left; border: 1px solid #ddd; }
.wiki-content :deep(td) { padding: 6px 10px; border: 1px solid #ddd; }
</style>
