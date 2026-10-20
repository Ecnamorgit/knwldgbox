<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { Search, Loader2, ExternalLink, UserSearch, Fingerprint } from 'lucide-vue-next'
import { apiService } from '../../services/api'
import SendToGraphButton from '../SendToGraphButton.vue'

const name = ref('')
const isScanning = ref(false)
const variants = ref([])
const results = ref([])            // { site, url, variant, source }
const progress = ref({ done: 0, total: 0, current: '' })
const ws = ref(null)

function getDomain(url) {
  try { return new URL(url).hostname.replace('www.', '') } catch { return url }
}
function getFavicon(url) {
  try { return `https://www.google.com/s2/favicons?domain=${new URL(url).hostname}&sz=32` } catch { return '' }
}

const CONF = { high: 3, medium: 2, low: 1 }
const minConf = ref('low')   // 'low' = show all, 'medium' = hide low, 'high' = high only

// Group accounts by platform, filtered by confidence, best-confidence first
const grouped = computed(() => {
  const min = CONF[minConf.value]
  const map = {}
  for (const r of results.value) {
    if ((CONF[r.confidence] || 1) < min) continue
    if (!map[r.site]) map[r.site] = { site: r.site, accounts: [] }
    if (!map[r.site].accounts.some(a => a.url === r.url)) {
      map[r.site].accounts.push({ url: r.url, variant: r.variant, source: r.source, confidence: r.confidence || 'low' })
    }
  }
  const arr = Object.values(map)
  for (const g of arr) {
    g.maxConf = Math.max(...g.accounts.map(a => CONF[a.confidence] || 1))
    g.accounts.sort((a, b) => (CONF[b.confidence] || 1) - (CONF[a.confidence] || 1))
  }
  return arr.sort((a, b) => b.maxConf - a.maxConf || a.site.localeCompare(b.site))
})

const platformCount = computed(() => grouped.value.length)
const accountCount = computed(() => grouped.value.reduce((n, g) => n + g.accounts.length, 0))

function start() {
  const q = name.value.trim()
  if (!q || isScanning.value) return
  variants.value = []
  results.value = []
  progress.value = { done: 0, total: 0, current: '' }
  isScanning.value = true

  ws.value = apiService.createReconWebSocket()
  ws.value.onopen = () => ws.value.send(JSON.stringify({ action: 'search', name: q }))
  ws.value.onmessage = (ev) => {
    const d = JSON.parse(ev.data)
    if (d.type === 'variants') {
      variants.value = d.variants
      progress.value.total = d.variants.length
    } else if (d.type === 'found') {
      // dedupe by url+variant
      if (!results.value.some(r => r.url === d.url && r.variant === d.variant)) {
        results.value.push({ site: d.site, url: d.url, variant: d.variant, source: d.source, extra: d.extra, confidence: d.confidence || 'low' })
      }
    } else if (d.type === 'progress') {
      progress.value = { done: d.done, total: d.total, current: d.variant }
    } else if (d.type === 'done') {
      isScanning.value = false
      if (ws.value) ws.value.close()
    } else if (d.type === 'error') {
      isScanning.value = false
      if (ws.value) ws.value.close()
    }
  }
  ws.value.onerror = () => { isScanning.value = false }
}

function stop() {
  if (ws.value) ws.value.close()
  isScanning.value = false
}

onUnmounted(stop)
</script>

