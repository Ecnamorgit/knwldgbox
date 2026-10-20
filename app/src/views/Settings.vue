<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Save, Key, Shield, Phone, Activity, Send, Palette, MonitorPlay, Type, Upload, Sparkles } from 'lucide-vue-next'

import { apiService } from '../services/api'

const { t } = useI18n()

const settings = ref({
  telegram_api_id: '',
  telegram_api_hash: '',
  telegram_phone: '',
  urlscan_api_key: '',
  ai_provider: 'local',
  ollama_url: 'http://localhost:11434',
  ollama_model: 'qwen2.5:7b',
  openrouter_api_key: '',
  openrouter_model: 'google/gemini-2.0-flash-exp:free',
  openrouter_system_prompt: 'You are a professional, objective intelligence analyst. Provide concise, accurate, and professional answers.'
})

const ollamaModels = ref([])

async function loadOllamaModels() {
  try {
    const host = window.location.hostname
    const port = import.meta.env.VITE_API_PORT || 8000
    const res = await fetch(`http://${host}:${port}/api/ollama/models`)
    const json = await res.json()
    if (json && json.status === 'success') {
      ollamaModels.value = json.models
    }
  } catch (error) {
    console.error("Failed to load Ollama models", error)
  }
}

const openRouterModels = ref([
  { name: 'Gemini 2.0 Flash (Free)', value: 'google/gemini-2.0-flash-exp:free' },
  { name: 'Mistral 7B Instruct (Free)', value: 'mistralai/mistral-7b-instruct:free' },
  { name: 'Llama 3 8B Instruct (Free)', value: 'meta-llama/llama-3-8b-instruct:free' },
  { name: 'Nvidia Nemotron 3 Super 120B (Free)', value: 'nvidia/nemotron-3-super-120b-a12b:free' },
  { name: 'Nvidia Nemotron 3 Ultra 550B (Free)', value: 'nvidia/nemotron-3-ultra-550b-a55b:free' },
  { name: 'Claude 3 Haiku (Paid)', value: 'anthropic/claude-3-haiku' },
  { name: 'GPT-3.5 Turbo (Paid)', value: 'openai/gpt-3.5-turbo' }
])

async function loadOpenRouterModels() {
  try {
    const res = await fetch('https://openrouter.ai/api/v1/models')
    const json = await res.json()
    if (json && json.data) {
      const freeModels = json.data.filter(m => m.pricing && m.pricing.prompt === "0" && m.pricing.completion === "0")
      const dynamicModels = freeModels.map(m => ({
        name: `${m.name}`,
        value: m.id
      }))
      
      // Keep existing paid models, and any models not in the fetched list
      const existingValues = new Set(dynamicModels.map(m => m.value))
      const combined = [
        ...dynamicModels.sort((a, b) => a.name.localeCompare(b.name)),
        ...openRouterModels.value.filter(m => !existingValues.has(m.value))
      ]
      
      openRouterModels.value = combined
    }
  } catch (error) {
    console.error("Failed to load OpenRouter models", error)
  }
}

const customization = ref({
  appTheme: 'theme-brutalist',
  accentColor: 'default',
  defaultView: '/',
  fontFamily: 'JetBrains Mono',
  customFontData: null,
  customFontName: ''
})

const appThemes = computed(() => [
  { name: t('settings.themeBrutalist'), value: 'theme-brutalist' },
  { name: t('settings.themeEnterprise'), value: 'theme-enterprise' },
  { name: t('settings.themeCyber'), value: 'theme-cyber' }
])

const availableFonts = [
  { name: 'JetBrains Mono', value: 'JetBrains Mono' },
  { name: 'Inter', value: 'Inter' },
  { name: 'Roboto', value: 'Roboto' },
  { name: 'Fira Code', value: 'Fira Code' },
  { name: 'Courier New', value: 'Courier New' },
  { name: 'Upload Custom Font...', value: 'custom' }
]

