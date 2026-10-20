"""
Bluesky (AT Protocol) OSINT module.

Bluesky's public API needs no authentication, so we can pull a target's full
public footprint — profile, posts, follows, followers — and auto-extract
intel (emails, links, mentioned handles, dates, ages) from the text.
"""
import re
import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter()

BASE = "https://public.api.bsky.app/xrpc"

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
URL_RE = re.compile(r"https?://[^\s)]+")
MENTION_RE = re.compile(r"(?<![\w.])@([a-zA-Z0-9_](?:[a-zA-Z0-9_.]{1,38})?)")
DATE_RE = re.compile(r"\b\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}\b")
AGE_RE = re.compile(r"\b\d{1,2}\s?ans\b", re.IGNORECASE)


async def _get(client, endpoint, params):
    r = await client.get(f"{BASE}/{endpoint}", params=params, timeout=20.0)
    r.raise_for_status()
    return r.json()


def _extract_intel(texts):
    emails, urls, mentions, dates, ages = set(), set(), set(), set(), set()
    for t in texts:
        if not t:
            continue
        emails.update(EMAIL_RE.findall(t))
        urls.update(URL_RE.findall(t))
        mentions.update("@" + m for m in MENTION_RE.findall(t))
        dates.update(DATE_RE.findall(t))
        ages.update(a.strip() for a in AGE_RE.findall(t))
    return {
        "emails": sorted(emails),
        "urls": sorted(urls),
        "mentions": sorted(mentions),
        "dates": sorted(dates),
        "ages": sorted(ages),
    }


def _actor_card(a):
    return {
        "handle": a.get("handle"),
        "displayName": a.get("displayName"),
        "description": (a.get("description") or "")[:140],
        "avatar": a.get("avatar"),
    }


async def _build_dossier(client, prof):
    handle = prof.get("handle")

    # Posts
    posts, post_texts = [], []
    try:
        feed = await _get(client, "app.bsky.feed.getAuthorFeed",
                          {"actor": handle, "limit": 40})
    except Exception:
        feed = {"feed": []}
    for it in feed.get("feed", []):
        p = it.get("post", {})
        rec = p.get("record", {})
        text = rec.get("text", "")
        post_texts.append(text)
        links = []
        for f in (rec.get("facets") or []):
            for feat in f.get("features", []):
                if feat.get("uri"):
                    links.append(feat["uri"])
        rkey = (p.get("uri", "") or "").split("/")[-1]
        posts.append({
            "text": text,
            "createdAt": rec.get("createdAt", ""),
            "url": f"https://bsky.app/profile/{handle}/post/{rkey}" if rkey else "",
            "links": links,
            "likes": p.get("likeCount", 0),
            "reposts": p.get("repostCount", 0),
            "replies": p.get("replyCount", 0),
        })

    # Follows / followers (first page each)
    async def actors_of(endpoint, key):
        try:
            d = await _get(client, endpoint, {"actor": handle, "limit": 40})
            return [_actor_card(a) for a in d.get(key, [])]
        except Exception:
            return []

    follows = await actors_of("app.bsky.graph.getFollows", "follows")
    followers = await actors_of("app.bsky.graph.getFollowers", "followers")

    intel = _extract_intel([prof.get("description", "")] + post_texts)
    # Fold in the resolved facet links from posts
    all_urls = set(intel["urls"])
    for p in posts:
        all_urls.update(p["links"])
    intel["urls"] = sorted(all_urls)

    return {
        "mode": "profile",
        "profile": {
            "handle": handle,
            "did": prof.get("did"),
            "displayName": prof.get("displayName"),
            "description": prof.get("description"),
            "avatar": prof.get("avatar"),
            "banner": prof.get("banner"),
            "createdAt": prof.get("createdAt"),
            "followersCount": prof.get("followersCount"),
            "followsCount": prof.get("followsCount"),
            "postsCount": prof.get("postsCount"),
        },
        "intel": intel,
        "posts": posts,
        "follows": follows,
        "followers": followers,
    }


@router.get("/api/bluesky/lookup")
async def bluesky_lookup(q: str):
    """Resolve a handle to a full dossier, or search by name/term."""
    q = (q or "").strip().lstrip("@")
    if not q:
        raise HTTPException(status_code=400, detail="Empty query")

    async with httpx.AsyncClient() as client:
        # A term without spaces is likely a handle -> try a direct profile.
        # Bare handles (no dot) default to the .bsky.social domain.
        if " " not in q:
            candidates = [q]
            if "." not in q:
                candidates.append(f"{q}.bsky.social")
            for actor in candidates:
                try:
                    prof = await _get(client, "app.bsky.actor.getProfile", {"actor": actor})
                    return await _build_dossier(client, prof)
                except Exception:
                    continue
        # Otherwise (or if not found) search actors by term.
        try:
            res = await _get(client, "app.bsky.actor.searchActors",
                             {"term": q, "limit": 20})
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Bluesky API error: {e}")
        return {"mode": "search", "actors": [_actor_card(a) for a in res.get("actors", [])]}
