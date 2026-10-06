from fastapi import FastAPI
from pydantic import BaseModel
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from readability import Document
import html2text
import httpx
import re

app = FastAPI()

SOLVERR_URL = "http://solverr:8191/v1"


class BrowseRequest(BaseModel):
    url: str
    wait_selector: str | None = None
    extract_text: bool = True
    block_media: bool = True


# ============================================================
# COOKIE KILLER ESTESO
# ============================================================
COOKIE_KILLER_JS = """
async () => {
    const CMP_SELECTORS = [
        // OneTrust
        '#onetrust-banner-sdk', '#onetrust-consent-sdk',
        // Cookiebot
        '#cookiebot', '#CybotCookiebotDialog', '#CybotCookiebotDialogBodyUnderlay',
        // Quantcast
        '.qc-cmp2-container', '#qc-cmp2-container',
        // TrustArc
        '#truste-consent-track', '.truste_box_overlay', '.truste_overlay',
        // Generic
        '.cc-window', '.fc-consent-root', '#cookie-notice',
        '.paywall', '[class*="cookie-banner"]', '[id*="cookie-consent"]',
        // Iubenda (Repubblica, Corriere, GEDI)
        '#iubenda-cs-banner', '.iubenda-cs-container', '.iubenda-cs-visible',
        '[class*="iubenda"]', 'iframe[src*="iubenda"]',
        // Didomi (molti giornali italiani)
        '#didomi-host', '#didomi-notice', '.didomi-popup-backdrop',
        '.didomi-notice-popup', '[class*="didomi"]',
        // Complianz
        '.cmplz-cookiebanner', '.cmplz-manage-consent',
        // CookieYes
        '.cky-consent-container', '.cky-modal',
        // GDPR Cookie Consent
        '.cli-modal-backdrop', '#cookie-law-info-bar',
        // Termly
        '.termly-cookie-policy', '#termly-code-snippet-support',
        // Klaro
        '.klaro .cookie-modal', '.klaro .cookie-notice',
        // CCPA
        '#ccpa-banner', '#ccpa-notice',
        // Funding Choices (Google)
        '.fc-consent-root', '.fc-dialog-overlay',
        // Other
        '#gdpr-banner', '.gdpr-banner', '#cookie-law-info-bar',
    ];

    // 1. Nascondi (display:none) invece di rimuovere, per evitare anti-tamper
    CMP_SELECTORS.forEach(sel => {
        document.querySelectorAll(sel).forEach(el => {
            el.style.setProperty('display', 'none', 'important');
            el.style.setProperty('visibility', 'hidden', 'important');
            el.style.setProperty('opacity', '0', 'important');
            el.style.setProperty('pointer-events', 'none', 'important');
        });
    });

    // 2. Sblocca lo scroll (molti CMP lo bloccano)
    document.documentElement.style.setProperty('overflow', 'auto', 'important');
    document.body.style.setProperty('overflow', 'auto', 'important');
    document.body.style.setProperty('position', 'static', 'important');
    document.body.style.setProperty('height', 'auto', 'important');

    // 3. Rimuovi backdrop/overlay generici (position:fixed + z-index alto)
    document.querySelectorAll('body > div, body > aside, body > section').forEach(el => {
        try {
            const s = window.getComputedStyle(el);
            const z = parseInt(s.zIndex) || 0;
            if (s.position === 'fixed' && z > 1000 && el.offsetHeight > window.innerHeight * 0.5) {
                el.style.setProperty('display', 'none', 'important');
            }
        } catch (e) { /* ignore */ }
    });

    // 4. Rimuovi eventuali iframe CMP
    document.querySelectorAll('iframe').forEach(iframe => {
        const src = (iframe.src || '').toLowerCase();
        if (src.includes('iubenda') || src.includes('didomi') || src.includes('onetrust') ||
            src.includes('cookiebot') || src.includes('consent')) {
            iframe.style.setProperty('display', 'none', 'important');
        }
    });

    return 'cookie-killer: done';
}
"""


