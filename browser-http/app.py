import asyncio
from urllib.parse import urljoin
from fastapi import FastAPI
from pydantic import BaseModel
from curl_cffi import requests
from readability import Document
import html2text

# ===== SSRF GUARD (injected by fix script) =====
import asyncio as _aio, ipaddress as _ipa, re as _re, socket as _sock, os as _os, time as _time
from urllib.parse import urlparse as _urlparse
from fastapi import HTTPException as _HTTPException

_NUM_HOST = _re.compile(r"(0x[0-9a-f]+|\d+)(\.(0x[0-9a-f]+|\d+))*")
_PRIV_SUFFIX = (".local", ".internal", ".localhost", ".lan", ".home.arpa", ".docker", ".svc")
_DNS_CACHE = {}
_SEM = _aio.Semaphore(int(_os.environ.get("MAX_CONCURRENT", "4")))


def _resolve(host):
    now = _time.time()
    hit = _DNS_CACHE.get(host)
    if hit and now - hit[0] < 30:
        return hit[1]
    try:
        ips = [_ipa.ip_address(a[4][0].split("%")[0]) for a in _sock.getaddrinfo(host, None)]
    except (OSError, ValueError):
        ips = []
    if len(_DNS_CACHE) > 2000:
        _DNS_CACHE.clear()
    _DNS_CACHE[host] = (now, ips)
    return ips


def blocked_reason(url):
    """None se l'URL e' lecito, altrimenti il motivo del rifiuto."""
    try:
        u = _urlparse(url)
        host = (u.hostname or "").lower().rstrip(".")
    except ValueError:
        return "url non valido"
    if u.scheme not in ("http", "https"):
        return "schema non consentito"
    if not host or host == "localhost" or host.endswith(_PRIV_SUFFIX):
        return "host non consentito"
    # .onion/.i2p non sono di competenza del clearnet: rifiuta senza risolvere
    if host.endswith(".onion") or host.endswith(".i2p"):
        return "host .onion/.i2p non gestito da questo container"
    try:
        ips = [_ipa.ip_address(host)]
    except ValueError:
        if _NUM_HOST.fullmatch(host):
            return "host numerico ambiguo"
        if "." not in host:
            return "host senza dominio (rete interna?)"
        ips = _resolve(host)
    for ip in ips:
        if ip.version == 6 and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if not ip.is_global:
            return "IP non pubblico"
    return None


async def guard_route(route):
    url = route.request.url
    scheme = url.split(":", 1)[0].lower()
    if scheme in ("data", "blob", "about"):
        await route.fallback()
        return
    if scheme not in ("http", "https"):
        await route.abort()
        return
    why = await _aio.to_thread(blocked_reason, url)
    if why:
        print("[guard] bloccato " + url[:120] + " (" + why + ")", flush=True)
        await route.abort()
    else:
        await route.fallback()
# ===== /SSRF GUARD =====


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