<template>
  <div class="recon-module">
    <div class="search-panel glass-panel">
      <div class="input-wrapper">
        <UserSearch class="icon-lead" size="20" />
        <input
          v-model="name"
          type="text"
          placeholder="Full name (ex: Mélanie Lefevre) — generates handle variants"
          @keyup.enter="start"
          :disabled="isScanning"
        />
        <button class="btn-search" @click="start" v-if="!isScanning">
          <Search size="18" /> Run Recon
        </button>
        <button class="btn-stop" @click="stop" v-else>
          <Loader2 size="18" class="spin" /> Stop
        </button>
      </div>
    </div>

    <!-- Variants -->
    <div class="variants-box" v-if="variants.length">
      <span class="vlabel">{{ variants.length }} variants tested:</span>
      <span class="vchip" :class="[`conf-${v.confidence}`, { active: progress.current === v.name }]" v-for="v in variants" :key="v.name">{{ v.name }}</span>
    </div>

    <!-- Progress -->
    <div class="progress-area" v-if="isScanning || results.length">
      <div class="progress-header">
        <div class="status" :class="{ scanning: isScanning }">
          <div class="dot" v-if="isScanning"></div>
          <span v-if="isScanning">Scanning {{ progress.done }}/{{ progress.total }} variants…</span>
          <span v-else>Scan complete.</span>
        </div>
        <div class="tally" v-if="results.length">
          <span class="num">{{ accountCount }}</span> accounts ·
          <span class="num">{{ platformCount }}</span> platforms
        </div>
      </div>
      <div class="track" v-if="isScanning">
        <div class="fill" :style="{ width: progress.total ? (progress.done / progress.total * 100) + '%' : '0%' }"></div>
      </div>
    </div>

    <!-- Confidence filter -->
    <div class="conf-filter" v-if="results.length">
      <span class="cf-label">Confidence</span>
      <button class="cf-btn" :class="{ active: minConf === 'low' }" @click="minConf = 'low'">All</button>
      <button class="cf-btn" :class="{ active: minConf === 'medium' }" @click="minConf = 'medium'">Medium +</button>
      <button class="cf-btn high" :class="{ active: minConf === 'high' }" @click="minConf = 'high'">High only</button>
      <span class="cf-hint">High = unique handle · Low = common/initials (homonym-prone)</span>
    </div>

    <!-- Aggregated footprint -->
    <div class="footprint" v-if="grouped.length">
      <div class="platform-card" v-for="g in grouped" :key="g.site">
        <img :src="getFavicon(g.url)" class="favicon" alt="" @error="$event.target.style.display='none'" />
        <div class="pf-info">
          <div class="pf-head">
            <span class="pf-name">{{ g.site }}</span>
            <span class="pf-count" v-if="g.accounts.length > 1">{{ g.accounts.length }}</span>
          </div>
          <a v-for="acc in g.accounts" :key="acc.url" :href="acc.url" target="_blank" rel="noopener" class="pf-acc">
            <span class="conf-dot" :class="acc.confidence" :title="`${acc.confidence} confidence`"></span>
            <span class="pf-variant">{{ acc.variant }}</span>
            <span class="pf-url">{{ getDomain(acc.url) }}</span>
            <span class="pf-src" :class="acc.source">{{ acc.source }}</span>
            <ExternalLink size="11" />
          </a>
        </div>
        <SendToGraphButton :label="`${g.site}: ${g.accounts[0].variant}`" iconName="Globe" color="#8B5CF6" :notes="g.accounts.map(a=>a.url).join(' | ')" />
      </div>
    </div>

    <!-- Empty -->
    <div class="empty-state" v-if="!isScanning && !results.length && !variants.length">
      <div class="empty-icon"><Fingerprint size="42" /></div>
      <h3>Identity Recon</h3>
      <p>Enter a person's name. The engine generates likely username variants (firstlast, lastfirst, first.last, f.last…) and sweeps them through Sherlock + Bluesky in parallel, aggregating every account found into one footprint.</p>
    </div>
  </div>
</template>

<style scoped>
.recon-module { display: flex; flex-direction: column; flex: 1; }

