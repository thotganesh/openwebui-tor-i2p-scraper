from fastapi import FastAPI
from pydantic import BaseModel
from curl_cffi import requests
from readability import Document
import html2text

app = FastAPI()


class Request(BaseModel):
    url: str


def extract_text(html: str) -> str:
    """Two-level extraction: Readability first, html2text fallback."""
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True
    h.body_width = 0

    try:
        doc = Document(html)
        clean = h.handle(doc.summary()).strip()
        if clean and len(clean) > 200:
            return clean
    except Exception:
        pass

    try:
        return h.handle(html).strip()
    except Exception as e:
        return f"Extraction error: {e}"


@app.post("/browse")
async def browse(req: Request):
    try:
        response = requests.get(
            req.url,
            impersonate="chrome124",
            timeout=30,
            allow_redirects=True,
        )

        if response.status_code != 200:
            return {
                "error": f"HTTP {response.status_code}",
                "text": "",
                "title": "",
                "final_url": req.url,
            }

        # response.url reflects redirects (curl_cffi behavior)
        final_url = str(response.url) if response.url else req.url
        html = response.text

        try:
            doc = Document(html)
            title = doc.title() or ""
        except Exception:
            title = ""

        text = extract_text(html)

        return {
            "title": title,
            "text": text,           # no 10k truncation
            "final_url": final_url, # URL after redirects
        }

    except Exception as e:
        return {
            "error": str(e),
            "text": "",
            "title": "",
            "final_url": req.url,
        }


@app.get("/health")
async def health():
    return {"status": "ok"}
