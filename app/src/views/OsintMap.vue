<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { Search, ExternalLink, X, Globe, MapPin, ChevronRight } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import osintData from '../data/osint_links.json'

const { t } = useI18n()
const mapContainer = ref(null)
const searchQuery = ref('')
const selectedCountry = ref(null)
const isPanelOpen = ref(false)
let map = null
let markers = []
let tiles = null
let observer = null

const countryList = computed(() => {
  const list = Object.entries(osintData).map(([code, data]) => ({
    code,
    ...data
  }))
  if (!searchQuery.value) return list
  const q = searchQuery.value.toLowerCase()
  return list.filter(c =>
    c.name.toLowerCase().includes(q) ||
    c.links.some(l => l.title.toLowerCase().includes(q))
  )
})

const selectedLinks = computed(() => {
  if (!selectedCountry.value) return []
  return selectedCountry.value.links || []
})

function selectCountry(country) {
  selectedCountry.value = country
  isPanelOpen.value = true
  if (map) {
    map.flyTo([country.lat, country.lng], 5, { duration: 1.2 })
  }
}

function closePanel() {
  isPanelOpen.value = false
  selectedCountry.value = null
}

onMounted(async () => {
  const L = await import('leaflet')
  await import('leaflet/dist/leaflet.css')

  map = L.map(mapContainer.value, {
    center: [20, 0],
    zoom: 3,
    minZoom: 2,
    maxZoom: 12,
    zoomControl: false,
    attributionControl: false,
    maxBounds: [[-90, -180], [90, 180]],
    maxBoundsViscosity: 1.0
  })

  // Free, no-API-key basemap (Esri Canvas) that keeps the dark theme.
  // CartoDB's keyless tiles were retired and now return "API key required".
  const tileFor = (light) => light
    ? 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}'
    : 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}'

  const isLight = document.body.classList.contains('light-mode')
  tiles = L.tileLayer(tileFor(isLight), {
    maxZoom: 16,
    noWrap: true,
    bounds: [[-90, -180], [90, 180]]
  }).addTo(map)

  // Swap tiles when light mode is toggled
  observer = new MutationObserver(() => {
    const lightNow = document.body.classList.contains('light-mode')
    tiles.setUrl(tileFor(lightNow))
  })
  observer.observe(document.body, { attributes: true, attributeFilter: ['class'] })

  // Ensure map sizing is correct after layout settles
  nextTick(() => map.invalidateSize())

  L.control.zoom({ position: 'bottomright' }).addTo(map)
  L.control.attribution({ position: 'bottomleft', prefix: false })
    .addAttribution('Tiles &copy; <a href="https://www.esri.com/">Esri</a>')
    .addTo(map)

  // Custom marker icon
  const markerIcon = L.divIcon({
    className: 'osint-marker',
    html: '<div class="marker-dot"></div>',
    iconSize: [14, 14],
    iconAnchor: [7, 7]
  })

  const markerActiveIcon = L.divIcon({
    className: 'osint-marker active',
    html: '<div class="marker-dot"></div>',
    iconSize: [18, 18],
    iconAnchor: [9, 9]
  })

  // Add markers for each country
  Object.entries(osintData).forEach(([code, data]) => {
    const marker = L.marker([data.lat, data.lng], { icon: markerIcon })
    marker.bindTooltip(`<b>${data.name}</b><br>${data.links.length} ${t('osintMap.tools')}`, {
      className: 'osint-tooltip',
      direction: 'top',
      offset: [0, -8]
    })
    marker.on('click', () => {
      selectCountry({ code, ...data })
    })
    marker.addTo(map)
    markers.push({ code, marker, defaultIcon: markerIcon, activeIcon: markerActiveIcon })
  })

  // Watch for selected country to highlight marker
  watch(selectedCountry, (newVal) => {
    markers.forEach(m => {
      m.marker.setIcon(newVal && m.code === newVal.code ? m.activeIcon : m.defaultIcon)
    })
  })
})

onUnmounted(() => {
  if (observer) observer.disconnect()
  if (map) {
    map.remove()
    map = null
  }
})
</script>

