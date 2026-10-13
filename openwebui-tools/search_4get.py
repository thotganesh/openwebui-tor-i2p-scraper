"""
title: 4get Search
description: Ricerca web multi-engine tramite 4get (Google, Brave, DDG, Startpage) con fallback SearXNG
author: NeoPC
version: 1.0.0
required_open_webui_version: 0.3.0
"""
import httpx


class Tools:
    def __init__(self):
        self.fourget_url = "http://fourget:80/api/v1/web"
        self.searxng_url = "http://searxng:8080/search"

    async def search_4get(
        self,
        query: str,
        max_results: int = 8,
        engine: str = "auto",
    ) -> str:
        """
        Cerca sul web tramite 4get (Google, Brave, DDG, Startpage) e fallback su SearXNG.
        :param query: Cosa cercare.
        :param max_results: Numero massimo di risultati.
        :param engine: Motore 4get (google, brave, ddg, startpage). Default auto.
        """
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                r = await client.get(
                    self.fourget_url,
                    params={"s": query, "scraper": engine},
                )
                r.raise_for_status()
                data = r.json()
                results = data.get("web", [])[:max_results]
                if results:
                    out = []
                    for i, res in enumerate(results, 1):
                        out.append(
                            f"{i}. {res.get('title')}\n"
                            f"   {res.get('url')}\n"
                            f"   {(res.get('description') or '')[:250]}"
                        )
                    return "\n".join(out)
            except Exception:
                pass

            try:
                r = await client.get(
                    self.searxng_url,
                    params={"q": query, "format": "json", "language": "it-IT"},
                )
                r.raise_for_status()
                data = r.json()
                results = data.get("results", [])[:max_results]
                out = []
                for i, res in enumerate(results, 1):
                    out.append(
                        f"{i}. {res.get('title')}\n"
                        f"   {res.get('url')}\n"
                        f"   {(res.get('content') or '')[:250]}"
                    )
                return "\n".join(out) or "Nessun risultato."
            except Exception as e:
                return f"Errore ricerca: {e}"