# ============================================================
# RILEVAMENTO CHALLENGE
# ============================================================
def is_challenge_page(html: str, title: str) -> bool:
    indicators = [
        "just a moment",
        "checking your browser",
        "verify you are human",
        "cf-chl",
        "turnstile",
        "attention required",
        "enable javascript and cookies to continue",
    ]
    combined = (html + (title or "")).lower()
    return any(ind in combined for ind in indicators)


# ============================================================
# RILEVAMENTO BANNER CMP RESIDUO
# ============================================================
def is_cookie_banner(text: str) -> bool:
    """Euristica: se il testo sembra un banner cookie invece di contenuto reale."""
    if len(text) > 3000:
        return False
    lower = text.lower()
    indicators = [
        "consenso all'utilizzo di cookie",
        "cookie policy",
        "finalità diverse da quelle strettamente necessarie",
        "pannello delle preferenze pubblicitarie",
        "rifiuta e abbonati",
        "accetta e chiudi",
        "gestione cookie",
        "we use cookies",
        "accept all cookies",
    ]
    hits = sum(1 for ind in indicators if ind in lower)
    return hits >= 2


# ============================================================
# SOLVERR
# ============================================================
async def solve_with_solverr(url: str) -> str:
    async with httpx.AsyncClient(timeout=90) as client:
        try:
            r = await client.post(
                SOLVERR_URL,
                json={"cmd": "request.get", "url": url, "maxTimeout": 60000},
            )
            data = r.json()
            if data.get("status") == "ok":
                return data.get("solution", {}).get("response", "")
        except Exception:
            pass
    return ""


# ============================================================
# ESTRAZIONE TESTO
# ============================================================
def pulisci_testo(html_content: str) -> str:
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True
    h.body_width = 0

    try:
        doc = Document(html_content)
        testo_pulito = h.handle(doc.summary()).strip()
        if testo_pulito and len(testo_pulito) > 200:
            return testo_pulito
    except Exception:
        pass

    try:
        return h.handle(html_content).strip()
    except Exception as e:
        return f"Errore nell'estrazione del testo: {e}"


# ============================================================
# ENDPOINT PRINCIPALE
# ============================================================
@app.post("/browse")
async def browse(req: BrowseRequest):
    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="it-IT",
        )
        page = await context.new_page()

        if req.block_media:
            await page.route(
                "**/*.{png,jpg,jpeg,gif,svg,woff,woff2,mp4,webm}",
                lambda route: route.abort(),
            )

        html = ""
        title = ""
        try:
            await page.goto(req.url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(2500)

            # Cookie killer (1a passata)
            await page.evaluate(COOKIE_KILLER_JS)

            # Seconda passata dopo un breve delay (alcuni CMP riappaiono)
            await page.wait_for_timeout(1000)
            await page.evaluate(COOKIE_KILLER_JS)

            html = await page.content()
            title = await page.title()
        except Exception as e:
            await browser.close()
            return {
                "title": "",
                "final_url": req.url,
                "text": "",
                "error": f"Errore Playwright: {e}",
            }

        await browser.close()

        # Fallback Solverr se challenge rilevata
        if is_challenge_page(html, title):
            solverr_html = await solve_with_solverr(req.url)
            if solverr_html:
                html = solverr_html
                try:
                    doc = Document(html)
                    title = doc.title() or title
                except Exception:
                    pass
            else:
                return {
                    "title": title,
                    "final_url": req.url,
                    "text": "",
                    "error": "Challenge rilevata ma Solverr non ha risolto",
                }

        result = {"title": title, "final_url": req.url}
        if req.extract_text:
            text = pulisci_testo(html)

            # Se il testo sembra un banner CMP residuo, ritenta con Solverr
            if is_cookie_banner(text):
                solverr_html = await solve_with_solverr(req.url)
                if solverr_html:
                    text2 = pulisci_testo(solverr_html)
                    if len(text2) > len(text):
                        text = text2
                        try:
                            doc = Document(solverr_html)
                            title = doc.title() or title
                        except Exception:
                            pass

            result["text"] = text

        return result


@app.get("/health")
async def health():
    return {"status": "ok"}
