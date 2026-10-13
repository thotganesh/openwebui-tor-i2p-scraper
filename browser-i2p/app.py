import asyncio
from fastapi import FastAPI
from pydantic import BaseModel
from playwright.async_api import async_playwright
from readability import Document
import html2text

import asyncio as _aio, os as _os
import ipaddress as _ipa, re as _re, socket as _sock, time as _time
from urllib.parse import urlparse as _urlparse
from fastapi import HTTPException as _HTTPException
_SEM = _aio.Semaphore(int(_os.environ.get("MAX_CONCURRENT", "2")))

# ===== SSRF guard (shared module) =====
# Solo host .i2p sono accettati; nessuna risoluzione DNS.
from shared.ssrf_guard import (
    blocked_reason_anon,
    check_redirect_chain_clearnet,
)


def blocked_reason(url):
    return blocked_reason_anon(url, ".i2p")


async def guard_route(route):
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


async def chain_check(resp, page):
    """Scarta il risultato se un redirect punta a host non pubblici."""
    urls, r = [], (resp.request if resp is not None else None)
    while r is not None:
        urls.append(r.url)
        r = r.redirected_from
    urls.append(page.url)
    why = check_redirect_chain_clearnet(urls)
    if why:
        raise RuntimeError("redirect/URL bloccato: " + why)

# ===== /SSRF guard =====

app = FastAPI()


class BrowseRequest(BaseModel):
    url: str
    extract_text: bool = True
    block_media: bool = True
    js_enabled: bool = False


I2P_PROXY = {"server": "http://i2p-proxy:4444"}

FIREFOX_PREFS = {
    # Privacy & anti-fingerprinting (eyedeekay profile)
    "privacy.resistFingerprinting": True,
    "privacy.resistFingerprinting.letterboxing": True,
    "privacy.spoof_english": 2,
    # Network isolation
    "media.peerconnection.enabled": False,
    "network.dns.disablePrefetch": True,
    "network.prefetch-next": False,
    "network.proxy.socks_remote_dns": True,
    # Disable sensors & hardware access
    "geo.enabled": False,
    "webgl.disabled": True,
    "dom.battery.enabled": False,
    "device.sensors.enabled": False,
    "media.navigator.enabled": False,
    # Anti-Spectre (from eyedeekay profile)
    "javascript.options.shared_memory": False,
    # Additional privacy
    "browser.cache.disk.enable": False,
    "browser.cache.memory.enable": False,
    "network.http.sendRefererHeader": 0,
    "dom.storage.enabled": False,
    "dom.indexedDB.enabled": False,
}


# Extended cookie killer (aligned with browser-clear)
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
    document.documentElement.style.setProperty('overflow', 'auto', 'important');
    if (document.body) {
        document.body.style.setProperty('overflow', 'auto', 'important');
    }
    return 'cookie-killer: done';
}
"""


def pulisci_testo(html_content: str) -> str:
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True
    h.body_width = 0

    try:
        doc = Document(html_content)
        testo = h.handle(doc.summary()).strip()
        if testo:
            return testo
    except Exception:
        pass

    try:
        return h.handle(html_content).strip()
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
    async with async_playwright() as p:
        browser = None
        try:
            browser = await p.firefox.launch(
                headless=True,
                proxy=I2P_PROXY,
                firefox_user_prefs=FIREFOX_PREFS,
            )
            context = await browser.new_context(
                viewport={"width": 1000, "height": 900},
                timezone_id="UTC",
                locale="en-US",
                java_script_enabled=req.js_enabled,
            )
            await context.route("**/*", guard_route)
            page = await context.new_page()

            if req.block_media:
                await page.route(
                    "**/*",
                    lambda route: route.abort()
                    if route.request.resource_type in {"image", "media", "font"}
                    else route.continue_(),
                )

            # AIRBAG: catch navigation errors
            try:
                _nav = await page.goto(req.url, wait_until="domcontentloaded", timeout=120000)
                await chain_check(_nav, page)
                await page.wait_for_timeout(2500)
            except Exception as e:
                return {
                    "title": "I2P Network Error",
                    "final_url": req.url,
                    "text": f"I2P site currently unreachable or router not yet synced. Detail: {e}",
                }

            if req.js_enabled:
                try:
                    await page.evaluate(COOKIE_KILLER_JS)
                except Exception as e:
                    print(f"[warn] Cookie killer failed: {e}")

            await chain_check(None, page)
            result = {"title": await page.title(), "final_url": page.url}
            if req.extract_text:
                result["text"] = pulisci_testo(await page.content())

            return result
        finally:
            if browser is not None:
                try:
                    await browser.close()
                except Exception:
                    pass


@app.get("/health")
async def health():
    return {"status": "ok"}