<template>
  <div class="osint-map-page">
    <!-- Header -->
    <div class="map-header">
      <div class="header-left">
        <h1 class="page-title">
          <Globe size="28" class="text-orange" />
          {{ t('osintMap.title') }}
        </h1>
        <p class="page-subtitle">
          <span class="stat-badge">{{ Object.keys(osintData).length }} {{ t('osintMap.countries') }}</span>
          <span class="stat-badge accent">{{ Object.values(osintData).reduce((a, c) => a + c.links.length, 0) }} {{ t('osintMap.tools') }}</span>
          {{ t('osintMap.subtitleText') }}
        </p>
      </div>
      <div class="search-box">
        <Search size="16" class="search-icon" />
        <input
          v-model="searchQuery"
          type="text"
          :placeholder="t('osintMap.searchPlaceholder')"
          class="search-input"
        />
      </div>
    </div>

    <!-- Main Layout -->
    <div class="map-layout">
      <!-- Country List Sidebar -->
      <div class="country-sidebar glass-panel">
        <div class="sidebar-header">{{ t('osintMap.sidebarHeader') }}</div>
        <div class="country-list">
          <button
            v-for="country in countryList"
            :key="country.code"
            :class="['country-item', { active: selectedCountry?.code === country.code }]"
            @click="selectCountry(country)"
          >
            <MapPin size="14" class="pin-icon" />
            <span class="country-name">{{ country.name }}</span>
            <span class="link-count">{{ country.links.length }}</span>
          </button>
          <div v-if="countryList.length === 0" class="no-results">
            {{ t('osintMap.noResults') }}
          </div>
        </div>
      </div>

      <!-- Map Container -->
      <div class="map-area">
        <div ref="mapContainer" class="leaflet-map"></div>

        <!-- Slide-in Panel -->
        <transition name="slide">
          <div v-if="isPanelOpen && selectedCountry" class="detail-panel glass-panel">
            <div class="panel-header">
              <div>
                <h2 class="panel-title">{{ selectedCountry.name }}</h2>
                <span class="panel-count">{{ selectedLinks.length }} {{ t('osintMap.resources') }}</span>
              </div>
              <button class="close-btn" @click="closePanel">
                <X size="20" />
              </button>
            </div>
            <div class="panel-links">
              <a
                v-for="(link, idx) in selectedLinks"
                :key="idx"
                :href="link.url"
                target="_blank"
                rel="noopener"
                class="link-card"
              >
                <div class="link-info">
                  <span class="link-title">{{ link.title }}</span>
                  <span class="link-url">{{ link.url.replace('https://', '').replace('http://', '').slice(0, 50) }}{{ link.url.length > 60 ? '...' : '' }}</span>
                </div>
                <ExternalLink size="16" class="link-ext" />
              </a>
            </div>
          </div>
        </transition>
      </div>
    </div>
  </div>
</template>

<style scoped>
.osint-map-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 16px;
  overflow: hidden;
  min-height: 0;
}

/* Header */
.map-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 1.8rem;
  margin: 0;
}

.page-subtitle {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.stat-badge {
  background: var(--overlay-8);
  border: 1px solid var(--border-color);
  padding: 2px 10px;

  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-main);
}

.stat-badge.accent {
  background: rgba(var(--accent-rgb), 0.12);
  border-color: rgba(var(--accent-rgb), 0.3);
  color: var(--accent-orange);
}

.search-box {
  position: relative;
  min-width: 280px;
}

.search-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
}

.search-input {
  width: 100%;
  background: var(--bg-panel);
  border: 1px solid var(--border-color);
  color: var(--text-main);
  padding: 10px 12px 10px 36px;

  font-size: 0.9rem;
  outline: none;
  transition: border-color 0.2s;
}

.search-input:focus {
  border-color: var(--accent-orange);
}

/* Layout */
.map-layout {
  display: flex;
  flex: 1;
  gap: 16px;
  min-height: 0;
}

/* Country Sidebar */
.country-sidebar {
  width: 240px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;

  overflow: hidden;
}

.sidebar-header {
  padding: 12px 16px;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border-color);
}

.country-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.country-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  background: transparent;
  border: 1px solid transparent;

  color: var(--text-muted);
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.15s ease;
  text-align: left;
}

