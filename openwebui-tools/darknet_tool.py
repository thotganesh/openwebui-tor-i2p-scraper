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
        Cerca su siti .onion usando Ahmia (clearnet) con gestione del token rotante.
        Usa un User-Agent browser reale per evitare il blocco di Ahmia.
        """
        import re
        from urllib.parse import urlencode

        encoded = quote(query)
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }

        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=headers) as client:
                home = await client.get("https://ahmia.fi/")
                home_html = home.text

                # Estrazione atomica: name e value dallo stesso tag <input>
                m = re.search(
                    r'<input[^>]*type="hidden"[^>]*name="([0-9a-f]+)"[^>]*value="([0-9a-f]+)"',
                    home_html,
                )
                if m:
                    token_name, token_value = m.group(1), m.group(2)
                else:
                    # Fallback: ordine attributi invertito
                    m2 = re.search(
                        r'<input[^>]*type="hidden"[^>]*value="([0-9a-f]+)"[^>]*name="([0-9a-f]+)"',
                        home_html,
                    )
                    if m2:
                        token_value, token_name = m2.group(1), m2.group(2)
                    else:
                        token_name, token_value = None, None

                if not token_name or not token_value:
                    return "[TOR ONION SEARCH | Ahmia] Token non trovato. Riprova con search_onion_tor66."

                search_url = f"https://ahmia.fi/search/?q={encoded}&" + urlencode({token_name: token_value})
                r = await client.get(
                    search_url,
                    headers={"Referer": "https://ahmia.fi/"},
                )

                html = r.text
                onion_urls = re.findall(r'redirect_url=(http://[a-z0-9]+\.onion[^"&\s]*)', html)

                if onion_urls:
                    seen = set()
                    unique = []
                    for u in onion_urls:
                        if u not in seen:
                            seen.add(u)
                            unique.append(u)

                    out = [f"**Risultati Ahmia per:** {query} ({len(unique)} trovati)\n"]
                    for i, u in enumerate(unique[:15], 1):
                        out.append(f"{i}. {u}")
                    out.append("\n**Nota:** per leggere usa read_tor.")
                    return "[TOR ONION SEARCH | Ahmia] " + "\n".join(out)

                if "No results" in html or "did not match" in html:
                    return f"[TOR ONION SEARCH | Ahmia] Nessun risultato per: {query}"

                return f"[TOR ONION SEARCH | Ahmia] Nessun risultato (HTML len: {len(html)}). Prova search_onion_tor66."

        except Exception as e:
            return f"[TOR ONION SEARCH | Ahmia] Errore: {e}"

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
