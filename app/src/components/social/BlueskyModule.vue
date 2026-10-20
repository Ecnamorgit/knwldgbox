<script setup>
import { ref } from 'vue'
import { Search, Loader2, ExternalLink, AtSign, Mail, Link2, Calendar, Users, MessageSquare, Repeat2, Heart } from 'lucide-vue-next'
import SendToGraphButton from '../SendToGraphButton.vue'

const query = ref('')
const isLoading = ref(false)
const error = ref('')
const result = ref(null)

const API = `http://${window.location.hostname}:${import.meta.env.VITE_API_PORT || 8000}/api/bluesky/lookup`

async function lookup(term) {
  const q = (term ?? query.value).trim()
  if (!q || isLoading.value) return
  query.value = q
  isLoading.value = true
  error.value = ''
  result.value = null
  try {
    const res = await fetch(`${API}?q=${encodeURIComponent(q)}`)
    const data = await res.json()
    if (!res.ok) { error.value = data.detail || 'Lookup failed'; return }
    result.value = data
  } catch (e) {
    error.value = e.message
  } finally {
    isLoading.value = false
  }
}

function openActor(handle) {
  lookup(handle)
}

function fmtDate(s) {
  if (!s) return ''
  try { return new Date(s).toLocaleDateString() } catch { return s.slice(0, 10) }
}

const intelHasAny = (i) => i && (i.emails.length || i.urls.length || i.mentions.length || i.dates.length || i.ages.length)
</script>

