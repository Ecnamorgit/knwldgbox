# Use the OS certificate store so HTTPS works behind antivirus/VPN TLS
# inspection (e.g. Avast Web Shield), which GHunt's Google API calls hit.
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from dotenv import load_dotenv
import feedparser
from config import ENV_FILE, ARCHIVES_DIR
from fastapi.staticfiles import StaticFiles
import os
import json
import base64
import httpx
import time
import re
from datetime import date

try:
    from geotext import GeoText
    from geopy.geocoders import Nominatim
    geolocator = Nominatim(user_agent="knwldgbox-osint")
except ImportError:
    GeoText = None
    geolocator = None

geo_cache = {}


try:
    with open(os.path.join(os.path.dirname(__file__), "fr_en_countries.json"), "r", encoding="utf-8") as _f:
        FR_EN_DICT = json.load(_f)
except Exception:
    FR_EN_DICT = {}

from telegram_service import telegram_service
from sherlock_service import sherlock_service
from recon_service import recon_service
import dataleak_service
import graph_service
import whois_service
import collage_service
import tiktok_service
import ghunt_service
import holehe_service
import maigret_service
import bluesky_service
import downloader_service
import archive_service
import target_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv(dotenv_path=ENV_FILE, override=True)
    await telegram_service.initialize()
    yield
    await telegram_service.disconnect()


app = FastAPI(title="KNWLDG OSINT Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:8001",
        "http://localhost:8001",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dataleak_service.router)
app.include_router(graph_service.router)
app.include_router(whois_service.router)
app.include_router(collage_service.router)
app.include_router(tiktok_service.router)
app.include_router(ghunt_service.router)
app.include_router(holehe_service.router)
app.include_router(maigret_service.router)
app.include_router(bluesky_service.router)
app.include_router(downloader_service.router)
app.include_router(archive_service.router)
app.include_router(target_service.router)

app.mount("/archives", StaticFiles(directory=str(ARCHIVES_DIR)), name="archives")


class SettingsPayload(BaseModel):
    telegram_api_id: str | None = None
    telegram_api_hash: str | None = None
    telegram_phone: str | None = None
    urlscan_api_key: str | None = None
    openrouter_api_key: str | None = None
    openrouter_model: str | None = None
    openrouter_system_prompt: str | None = None
    ai_provider: str | None = None
    ollama_url: str | None = None
    ollama_model: str | None = None

class AuthCodePayload(BaseModel):
    code: str

@app.post("/api/settings")
async def save_settings(payload: SettingsPayload):
    env_content = ""
    if payload.telegram_api_id:
        env_content += f"TG_API_ID={payload.telegram_api_id}\n"
    if payload.telegram_api_hash:
        env_content += f"TG_API_HASH={payload.telegram_api_hash}\n"
    if payload.telegram_phone:
        env_content += f"TG_PHONE={payload.telegram_phone}\n"
    if payload.urlscan_api_key:
        env_content += f"URLSCAN_API_KEY={payload.urlscan_api_key}\n"
    if payload.openrouter_api_key:
        env_content += f"OPENROUTER_API_KEY={payload.openrouter_api_key}\n"
    if payload.openrouter_model:
        env_content += f"OPENROUTER_MODEL={payload.openrouter_model}\n"
    if payload.openrouter_system_prompt is not None:
        encoded = base64.b64encode(payload.openrouter_system_prompt.encode('utf-8')).decode('utf-8')
        env_content += f"OPENROUTER_SYSTEM_PROMPT={encoded}\n"
    if payload.ai_provider:
        env_content += f"AI_PROVIDER={payload.ai_provider}\n"
    if payload.ollama_url:
        env_content += f"OLLAMA_URL={payload.ollama_url}\n"
    if payload.ollama_model:
        env_content += f"OLLAMA_MODEL={payload.ollama_model}\n"

    with open(ENV_FILE, "w") as f:
        f.write(env_content)
        
    
    load_dotenv(dotenv_path=ENV_FILE, override=True)
    return await telegram_service.initialize()

@app.post("/api/telegram/auth/send_code")
async def send_code():
    try:
        return await telegram_service.send_auth_code()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/telegram/auth/verify_code")
