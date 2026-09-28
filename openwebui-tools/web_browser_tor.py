"""
title: Web Browser (Tor/Anonymous)
description: Naviga siti .onion o normali in forma completamente anonima tramite rete Tor (Snowflake)
"""
import httpx

class Tools:
    def __init__(self):
        self.base_url = "http://browser-tor:8081"

    async def browse_tor(self, url: str) -> str:
        """
        Naviga una pagina web (anche .onion) tramite la rete Tor per anonimato completo.
        :param url: URL completo da visitare, incluso indirizzi .onion
        """
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(f"{self.base_url}/browse", json={"url": url})
            data = r.json()
            return f"Titolo: {data.get('title')}\nURL finale: {data.get('final_url')}\n\n{data.get('text', '')[:4000]}"
