<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { Search, Loader2, ExternalLink, User, Settings, Clock, Filter } from 'lucide-vue-next'
import { apiService } from '../../services/api'
import SendToGraphButton from '../SendToGraphButton.vue'

const { t } = useI18n()
const route = useRoute()

const username = ref('')
const isSearching = ref(false)
const progressText = ref('')
const results = ref([])
const ws = ref(null)

const filterText = ref('')
const filteredResults = computed(() => {
  if (!filterText.value) return results.value
  const q = filterText.value.toLowerCase()
  return results.value.filter(r => r.site.toLowerCase().includes(q))
})

const showSettings = ref(false)
const timeout = ref(60)

function getDomain(url) {
  try { return new URL(url).hostname.replace('www.', '') }
  catch { return url }
}

function getFaviconUrl(url) {
  try { return `https://www.google.com/s2/favicons?domain=${new URL(url).hostname}&sz=32` }
  catch { return '' }
}

function startSearch() {
  if (!username.value.trim() || isSearching.value) return

  results.value = []
  isSearching.value = true
  progressText.value = t('socialForensics.sherlock.initializing')

  ws.value = apiService.createSherlockWebSocket()

  ws.value.onopen = () => {
    ws.value.send(JSON.stringify({
      action: 'search',
      username: username.value,
      timeout: timeout.value
    }))
    progressText.value = t('socialForensics.sherlock.hunting', { username: `@${username.value}` })
  }

  ws.value.onmessage = (event) => {
    const data = JSON.parse(event.data)

    if (data.type === 'found') {
      results.value.push({ site: data.site, url: data.url })
    } else if (data.type === 'info') {
      progressText.value = data.text.replace('[*]', '').trim()
    } else if (data.type === 'done') {
      isSearching.value = false
      progressText.value = t('socialForensics.sherlock.complete', { count: results.value.length })
      if (ws.value) ws.value.close()
    } else if (data.type === 'error') {
      isSearching.value = false
      progressText.value = `${t('socialForensics.sherlock.errorPrefix')} ${data.text}`
      if (ws.value) ws.value.close()
    }
  }

  ws.value.onerror = () => {
    isSearching.value = false
    progressText.value = t('socialForensics.sherlock.wsError')
  }
}

function stopSearch() {
  if (ws.value && isSearching.value) {
    ws.value.close()
    isSearching.value = false
    progressText.value = t('socialForensics.sherlock.aborted')
  }
}

watch(
  () => route.query,
  (query) => {
    if (query.tab === 'sherlock' && query.query) {
      if (username.value !== query.query) {
        username.value = query.query
        // Delay slightly to let the UI update before starting WS
        setTimeout(() => startSearch(), 50)
      }
    }
  },
  { immediate: true }
)

onUnmounted(() => {
  stopSearch()
})
</script>