const accentColors = computed(() => [
  { name: t('settings.themeDefault'), value: 'default', rgb: '' },
  { name: 'Orange', value: '#FF7700', rgb: '255, 119, 0' },
  { name: 'Purple', value: '#B026FF', rgb: '176, 38, 255' },
  { name: 'Green', value: '#00FF88', rgb: '0, 255, 136' },
  { name: 'Blue', value: '#3B82F6', rgb: '59, 130, 246' },
  { name: 'Red', value: '#FF003C', rgb: '255, 0, 60' }
])

const availableViews = computed(() => [
  { name: t('settings.views.dashboard'), path: '/' },
  { name: t('settings.views.monitoring'), path: '/monitoring' },
  { name: t('settings.views.targetAnalysis'), path: '/target' },
  { name: t('settings.views.networkGraph'), path: '/network' },
  { name: t('settings.views.socialForensics'), path: '/social' },
  { name: t('settings.views.dataLeaks'), path: '/leaks' },
  { name: t('settings.views.knwldgTools'), path: '/tools' },
  { name: t('settings.views.archives'), path: '/archives' },
  { name: t('settings.views.osintMap'), path: '/osint-map' }
])

const isSaved = ref(false)
const needsAuth = ref(false)
const authCode = ref('')
const authError = ref('')

onMounted(() => {
  const savedSettings = localStorage.getItem('knwldg_api_settings')
  if (savedSettings) {
    settings.value = { ...settings.value, ...JSON.parse(savedSettings) }
  }

  const savedCustom = localStorage.getItem('knwldg_app_customization')
  if (savedCustom) {
    customization.value = { ...customization.value, ...JSON.parse(savedCustom) }
  }
  
  loadOpenRouterModels()
  loadOllamaModels()
})

function applyCustomization() {
  const prefs = customization.value
  
  if (prefs.appTheme) {
    document.body.classList.remove('theme-brutalist', 'theme-enterprise', 'theme-cyber')
    document.body.classList.add(prefs.appTheme)
  }

  if (prefs.accentColor === 'default') {
    document.body.style.removeProperty('--accent-orange')
    document.body.style.removeProperty('--accent-rgb')
  } else {
    document.body.style.setProperty('--accent-orange', prefs.accentColor)
    const colorObj = accentColors.value.find(c => c.value === prefs.accentColor)
    if (colorObj) {
      document.body.style.setProperty('--accent-rgb', colorObj.rgb)
    }
  }

  if (prefs.fontFamily) {
    if (prefs.fontFamily === 'custom' && prefs.customFontData) {
      let style = document.getElementById('custom-font-style')
      if (!style) {
        style = document.createElement('style')
        style.id = 'custom-font-style'
        document.head.appendChild(style)
      }
      style.innerHTML = `
        @font-face {
          font-family: 'UserCustomFont';
          src: url('${prefs.customFontData}');
        }
      `
      document.body.style.fontFamily = "'UserCustomFont', monospace"
    } else {
      const style = document.getElementById('custom-font-style')
      if (style) style.remove()
      document.body.style.fontFamily = `"${prefs.fontFamily}", monospace`
    }
  }
}

function handleFontUpload(event) {
  const file = event.target.files[0]
  if (!file) return
  
  customization.value.customFontName = file.name
  
  const reader = new FileReader()
  reader.onload = (e) => {
    customization.value.customFontData = e.target.result
    applyCustomization()
  }
  reader.readAsDataURL(file)
}

// Live preview customization
watch(customization, () => {
  applyCustomization()
}, { deep: true })

async function saveSettings() {
  localStorage.setItem('knwldg_api_settings', JSON.stringify(settings.value))
  localStorage.setItem('knwldg_app_customization', JSON.stringify(customization.value))
  applyCustomization()

  try {
    const data = await apiService.saveSettings(settings.value)

    if (data.status === 'needs_auth') {
      needsAuth.value = true
      await apiService.requestTelegramCode()
      return
    }
  } catch (e) {
    console.error("Failed to push settings to backend", e)
  }

  isSaved.value = true
  setTimeout(() => { isSaved.value = false }, 3000)
}

async function verifyCode() {
  authError.value = ''
  try {
    await apiService.verifyTelegramCode(authCode.value)
    needsAuth.value = false
    isSaved.value = true
    setTimeout(() => { isSaved.value = false }, 3000)
  } catch (e) {
    authError.value = e.message || 'Failed to verify code'
  }
}
</script>

