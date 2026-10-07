"""
title: Darknet (Tor + I2P)
description: Cerca e legge su Tor (.onion) e I2P (.i2p). Include ricerca web anonima via DuckDuckGo e Ahmia.
author: NeoPC
version: 2.0.0
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
        usando DuckDuckGo HTML (non-JavaScript). Restituisce risultati
        di ricerca per il web accessibile via Tor.

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
        Cerca specificamente su siti .onion (servizi nascosti Tor) usando Ahmia.
        Usa l'accesso clearnet di Ahmia (piu' affidabile dell'accesso .onion
        che richiede un token di sessione che cambia).

        :param query: Termine di ricerca.
        """
        encoded = quote(query)
        search_url = f"https://ahmia.fi/search/?q={encoded}"
        result = await self._post_http({"url": search_url})
        return "[TOR ONION SEARCH | Ahmia clearnet] " + self._format(result)

    async def search_onion_torch(self, query: str) -> str:
        """
        Cerca su siti .onion usando Torch (indice piu' ampio di Ahmia,
        meno filtrato ma con piu' spam). Fallback se Ahmia non basta.

        :param query: Termine di ricerca.
        """
        encoded = quote(query)
        search_url = (
            "http://xmh57jrknzkhv6y3ls3ubitzfqnkrwxhopf5aygthi7d6rplyvk3noyd.onion"
            f"/cgi-bin/omega/omega?P={encoded}"
        )
        result = await self._post(
            self.tor_url,
            {"url": search_url, "js_enabled": False, "block_media": True},
        )
        return "[TOR ONION SEARCH | Torch] " + self._format(result)


    # ============================================================
    # RICERCA SU I2P
    # ============================================================

    # RICERCA SU I2P
    # ============================================================

    async def search_i2p(self, query: str) -> str:
        """
        Cerca su eepsite I2P. Prova Ahmia (gateway clearnet) + Legwork (I2P nativo).
        Nota: I2P ha pochi motori di ricerca, i risultati possono essere scarsi.

        :param query: Termine di ricerca.
        """
        encoded = quote(query)
        results = []

        # 1. Ahmia I2P gateway (clearnet)
        try:
            ahmia_url = f"https://ahmia.fi/i2p/search/?q={encoded}"
            r1 = await self._post_http({"url": ahmia_url})
            if r1 and not r1.get("error") and len(r1.get("text", "")) > 200:
                results.append("--- Ahmia I2P ---\n" + self._format(r1))
        except Exception:
            pass

        # 2. Legwork (I2P nativo via browser-i2p)
        try:
            legwork_url = f"http://legwork.i2p/search/?q={encoded}"
            r2 = await self._post(
                self.i2p_url,
                {"url": legwork_url, "js_enabled": False, "block_media": True},
            )
            if r2 and not r2.get("error") and len(r2.get("text", "")) > 200:
                results.append("--- Legwork I2P ---\n" + self._format(r2))
        except Exception:
            pass

        if not results:
            return "[I2P SEARCH] Nessun risultato (motori I2P spesso offline, riprova)"

        return "[I2P SEARCH | " + str(len(results)) + " motori]\n\n" + "\n\n".join(results)


    # ============================================================
    # LETTURA PAGINE
    # ============================================================

    # LETTURA PAGINE
    # ============================================================

    async def read_tor(self, url: str, js_enabled: bool = False) -> str:
        """
        Legge una pagina tramite rete Tor. Usa questo per siti .onion o quando
        l'utente chiede esplicitamente la massima anonimita'.

        :param url: URL completo (.onion o clearnet).
        :param js_enabled: True attiva JavaScript (compatibilita'). False per
                           massima sicurezza e anti-fingerprinting. Default False.
        """
        result = await self._post(
            self.tor_url,
            {"url": url, "js_enabled": js_enabled, "block_media": True},
        )
        prefix = "[TOR] " if js_enabled else "[TOR | JS OFF] "
        return prefix + self._format(result)

    async def read_i2p(self, url: str, js_enabled: bool = False) -> str:
        """
        Legge un eepsite I2P (.i2p). JavaScript disabilitato di default per
        sicurezza (I2P e' intrinsecamente lento e ostile agli script).

        :param url: URL completo .i2p.
        :param js_enabled: True per attivare JavaScript (sconsigliato).
                           Default False.
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
