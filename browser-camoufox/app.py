from fastapi import FastAPI
from pydantic import BaseModel
from camoufox.async_api import AsyncCamoufox
from readability import Document
import html2text

# ===== SSRF GUARD (injected by fix script) =====
import asyncio as _aio, ipaddress as _ipa, re as _re, socket as _sock, os as _os, time as _time
from urllib.parse import urlparse as _urlparse
from fastapi import HTTPException as _HTTPException

_NUM_HOST = _re.compile(r"(0x[0-9a-f]+|\d+)(\.(0x[0-9a-f]+|\d+))*")
_PRIV_SUFFIX = (".local", ".internal", ".localhost", ".lan", ".home.arpa", ".docker", ".svc")
_DNS_CACHE = {}
_SEM = _aio.Semaphore(int(_os.environ.get("MAX_CONCURRENT", "2")))


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
def chain_check(resp, page):
    """Scarta il risultato se un redirect (o l'URL finale) punta a host non pubblici."""
    urls, r = [], (resp.request if resp is not None else None)
    while r is not None:
        urls.append(r.url)
        r = r.redirected_from
    urls.append(page.url)
    for u in urls:
        why = blocked_reason(u)
        if why:
            raise RuntimeError("redirect/URL bloccato (" + why + "): " + u[:120])
# ===== /SSRF GUARD =====

app = FastAPI()


class BrowseRequest(BaseModel):
    url: str
    block_media: bool = False
    humanize: bool = True
    os: str = "windows"
    wait_ms: int = 5000


COOKIE_KILLER_JS = """
async () => {
    const CMP_SELECTORS = [
        '#onetrust-banner-sdk', '#onetrust-consent-sdk',
        '#cookiebot', '#CybotCookiebotDialog',
        '.qc-cmp2-container', '#qc-cmp2-container',
        '#truste-consent-track', '.truste_box_overlay',
        '.cc-window', '.fc-consent-root', '#cookie-notice',
        '.paywall', '[class*="cookie-banner"]', '[id*="cookie-consent"]',
        '#iubenda-cs-banner', '.iubenda-cs-container', '.iubenda-cs-visible',
        '[class*="iubenda"]', 'iframe[src*="iubenda"]',
        '#didomi-host', '#didomi-notice', '.didomi-popup-backdrop',
        '[class*="didomi"]',
        '.cmplz-cookiebanner', '.cmplz-manage-consent',
        '.cky-consent-container', '.cky-modal',
        '.cli-modal-backdrop', '#cookie-law-info-bar',
        '.termly-cookie-policy',
        '.klaro .cookie-modal', '.klaro .cookie-notice',
        '#ccpa-banner',
        '.fc-dialog-overlay',
        '#gdpr-banner', '.gdpr-banner',
    ];
    CMP_SELECTORS.forEach(sel => {
        document.querySelectorAll(sel).forEach(el => {
            el.style.setProperty('display', 'none', 'important');
            el.style.setProperty('visibility', 'hidden', 'important');
        });
    });

    // *** FIX IUBENDA: rimuovi le classi che nascondono il contenuto ***
    document.documentElement.classList.remove('is-iubenda-cs-banner-open');
    if (document.body) {
        document.body.classList.remove('is-iubenda-cs-banner-open');
    }

    // Forza overflow visibile
    document.documentElement.style.setProperty('overflow', 'auto', 'important');
    if (document.body) {
        document.body.style.setProperty('overflow', 'auto', 'important');
        document.body.style.setProperty('position', 'static', 'important');
        document.body.style.setProperty('opacity', '1', 'important');
        document.body.style.setProperty('visibility', 'visible', 'important');
        document.body.style.setProperty('height', 'auto', 'important');
        document.body.style.setProperty('filter', 'none', 'important');
    }

    // Rimuovi backdrop overlay
    document.querySelectorAll('body > div').forEach(el => {
        try {
            const s = window.getComputedStyle(el);
            const z = parseInt(s.zIndex) || 0;
            if (s.position === 'fixed' && z > 1000) {
                el.style.setProperty('display', 'none', 'important');
            }
        } catch (e) { }
    });

    return 'cookie-killer: done';
}
"""


def clean_text(html: str) -> str:
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True
    h.body_width = 0

    # Tentativo 1: Readability (richiede articolo strutturato)
    try:
        doc = Document(html)
        t = h.handle(doc.summary()).strip()
        # *** Soglia ALZATA: se Readability da' poco, usa fallback ***
        if t and len(t) > 3000:
            return t
    except Exception:
        pass

    # Tentativo 2: html2text su tutto l'HTML
    try:
        return h.handle(html).strip()
    except Exception as e:
        return f"Extraction error: {e}"


@app.post("/browse")
async def browse(req: BrowseRequest):
    why = await _aio.to_thread(blocked_reason, req.url)
    if why:
        raise _HTTPException(status_code=400, detail=why)
    async with _SEM:
        return await _browse_impl(req)


async def _browse_impl(req: BrowseRequest):
    try:
        kwargs = {
            "headless": True,
            "humanize": req.humanize,
            "block_webrtc": True,
            "os": req.os,
        }
        if req.block_media:
            kwargs["block_images"] = True
            kwargs["i_know_what_im_doing"] = True

        async with AsyncCamoufox(**kwargs) as browser:
            page = await browser.new_page()
            await page.route("**/*", guard_route)
            _nav = await page.goto(req.url, wait_until="domcontentloaded", timeout=60000)
            chain_check(_nav, page)
            await page.wait_for_timeout(req.wait_ms)
            try:
                await page.evaluate(COOKIE_KILLER_JS)
            except Exception:
                pass
            await page.wait_for_timeout(1500)
            chain_check(None, page)
            html = await page.content()
            return {
                "title": await page.title(),
                "final_url": page.url,
                "text": clean_text(html),
            }
    except Exception as e:
        return {"error": str(e), "text": "", "title": ""}


@app.get("/health")
async def health():
    return {"status": "ok"}
