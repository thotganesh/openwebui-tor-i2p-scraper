"""
title: Darknet (Tor + I2P)
description: Cerca e legge su Tor (.onion) e I2P (.i2p). Include ricerca web anonima via DuckDuckGo e Ahmia.
author: NeoPC
version: 3.0.0
required_open_webui_version: 0.3.0
"""

import httpx
from urllib.parse import quote


class Tools:
    def __init__(self):
        self.tor_url = "http://browser-tor:8081"
        self.i2p_url = "http://browser-i2p:8083"
        self.http_url = "http://browser-http:8084"

    # ============================================================
    # RICERCA SU TOR
    # ============================================================

    async def search_web_tor(self, query: str) -> str:
        """
        Cerca sul web normale (clearnet) in modo anonimo tramite Tor,
        usando DuckDuckGo HTML (non-JavaScript).

        :param query: Termine di ricerca.
        """
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
        Cerca specificamente su siti .onion usando Ahmia (clearnet + API JSON).
        Questo e' il motore piu' affidabile e filtrato.

        :param query: Termine di ricerca.
        """
        encoded = quote(query)
        search_url = f"https://ahmia.fi/search/?q={encoded}&format=json"
        result = await self._post_http({"url": search_url})
        if result and result.get("error"):
            search_url = f"https://ahmia.fi/search/?q={encoded}"
            result = await self._post_http({"url": search_url})
        return "[TOR ONION SEARCH | Ahmia] " + self._format(result)

    async def search_onion_tor66(self, query: str) -> str:
        """
        Cerca su siti .onion usando Tor66 (directory di link freschi, no JS).
        Usare come fallback se Ahmia non basta, per trovare servizi appena emersi.

        :param query: Termine di ricerca.
        """
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
        """
        Cerca su eepsite I2P usando Legwork (motore nativo I2P).
        Nota: I2P ha pochissimi motori di ricerca, i risultati sono scarsi.

        :param query: Termine di ricerca.
        """
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
        """
        Legge una pagina tramite rete Tor.

        :param url: URL completo (.onion o clearnet).
        :param js_enabled: True attiva JavaScript. Default False.
        """
        result = await self._post(
            self.tor_url,
            {"url": url, "js_enabled": js_enabled, "block_media": True},
        )
        prefix = "[TOR] " if js_enabled else "[TOR | JS OFF] "
        return prefix + self._format(result)

    async def read_i2p(self, url: str, js_enabled: bool = False) -> str:
        """
        Legge un eepsite I2P (.i2p).

        :param url: URL completo .i2p.
        :param js_enabled: True attiva JavaScript. Default False.
        """
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
            return f"Errore: {data['error']}"
        title = data.get("title", "Senza titolo")
        url = data.get("final_url", "")
        text = data.get("text", "")
        if not text:
            return f"Titolo: {title}\nURL: {url}\n\nNessun contenuto estratto."
        return f"Titolo: {title}\nURL finale: {url}\n\n{text[:6000]}"
