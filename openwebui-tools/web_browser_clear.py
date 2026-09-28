"""
title: Web Browser (Clear)
description: Naviga siti web normali tramite browser headless Chromium con stealth anti-detection
"""
import httpx

class Tools:
    def __init__(self):
        self.base_url = "http://browser-clear:8080"

    async def browse_web(self, url: str) -> str:
        """
        Naviga una pagina web normale ed estrae il testo.
        :param url: URL completo da visitare (es. https://example.com)
        """
        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.post(f"{self.base_url}/browse", json={"url": url})
            data = r.json()
            return f"Titolo: {data.get('title')}\nURL finale: {data.get('final_url')}\n\n{data.get('text', '')[:4000]}"
