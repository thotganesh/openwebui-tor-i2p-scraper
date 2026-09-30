"""
title: Web Browser (I2P Darknet)
description: Naviga esclusivamente la rete chiusa I2P (siti .i2p) in totale sicurezza. Controllo JavaScript integrato per massima OpSec.
"""

import httpx


class Tools:
    def __init__(self):
        # Punta alla nuova porta 8083 del container browser-i2p
        self.base_url = "http://browser-i2p:8083"

    async def browse_i2p(
        self, url: str, js_enabled: bool = True, block_media: bool = True
    ) -> str:
        """
        Naviga siti della rete I2P (.i2p) tramite router i2pd locale (Garlic Routing).
        :param url: URL completo da visitare (deve essere un indirizzo .i2p).
        :param js_enabled: Imposta a False per disabilitare JavaScript. Consigliato per la massima sicurezza contro fingerprinting e script ostili sulla rete I2P.
        :param block_media: Imposta a True per bloccare immagini/video pesanti e velocizzare la navigazione I2P (che è intrinsecamente lenta).
        """
        async with httpx.AsyncClient(timeout=150) as client:
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

                status_js = "JS: OFF (Stealth)" if not js_enabled else "JS: ON"
                text_content = data.get("text", "")[:4000]

                return f"[I2P NETWORK | {status_js}]\nTitolo: {data.get('title')}\nURL finale: {data.get('final_url')}\n\n{text_content}"
            except Exception as e:
                return f"Errore durante la navigazione I2P (Il sito potrebbe essere offline, molto comune su I2P): {str(e)}"