<template>
  <div class="bsky-module">
    <!-- Search -->
    <div class="search-panel glass-panel">
      <div class="input-wrapper">
        <AtSign class="icon-lead" size="20" />
        <input
          v-model="query"
          type="text"
          placeholder="Handle (ex: lefevremelanie) or a name to search…"
          @keyup.enter="lookup()"
          :disabled="isLoading"
        />
        <button class="btn-search" @click="lookup()" v-if="!isLoading">
          <Search size="18" /> Investigate
        </button>
        <button class="btn-search loading" disabled v-else>
          <Loader2 size="18" class="spin" /> Scanning…
        </button>
      </div>
    </div>

    <div class="error-box" v-if="error">{{ error }}</div>

    <!-- SEARCH MODE: actor list -->
    <div v-if="result && result.mode === 'search'">
      <div class="section-label">{{ result.actors.length }} profiles found — click one to investigate</div>
      <div v-if="result.actors.length === 0" class="empty-hint">No Bluesky account matched.</div>
      <div class="actor-grid">
        <button class="actor-card" v-for="a in result.actors" :key="a.handle" @click="openActor(a.handle)">
          <img v-if="a.avatar" :src="a.avatar" class="avatar-sm" alt="" @error="$event.target.style.display='none'" />
          <div class="actor-info">
            <span class="actor-name">{{ a.displayName || a.handle }}</span>
            <span class="actor-handle">@{{ a.handle }}</span>
            <span class="actor-desc" v-if="a.description">{{ a.description }}</span>
          </div>
        </button>
      </div>
    </div>

    <!-- PROFILE MODE: dossier -->
    <div v-else-if="result && result.mode === 'profile'" class="dossier">
      <!-- Header -->
      <div class="profile-header glass-panel">
        <img v-if="result.profile.avatar" :src="result.profile.avatar" class="avatar-lg" alt="" @error="$event.target.style.display='none'" />
        <div class="profile-meta">
          <h2>{{ result.profile.displayName || result.profile.handle }}</h2>
          <a :href="`https://bsky.app/profile/${result.profile.handle}`" target="_blank" class="profile-handle">
            @{{ result.profile.handle }} <ExternalLink size="12" />
          </a>
          <p class="profile-bio" v-if="result.profile.description">{{ result.profile.description }}</p>
          <div class="profile-stats">
            <span><b>{{ result.profile.postsCount }}</b> posts</span>
            <span><b>{{ result.profile.followersCount }}</b> followers</span>
            <span><b>{{ result.profile.followsCount }}</b> following</span>
            <span class="created"><Calendar size="13" /> {{ fmtDate(result.profile.createdAt) }}</span>
          </div>
        </div>
        <SendToGraphButton
          :label="result.profile.handle"
          iconName="Globe"
          color="#3B82F6"
          :notes="`Bluesky: ${result.profile.description || ''}`"
        />
      </div>

      <!-- Extracted intel -->
      <div class="intel-panel glass-panel" v-if="intelHasAny(result.intel)">
        <div class="intel-title">🔎 Extracted intel</div>
        <div class="intel-row" v-if="result.intel.emails.length">
          <Mail size="14" /><span class="intel-k">Emails</span>
          <span class="chip email" v-for="x in result.intel.emails" :key="x">{{ x }}</span>
        </div>
        <div class="intel-row" v-if="result.intel.dates.length || result.intel.ages.length">
          <Calendar size="14" /><span class="intel-k">Dates / ages</span>
          <span class="chip date" v-for="x in result.intel.dates" :key="x">{{ x }}</span>
          <span class="chip date" v-for="x in result.intel.ages" :key="x">{{ x }}</span>
        </div>
        <div class="intel-row" v-if="result.intel.mentions.length">
          <AtSign size="14" /><span class="intel-k">Mentions</span>
          <span class="chip" v-for="x in result.intel.mentions" :key="x">{{ x }}</span>
        </div>
        <div class="intel-row" v-if="result.intel.urls.length">
          <Link2 size="14" /><span class="intel-k">Links</span>
          <a class="chip link" v-for="x in result.intel.urls" :key="x" :href="x" target="_blank" rel="noopener">{{ x.replace(/^https?:\/\//,'').slice(0,46) }}</a>
        </div>
      </div>

      <!-- Posts -->
      <div class="section-label" v-if="result.posts.length">Posts ({{ result.posts.length }})</div>
      <div class="post-card" v-for="(p, i) in result.posts" :key="i">
        <div class="post-head">
          <span class="post-date">{{ fmtDate(p.createdAt) }}</span>
          <a v-if="p.url" :href="p.url" target="_blank" class="post-link"><ExternalLink size="12" /></a>
        </div>
        <div class="post-text">{{ p.text }}</div>
        <a v-for="l in p.links" :key="l" :href="l" target="_blank" class="post-embed-link"><Link2 size="12" /> {{ l.replace(/^https?:\/\//,'').slice(0,60) }}</a>
        <div class="post-stats">
          <span><Heart size="12" /> {{ p.likes }}</span>
          <span><Repeat2 size="12" /> {{ p.reposts }}</span>
          <span><MessageSquare size="12" /> {{ p.replies }}</span>
        </div>
      </div>

      <!-- Graph: follows / followers -->
      <div class="graph-cols">
        <div class="graph-col">
          <div class="section-label"><Users size="14" /> Following ({{ result.follows.length }})</div>
          <button class="mini-actor" v-for="a in result.follows" :key="a.handle" @click="openActor(a.handle)">
            <img v-if="a.avatar" :src="a.avatar" class="avatar-xs" alt="" @error="$event.target.style.display='none'" />
            <span class="mini-name">{{ a.displayName || a.handle }}</span>
            <span class="mini-handle">@{{ a.handle }}</span>
          </button>
          <div v-if="result.follows.length === 0" class="empty-hint">—</div>
        </div>
        <div class="graph-col">
          <div class="section-label"><Users size="14" /> Followers ({{ result.followers.length }})</div>
          <button class="mini-actor" v-for="a in result.followers" :key="a.handle" @click="openActor(a.handle)">
            <img v-if="a.avatar" :src="a.avatar" class="avatar-xs" alt="" @error="$event.target.style.display='none'" />
            <span class="mini-name">{{ a.displayName || a.handle }}</span>
            <span class="mini-handle">@{{ a.handle }}</span>
          </button>
          <div v-if="result.followers.length === 0" class="empty-hint">—</div>
        </div>
      </div>
    </div>

    <!-- Empty -->
    <div class="empty-state" v-else-if="!isLoading && !error">
      <div class="empty-icon"><AtSign size="42" /></div>
      <h3>Bluesky OSINT</h3>
      <p>Bluesky is fully public (AT Protocol, no login). Enter a handle to pull the full profile, posts, follows &amp; followers — with emails, links, dates and mentions auto-extracted.</p>
    </div>
  </div>
</template>

<style scoped>
.bsky-module { display: flex; flex-direction: column; flex: 1; }

.search-panel { padding: 16px; margin-bottom: 20px; }
.input-wrapper { display: flex; align-items: center; background: var(--bg-panel); border: 1px solid var(--border-color); padding: 4px; position: relative; }
.icon-lead { position: absolute; left: 16px; color: var(--text-muted); }
.input-wrapper input { flex: 1; background: transparent; border: none; color: var(--text-main); padding: 14px 16px 14px 48px; font-size: 1.1rem; outline: none; }
.btn-search { display: flex; align-items: center; gap: 8px; background: var(--accent-orange); color: #000; border: none; padding: 12px 24px; font-weight: 600; cursor: pointer; transition: var(--transition); }
.btn-search:hover:not(:disabled) { filter: brightness(1.15); }
.btn-search.loading { background: var(--overlay-10); color: var(--text-muted); cursor: default; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { 100% { transform: rotate(360deg); } }

.error-box { background: rgba(239,68,68,0.12); border: 1px solid rgba(239,68,68,0.35); color: var(--accent-red); padding: 12px 16px; margin-bottom: 16px; font-size: 0.9rem; }

.section-label { display: flex; align-items: center; gap: 6px; font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); margin: 18px 0 10px; }
.empty-hint { color: var(--text-muted); font-size: 0.85rem; padding: 6px 2px; }

/* actor search grid */
.actor-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px; }
.actor-card { display: flex; gap: 12px; align-items: flex-start; text-align: left; background: var(--bg-panel); border: 1px solid var(--border-color); padding: 12px; cursor: pointer; transition: var(--transition); }
.actor-card:hover { border-color: rgba(var(--accent-rgb),0.4); background: rgba(var(--accent-rgb),0.04); }
.avatar-sm { width: 42px; height: 42px; border-radius: 50%; flex-shrink: 0; object-fit: cover; }
.actor-info { display: flex; flex-direction: column; min-width: 0; }
.actor-name { color: var(--text-main); font-weight: 600; font-size: 0.92rem; }
.actor-handle { color: var(--accent-orange); font-size: 0.78rem; }
.actor-desc { color: var(--text-muted); font-size: 0.78rem; margin-top: 4px; }

/* dossier */
.profile-header { display: flex; gap: 18px; align-items: flex-start; padding: 20px; margin-bottom: 16px; }
.avatar-lg { width: 80px; height: 80px; border-radius: 50%; object-fit: cover; flex-shrink: 0; border: 2px solid var(--border-color); }
.profile-meta { flex: 1; min-width: 0; }
.profile-meta h2 { margin: 0 0 2px; font-size: 1.4rem; }
.profile-handle { display: inline-flex; align-items: center; gap: 4px; color: var(--accent-orange); text-decoration: none; font-size: 0.85rem; }
.profile-bio { color: var(--text-main); font-size: 0.9rem; margin: 10px 0; line-height: 1.4; }
.profile-stats { display: flex; flex-wrap: wrap; gap: 16px; color: var(--text-muted); font-size: 0.82rem; }
.profile-stats b { color: var(--text-main); }
.profile-stats .created { display: inline-flex; align-items: center; gap: 4px; }

/* intel */
.intel-panel { padding: 16px; margin-bottom: 18px; display: flex; flex-direction: column; gap: 10px; }
.intel-title { font-size: 0.85rem; font-weight: 700; color: var(--accent-orange); }
.intel-row { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; color: var(--text-muted); }
.intel-k { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; margin-right: 4px; min-width: 76px; }
.chip { background: var(--overlay-8); border: 1px solid var(--border-color); padding: 2px 8px; font-size: 0.78rem; color: var(--text-main); text-decoration: none; }
.chip.email { color: var(--accent-green); border-color: rgba(0,255,136,0.3); }
.chip.date { color: var(--accent-orange); border-color: rgba(var(--accent-rgb),0.3); }
.chip.link:hover { border-color: var(--accent-orange); color: var(--accent-orange); }

/* posts */
.post-card { background: var(--bg-panel); border: 1px solid var(--border-color); padding: 12px 14px; margin-bottom: 8px; }
.post-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.post-date { color: var(--text-muted); font-size: 0.75rem; }
.post-link { color: var(--text-muted); }
.post-text { color: var(--text-main); font-size: 0.9rem; line-height: 1.45; white-space: pre-wrap; }
.post-embed-link { display: inline-flex; align-items: center; gap: 4px; margin-top: 8px; color: var(--accent-orange); font-size: 0.78rem; text-decoration: none; }
.post-stats { display: flex; gap: 16px; margin-top: 8px; color: var(--text-muted); font-size: 0.75rem; }
.post-stats span { display: inline-flex; align-items: center; gap: 4px; }

/* graph */
.graph-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 8px; }
.mini-actor { display: flex; align-items: center; gap: 8px; width: 100%; text-align: left; background: var(--bg-panel); border: 1px solid var(--border-color); padding: 8px 10px; margin-bottom: 6px; cursor: pointer; transition: var(--transition); }
.mini-actor:hover { border-color: rgba(var(--accent-rgb),0.4); }
.avatar-xs { width: 26px; height: 26px; border-radius: 50%; object-fit: cover; flex-shrink: 0; }
.mini-name { color: var(--text-main); font-size: 0.82rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.mini-handle { color: var(--text-muted); font-size: 0.72rem; margin-left: auto; white-space: nowrap; }

/* empty */
.empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; flex: 1; padding: 48px; text-align: center; }
.empty-icon { width: 90px; height: 90px; background: var(--overlay-8); border: 1px dashed var(--border-color); display: flex; align-items: center; justify-content: center; margin-bottom: 20px; color: var(--text-muted); }
.empty-state h3 { font-size: 1.4rem; margin-bottom: 8px; }
.empty-state p { color: var(--text-muted); max-width: 440px; }

@media (max-width: 768px) {
  .graph-cols { grid-template-columns: 1fr; }
}
</style>