<template>
  <div class="sherlock-module">
    <div class="search-panel glass-panel">
      <div class="input-wrapper">
        <User class="icon-user" size="20" />
        <input
          v-model="username"
          type="text"
          :placeholder="t('socialForensics.sherlock.placeholder')"
          @keyup.enter="startSearch"
          :disabled="isSearching"
        />
        <button class="btn-settings" @click="showSettings = !showSettings" :class="{ active: showSettings }">
          <Settings size="18" />
        </button>
        <button class="btn-search" @click="startSearch" v-if="!isSearching">
          <Search size="18" /> {{ t('socialForensics.sherlock.search') }}
        </button>
        <button class="btn-stop" @click="stopSearch" v-else>
          <Loader2 size="18" class="spin" /> {{ t('socialForensics.sherlock.abort') }}
        </button>
      </div>
      <div class="settings-panel" v-if="showSettings">
        <div class="setting-item">
          <div class="setting-header">
            <Clock size="16" class="text-blue" />
            <label>{{ t('socialForensics.sherlock.timeout') }}</label>
            <div class="range-wrapper">
              <input type="range" v-model="timeout" min="10" max="120" class="range-slider" :disabled="isSearching" />
              <span class="range-value">{{ timeout }}s</span>
            </div>
          </div>
          <p class="setting-desc">{{ t('socialForensics.sherlock.timeoutHelp') }}</p>
        </div>
      </div>
    </div>
    <div class="progress-area" v-if="isSearching || results.length > 0 || progressText">
      <div class="progress-header">
        <div class="status-badge" :class="{ 'scanning': isSearching, 'done': !isSearching && results.length > 0, 'error': progressText.includes('Error') }">
          <div class="pulse-dot" v-if="isSearching"></div>
          <span>{{ progressText || (isSearching ? t('socialForensics.sherlock.scanning') : t('socialForensics.sherlock.idle')) }}</span>
        </div>
        <div class="counter" v-if="results.length > 0">
          <span class="count-number">{{ results.length }}</span> {{ t('socialForensics.sherlock.found') }}
        </div>
      </div>
      <div class="progress-track" v-if="isSearching">
        <div class="progress-fill indeterminate"></div>
      </div>
    </div>
    <div class="filter-wrapper" v-if="results.length > 0">
      <Filter size="16" class="filter-icon" />
      <input type="text" v-model="filterText" :placeholder="t('socialForensics.sherlock.filterPlaceholder')" class="filter-input" />
    </div>

    <div class="results-grid" v-if="filteredResults.length > 0">
      <div
        v-for="(res, idx) in filteredResults"
        :key="idx"
        class="result-card"
      >
        <img :src="getFaviconUrl(res.url)" class="site-favicon" alt="" @error="$event.target.style.display='none'" />
        <div class="site-info">
          <span class="site-name">{{ res.site }}</span>
          <a :href="res.url" target="_blank" class="url-link">
            <span class="site-url">{{ getDomain(res.url) }}</span>
            <ExternalLink size="12" class="link-icon" />
          </a>
        </div>
        <SendToGraphButton
          :label="`${username} on ${res.site}`"
          iconName="Globe"
          color="#F97316"
          :notes="res.url"
        />
      </div>
    </div>
    <div class="empty-state" v-if="!isSearching && results.length === 0 && !progressText">
      <div class="empty-icon-wrapper">
        <Search size="48" class="text-muted" />
      </div>
      <h3>{{ t('socialForensics.sherlock.readyTitle') }}</h3>
      <p>{{ t('socialForensics.sherlock.readyText') }}</p>
      <p class="text-muted" style="font-size: 0.8rem; margin-top: 8px;">{{ t('socialForensics.sherlock.poweredBy') }}</p>
    </div>
  </div>
</template>

<style scoped>
.sherlock-module {
  display: flex;
  flex-direction: column;
  flex: 1;
}

/* ── Search Panel ─────────────────────────────── */
.search-panel {
  padding: 16px;

  margin-bottom: 20px;
}

.input-wrapper {
  display: flex;
  align-items: center;
  background: var(--bg-panel);
  border: 1px solid var(--border-color);

  padding: 4px;
  position: relative;
}

.icon-user {
  position: absolute;
  left: 16px;
  color: var(--text-muted);
}

.btn-settings {
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  color: var(--text-muted);
  border: 1px solid var(--border-color);
  padding: 12px;

  cursor: pointer;
  transition: var(--transition);
  margin-right: 8px;
}
.btn-settings:hover, .btn-settings.active {
  background: var(--overlay-10);
  color: var(--text-main);
}

.input-wrapper input {
  flex: 1;
  background: transparent;
  border: none;
  color: var(--text-main);
  padding: 14px 16px 14px 48px;
  font-size: 1.1rem;
  outline: none;
}

.btn-search {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--accent-orange);
  color: #000;
  border: none;
  padding: 12px 24px;

  font-weight: 600;
  cursor: pointer;
  transition: var(--transition);
}
.btn-search:hover { filter: brightness(1.15); }