async def verify_code(payload: AuthCodePayload):
    try:
        return await telegram_service.verify_auth_code(payload.code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/extract_locations")
async def extract_locations(payload: dict):
    if not GeoText:
        return {"status": "error", "message": "Geotext or Geopy is missing."}
    
    text = payload.get("text", "")
    if not text:
        return {"status": "success", "locations": []}
    
    
    places = GeoText(text)
    false_positives = {"Ans", "De", "La", "Le", "Les", "Des", "Du", "Un", "Une", "Et", "Sur", "Dans", "Pour", "A", "En", "Or", "Au", "Aux", "Ce", "Ces", "Se", "Me", "Te", "Ne", "Pas", "Qui", "Que", "Qu", "Of", "In", "On", "At", "To", "And", "The", "Is", "Are", "Am", "Be", "Est", "Sont", "Va", "Aller", "Fait", "Non", "Oui"}
    valid_places = [p for p in (places.cities + places.countries) if (len(p) > 2 or p in ["US", "UK"]) and p not in false_positives]
    locations_to_find = list(set(valid_places))
    
    
    text_lower = f" {text.lower()} "
    for fr_term, en_term in FR_EN_DICT.items():
        if f" {fr_term} " in text_lower:
            locations_to_find.append(en_term)
    
    locations_to_find = list(set(locations_to_find))
    
    
    hardcoded_coords = {
        "Gaza Strip": {"lat": 31.4167, "lng": 34.3333},
        "West Bank": {"lat": 32.0000, "lng": 35.2500},
        "Palestine": {"lat": 31.9522, "lng": 35.2332},
        "Middle East": {"lat": 29.2985, "lng": 42.5510},
    }
    
    known_countries = set(FR_EN_DICT.values()) - {"Paris", "Moscow", "Kyiv", "London", "Beijing", "Rome", "Berlin", "Madrid", "Tokyo"}
    
    results = []
    for city in locations_to_find[:8]:
        if city in geo_cache:
            results.append(geo_cache[city])
            continue
            
        if city in hardcoded_coords:
            data = {
                "name": city,
                "lat": hardcoded_coords[city]["lat"],
                "lng": hardcoded_coords[city]["lng"]
            }
            geo_cache[city] = data
            results.append(data)
            continue
            
        try:
            # If we know it's a country, use a structured query to prevent Nominatim from returning US cities
            query = {"country": city} if city in known_countries else city
            location = geolocator.geocode(query, language="fr", timeout=3)
            
            # Fallback if structured query fails
            if not location and isinstance(query, dict):
                location = geolocator.geocode(city, language="fr", timeout=3)
                
            if location:
                data = {
                    "name": city,
                    "lat": location.latitude,
                    "lng": location.longitude
                }
                geo_cache[city] = data
                results.append(data)
            time.sleep(1.1)
        except Exception:
            pass
            
    return {"status": "success", "locations": results}

@app.get("/api/rss")
async def get_rss_feed(url: str):
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Only HTTP/HTTPS URLs are allowed.")
    try:
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            return {"status": "error", "message": "Invalid RSS feed."}

        entries = []
        for entry in feed.entries[:15]:
            media_url = ""
            if "media_content" in entry and len(entry.media_content) > 0:
                media_url = entry.media_content[0].get("url", "")
            elif "enclosures" in entry and len(entry.enclosures) > 0:
                for enc in entry.enclosures:
                    if enc.get("type", "").startswith("image/") or enc.get("type", "").startswith("video/"):
                        media_url = enc.get("href", "")
                        break
            
            entries.append({
                "title": entry.get("title", "No Title"),
                "link": entry.get("link", "#"),
                "published": entry.get("published", ""),
                "summary": (entry.get("summary", "")[:200] + "...") if entry.get("summary") else "",
                "media": media_url
            })

        return {
            "title": feed.feed.get("title", "RSS Feed"),
            "entries": entries
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/rss/upload")
async def upload_rss_feed(file: UploadFile = File(...)):
    try:
        content = await file.read()
        feed = feedparser.parse(content)
        if feed.bozo and not feed.entries:
            return {"status": "error", "message": "Invalid RSS feed."}

        entries = [
            {
                "title": entry.get("title", "No Title"),
                "link": entry.get("link", "#"),
                "published": entry.get("published", ""),
                "summary": (entry.get("summary", "")[:200] + "...") if entry.get("summary") else ""
            }
            for entry in feed.entries[:15]
        ]

        return {
            "title": feed.feed.get("title", "Local RSS File"),
            "entries": entries
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ---------------------------------------------------------------------------
# AI provider abstraction: routes chat-completions to a local Ollama server
# (free, offline, no API key) or to OpenRouter, depending on AI_PROVIDER.
# Both expose the same OpenAI-compatible /chat/completions schema.
# ---------------------------------------------------------------------------

def _get_ai_provider() -> str:
    return (os.getenv("AI_PROVIDER") or "openrouter").strip().lower()


async def llm_chat(messages: list, model: str | None = None,
                   api_key: str | None = None, timeout: float = 120.0) -> str:
    """Send a chat-completion and return the assistant text.

    Raises HTTPException with a helpful message on failure.
    """
    provider = _get_ai_provider()

    if provider in ("local", "ollama"):
        base = (os.getenv("OLLAMA_URL") or "http://localhost:11434").rstrip("/")
        # A model id containing "/" is an OpenRouter id (e.g. left over in the
        # UI); ignore it for the local provider and fall back to OLLAMA_MODEL.
        ollama_model = model if (model and "/" not in model) else None
        ollama_model = ollama_model or os.getenv("OLLAMA_MODEL") or "qwen2.5:7b"
        payload = {"model": ollama_model, "messages": messages, "stream": False}
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(f"{base}/v1/chat/completions",
                                        json=payload, timeout=timeout)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            raise HTTPException(status_code=503, detail=(
                f"Cannot reach Ollama at {base}. Is it running? "
                f"Start it, then run: ollama pull {ollama_model}"))
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code,
                                detail=f"Ollama error: {res.text}")
        data = res.json()
        if "choices" not in data or not data["choices"]:
            raise HTTPException(status_code=500,
                                detail=f"Unexpected Ollama response: {data}")
        return data["choices"][0]["message"]["content"]

    # Default: OpenRouter
    api_key = api_key or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail=(
            "OpenRouter API Key not found. Add it in Settings, or switch the "
            "AI provider to Local (Ollama)."))
    ai_model = model or os.getenv("OPENROUTER_MODEL") or "openrouter/free"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "http://localhost:5173",
        "X-Title": "KNWLDGBox",
        "Content-Type": "application/json",
    }
    payload = {"model": ai_model, "messages": messages}
    async with httpx.AsyncClient() as client:
        res = await client.post("https://openrouter.ai/api/v1/chat/completions",
                                json=payload, headers=headers, timeout=timeout)
    if res.status_code != 200:
        raise HTTPException(status_code=res.status_code,
                            detail=f"OpenRouter API error: {res.text}")
    data = res.json()
    if "choices" not in data or not data["choices"]:
        raise HTTPException(status_code=500,
                            detail=f"Unexpected OpenRouter response: {data}")
    return data["choices"][0]["message"]["content"]


