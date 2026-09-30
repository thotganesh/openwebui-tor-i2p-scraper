```markdown
# Open WebUI Tor & I2P Stealth Web Scraper 🕵️‍♂️🕷️

A robust, triple-path web scraping infrastructure built for local AI models (specifically designed as tools for **Open WebUI**). It provides three distinct Playwright-based browser containers that feed clean, optimized Markdown text to your LLM, saving RAM, reducing token usage, bypassing anti-bot measures, and ensuring total operational security across Clearnet, Tor, and I2P Darknets.

## 🌟 Core Features

1. **Triple Browsing Paths:**
   * **Clear Browser (Chromium):** Uses `playwright-stealth` and dynamic media blocking to bypass common anti-bot challenges (like Cloudflare) using your real IP.
   * **Tor Browser (Firefox):** Hardened against WebRTC leaks, routes traffic exclusively through the Tor network using the **Snowflake** pluggable transport (bypassing ISP Tor blocks). Generates a new Tor circuit on demand via `stem`.
   * **I2P Browser (Firefox):** Completely isolated Garlic Routing via a local `i2pd` proxy to securely explore `.i2p` eepsites with zero IP leak risk.
2. **Dynamic OpSec & JavaScript Control:** Granular control over JavaScript execution directly from the AI prompt to instantly mitigate browser fingerprinting and zero-day exploits on Darknets.
3. **GDPR/Cookie Killer:** Injects JavaScript to dynamically detect and destroy intrusive Consent Management Platforms (CMPs) and paywalls before text extraction.
4. **Smart Extraction:** Uses Mozilla Readability and `html2text` to strip away menus, ads, and sidebars, delivering only the core article in pure Markdown. Includes a fallback mechanism for homepages and search engines.
5. **Token & RAM Optimized:** Conditionally blocks heavy media (images, videos, fonts) at the network level via Playwright routing.

## 🧩 Open WebUI Tools

This project ships as **three Open WebUI tools that work together**. Ready-to-import files
are in [`openwebui-tools/`](openwebui-tools/):

| Tool | File | Purpose |
|---|---|---|
| **Web Browser (Clear)** | [`web_browser_clear.py`](openwebui-tools/web_browser_clear.py) | Normal sites via headless Chromium + stealth |
| **Web Browser (Tor)** | [`web_browser_tor.py`](openwebui-tools/web_browser_tor.py) | Anonymous browsing + .onion via Tor/Snowflake |
| **Web Browser (I2P)** | [`web_browser_i2p.py`](openwebui-tools/web_browser_i2p.py) | Garlic Routing for .i2p eepsites via local i2pd |

> ⚠️ **All tools are required.** They are the pillars of the same stack: install all of them in Open WebUI and enable them in your chat.

## 🏗️ Architecture

```text
                    ┌─────────────────────┐
                    │   OpenWebUI (AI)    │
                    └──────────┬──────────┘
                               │ ai-net (Docker bridge)
          ┌────────────────────┼────────────────────┐
          │                    │                    │
┌─────────▼──────┐  ┌──────────▼─────┐  ┌───────────▼─────┐
│ browser-clear  │  │  browser-tor   │  │   browser-i2p   │
│ Chromium       │  │  Firefox       │  │   Firefox       │
│ port 8080/8082 │  │  port 8081     │  │   port 8083     │
└────────────────┘  └──────────┬─────┘  └───────────┬─────┘
                               │                    │
                    ┌──────────▼─────┐  ┌───────────▼─────┐
                    │   tor-proxy    │  │    i2p-proxy    │
                    │   Snowflake    │  │   i2pd router   │
                    └────────────────┘  └─────────────────┘

```

> All traffic runs on the internal Docker network `ai-net`: no Tor or I2P proxy ports are exposed to the outside.

## 📖 Complete Tutorial

> Build the stack from scratch: Tor with Snowflake, I2P Garlic Routing, anonymous browser and "clear" browser with intelligent text extraction, integrated as tools for a local AI on OpenWebUI.

### Prerequisites

* A VPS with Docker and Docker Compose (the `docker compose` command)
* **Outgoing UDP open**: Snowflake negotiates via WebRTC/ICE, which uses UDP. If the provider blocks it, Tor stays stuck in bootstrap
* A Docker network shared with OpenWebUI, here called `ai-net`. If it doesn't exist: `docker network create ai-net`
* Free ports on the host: `8081` (browser-tor), `8082` (browser-clear), and `8083` (browser-i2p)
* OpenWebUI already running and connected to `ai-net`

### Folder structure

```text
~/ai-stack/
├── docker-compose.yml
├── tor-snowflake/
│   ├── Dockerfile
│   └── torrc
├── browser-tor/
│   ├── Dockerfile
│   └── app.py
├── browser-clear/
│   ├── Dockerfile
│   └── app.py
├── browser-i2p/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py
└── i2p-data/

