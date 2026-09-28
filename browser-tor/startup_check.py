import asyncio
import sys
from playwright.async_api import async_playwright

TOR_PROXY = {"server": "socks5://tor-proxy:9150"}

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

async def main():
    print("[startup-check] Verifica configurazione WebRTC di produzione...", flush=True)
    async with async_playwright() as p:
        browser = await p.firefox.launch(
            headless=True,
            proxy=TOR_PROXY,
            firefox_user_prefs=FIREFOX_PREFS,
        )
        page = await (await browser.new_context()).new_page()
        await page.goto("data:text/html,<html><body></body></html>")
        result = await page.evaluate(WEBRTC_LEAK_SCRIPT)
        await browser.close()

    if result == "DISABLED":
        print("[startup-check] OK: RTCPeerConnection non disponibile, nessun rischio leak.", flush=True)
        sys.exit(0)

    if isinstance(result, list) and len(result) > 0:
        print(f"[startup-check] ERRORE CRITICO: WebRTC leak rilevato! IP esposti: {result}", flush=True)
        print("[startup-check] Il container NON si avvia per motivi di sicurezza.", flush=True)
        sys.exit(1)

    print("[startup-check] OK: nessun leak rilevato.", flush=True)
    sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