.btn-stop {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(239, 68, 68, 0.2);
  color: var(--accent-red);
  border: 1px solid rgba(239, 68, 68, 0.4);
  padding: 12px 24px;

  font-weight: 600;
  cursor: pointer;
  transition: var(--transition);
}
.btn-stop:hover { background: rgba(239, 68, 68, 0.3); }

.spin { animation: spin 1s linear infinite; }
@keyframes spin { 100% { transform: rotate(360deg); } }

/* ── Settings Panel ───────────────────────────── */
.settings-panel {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px dashed var(--border-color);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.setting-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.setting-header {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--text-main);
  font-size: 0.9rem;
  font-weight: 500;
}
.setting-header label { flex: 1; margin-bottom: 0; }

.setting-desc {
  font-size: 0.8rem;
  color: var(--text-muted);
  padding-left: 28px;
  margin: 0;
}

/* ── Progress ─────────────────────────────────── */
.progress-area {
  margin-bottom: 24px;
  padding: 0 4px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
  color: var(--text-muted);
}
.status-badge.scanning { color: var(--accent-orange); }
.status-badge.done { color: var(--accent-green); }
.status-badge.error { color: var(--accent-red); }

.pulse-dot {
  width: 8px;
  height: 8px;
  background: var(--accent-orange);

  animation: pulse 1.5s infinite;
}
@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(var(--accent-rgb), 0.4); }
  70% { box-shadow: 0 0 0 6px rgba(var(--accent-rgb), 0); }
  100% { box-shadow: 0 0 0 0 rgba(var(--accent-rgb), 0); }
}

.counter {
  font-size: 0.85rem;
  color: var(--text-muted);
}
.count-number {
  color: var(--accent-orange);
  font-weight: 700;
  font-size: 1.1rem;
}

.progress-track {
  height: 3px;
  background: var(--overlay-8);

  overflow: hidden;
}
.progress-fill.indeterminate {
  height: 100%;
  width: 30%;
  background: linear-gradient(90deg, var(--accent-orange), #ff3366);

  animation: indeterminate 1.4s ease-in-out infinite;

}
@keyframes indeterminate {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(400%); }
}

/* ── Results Grid ─────────────────────────────── */
/* ── Results Filter ─────────────────────────────── */
.filter-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--bg-panel);
  border: 1px solid var(--border-color);
  padding: 8px 12px;
  margin-bottom: 16px;
  border-radius: 4px;
}

.filter-icon {
  color: var(--text-muted);
}

.filter-input {
  flex: 1;
  background: transparent;
  border: none;
  color: var(--text-main);
  outline: none;
  font-size: 0.9rem;
}

.results-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
  padding-bottom: 32px;
}

.result-card {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--bg-panel);
  border: 1px solid var(--border-color);
  padding: 12px 14px;

  transition: all 0.25s ease;
}

.result-card:hover {
  border-color: rgba(var(--accent-rgb), 0.4);
  background: rgba(var(--accent-rgb), 0.04);
}

.site-favicon {
  width: 24px;
  height: 24px;

  flex-shrink: 0;
}

.site-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.site-name {
  color: var(--text-main);
  font-size: 0.9rem;
  font-weight: 500;
}

.site-url {
  color: var(--text-muted);
  font-size: 0.75rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.url-link {
  display: flex;
  align-items: center;
  gap: 4px;
  text-decoration: none;
  color: var(--text-muted);
}

.url-link:hover .site-url {
  color: var(--accent-orange);
}

.url-link:hover .link-icon {
  color: var(--accent-orange);
}

.link-icon {
  color: var(--text-muted);
  transition: color 0.2s ease;
  flex-shrink: 0;
}

/* ── Empty State ──────────────────────────────── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: 48px;
  text-align: center;
}

.empty-icon-wrapper {
  width: 96px;
  height: 96px;

  background: var(--overlay-8);
  border: 1px dashed var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24px;
}

.empty-state h3 {
  font-size: 1.5rem;
  color: var(--text-main);
  margin-bottom: 8px;
}

.empty-state p {
  color: var(--text-muted);
  max-width: 400px;
}
</style>
