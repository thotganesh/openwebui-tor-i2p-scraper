from fastapi import FastAPI
from pydantic import BaseModel
from curl_cffi import requests
from readability import Document
import html2text

app = FastAPI()

class Request(BaseModel):
    url: str

@app.post("/browse")
async def browse(req: Request):
    try:
        # Impersona Chrome 124 a livello TLS (JA3/JA4)
        response = requests.get(
            req.url,
            impersonate="chrome124",
            timeout=30,
            allow_redirects=True
        )
        
        if response.status_code != 200:
            return {
                "error": f"HTTP {response.status_code}",
                "text": "",
                "title": "",
                "final_url": req.url
            }
        
        html = response.text
        doc = Document(html)
        title = doc.title()
        
        # Estrazione con Readability
        content_html = doc.summary()
        
        # Converti in Markdown
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.body_width = 0  # Nessun wrapping
        text = h.handle(content_html)
        
        return {
            "title": title,
            "text": text[:10000],
            "final_url": req.url
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "text": "",
            "title": "",
            "final_url": req.url
        }

@app.get("/health")
async def health():
    return {"status": "ok"}