```

```bash
mkdir -p ~/ai-stack/{tor-snowflake,browser-tor,browser-clear,browser-i2p,i2p-data}
# VITAL: i2pd runs as non-root, it needs permissions to write its addressbook
chmod -R 777 ~/ai-stack/i2p-data
cd ~/ai-stack

```

---

### 1. tor-proxy: Tor + Snowflake

#### 1.1 Dockerfile (multi-stage) — [`tor-snowflake/Dockerfile`](https://www.google.com/search?q=tor-snowflake/Dockerfile)

```dockerfile
# --- Stage 1: build of snowflake-client ---
FROM golang:1.23-bookworm AS builder
ENV GOTOOLCHAIN=auto
RUN git clone [https://git.torproject.org/pluggable-transports/snowflake.git](https://git.torproject.org/pluggable-transports/snowflake.git) /tmp/snowflake \
    && cd /tmp/snowflake/client \
    && go build -o /usr/local/bin/snowflake-client .
# --- Stage 2: final image, runtime only ---
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y \
    tor obfs4proxy ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/local/bin/snowflake-client /usr/local/bin/snowflake-client
RUN chmod +x /usr/local/bin/snowflake-client
EXPOSE 9150
CMD ["tor", "-f", "/etc/tor/torrc"]

```

#### 1.2 ControlPort password

Generate the Tor ControlPort hash:

```bash
docker run --rm debian:bookworm-slim bash -c \
  "apt-get update -qq && apt-get install -y -qq tor >/dev/null && tor --hash-password 'YourSecurePassword'"
# copy the hash starting with 16: into the torrc

```

#### 1.3 torrc — [`tor-snowflake/torrc`](https://www.google.com/search?q=tor-snowflake/torrc)

```ini
SocksPort 0.0.0.0:9150
UseBridges 1
ClientTransportPlugin snowflake exec /usr/local/bin/snowflake-client \
  -url [https://snowflake-broker.torproject.net.global.prod.fastly.net/](https://snowflake-broker.torproject.net.global.prod.fastly.net/) \
  -front cdn.sstatic.net \
  -ice stun:stun.l.google.com:19302,stun:stun.antisip.com:3478,stun:stun.bluesip.net:3478,stun:stun.dus.net:3478,stun:stun.epygi.com:3478,stun:stun.sonetel.com:3478,stun:stun.uls.co.za:3478,stun:stun.voipgate.com:3478,stun:stun.voys.nl:3478
Bridge snowflake 192.0.2.3:80 2B280B23E1107BB62ABFC40DDCC8824814F80A72 fingerprint=2B280B23E1107BB62ABFC40DDCC8824814F80A72 url=[https://snowflake-broker.torproject.net.global.prod.fastly.net/](https://snowflake-broker.torproject.net.global.prod.fastly.net/) fronts=foursquare.com,github.githubassets.com ice=stun:stun.l.google.com:19302,stun:stun.antisip.com:3478,stun:stun.bluesip.net:3478,stun:stun.dus.net:3478,stun:stun.epygi.com:3478,stun:stun.sonetel.com:3478,stun:stun.uls.co.za:3478,stun:stun.voipgate.com:3478,stun:stun.voys.nl:3478 utls-imitate=hellorandomizedalpn
ControlPort 0.0.0.0:9151
HashedControlPassword 16:PASTE_THE_GENERATED_HASH_HERE

```

---

### 2. browser-tor: anonymity via Tor — [`browser-tor/`](https://www.google.com/search?q=browser-tor/)

```dockerfile
FROM [mcr.microsoft.com/playwright/python:v1.48.0-jammy](https://mcr.microsoft.com/playwright/python:v1.48.0-jammy)
WORKDIR /app
RUN pip install fastapi uvicorn httpx playwright==1.48.0 stem readability-lxml html2text lxml
COPY app.py /app/app.py
EXPOSE 8081
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8081"]

```

What it does:

* **Hardened Firefox**: `privacy.resistFingerprinting`, viewport 1000x900, UTC timezone.
* **WebRTC disabled**: prevents ICE/STUN leaks.
* **New circuit per request**: NEWNYM via ControlPort (`stem`).

---

### 3. browser-clear: normal navigation with stealth — [`browser-clear/`](https://www.google.com/search?q=browser-clear/)

```dockerfile
FROM [mcr.microsoft.com/playwright/python:v1.48.0-jammy](https://mcr.microsoft.com/playwright/python:v1.48.0-jammy)
WORKDIR /app
RUN pip install fastapi uvicorn playwright-stealth httpx playwright==1.48.0 readability-lxml html2text lxml
COPY app.py /app/app.py
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]

```

What it does:

* **Stealth**: `Stealth().use_async(async_playwright())` masks automation signals.
* **WebRTC intentionally enabled**: mimics real user behavior.

---

### 4. browser-i2p & proxy: Garlic Routing — [`browser-i2p/`](https://www.google.com/search?q=browser-i2p/)

```dockerfile
FROM [mcr.microsoft.com/playwright/python:v1.40.0-jammy](https://mcr.microsoft.com/playwright/python:v1.40.0-jammy)
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install firefox
COPY . .
EXPOSE 8083
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8083"]

```

What it does:

* Relies on an isolated `i2pd` router container.
* Includes an "Airbag" `try...except` block to gracefully handle offline `.i2p` eepsites.

---

### 5. docker-compose.yml — [`docker-compose.yml`](https://www.google.com/search?q=docker-compose.yml)

```yaml
services:
  tor-proxy:
    build: ./tor-snowflake
    container_name: tor-proxy
    networks: [ai-net]
    volumes:
      - ./tor-snowflake/torrc:/etc/tor/torrc:ro
    restart: unless-stopped

  browser-tor:
    build: ./browser-tor
    container_name: browser-tor
    networks: [ai-net]
    depends_on: [tor-proxy]
    ports:
      - "127.0.0.1:8081:8081"
    restart: unless-stopped

  browser-clear:
    build: ./browser-clear
    container_name: browser-clear
    networks: [ai-net]
    ports:
      - "127.0.0.1:8082:8080"
    restart: unless-stopped

  i2p-proxy:
    image: purplei2p/i2pd:latest
    container_name: i2p-proxy
    networks: [ai-net]
    command: --httpproxy.address=0.0.0.0 --socksproxy.address=0.0.0.0
    restart: unless-stopped
    volumes:
      - ./i2p-data:/home/i2pd/data

  browser-i2p:
    build: ./browser-i2p
    container_name: browser-i2p
    networks: [ai-net]
    depends_on: [i2p-proxy]
    ports:
      - "127.0.0.1:8083:8083"
    restart: unless-stopped

networks:
  ai-net:
    external: true

```

---

### 6. Build and startup

```bash
cd ~/ai-stack
docker compose build
docker compose up -d
docker compose ps                      # all five containers "Up"
docker compose logs -f tor-proxy       # wait for "Bootstrapped 100% (done)"

```

> [!IMPORTANT]
> **I2P Warm-up Time:** The `i2pd` router requires 3-5 minutes on its very first boot to build Garlic Tunnels and populate its addressbook. Test it by running the curl command below against `http://stats.i2p` after 5 minutes.

---

### 7. Verification: test battery

```bash
# 1) browser-clear: must show IsTor:false with the VPS's real IP
curl -s -X POST [http://127.0.0.1:8082/browse](http://127.0.0.1:8082/browse) -H "Content-Type: application/json" -d '{"url": "[https://check.torproject.org/api/ip](https://check.torproject.org/api/ip)"}'

# 2) browser-tor: must show IsTor:true with an exit node IP
curl -s -X POST [http://127.0.0.1:8081/browse](http://127.0.0.1:8081/browse) -H "Content-Type: application/json" -d '{"url": "[https://check.torproject.org/api/ip](https://check.torproject.org/api/ip)"}'

# 3) browser-tor on a real .onion (DuckDuckGo)
curl -s -X POST [http://127.0.0.1:8081/browse](http://127.0.0.1:8081/browse) -H "Content-Type: application/json" -d '{"url": "[http://duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion](http://duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion)"}'

# 4) browser-i2p on an eepsite (stats.i2p)
curl -s -X POST [http://127.0.0.1:8083/browse](http://127.0.0.1:8083/browse) -H "Content-Type: application/json" -d '{"url": "http://stats.i2p", "js_enabled": false}'

```

---

### 8. Integration with OpenWebUI

In OpenWebUI go to **Admin → Workspace → Tools → new tool**. Paste the content of each file (one tool per file).

#### 8.1 Tool 1: Clear Browser

```python
"""
title: Web Browser (Clear)
description: Browses normal websites (headless Chromium + stealth) and returns the content in clean Markdown
"""
import httpx

class Tools:
    def __init__(self):
        self.base_url = "http://browser-clear:8080"

    async def browse_web(self, url: str, block_media: bool = True) -> str:
        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.post(f"{self.base_url}/browse", json={"url": url, "block_media": block_media})
            if r.status_code != 200:
                return f"Error from the browser-service: HTTP {r.status_code}"
            data = r.json()
            return f"Title: {data.get('title')}\nFinal URL: {data.get('final_url')}\n\n{data.get('text', '')[:4000]}"

```

#### 8.2 Tool 2: Tor Browser

```python
"""
title: Web Browser (Tor/Anonymous)
description: Naviga siti .onion o normali in forma completamente anonima tramite rete Tor (Snowflake)
"""
import httpx

class Tools:
    def __init__(self):
        self.base_url = "http://browser-tor:8081"

    async def browse_tor(self, url: str, block_media: bool = True, js_enabled: bool = True) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            try:
                r = await client.post(
                    f"{self.base_url}/browse", 
                    json={"url": url, "block_media": block_media, "js_enabled": js_enabled}
                )
                r.raise_for_status()
                data = r.json()
                return f"[TOR NETWORK | JS: {'ON' if js_enabled else 'OFF'}]\nTitolo: {data.get('title')}\nURL finale: {data.get('final_url')}\n\n{data.get('text', '')[:4000]}"
            except Exception as e:
                return f"Errore di connessione al nodo Tor locale: {e}"

```

#### 8.3 Tool 3: I2P Browser

```python
"""
title: Web Browser (I2P)
description: Naviga eepsites (.i2p) in modo sicuro e isolato tramite rete I2P (Garlic Routing)
"""
import httpx

class Tools:
    def __init__(self):
        self.base_url = "http://browser-i2p:8083"

    async def browse_i2p(self, url: str, block_media: bool = True, js_enabled: bool = True) -> str:
        async with httpx.AsyncClient(timeout=130) as client:
            try:
                r = await client.post(
                    f"{self.base_url}/browse", 
                    json={"url": url, "block_media": block_media, "js_enabled": js_enabled}
                )
                r.raise_for_status()
                data = r.json()
                return f"[I2P NETWORK | JS: {'ON' if js_enabled else 'OFF'}]\nTitolo: {data.get('title')}\nURL finale: {data.get('final_url')}\n\n{data.get('text', '')[:4000]}"
            except Exception as e:
                return f"Errore di connessione al router I2P locale o timeout: {e}"

```

#### 8.4 Avoiding conflicts with native Web Search

Disable the integrated Web Search (Admin Panel → Settings → Web Search → OFF) to prevent conflicts. Update your System Prompt:

```text
To browse normal websites ALWAYS use the browse_web tool.
For .onion sites ALWAYS use the browse_tor tool.
For .i2p eepsites ALWAYS use the browse_i2p tool.
You have no other way to access the internet. By default, keep JavaScript enabled unless the user explicitly asks for maximum security.

```

---

### 9. Intelligent text extraction

Four mechanisms, present in all browsers:

1. **Resource blocking** (`block_media`): `page.route("**/*.{png,jpg,...}")` stops media before downloading.
2. **Cookie killer**: removes the containers of the main CMPs from the DOM and restores scrolling.
3. **Two-level extraction**: level 1 Readability; level 2 fallback html2text on all HTML. You never get a hard error.
4. **`domcontentloaded` + fixed wait (2500 ms)** instead of `networkidle`: ad-filled sites never reach the "silent network".

> [!WARNING]
> Some CMPs have anti-tamper protection. In those cases, hide with `el.style.setProperty('display','none','important')` instead of removing.

---

### 10. Troubleshooting

| Error / symptom | Cause | Solution |
| --- | --- | --- |
| I2P container `Restarting (139)` | Permission denied on `/home/i2pd/data` | Run `chmod -R 777 i2p-data` |
| I2P `NS_ERROR_UNKNOWN_PROXY_HOST` | The proxy container is down/inaccessible | Check I2P permissions and restart |
| I2P `Host not found in addressbook` | I2P router is still warming up | Wait 5 mins, visit `http://stats.i2p` |
| `Error parsing Bridge address 'auto'` | Incorrect or leftover torrc syntax | Rewrite the torrc from scratch |
| `general SOCKS server failure` | obfs4 bridge with made-up cert | Use Snowflake with the official bridge line |
| `invalid go version` | Image's Go too old | Multi-stage with golang and `ENV GOTOOLCHAIN=auto` |
| `port is already allocated` | Host port already used | Change the mapping (e.g. `8082:8080`) |
| `RTCPeerConnection is not defined` | With WebRTC disabled the API doesn't exist | Leak test with WebRTC re-enabled |
| `Browser does not support socks5 proxy auth` | Playwright lacks SOCKS auth | Isolate circuits with ControlPort and NEWNYM |
| `Invalid IP address: tor-proxy` | stem requires a literal IP | `socket.gethostbyname("tor-proxy")` |

---

### 11. Useful commands

```bash
cd ~/ai-stack
docker compose ps                                        # container status
docker compose logs -f browser-tor                       # Tor logs in real time
docker compose logs -f i2p-proxy                         # monitor I2P tunnels
docker compose build browser-clear browser-tor browser-i2p
docker compose restart tor-proxy                         # restart only Tor
docker compose down                                      # stop everything

```

```

```
