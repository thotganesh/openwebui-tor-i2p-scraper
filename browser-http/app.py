import asyncio as _aio
import os as _os
from fastapi import HTTPException as _HTTPException
import asyncio
from urllib.parse import urljoin
from fastapi import FastAPI
from pydantic import BaseModel
from curl_cffi import requests
from readability import Document
import html2text

# ===== SSRF guard (shared module) =====
# Logica in shared/ssrf_guard.py, montata in /app/shared (read-only).
from shared.ssrf_guard import (
    blocked_reason_clearnet as blocked_reason,
    check_redirect_chain_clearnet,
)


async def guard_route(route):
    """Aborta la richiesta Playwright se l'URL punta a un host non pubblico."""
    url = route.request.url
    scheme = url.split(":", 1)[0].lower()
    if scheme in ("data", "blob", "about"):
        await route.fallback()
        return
    if scheme not in ("http", "https"):
        await route.abort()
        return
    why = blocked_reason(url)
    if why:
        print("[guard] bloccato " + url[:120] + " (" + why + ")", flush=True)
        await route.abort()
    else:
        await route.fallback()


# ===== /SSRF guard =====


_SEM = _aio.Semaphore(int(_os.environ.get("MAX_CONCURRENT", "4")))

app = FastAPI()


class Request(BaseModel):
    url: str


def extract_text(html: str) -> str:
    """Two-level extraction: Readability first, html2text fallback."""
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True
    h.body_width = 0

    try:
        doc = Document(html)
        clean = h.handle(doc.summary()).strip()
        if clean and len(clean) > 200:
            return clean
    except Exception:
        pass

    try:
        return h.handle(html).strip()
    except Exception as e:
        return f"Extraction error: {e}"


_REDIRECTS = (301, 302, 303, 307, 308)


def _fetch(url):
    cur = url
    for _ in range(6):
        why = blocked_reason(cur)
        if why:
            return None, cur, why
        resp = requests.get(cur, impersonate="chrome124", timeout=30, allow_redirects=False)
        loc = resp.headers.get("location")
        if resp.status_code in _REDIRECTS and loc:
            cur = urljoin(cur, loc)
            continue
        return resp, cur, None
    return None, cur, "troppi redirect"


@app.post("/browse")
async def browse(req: Request):
    why = await asyncio.to_thread(blocked_reason, req.url)
    if why:
        raise _HTTPException(status_code=400, detail=why)
    try:
        async with _SEM:
            response, final_url, why = await asyncio.to_thread(_fetch, req.url)
    except Exception as e:
        return {"error": str(e), "text": "", "title": "", "final_url": req.url}
    if why:
        raise _HTTPException(status_code=400, detail=why)
    if response.status_code != 200:
        return {"error": f"HTTP {response.status_code}", "text": "", "title": "", "final_url": final_url}
    html = response.text
    try:
        title = Document(html).title() or ""
    except Exception:
        title = ""
    return {"title": title, "text": extract_text(html), "final_url": final_url}


@app.get("/health")
async def health():
    return {"status": "ok"}
