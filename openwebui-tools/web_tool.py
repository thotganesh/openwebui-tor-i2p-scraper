"""
title: Web (Search + Reader)
description: Cerca su internet (SearXNG) e legge qualsiasi pagina web normale. Sceglie automaticamente il metodo piu' veloce.
author: NeoPC
version: 1.1.0
required_open_webui_version: 0.3.0
"""

import httpx


class Tools:
    def __init__(self):
        self.searxng_url = "http://searxng:8080"
        self.http_url = "http://browser-http:8084"
        self.clear_url = "http://browser-clear:8080"
        self.camoufox_url = "http://browser-camoufox:8085"

    async def search_web(self, query: str, num: int = 5) -> str:
        """
        Cerca su internet usando SearXNG (aggregatore di Google, Bing, DuckDuckGo,
        Brave, Wikipedia, Qwant). Restituisce titolo, estratto e URL dei risultati.

        :param query: Termine di ricerca.
        :param num: Numero massimo di risultati (default 5, max 10).
        """
        num = min(max(num, 1), 10)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(
                    f"{self.searxng_url}/search",
                    params={"q": query, "format": "json", "language": "it-IT", "safesearch": 0},
                )
                data = r.json()
                results = data.get("results", [])[:num]
                if not results:
                    return f"Nessun risultato trovato per: {query}"
                out = [f"**Risultati per:** {query}\n"]
                for i, item in enumerate(results, 1):
                    out.append(
                        f"{i}. **{item.get('title', 'Senza titolo')}**\n"
                        f"   {item.get('content', '')[:300]}\n"
                        f"   URL: {item.get('url', '')}\n"
                        f"   (fonte: {item.get('engine', '')})"
                    )
                return "\n\n".join(out)
        except Exception as e:
            return f"Errore durante la ricerca: {str(e)}"

    async def read_web(self, url: str) -> str:
        """
        Legge una pagina web normale. Prova prima HTTP veloce, poi browser completo
        se il contenuto e' troppo corto o c'e' un errore.

        :param url: URL completo da visitare.
        """
        result = await self._post(self.http_url, {"url": url})
        if not result or result.get("error"):
            return await self.read_web_full(url)
        if len(result.get("text", "")) < 200:
            return await self.read_web_full(url)
        return self._format(result)

    async def read_web_full(self, url: str) -> str:
        """
        Legge una pagina web usando un browser completo. Prova prima Patchright
        (Chromium stealth), poi Camoufox (Firefox anti-fingerprint) come fallback.

        USA QUESTA se read_web fallisce, se la pagina richiede JavaScript, o
        se sospetti Cloudflare/Turnstile/DataDome.

        :param url: URL completo da visitare.
        """
        # Tentativo 1: browser-clear (Patchright)
        result_clear = await self._post(self.clear_url, {"url": url})
        text_clear = result_clear.get("text", "")

        if text_clear and len(text_clear) > 5000:
            return self._format(result_clear)

        # Tentativo 2: browser-camoufox (Firefox stealth)
        result_camoufox = await self._post(self.camoufox_url, {"url": url})
        text_camoufox = result_camoufox.get("text", "")

        # Restituisci il risultato MIGLIORE
        if len(text_camoufox) > len(text_clear):
            return self._format(result_camoufox)
        return self._format(result_clear)

    async def _post(self, base_url: str, payload: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=200) as client:
                r = await client.post(f"{base_url}/browse", json=payload)
                return r.json()
        except Exception as e:
            return {"error": str(e), "text": "", "title": ""}

    def _format(self, data: dict) -> str:
        if not data:
            return "Errore: nessuna risposta dal servizio."
        if data.get("error"):
            return f"Errore: {data['error']}"
        text = data.get("text", "")
        if not text:
            return f"Titolo: {data.get('title', '')}\nURL: {data.get('final_url', '')}\n\nNessun contenuto estratto."
        return f"Titolo: {data.get('title', '')}\nURL finale: {data.get('final_url', '')}\n\n{text[:6000]}"
