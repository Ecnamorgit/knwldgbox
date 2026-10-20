"""
Identity Recon: from a name, generate username variants, then sweep them
through Sherlock + Bluesky in parallel and aggregate every account found.
"""
import re
import json
import asyncio
import unicodedata

import httpx
from fastapi import WebSocket

BSKY = "https://public.api.bsky.app/xrpc"
MAX_CONCURRENCY = 4
SHERLOCK_TIMEOUT = 30


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def generate_variants(name: str) -> list:
    """Turn a name (or handle) into likely username variants."""
    name = _strip_accents((name or "").strip().lower())
    tokens = [re.sub(r"[^a-z0-9]", "", t) for t in re.split(r"[\s._\-]+", name)]
    tokens = [t for t in tokens if t]
    variants = set()
    if not tokens:
        return []
    if len(tokens) == 1:
        variants.add(tokens[0])
    else:
        first, last = tokens[0], tokens[-1]
        variants.update([
            first + last, last + first,
            f"{first}.{last}", f"{last}.{first}",
            f"{first}_{last}", f"{last}_{first}",
            f"{first}-{last}",
            first[0] + last, first + last[0],
            f"{first[0]}.{last}", f"{first}.{last[0]}",
            "".join(tokens),
        ])
    return sorted(v for v in variants if 2 <= len(v) <= 30)


async def _bsky_profile(client, actor: str):
    for a in ([actor] if "." in actor else [actor, f"{actor}.bsky.social"]):
        try:
            r = await client.get(f"{BSKY}/app.bsky.actor.getProfile",
                                 params={"actor": a}, timeout=12.0)
            if r.status_code == 200:
                return r.json()
        except Exception:
            continue
    return None


class ReconService:
    async def handle_websocket(self, websocket: WebSocket):
        await websocket.accept()
        send_lock = asyncio.Lock()
        procs = []

        async def send(obj):
            async with send_lock:
                await websocket.send_json(obj)

        try:
            payload = json.loads(await websocket.receive_text())
            if payload.get("action") != "search":
                return
            name = (payload.get("name") or "").strip()
            if not name:
                await send({"type": "error", "text": "Empty query"})
                return

            variants = generate_variants(name)
            await send({"type": "variants", "variants": variants})
            total = len(variants)
            progress = {"n": 0}
            sem = asyncio.Semaphore(MAX_CONCURRENCY)

            async with httpx.AsyncClient() as client:
                async def run_variant(v):
                    async with sem:
                        # --- Sherlock ---
                        try:
                            p = await asyncio.create_subprocess_exec(
                                "sherlock", v, "--print-found",
                                "--timeout", str(SHERLOCK_TIMEOUT),
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE,
                            )
                            procs.append(p)
                            while True:
                                line = await p.stdout.readline()
                                if not line:
                                    break
                                text = line.decode("utf-8", "ignore").strip()
                                if text.startswith("[+]"):
                                    parts = text[4:].split(": http", 1)
                                    if len(parts) == 2:
                                        await send({
                                            "type": "found", "variant": v,
                                            "site": parts[0].strip(),
                                            "url": "http" + parts[1].strip(),
                                            "source": "sherlock",
                                        })
                            await p.wait()
                        except Exception as e:
                            await send({"type": "log", "text": f"{v}: {e}"})

                        # --- Bluesky ---
                        try:
                            prof = await _bsky_profile(client, v)
                            if prof:
                                await send({
                                    "type": "found", "variant": v,
                                    "site": "Bluesky",
                                    "url": f"https://bsky.app/profile/{prof.get('handle')}",
                                    "source": "bluesky",
                                    "extra": prof.get("displayName"),
                                })
                        except Exception:
                            pass

                        progress["n"] += 1
                        await send({"type": "progress", "done": progress["n"],
                                    "total": total, "variant": v})

                await asyncio.gather(*[run_variant(v) for v in variants])

            await send({"type": "done"})
        except Exception as e:
            try:
                await send({"type": "error", "text": str(e)})
            except Exception:
                pass
        finally:
            for p in procs:
                if p.returncode is None:
                    try:
                        p.terminate()
                    except Exception:
                        pass


recon_service = ReconService()
