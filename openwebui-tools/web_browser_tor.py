"""
title: Web Browser (Tor/Anonymous)
description: Naviga siti .onion o normali in forma completamente anonima tramite rete Tor (Snowflake). Permette il controllo del JavaScript per azzerare il fingerprinting.
"""

import httpx


class Tools:
    def __init__(self):
        self.base_url = "http://browser-tor:8081"

    async def browse_tor(
        self, url: str, js_enabled: bool = True, block_media: bool = True
    ) -> str:
        """
        Naviga una pagina web (anche .onion) tramite la rete Tor per anonimato completo.
        :param url: URL completo da visitare, incluso indirizzi .onion.
        :param js_enabled: Imposta a False per disabilitare completamente JavaScript. Da usare quando l'utente chiede la MASSIMA SICUREZZA e anti-fingerprinting.
        :param block_media: Imposta a True per bloccare immagini/video pesanti e velocizzare Tor.
        """
        async with httpx.AsyncClient(timeout=120) as client:
            try:
                r = await client.post(
                    f"{self.base_url}/browse",
                    json={
                        "url": url,
                        "js_enabled": js_enabled,
                        "block_media": block_media,
                    },
                )
                r.raise_for_status()
                data = r.json()

                # Creiamo l'etichetta visiva per capire subito se JS era acceso o spento
                status_js = (
                    "JS: OFF (Stealth/Anonymized)" if not js_enabled else "JS: ON"
                )
                text_content = data.get("text", "")[:4000]

                return f"[TOR NETWORK | {status_js}]\nTitolo: {data.get('title')}\nURL finale: {data.get('final_url')}\n\n{text_content}"
            except Exception as e:
                return f"Errore durante la navigazione Tor: {str(e)}"