@app.get("/api/ollama/models")
async def list_ollama_models():
    """List models installed on the local Ollama server (for UI dropdowns)."""
    base = (os.getenv("OLLAMA_URL") or "http://localhost:11434").rstrip("/")
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(f"{base}/api/tags", timeout=10.0)
        data = res.json()
        models = [m.get("name") for m in data.get("models", []) if m.get("name")]
        return {"status": "success", "models": models}
    except Exception as e:
        return {"status": "error", "models": [], "detail": str(e)}


# ---------------------------------------------------------------------------
# Web search (DuckDuckGo, free/keyless) so the offline AI can answer about
# current events: the model plans a query, we search, and feed real results
# (with sources) back for a grounded answer.
# ---------------------------------------------------------------------------

def web_search(query: str, max_results: int = 5) -> list:
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        print(f"[websearch] error: {e}")
        return []


_GREETINGS = ("bonjour", "salut", "coucou", "merci", "hello", "hi", "hey",
              "ok", "ça va", "ca va", "yo", "bonsoir", "thanks", "thx")


def _looks_trivial(text: str) -> bool:
    """Small talk / greetings that don't warrant a web search."""
    t = text.strip().lower().rstrip("!?. ")
    if len(t.split()) <= 2:
        return True
    return any(t == g or t.startswith(g + " ") for g in _GREETINGS)


