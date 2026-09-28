from fastapi import FastAPI
from pydantic import BaseModel
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from readability import Document
import html2text

app = FastAPI()

class BrowseRequest(BaseModel):
    url: str
    wait_selector: str | None = None
    extract_text: bool = True
    block_media: bool = True

COOKIE_KILLER_JS = """
async () => {
    const KNOWN_CMP_SELECTORS = [
        '#onetrust-banner-sdk', '#onetrust-consent-sdk',
        '#cookiebot', '#CybotCookiebotDialog',
        '.qc-cmp2-container', '#qc-cmp2-container',
        '#truste-consent-track', '.truste_box_overlay',
        '.cc-window', '.fc-consent-root', '#cookie-notice',
        '.paywall', '[class*="cookie-banner"]', '[id*="cookie-consent"]'
    ];
    KNOWN_CMP_SELECTORS.forEach(sel => {
        document.querySelectorAll(sel).forEach(el => el.remove());
    });
    document.body.style.overflow = 'auto'; 
}
"""

def pulisci_testo(html_content: str) -> str:
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True 
    h.body_width = 0
    
    try:
        # Tentativo 1: Cerca un articolo strutturato
        doc = Document(html_content)
        testo_pulito = h.handle(doc.summary()).strip()
        if testo_pulito:
            return testo_pulito
    except Exception:
        pass
        
    try:
        # Fallback: Se è una home page/motore di ricerca, formatta tutto
        return h.handle(html_content).strip()
    except Exception as e:
        return f"Errore nell'estrazione del testo: {e}"

@app.post("/browse")
async def browse(req: BrowseRequest):
    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
        )
        page = await context.new_page()

        if req.block_media:
            await page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,mp4,webm}", lambda route: route.abort())

        await page.goto(req.url, wait_until="domcontentloaded", timeout=60000)
        
        await page.wait_for_timeout(2500) 
        await page.evaluate(COOKIE_KILLER_JS)

        result = {"title": await page.title(), "final_url": page.url}
        if req.extract_text:
            result["text"] = pulisci_testo(await page.content())

        await browser.close()
        return result

@app.get("/health")
async def health():
    return {"status": "ok"}
