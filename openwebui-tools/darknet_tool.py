"""
title: Darknet (Tor + I2P)
description: Cerca e legge su Tor (.onion) e I2P (.i2p). Include ricerca web anonima via DuckDuckGo, Ahmia e Tor66.
author: NeoPC
version: 3.1.0
required_open_webui_version: 0.3.0
"""

import re
import httpx
from urllib.parse import quote, urlencode


class Tools:
    def __init__(self):
        self.tor_url = "http://browser-tor:8081"
        self.i2p_url = "http://browser-i2p:8083"
        self.http_url = "http://browser-http:8084"

    # ============================================================
    # RICERCA SU TOR
    # ============================================================

    async def search_web_tor(self, query: str) -> str:
        """Cerca sul web normale in modo anonimo tramite Tor (DuckDuckGo HTML)."""
        encoded = quote(query)
        search_url = (
            "https://duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion/html"
            f"?q={encoded}"
        )
        result = await self._post(
            self.tor_url,
            {"url": search_url, "js_enabled": False, "block_media": True},
        )
        return "[TOR SEARCH | DuckDuckGo HTML] " + self._format(result)

    async def search_onion(self, query: str) -> str:
        """
        Cerca su siti .onion usando Ahmia (clearnet).
        Gestisce il sistema di token rotanti di Ahmia recuperando il token
        dalla home page prima di ogni ricerca.
        """
        encoded = quote(query)
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                home = await client.get("https://ahmia.fi/")
                home_html = home.text

                token_match = re.search(
                    r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]+)"',
                    home_html,
                )
                token_name = token_match.group(1) if token_match else None
                token_value = token_match.group(2) if token_match else None

                search_url = f"https://ahmia.fi/search/?q={encoded}"
                if token_name and token_value:
                    search_url += "&" + urlencode({token_name: token_value})

                r = await client.get(
                    search_url,
                    headers={"Referer": "https://ahmia.fi/"},
                )

                html = r.text
                results = re.findall(
                    r'<a[^>]*href="[^"]*redirect_url=([^"&]+)[^"]*"[^>]*>(.*?)</a>',
                    html,
                    re.DOTALL,
                )
                if results:
                    out = ["**Risultati Ahmia per:** " + query + "\n"]
                    for i, (onion_url, title) in enumerate(results[:10], 1):
                        clean_title = re.sub(r"<[^>]+>", "", title).strip()
                        out.append(str(i) + ". " + clean_title + "\n   http://" + onion_url)
                    return "[TOR ONION SEARCH | Ahmia] " + "\n\n".join(out)

                return "[TOR ONION SEARCH | Ahmia] " + html[:6000]

        except Exception as e:
            return "[TOR ONION SEARCH | Ahmia] Errore: " + str(e)

    async def search_onion_tor66(self, query: str) -> str:
        """Cerca su siti .onion usando Tor66 (directory di link freschi, no JS)."""
        encoded = quote(query)
        search_url = (
            "http://tor66sewebgixwhcqfnp5inzp5x5uohhdy3kvtnyfxc2e5mxiuh34iid.onion"
            f"/search?q={encoded}"
        )
        result = await self._post(
            self.tor_url,
            {"url": search_url, "js_enabled": False, "block_media": True},
        )
        return "[TOR ONION SEARCH | Tor66] " + self._format(result)

    # ============================================================
    # RICERCA SU I2P
    # ============================================================

    async def search_i2p(self, query: str) -> str:
        """Cerca su eepsite I2P usando Legwork."""
        encoded = quote(query)
        legwork_url = f"http://legwork.i2p/search/?q={encoded}"
        result = await self._post(
            self.i2p_url,
            {"url": legwork_url, "js_enabled": False, "block_media": True},
        )
        return "[I2P SEARCH | Legwork] " + self._format(result)

    # ============================================================
    # LETTURA PAGINE
    # ============================================================

    async def read_tor(self, url: str, js_enabled: bool = False) -> str:
        """Legge una pagina tramite rete Tor."""
        result = await self._post(
            self.tor_url,
            {"url": url, "js_enabled": js_enabled, "block_media": True},
        )
        prefix = "[TOR] " if js_enabled else "[TOR | JS OFF] "
        return prefix + self._format(result)

    async def read_i2p(self, url: str, js_enabled: bool = False) -> str:
        """Legge un eepsite I2P (.i2p)."""
        result = await self._post(
            self.i2p_url,
            {"url": url, "js_enabled": js_enabled, "block_media": True},
        )
        prefix = "[I2P] " if js_enabled else "[I2P | JS OFF] "
        return prefix + self._format(result)

    # ============================================================
    # HELPER INTERNI
    # ============================================================

    async def _post(self, base_url: str, payload: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=200) as client:
                r = await client.post(f"{base_url}/browse", json=payload)
                return r.json()
        except Exception as e:
            return {"error": str(e), "text": "", "title": ""}

    async def _post_http(self, payload: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(f"{self.http_url}/browse", json=payload)
                return r.json()
        except Exception as e:
            return {"error": str(e), "text": "", "title": ""}

    def _format(self, data: dict) -> str:
        if not data:
            return "Errore: nessuna risposta dal servizio."
        if data.get("error"):
            return "Errore: " + str(data["error"])
        title = data.get("title", "Senza titolo")
        url = data.get("final_url", "")
        text = data.get("text", "")
        if not text:
            return "Titolo: " + title + "\nURL: " + url + "\n\nNessun contenuto estratto."
        return "Titolo: " + title + "\nURL finale: " + url + "\n\n" + text[:6000]