async def plan_search_query(messages: list, model: str | None) -> str | None:
    """Turn the user's last message into a focused web-search query.

    Search-first: any real question triggers a search; only trivial small talk
    is skipped. (Letting a small local model decide yes/no is unreliable.)
    """
    last_user = next((m.get("content", "") for m in reversed(messages)
                      if m.get("role") == "user"), "")
    if not last_user.strip() or _looks_trivial(last_user):
        return None
    today = date.today().isoformat()
    router = [
        {"role": "system", "content": (
            f"Today is {today}. Rewrite the user's message as one concise web "
            "search query to find current, factual information. Add the year "
            "when the topic is recent. Output ONLY the query: no quotes, no "
            "explanation, no label.")},
        {"role": "user", "content": last_user[:1000]},
    ]
    try:
        out = (await llm_chat(router, model=model, timeout=60.0)).strip()
    except Exception:
        return last_user[:200]  # fall back to searching the raw question
    first_line = out.strip().strip('"').splitlines()[0].strip() if out else ""
    # Guard against the model echoing a refusal/label instead of a query.
    if not first_line or first_line.upper().startswith("NONE") or len(first_line) > 200:
        return last_user[:200]
    return first_line


def format_search_context(query: str, results: list) -> str:
    today = date.today().isoformat()
    lines = [f'Today is {today}. Web search results for "{query}":', ""]
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        href = r.get("href", "") or r.get("url", "")
        body = (r.get("body", "") or "")[:400]
        lines.append(f"[{i}] {title}\n{href}\n{body}")
    lines += [
        "",
        "Answer the user's last question following these rules strictly:",
        "- Use ONLY the information in the results above. Do NOT add anything "
        "from your own prior knowledge or assumptions.",
        "- After every factual statement, cite its source by number only, "
        "e.g. [1] or [2]. NEVER write a URL yourself — the clickable source "
        "links are shown to the user separately, and any URL you type would be "
        "wrong.",
        "- Report dates, figures and place names EXACTLY as they appear in the "
        "sources. Do not round or approximate them.",
        "- If a detail (cause, date, number, location) is NOT stated in the "
        "results, say it is not specified in the sources. Never guess, infer "
        "or invent it — this is the most important rule.",
        "- If the results do not answer the question, say so plainly instead "
        "of answering from memory.",
        "- Still answer as fully as the sources allow: report EVERY relevant "
        "fact they contain (places, figures, events). Being careful means not "
        "inventing — it does not mean withholding facts that ARE present.",
        "- If the user's date or a detail is slightly off but the sources "
        "clearly describe the same event, answer about that event and give "
        "the correct date/detail from the sources.",
        "- Answer in the same language as the user.",
        "- Do NOT append a 'Sources' list or any URLs — they are displayed to "
        "the user automatically below your answer."]
    return "\n".join(lines)


class RssSummarizeRequest(BaseModel):
    entries: list
    api_key: str | None = None
    model: str | None = None
    language: str | None = None