<template>
  <div class="settings-page">
    <div class="header-section">
      <h1 class="page-title">{{ t('settings.title') }}</h1>
      <p class="page-subtitle">{{ t('settings.subtitle') }}</p>
    </div>

    <!-- Auth Code Modal/Overlay -->
    <div class="auth-overlay" v-if="needsAuth">
      <div class="auth-modal glass-panel">
        <h3>{{ t('settings.telegramAuthTitle') }}</h3>
        <p>{{ t('settings.telegramAuthMessage') }}</p>
        <div class="form-group">
          <input type="text" v-model="authCode" :placeholder="t('settings.codePlaceholder')" class="code-input" />
          <span class="text-error" v-if="authError">{{ authError }}</span>
        </div>
        <div class="auth-actions">
          <button class="btn-cancel" @click="needsAuth = false">{{ t('common.cancel') }}</button>
          <button class="btn-primary" @click="verifyCode">
            <Send size="16" /> {{ t('settings.verifyCode') }}
          </button>
        </div>
      </div>
    </div>

    <div class="settings-grid">
      <!-- Telegram Settings -->
      <div class="settings-panel glass-panel">
        <div class="panel-header">
          <div class="header-title">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-orange"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>
            <h2>{{ t('settings.telegramPanelTitle') }}</h2>
          </div>
          <p class="panel-desc">{{ t('settings.telegramPanelDesc') }}</p>
        </div>

        <div class="form-group">
          <label>{{ t('settings.apiId') }}</label>
          <div class="input-wrapper">
            <Key size="16" class="input-icon" />
            <input type="text" v-model="settings.telegram_api_id" :placeholder="t('settings.apiIdPlaceholder')" />
          </div>
        </div>

        <div class="form-group">
          <label>{{ t('settings.apiHash') }}</label>
          <div class="input-wrapper">
            <Shield size="16" class="input-icon" />
            <input type="password" v-model="settings.telegram_api_hash" :placeholder="t('settings.apiHashPlaceholder')" />
          </div>
        </div>

        <div class="form-group">
          <label>{{ t('settings.phoneNumber') }}</label>
          <div class="input-wrapper">
            <Phone size="16" class="input-icon" />
            <input type="text" v-model="settings.telegram_phone" :placeholder="t('settings.phonePlaceholder')" />
          </div>
        </div>
      </div>

      <!-- OSINT APIs -->
      <div class="settings-panel glass-panel">
        <div class="panel-header">
          <div class="header-title">
            <Activity size="20" class="text-purple" />
            <h2>{{ t('settings.osintPanelTitle') }}</h2>
          </div>
          <p class="panel-desc">{{ t('settings.osintPanelDesc') }}</p>
        </div>


        <div class="form-group">
          <label>{{ t('settings.urlscanKey') }}</label>
          <div class="input-wrapper">
            <Key size="16" class="input-icon" />
            <input type="password" v-model="settings.urlscan_api_key" :placeholder="t('settings.urlscanKey')" />
          </div>
        </div>

        <div class="form-group">
          <label>AI Provider</label>
          <div class="input-wrapper">
            <Sparkles size="16" class="input-icon" />
            <select v-model="settings.ai_provider" class="select-input">
              <option value="local">Local (Ollama) — free, offline</option>
              <option value="openrouter">OpenRouter (API key)</option>
            </select>
          </div>
        </div>

        <!-- Local Ollama provider -->
        <template v-if="settings.ai_provider === 'local'">
          <div class="form-group">
            <label>Local Model (Ollama)</label>
            <div class="input-wrapper">
              <Activity size="16" class="input-icon" />
              <select v-model="settings.ollama_model" class="select-input">
                <option v-for="m in ollamaModels" :key="m" :value="m">{{ m }}</option>
                <option v-if="settings.ollama_model && !ollamaModels.includes(settings.ollama_model)" :value="settings.ollama_model">{{ settings.ollama_model }}</option>
              </select>
            </div>
          </div>

          <div class="form-group">
            <label>Ollama URL</label>
            <div class="input-wrapper">
              <Key size="16" class="input-icon" />
              <input type="text" v-model="settings.ollama_url" placeholder="http://localhost:11434" />
            </div>
          </div>
        </template>

        <!-- OpenRouter provider -->
        <template v-else>
          <div class="form-group">
            <label>{{ t('settings.openRouterKey') }}</label>
            <div class="input-wrapper">
              <Sparkles size="16" class="input-icon" />
              <input type="password" v-model="settings.openrouter_api_key" placeholder="sk-or-v1-..." />
            </div>
          </div>

          <div class="form-group">
            <label>{{ t('settings.aiModel') }}</label>
            <div class="input-wrapper">
              <Activity size="16" class="input-icon" />
              <select v-model="settings.openrouter_model" class="select-input">
                <option v-for="model in openRouterModels" :key="model.value" :value="model.value">
                  {{ model.name }}
                </option>
              </select>
            </div>
          </div>
        </template>

        <div class="form-group" style="margin-top: 12px;">
          <label>AI System Prompt</label>
          <textarea 
            v-model="settings.openrouter_system_prompt" 
            class="input-field" 
            style="min-height: 80px; resize: vertical;"
          ></textarea>
        </div>
      </div>

      <!-- Personalization Settings -->
      <div class="settings-panel glass-panel">
        <div class="panel-header">
          <div class="header-title">
            <Palette size="20" class="text-green" />
            <h2>{{ t('settings.customizationTitle') }}</h2>
          </div>
          <p class="panel-desc">{{ t('settings.customizationDesc') }}</p>
        </div>

        <div class="form-group" style="margin-bottom: 12px;">
          <label>{{ t('settings.appTheme') }}</label>
          <div class="input-wrapper">
            <Palette size="16" class="input-icon" />
            <select v-model="customization.appTheme" class="select-input">
              <option v-for="theme in appThemes" :key="theme.value" :value="theme.value">
                {{ theme.name }}
              </option>
            </select>
          </div>
        </div>

        <div class="form-group">
          <label>{{ t('settings.accentColor') }}</label>
          <div class="color-options">
            <button
              v-for="color in accentColors"
              :key="color.value"
              class="color-btn"
              :class="{ active: customization.accentColor === color.value }"
              :style="{ backgroundColor: color.value }"
              @click="customization.accentColor = color.value"
              :title="color.name"
            ></button>
          </div>
        </div>

        <div class="form-group">
          <label>{{ t('settings.defaultView') }}</label>
          <div class="input-wrapper">
            <MonitorPlay size="16" class="input-icon" />
            <select v-model="customization.defaultView" class="select-input">
              <option v-for="view in availableViews" :key="view.path" :value="view.path">
                {{ view.name }}
              </option>
            </select>
          </div>
        </div>


        <div class="form-group" style="margin-top: 12px;">
          <label>{{ t('settings.typography') }}</label>
          <div class="input-wrapper">
            <Type size="16" class="input-icon" />
            <select v-model="customization.fontFamily" class="select-input">
              <option v-for="font in availableFonts" :key="font.value" :value="font.value">
                {{ font.name }}
              </option>
            </select>
          </div>
          <div v-if="customization.fontFamily === 'custom'" class="custom-font-upload mt-2" style="margin-top: 8px;">
            <input type="file" accept=".ttf,.woff,.woff2,.otf" @change="handleFontUpload" ref="fontInput" style="display: none" />
            <button class="btn-secondary" style="width: 100%; justify-content: center;" @click="$refs.fontInput.click()">
               <Upload size="14" /> {{ customization.customFontName ? t('settings.changeCustomFont') : t('settings.uploadFont') }}
            </button>
            <div class="text-xs text-green mt-1" v-if="customization.customFontName" style="margin-top: 4px; font-size: 0.8rem;">
              {{ t('settings.activeFont') }} {{ customization.customFontName }}
            </div>
          </div>
        </div>

      </div>
    </div>

    <!-- Actions -->
    <div class="actions-section">
      <div class="save-status" v-if="isSaved">
        {{ t('settings.savedStatus') }}
      </div>
      <button class="btn-save" @click="saveSettings">
        <Save size="18" />
        {{ t('settings.saveConfiguration') }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  flex: 1;
  overflow-y: auto;
  padding-right: 8px;
  display: flex;
  flex-direction: column;
  position: relative;
}

