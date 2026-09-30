import os
import asyncio
import socket
from fastapi import FastAPI
from pydantic import BaseModel
from playwright.async_api import async_playwright
from stem import Signal
from stem.control import Controller
from readability import Document
import html2text

app = FastAPI()

class BrowseRequest(BaseModel):
    url: str
    wait_selector: str | None = None
    extract_text: bool = True
    block_media: bool = True
    js_enabled: bool = True

TOR_PROXY = {"server": "socks5://tor-proxy:9150"}
CONTROL_PASSWORD = os.environ.get("TOR_CONTROL_PASSWORD")

FIREFOX_PREFS = {
    "media.peerconnection.enabled": False,
    "network.dns.disablePrefetch": True,
    "network.prefetch-next": False,
    "geo.enabled": False,
    "privacy.resistFingerprinting": True,
    "privacy.resistFingerprinting.letterboxing": True,
    "privacy.spoof_english": 2,
    "webgl.disabled": True,
    "dom.battery.enabled": False,
    "device.sensors.enabled": False,
    "media.navigator.enabled": False,
}

FIREFOX_PREFS_WEBRTC_TEST = dict(FIREFOX_PREFS)
FIREFOX_PREFS_WEBRTC_TEST["media.peerconnection.enabled"] = True

WEBRTC_LEAK_SCRIPT = """
async () => {
    if (typeof RTCPeerConnection === "undefined") return "DISABLED";
    return new Promise((resolve) => {
        const ips = new Set();
        const pc = new RTCPeerConnection({iceServers: [{urls: "stun:stun.l.google.com:19302"}]});
        pc.createDataChannel("");
        pc.onicecandidate = (e) => {
            if (!e.candidate) { resolve([...ips]); pc.close(); return; }
            const match = e.candidate.candidate.match(/(\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3})/);
            if (match) ips.add(match[1]);
        };
        pc.createOffer().then(o => pc.setLocalDescription(o));
        setTimeout(() => { resolve([...ips]); pc.close(); }, 5000);
    });
}
"""

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

def request_new_circuit():
    try:
        tor_proxy_ip = socket.gethostbyname("tor-proxy")
        with Controller.from_port(address=tor_proxy_ip, port=9151) as controller:
            controller.authenticate(password=CONTROL_PASSWORD)
            controller.signal(Signal.NEWNYM)
            print(f"[info] Nuovo circuito richiesto con successo (via {tor_proxy_ip})")
    except Exception as e:
        print(f"[warn] Impossibile richiedere nuovo circuito: {e}")

def pulisci_testo(html_content: str) -> str:
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True 
    h.body_width = 0
    
    try:
        doc = Document(html_content)
        testo_pulito = h.handle(doc.summary()).strip()
        if testo_pulito:
            return testo_pulito
    except Exception:
        pass
        
    try:
        return h.handle(html_content).strip()
    except Exception as e:
        return f"Errore nell'estrazione del testo: {e}"

@app.post("/browse")
async def browse(req: BrowseRequest):
    request_new_circuit()
    await asyncio.sleep(1)

    async with async_playwright() as p:
        browser = await p.firefox.launch(
            headless=True,
            proxy=TOR_PROXY,
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

        await page.goto(req.url, wait_until="domcontentloaded", timeout=90000)
        
        await page.wait_for_timeout(2500)

        # Only execute the Cookie Killer if JS is enabled!
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

@app.get("/webrtc-leak-check")
async def webrtc_leak_check():
    async with async_playwright() as p:
        browser = await p.firefox.launch(
            headless=True,
            proxy=TOR_PROXY,
            firefox_user_prefs=FIREFOX_PREFS_WEBRTC_TEST,
        )
        page = await (await browser.new_context()).new_page()
        await page.goto("data:text/html,<html><body></body></html>")
        leaked_ips = await page.evaluate(WEBRTC_LEAK_SCRIPT)
        await browser.close()
        return {
            "note": "Test con WebRTC volutamente riabilitato. In produzione (/browse) resta sempre disattivato.",
            "leaked_ips": leaked_ips,
            "leak_detected": len(leaked_ips) > 0,
        }

@app.get("/health")
async def health():
    return {"status": "ok"}