@app.post("/api/rss/summarize")
async def summarize_rss(req: RssSummarizeRequest):
    sys_prompt = None
    sys_prompt_b64 = os.getenv("OPENROUTER_SYSTEM_PROMPT")
    if sys_prompt_b64:
        try:
            sys_prompt = base64.b64decode(sys_prompt_b64).decode('utf-8')
        except:
            pass

    if sys_prompt:
        prompt = sys_prompt + "\\n\\nHere are the RSS feed entries:\\n\\n"
    elif req.language == "fr":
        prompt = "Vous êtes un analyste en renseignement professionnel et objectif. Veuillez fournir une synthèse exécutive des entrées de flux RSS suivantes du jour. Regroupez les sujets similaires, mettez en évidence les événements critiques ou les menaces, et maintenez un ton formel et analytique. Utilisez des émojis pertinents uniquement pour les titres majeurs afin de faciliter la lecture. Formatez votre réponse en Markdown propre et structuré :\\n\\n"
    else:
        prompt = "You are a professional, objective intelligence analyst. Please provide an executive summary of the following RSS feed entries from today. Group similar topics, highlight critical events or threats, and maintain a formal, analytical tone. Use relevant emojis only for major section titles to improve readability. Format your response in clean, structured Markdown:\\n\\n"

    for idx, entry in enumerate(req.entries):
        time_str = f" [{entry.get('time')}]" if entry.get('time') else ""
        prompt += f"{idx+1}. {entry.get('title')}{time_str} - {entry.get('summary')}\\n"

    try:
        summary = await llm_chat([{"role": "user", "content": prompt}],
                                 model=req.model, api_key=req.api_key, timeout=90.0)
        return {"status": "success", "summary": summary}
    except HTTPException:
        raise
    except httpx.ReadTimeout:
        raise HTTPException(status_code=504, detail="AI generation timed out. The selected model is too slow or overloaded. Please try another model.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ChatRequest(BaseModel):
    messages: list
    api_key: str | None = None
    model: str | None = None
    web_search: bool = False

@app.post("/api/chat")
async def chat_completion(req: ChatRequest):
    sys_prompt_b64 = os.getenv("OPENROUTER_SYSTEM_PROMPT")
    if sys_prompt_b64:
        try:
            sys_prompt = base64.b64decode(sys_prompt_b64).decode('utf-8')
            if req.messages and req.messages[0].get("role") != "system":
                req.messages.insert(0, {"role": "system", "content": sys_prompt})
        except:
            pass

    sources = []
    if req.web_search:
        query = await plan_search_query(req.messages, req.model)
        if query:
            sources = web_search(query, max_results=5)
            if sources:
                req.messages.append({"role": "system",
                                     "content": format_search_context(query, sources)})

    try:
        content = await llm_chat(req.messages, model=req.model,
                                 api_key=req.api_key, timeout=120.0)
        return {"status": "success",
                "message": {"role": "assistant", "content": content},
                "sources": [{"title": s.get("title"), "url": s.get("href") or s.get("url")}
                            for s in sources]}
    except HTTPException:
        raise
    except httpx.ReadTimeout:
        raise HTTPException(status_code=504, detail="AI generation timed out.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/telegram/media/{channel}/{message_id}")
async def get_telegram_media(channel: str, message_id: int):
    if not telegram_service.client or not telegram_service.client.is_connected():
        raise HTTPException(status_code=400, detail="Telegram client not connected")
    
    try:
        msg = await telegram_service.client.get_messages(channel, ids=message_id)
        if not msg or not getattr(msg, "media", None):
            raise HTTPException(status_code=404, detail="Media not found")
            
        buffer = await telegram_service.client.download_media(msg, file=bytes)
        if not buffer:
            raise HTTPException(status_code=500, detail="Failed to download media")
            
        mime_type = "application/octet-stream"
        if hasattr(msg, 'file') and msg.file and getattr(msg.file, 'mime_type', None):
            mime_type = msg.file.mime_type
            
        return Response(content=buffer, media_type=mime_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/telegram")
async def websocket_endpoint(websocket: WebSocket):
    await telegram_service.handle_websocket(websocket)

@app.websocket("/ws/sherlock")
async def sherlock_endpoint(websocket: WebSocket):
    await sherlock_service.handle_websocket(websocket)

@app.websocket("/ws/recon")
async def recon_endpoint(websocket: WebSocket):
    await recon_service.handle_websocket(websocket)


# Must be the LAST mount so /api/* and /ws/* routes take priority.
# In dev mode, app/dist won't exist and this block is skipped entirely.
from config import APP_DIR
from starlette.exceptions import HTTPException as StarletteHTTPException

class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except (HTTPException, StarletteHTTPException) as ex:
            if ex.status_code == 404:
                return await super().get_response("index.html", scope)
            raise

_frontend_dist = APP_DIR.parent / "app" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", SPAStaticFiles(directory=str(_frontend_dist), html=True), name="frontend")