.header-section { margin-bottom: 32px; }
.page-title { font-size: 2rem; margin-bottom: 8px; }
.page-subtitle { color: var(--text-muted); font-size: 0.95rem; }

.settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 24px;
  margin-bottom: 32px;
}

.settings-panel {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.panel-header {
  margin-bottom: 8px;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 16px;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.header-title h2 { font-size: 1.1rem; font-weight: 500; margin: 0; }
.panel-desc { font-size: 0.85rem; color: var(--text-muted); }

.form-group { display: flex; flex-direction: column; gap: 8px; }
.form-group label { font-size: 0.85rem; font-weight: 500; color: var(--text-muted); }

.input-wrapper { position: relative; display: flex; align-items: center; }
.input-icon { position: absolute; left: 12px; color: var(--text-muted); }

.input-wrapper input {
  width: 100%;
  background: var(--bg-panel);
  border: 1px solid var(--border-color);
  padding: 10px 12px 10px 40px;

  color: var(--text-main);
  font-size: 0.9rem;
  transition: var(--transition);
}

.input-wrapper input:focus,
.select-input:focus {
  border-color: var(--accent-orange);
  outline: none;

}

.select-input {
  width: 100%;
  background: var(--bg-panel);
  border: 1px solid var(--border-color);
  padding: 10px 12px 10px 40px;

  color: var(--text-main);
  font-size: 0.9rem;
  transition: var(--transition);
  appearance: none;
  cursor: pointer;
}

.select-input option {
  background: var(--bg-dark);
  color: var(--text-main);
}

.color-options {
  display: flex;
  gap: 12px;
  margin-top: 4px;
}

.color-btn {
  width: 32px;
  height: 32px;

  border: 2px solid transparent;
  cursor: pointer;
  transition: var(--transition);
  opacity: 0.7;
}

.color-btn:hover {
  opacity: 0.9;
  transform: scale(1.1);
}

.color-btn.active {
  opacity: 1;
  border-color: var(--text-main);
  transform: scale(1.15);

}



.actions-section {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 16px;
  padding: 24px;
  background: var(--overlay-8);

  border: 1px solid var(--border-color);
}

.save-status {
  color: var(--accent-green);
  font-size: 0.9rem;
  font-weight: 500;
}

.btn-save {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--accent-orange);
  color: var(--bg-dark);
  padding: 10px 24px;

  font-weight: 600;
  font-size: 0.95rem;
  transition: var(--transition);
}

.btn-save:hover {
  filter: brightness(1.15);
  transform: translateY(-1px);

}

/* Auth Modal Styles */
.auth-overlay {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.auth-modal {
  padding: 32px;
  max-width: 400px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  text-align: center;
}

.auth-modal h3 {
  font-size: 1.2rem;
  color: var(--accent-orange);
  margin-bottom: 8px;
}

.auth-modal p {
  font-size: 0.9rem;
  color: var(--text-muted);
  line-height: 1.4;
}

.code-input {
  background: var(--bg-panel);
  border: 1px solid var(--border-color);
  padding: 12px;

  color: var(--text-main);
  font-size: 1.1rem;
  text-align: center;
  letter-spacing: 2px;
}

.code-input:focus {
  border-color: var(--accent-orange);
  outline: none;
}

.text-error { color: var(--accent-red); font-size: 0.85rem; margin-top: 4px; }

.auth-actions {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}

.btn-cancel {
  flex: 1;
  padding: 10px;
  background: transparent;
  border: 1px solid var(--border-color);
  color: var(--text-main);

  cursor: pointer;
}

.btn-primary {
  flex: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: var(--accent-orange);
  color: #000;
  border: none;

  font-weight: 600;
  cursor: pointer;
}

.btn-secondary {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--overlay-8);
  color: var(--text-main);
  border: 1px dashed var(--border-color);
  padding: 8px 16px;

  font-size: 0.85rem;
  cursor: pointer;
  transition: var(--transition);
}

.btn-secondary:hover {
  background: var(--overlay-10);
  border-color: var(--border-color);
}

.text-green { color: var(--accent-green); }
</style>
