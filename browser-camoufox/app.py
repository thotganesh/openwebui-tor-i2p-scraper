from fastapi import FastAPI
from pydantic import BaseModel
from camoufox.async_api import AsyncCamoufox
from readability import Document
import html2text

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
            await page.goto(req.url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(req.wait_ms)
            try:
                await page.evaluate(COOKIE_KILLER_JS)
            except Exception:
                pass
            await page.wait_for_timeout(1500)
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
