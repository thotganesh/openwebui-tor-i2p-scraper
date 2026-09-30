import asyncio
from fastapi import FastAPI
from pydantic import BaseModel
from playwright.async_api import async_playwright
from readability import Document
import html2text

app = FastAPI()

class BrowseRequest(BaseModel):
    url: str
    extract_text: bool = True
    block_media: bool = True
    js_enabled: bool = True

# i2pd espone il proxy HTTP sulla porta 4444
I2P_PROXY = {"server": "http://i2p-proxy:4444"}

FIREFOX_PREFS = {
    "media.peerconnection.enabled": False,
    "network.dns.disablePrefetch": True,
    "network.prefetch-next": False,
    "geo.enabled": False,
    "privacy.resistFingerprinting": True,
    "webgl.disabled": True,
    "dom.battery.enabled": False,
    "device.sensors.enabled": False,
}

COOKIE_KILLER_JS = """
async () => {
    const KNOWN_CMP_SELECTORS = [
        '#onetrust-banner-sdk', '.cc-window', '.qc-cmp2-container',
        '[class*="cookie-banner"]', '[id*="cookie-consent"]'
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
        doc = Document(html_content)
        testo = h.handle(doc.summary()).strip()
        if testo: return testo
    except Exception:
        pass
    try:
        return h.handle(html_content).strip()
    except Exception as e:
        return f"Errore estrazione: {e}"

@app.post("/browse")
async def browse(req: BrowseRequest):
    async with async_playwright() as p:
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
        page = await context.new_page()

        if req.block_media:
            await page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,mp4,webm}", lambda route: route.abort())

        # --- AIRBAG: Blocco try/except per gestire i siti offline o I2P non sincronizzato ---
        try:
            await page.goto(req.url, wait_until="domcontentloaded", timeout=120000)
            await page.wait_for_timeout(2500)
        except Exception as e:
            await browser.close()
            return {
                "title": "Errore di Rete I2P", 
                "final_url": req.url, 
                "text": f"Sito I2P attualmente irraggiungibile o router I2P non ancora sincronizzato. Dettaglio: {e}"
            }
        
        # Se il JS è abilitato, puliamo i popup
        if req.js_enabled:
            try:
                await page.evaluate(COOKIE_KILLER_JS)
            except Exception as e:
                print(f"[warn] Failed to execute Cookie Killer: {e}")

        result = {"title": await page.title(), "final_url": page.url}
        if req.extract_text:
            result["text"] = pulisci_testo(await page.content())

        await browser.close()
        return result