.search-panel { padding: 16px; margin-bottom: 16px; }
.input-wrapper { display: flex; align-items: center; background: var(--bg-panel); border: 1px solid var(--border-color); padding: 4px; position: relative; }
.icon-lead { position: absolute; left: 16px; color: var(--text-muted); }
.input-wrapper input { flex: 1; background: transparent; border: none; color: var(--text-main); padding: 14px 16px 14px 48px; font-size: 1.05rem; outline: none; }
.btn-search { display: flex; align-items: center; gap: 8px; background: var(--accent-orange); color: #000; border: none; padding: 12px 24px; font-weight: 600; cursor: pointer; }
.btn-search:hover { filter: brightness(1.15); }
.btn-stop { display: flex; align-items: center; gap: 8px; background: rgba(239,68,68,0.2); color: var(--accent-red); border: 1px solid rgba(239,68,68,0.4); padding: 12px 24px; font-weight: 600; cursor: pointer; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { 100% { transform: rotate(360deg); } }

.variants-box { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-bottom: 16px; }
.vlabel { font-size: 0.78rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-right: 4px; }
.vchip { font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; background: var(--overlay-8); border: 1px solid var(--border-color); color: var(--text-muted); padding: 2px 8px; transition: all 0.2s; }
.vchip.active { color: var(--accent-orange); border-color: var(--accent-orange); }
.vchip.conf-high { border-left: 3px solid var(--accent-green); }
.vchip.conf-medium { border-left: 3px solid var(--accent-orange); }
.vchip.conf-low { border-left: 3px solid var(--text-muted); opacity: 0.75; }

.conf-filter { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.cf-label { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); }
.cf-btn { background: var(--bg-panel); border: 1px solid var(--border-color); color: var(--text-muted); padding: 5px 12px; font-size: 0.8rem; cursor: pointer; transition: var(--transition); }
.cf-btn:hover { color: var(--text-main); }
.cf-btn.active { background: rgba(var(--accent-rgb),0.12); color: var(--accent-orange); border-color: var(--accent-orange); }
.cf-btn.high.active { background: rgba(0,255,136,0.1); color: var(--accent-green); border-color: var(--accent-green); }
.cf-hint { font-size: 0.72rem; color: var(--text-muted); margin-left: auto; }

.conf-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.conf-dot.high { background: var(--accent-green); }
.conf-dot.medium { background: var(--accent-orange); }
.conf-dot.low { background: var(--text-muted); }

.progress-area { margin-bottom: 20px; }
.progress-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.status { display: flex; align-items: center; gap: 10px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: var(--text-muted); }
.status.scanning { color: var(--accent-orange); }
.dot { width: 8px; height: 8px; background: var(--accent-orange); animation: pulse 1.5s infinite; }
@keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(var(--accent-rgb),0.4); } 70% { box-shadow: 0 0 0 6px rgba(var(--accent-rgb),0); } 100% { box-shadow: 0 0 0 0 rgba(var(--accent-rgb),0); } }
.tally { font-size: 0.85rem; color: var(--text-muted); }
.tally .num { color: var(--accent-orange); font-weight: 700; font-size: 1.05rem; }
.track { height: 4px; background: var(--overlay-8); overflow: hidden; }
.fill { height: 100%; background: linear-gradient(90deg, var(--accent-orange), #ff3366); transition: width 0.4s ease; }

.footprint { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 10px; padding-bottom: 32px; }
.platform-card { display: flex; gap: 12px; align-items: flex-start; background: var(--bg-panel); border: 1px solid var(--border-color); padding: 12px 14px; transition: all 0.2s; }
.platform-card:hover { border-color: rgba(var(--accent-rgb),0.4); background: rgba(var(--accent-rgb),0.04); }
.favicon { width: 24px; height: 24px; flex-shrink: 0; margin-top: 2px; }
.pf-info { flex: 1; min-width: 0; }
.pf-head { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.pf-name { color: var(--text-main); font-weight: 600; font-size: 0.92rem; }
.pf-count { background: rgba(var(--accent-rgb),0.2); color: var(--accent-orange); font-size: 0.72rem; font-weight: 700; padding: 0 6px; }
.pf-acc { display: flex; align-items: center; gap: 8px; text-decoration: none; padding: 3px 0; color: var(--text-muted); }
.pf-variant { font-family: 'JetBrains Mono', monospace; font-size: 0.76rem; color: var(--accent-orange); }
.pf-url { font-size: 0.74rem; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; }
.pf-src { font-size: 0.64rem; text-transform: uppercase; letter-spacing: 0.04em; padding: 1px 5px; border: 1px solid var(--border-color); color: var(--text-muted); }
.pf-src.bluesky { color: #3B82F6; border-color: rgba(59,130,246,0.4); }
.pf-acc:hover .pf-url { color: var(--accent-orange); }

.empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; flex: 1; padding: 48px; text-align: center; }
.empty-icon { width: 90px; height: 90px; background: var(--overlay-8); border: 1px dashed var(--border-color); display: flex; align-items: center; justify-content: center; margin-bottom: 20px; color: var(--text-muted); }
.empty-state h3 { font-size: 1.4rem; margin-bottom: 8px; }
.empty-state p { color: var(--text-muted); max-width: 460px; }
</style>