.country-item:hover {
  background: var(--overlay-8);
  color: var(--text-main);
}

.country-item.active {
  background: rgba(var(--accent-rgb), 0.1);
  border-color: rgba(var(--accent-rgb), 0.3);
  color: var(--accent-orange);
}

.pin-icon { flex-shrink: 0; }

.country-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.link-count {
  background: var(--overlay-8);
  padding: 1px 7px;

  font-size: 0.75rem;
  font-weight: 600;
  flex-shrink: 0;
}

.country-item.active .link-count {
  background: rgba(var(--accent-rgb), 0.2);
  color: var(--accent-orange);
}

.no-results {
  padding: 24px 16px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.85rem;
}

/* Map Area */
.map-area {
  flex: 1;
  position: relative;

  overflow: hidden;
  border: 1px solid var(--border-color);
}

.leaflet-map {
  width: 100%;
  height: 100%;
  background: var(--bg-dark);
}

/* Detail Panel */
.detail-panel {
  position: absolute;
  top: 0;
  right: 0;
  width: 380px;
  height: 100%;

  display: flex;
  flex-direction: column;
  z-index: 1000;
  border-left: 1px solid var(--border-color);
  background: var(--bg-panel);
  backdrop-filter: blur(20px);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid var(--border-color);
}

.panel-title {
  margin: 0;
  font-size: 1.3rem;
  color: var(--text-main);
}

.panel-count {
  font-size: 0.8rem;
  color: var(--accent-orange);
  font-weight: 500;
}

.close-btn {
  background: var(--overlay-8);
  border: 1px solid var(--border-color);
  color: var(--text-muted);
  padding: 6px;

  cursor: pointer;
  transition: all 0.2s;
  display: flex;
}

.close-btn:hover {
  background: var(--overlay-10);
  border-color: var(--accent-red);
  color: var(--accent-red);
}

.panel-links {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.link-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;

  background: var(--overlay-8);
  border: 1px solid transparent;
  text-decoration: none;
  transition: all 0.15s ease;
}

.link-card:hover {
  background: rgba(var(--accent-rgb), 0.08);
  border-color: rgba(var(--accent-rgb), 0.2);
}

.link-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.link-title {
  color: var(--text-main);
  font-size: 0.88rem;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.link-url {
  color: var(--text-muted);
  font-size: 0.75rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.link-ext {
  color: var(--text-muted);
  flex-shrink: 0;
}

.link-card:hover .link-ext {
  color: var(--accent-orange);
}

/* Slide transition */
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.3s ease, opacity 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

/* Custom marker styles (global via deep) */
:deep(.osint-marker) {
  background: transparent !important;
  border: none !important;
}

:deep(.osint-marker .marker-dot) {
  width: 12px;
  height: 12px;
  background: var(--accent-orange);

  border: 2px solid rgba(var(--accent-rgb), 0.4);

  transition: all 0.2s ease;
}

:deep(.osint-marker:hover .marker-dot) {
  transform: scale(1.4);

}

:deep(.osint-marker.active .marker-dot) {
  width: 16px;
  height: 16px;
  background: #fff;
  border-color: var(--accent-orange);

}

:deep(.osint-tooltip) {
  background: var(--bg-panel) !important;
  backdrop-filter: blur(10px);
  border: 1px solid var(--border-color) !important;

  color: var(--text-main) !important;
  padding: 8px 12px !important;
  font-size: 0.85rem !important;

}

:deep(.osint-tooltip::before) {
  border-top-color: var(--border-color) !important;
}

:deep(.leaflet-control-zoom) {
  border: 1px solid var(--border-color) !important;

  overflow: hidden;
}

:deep(.leaflet-control-zoom a) {
  background: var(--bg-panel) !important;
  color: var(--text-main) !important;
  border-color: var(--border-color) !important;
}

:deep(.leaflet-control-zoom a:hover) {
  background: rgba(var(--accent-rgb), 0.15) !important;
  color: var(--accent-orange) !important;
}

@media (max-width: 900px) {
  .country-sidebar { display: none; }
  .detail-panel { width: 100%; border-radius: 0; }
}
</style>
