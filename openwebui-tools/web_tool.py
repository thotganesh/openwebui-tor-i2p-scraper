"""
title: Web (Search + Reader)
description: Cerca su internet (SearXNG) e legge qualsiasi pagina web normale. Sceglie automaticamente il metodo piu' veloce.
author: NeoPC
version: 1.0.0
required_open_webui_version: 0.3.0
"""

import httpx


class Tools:
    def __init__(self):
        self.searxng_url = "http://searxng:8080"
        self.http_url = "http://browser-http:8084"
        self.clear_url = "http://browser-clear:8080"

    # ============================================================
    # RICERCA WEB
    # ============================================================

    async def search_web(self, query: str, num: int = 5) -> str:
        """
        Cerca su internet usando SearXNG (aggregatore di Google, Bing, DuckDuckGo,
        Brave, Wikipedia, Qwant). Restituisce titolo, estratto e URL dei risultati.

        Usa questo quando l'utente chiede di cercare, trovare o sapere qualcosa
        su internet. Dopo aver ottenuto gli URL, usa read_web per leggere le
        pagine interessanti.

        :param query: Termine di ricerca (es. "ultime notizie intelligenza artificiale").
        :param num: Numero massimo di risultati (default 5, max 10).
        """
        num = min(max(num, 1), 10)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(
                    f"{self.searxng_url}/search",
                    params={
                        "q": query,
                        "format": "json",
                        "language": "it-IT",
                        "safesearch": 0,
                    },
                )
                data = r.json()
                results = data.get("results", [])[:num]

                if not results:
                    return f"Nessun risultato trovato per: {query}"

                out = [f"**Risultati per:** {query}\n"]
                for i, item in enumerate(results, 1):
                    title = item.get("title", "Senza titolo")
                    content = item.get("content", "")[:300]
                    url = item.get("url", "")
                    engine = item.get("engine", "")
                    out.append(
                        f"{i}. **{title}**\n"
                        f"   {content}\n"
                        f"   URL: {url}\n"
                        f"   (fonte: {engine})"
                    )

                return "\n\n".join(out)

        except Exception as e:
            return f"Errore durante la ricerca: {str(e)}"

    # ============================================================
    # LETTURA PAGINE WEB
    # ============================================================

    async def read_web(self, url: str) -> str:
        """
        Legge una pagina web normale (http/https). Prova prima HTTP veloce
        (curl_cffi con impersonificazione TLS), poi browser completo se il
        contenuto e' troppo corto o c'e' un errore.

        USA QUESTA per la maggior parte dei siti.

        :param url: URL completo da visitare (es. https://example.com).
        """
        # Tentativo 1: HTTP veloce
        result = await self._post(self.http_url, {"url": url})

        if not result or result.get("error"):
            return await self.read_web_full(url)

        text = result.get("text", "")
        if len(text) < 200:
            # Sospetto JS-only o challenge
            return await self.read_web_full(url)

        return self._format(result)

    async def read_web_full(self, url: str) -> str:
        """
        Legge una pagina web usando un browser completo (Playwright con stealth
        e fallback automatico a Solverr per Cloudflare/Turnstile).

        USA QUESTA se read_web fallisce, se la pagina richiede JavaScript, o
        se sospetti Cloudflare/Turnstile.

        :param url: URL completo da visitare (es. https://example.com).
        """
        result = await self._post(self.clear_url, {"url": url})
        return self._format(result)

    # ============================================================
    # HELPER INTERNI
    # ============================================================

    async def _post(self, base_url: str, payload: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=150) as client:
                r = await client.post(f"{base_url}/browse", json=payload)
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
