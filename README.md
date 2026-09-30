<div align="center">

# 🕵️‍♂️ Open WebUI Tor, I2P & Stealth Web Scraper 🕷️

**A robust, triple-path web scraping infrastructure for local AI models.**

Three Playwright-based browser containers that feed clean, optimized Markdown to your LLM —
saving RAM, cutting token usage, bypassing anti-bot measures and keeping your OpSec intact
across **Clearnet, Tor and I2P**.

![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-1.48.0-2EAD33?logo=playwright&logoColor=white)
![Python](https://img.shields.io/badge/Python-FastAPI-3776AB?logo=python&logoColor=white)
![Tor](https://img.shields.io/badge/Tor-Snowflake-7D4698?logo=torproject&logoColor=white)
![I2P](https://img.shields.io/badge/I2P-i2pd-1F4E79)
![Open WebUI](https://img.shields.io/badge/Open%20WebUI-Tools-black)

</div>

Built specifically as tools for **Open WebUI**.

---

## 📑 Table of Contents

- [🌟 Core Features](#-core-features)
- [🧩 Open WebUI Tools](#-open-webui-tools)
- [🏗️ Architecture](#️-architecture)
- [🚀 Quick Start](#-quick-start)
- [📖 Complete Tutorial](#-complete-tutorial)
  - [Prerequisites](#prerequisites)
  - [Folder structure](#folder-structure)
  - [1. tor-proxy: Tor + Snowflake](#1-tor-proxy-tor--snowflake)
  - [2. browser-tor: anonymity via Tor](#2-browser-tor-anonymity-via-tor)
  - [3. browser-clear: normal navigation with stealth](#3-browser-clear-normal-navigation-with-stealth)
  - [4. browser-i2p: Garlic Routing via I2P](#4-browser-i2p-garlic-routing-via-i2p)
  - [5. docker-compose.yml](#5-docker-composeyml)
  - [6. Build and startup](#6-build-and-startup)
  - [7. Verification: test battery](#7-verification-test-battery)
  - [8. Integration with OpenWebUI](#8-integration-with-openwebui)
  - [9. Intelligent text extraction](#9-intelligent-text-extraction)
  - [10. Troubleshooting](#10-troubleshooting)
  - [11. Useful commands](#11-useful-commands)

---

## 🌟 Core Features

| | Feature | Description |
|---|---|---|
| 🌐 | **Triple Browsing Paths** | Three independent browsers: Clearnet, Tor and I2P |
| 🛡️ | **Dynamic OpSec & JS Control** | Turn JavaScript on/off straight from the AI prompt to reduce fingerprinting and exploit surface |
| 🍪 | **GDPR/Cookie Killer** | Injects JavaScript to detect and destroy intrusive CMPs and paywalls before extraction |
| 🧠 | **Smart Extraction** | Mozilla Readability + `html2text` deliver only the core article in pure Markdown |
| ⚡ | **Token & RAM Optimized** | Heavy media (images, videos, fonts) blocked at network level via Playwright routing |

### 🌐 Triple Browsing Paths

- **Clear Browser (Chromium)** — uses `playwright-stealth` and dynamic media blocking to bypass common anti-bot challenges (like Cloudflare) with your real IP.
- **Tor Browser (Firefox)** — hardened against WebRTC leaks, routes traffic exclusively through the Tor network using the **Snowflake** pluggable transport (bypassing ISP Tor blocks). Generates a new Tor circuit on demand via `stem`.
- **I2P Browser (Firefox)** — completely isolated Garlic Routing through a local `i2pd` router to explore `.i2p` eepsites with no clearnet exposure.

### 🛡️ Dynamic OpSec & JavaScript Control

The Tor and I2P tools expose a `js_enabled` parameter. The AI can disable JavaScript on request (for example when the user asks for maximum security), instantly mitigating browser fingerprinting and hostile scripts on darknets.

### 🍪 GDPR/Cookie Killer

Dynamically detects and destroys Consent Management Platforms (CMPs) and paywalls before text extraction.

### 🧠 Smart Extraction

Strips away menus, ads and sidebars, delivering only the core article as pure Markdown. Includes a fallback mechanism for homepages and search engines.

### ⚡ Token & RAM Optimized

Conditionally blocks heavy media at the network level, so pages load faster and your model reads fewer tokens.

---

## 🧩 Open WebUI Tools

This project ships as **three Open WebUI tools that work together**. Ready-to-import files are in [`openwebui-tools/`](openwebui-tools/):

| Tool | File | Purpose |
|---|---|---|
| **Web Browser (Clear)** | [`web_browser_clear.py`](openwebui-tools/web_browser_clear.py) | Normal sites via headless Chromium + stealth |
| **Web Browser (Tor/Anonymous)** | [`web_browser_tor.py`](openwebui-tools/web_browser_tor.py) | Anonymous browsing + `.onion` via Tor/Snowflake |
| **Web Browser (I2P Darknet)** | [`web_browser_i2p.py`](openwebui-tools/web_browser_i2p.py) | Garlic Routing for `.i2p` eepsites via local `i2pd` |

> [!IMPORTANT]
> **All three tools are required.** They are the three pillars of the same stack: the Clear tool talks to `browser-clear`, the Tor tool to `browser-tor`, the I2P tool to `browser-i2p`. Install all of them.

### 📥 How to install

1. In OpenWebUI go to **Admin → Workspace → Tools → new tool**
2. Paste the content of each file (one tool per file)
3. Enable all the tools in your chat and make sure your model supports function calling

---

## 🏗️ Architecture

```text
                        ┌─────────────────────┐
                        │   OpenWebUI (AI)    │
                        └──────────┬──────────┘
                                   │ ai-net (Docker bridge)
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
┌─────────▼──────┐        ┌────────▼───────┐       ┌────────▼───────┐
│ browser-clear  │        │  browser-tor   │       │  browser-i2p   │
│ Chromium       │        │  Firefox       │       │  Firefox       │
│ port 8080/8082 │        │  port 8081     │       │  port 8083     │
└────────────────┘        └────────┬───────┘       └────────┬───────┘
                                   │                        │
                          ┌────────▼───────┐       ┌────────▼───────┐
                          │   tor-proxy    │       │   i2p-proxy    │
                          │   Snowflake    │       │   i2pd router  │
                          │ SOCKS :9150    │       │ HTTP  :4444    │
                          │ CTRL  :9151    │       │ SOCKS :4447    │
                          └────────────────┘       └────────────────┘
```

> [!NOTE]
> All traffic runs on the internal Docker network `ai-net`: no Tor or I2P proxy port is exposed to the outside.

---

## 🚀 Quick Start

Already know your way around Docker? Get the whole stack running in a few commands. Want to understand every piece? Skip to the [Complete Tutorial](#-complete-tutorial).

**Requirements:** a VPS with Docker + Docker Compose, outgoing UDP open, OpenWebUI already running.

```bash
# 1) Clone the repository
git clone https://github.com/thotganesh/openwebui-tor-i2p-scraper.git
cd openwebui-tor-i2p-scraper

# 2) Create the shared Docker network (skip if it already exists)
docker network create ai-net

# 3) Connect OpenWebUI to the network (skip if it's already connected)
docker network connect ai-net open-webui

# 4) I2P data folder: i2pd runs as non-root and needs write access
mkdir -p i2p-data && chmod -R 777 i2p-data

# 5) Tor ControlPort password: generate the hash...
docker run --rm debian:bookworm-slim bash -c \
  "apt-get update -qq && apt-get install -y -qq tor >/dev/null && tor --hash-password 'YourSecurePassword'"
#    ...paste it in tor-snowflake/torrc (HashedControlPassword 16:...)
#    ...and set the same plain-text password as CONTROL_PASSWORD in browser-tor/app.py

# 6) Build and start everything
docker compose up -d --build

# 7) Wait for Tor: look for "Bootstrapped 100% (done)"
docker compose logs -f tor-proxy
```

> [!IMPORTANT]
> - **Change the default password.** Never leave the placeholder values in `torrc` and `browser-tor/app.py`.
> - **I2P warm-up:** `i2pd` needs about 3-5 minutes on its first boot before `.i2p` sites resolve.
> - The first build takes a few minutes (Snowflake compilation + Playwright image, about 2 GB).

**Then:** install the three tools from [`openwebui-tools/`](openwebui-tools/) in OpenWebUI (see [How to install](#-how-to-install)) and run the [test battery](#7-verification-test-battery) to verify everything.

---

## 📖 Complete Tutorial

> Build the stack from scratch: Tor with Snowflake, I2P with `i2pd`, anonymous browsers and a "clear" browser with intelligent text extraction, integrated as tools for a local AI on OpenWebUI.

### Prerequisites

- 🖥️ A VPS with Docker and Docker Compose (the `docker compose` command)
- 📡 **Outgoing UDP open**: Snowflake negotiates via WebRTC/ICE, which uses UDP. If the provider blocks it, Tor stays stuck in bootstrap
- 🔗 A Docker network shared with OpenWebUI, here called `ai-net`. If it doesn't exist: `docker network create ai-net`
- 🔌 Free ports on the host: `8081` (browser-tor), `8082` (browser-clear) and `8083` (browser-i2p)
- 🤖 OpenWebUI already running and connected to `ai-net`

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
# VITAL: i2pd runs as non-root and needs permission to write its addressbook
chmod -R 777 ~/ai-stack/i2p-data
cd ~/ai-stack
```

---

### 1. tor-proxy: Tor + Snowflake

#### 1.1 Dockerfile (multi-stage) — [`tor-snowflake/Dockerfile`](tor-snowflake/Dockerfile)

```dockerfile
# --- Stage 1: build of snowflake-client ---
FROM golang:1.23-bookworm AS builder
# Allows Go to download by itself the toolchain required by the project's go.mod
ENV GOTOOLCHAIN=auto
RUN git clone https://git.torproject.org/pluggable-transports/snowflake.git /tmp/snowflake \
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

> [!NOTE]
> The Snowflake repo requires a very recent Go (1.25.x). With `golang:1.23` + `GOTOOLCHAIN=auto`, Go downloads the right toolchain by itself. The final stage contains only the compiled binary: the image stays lightweight.

#### 1.2 ControlPort password

The ControlPort is used to ask Tor for a new circuit (NEWNYM) before each request. Generate the hash:

```bash
docker run --rm debian:bookworm-slim bash -c \
  "apt-get update -qq && apt-get install -y -qq tor >/dev/null && tor --hash-password 'YourSecurePassword'"
# the last printed line is the hash, like: 16:AF97...  (copy it into the torrc)
```

Copy the hash (`16:...`) into the torrc. The same password in plain text goes into `CONTROL_PASSWORD` inside [`browser-tor/app.py`](browser-tor/app.py).

#### 1.3 torrc — [`tor-snowflake/torrc`](tor-snowflake/torrc)

```ini
SocksPort 0.0.0.0:9150
UseBridges 1
ClientTransportPlugin snowflake exec /usr/local/bin/snowflake-client \
  -url https://snowflake-broker.torproject.net.global.prod.fastly.net/ \
  -front cdn.sstatic.net \
  -ice stun:stun.l.google.com:19302,stun:stun.antisip.com:3478,stun:stun.bluesip.net:3478,stun:stun.dus.net:3478,stun:stun.epygi.com:3478,stun:stun.sonetel.com:3478,stun:stun.uls.co.za:3478,stun:stun.voipgate.com:3478,stun:stun.voys.nl:3478
Bridge snowflake 192.0.2.3:80 2B280B23E1107BB62ABFC40DDCC8824814F80A72 fingerprint=2B280B23E1107BB62ABFC40DDCC8824814F80A72 url=https://snowflake-broker.torproject.net.global.prod.fastly.net/ fronts=foursquare.com,github.githubassets.com ice=stun:stun.l.google.com:19302,stun:stun.antisip.com:3478,stun:stun.bluesip.net:3478,stun:stun.dus.net:3478,stun:stun.epygi.com:3478,stun:stun.sonetel.com:3478,stun:stun.uls.co.za:3478,stun:stun.voipgate.com:3478,stun:stun.voys.nl:3478 utls-imitate=hellorandomizedalpn
ControlPort 0.0.0.0:9151
HashedControlPassword 16:PASTE_THE_GENERATED_HASH_HERE
```

> [!WARNING]
> The `-ice` and `Bridge` lines are **one single line each**. Replace `PASTE_THE_GENERATED_HASH_HERE` with the generated hash. The IP `192.0.2.3` in the Bridge line is a placeholder from the official documentation: with Snowflake it doesn't matter, because the client connects to the broker via domain fronting and then negotiates with a volunteer proxy via WebRTC.

---

### 2. browser-tor: anonymity via Tor

📁 [`browser-tor/`](browser-tor/)

```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy
WORKDIR /app
RUN pip install fastapi uvicorn httpx playwright==1.48.0 stem readability-lxml html2text lxml
COPY app.py /app/app.py
EXPOSE 8081
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8081"]
```

What it does ([`browser-tor/app.py`](browser-tor/app.py)):

- 🦊 **Hardened Firefox**: `privacy.resistFingerprinting` + letterboxing reduce the browser's uniqueness; viewport 1000x900, UTC timezone and en-US language are values common among Tor users
- 🚫 **WebRTC disabled**: with WebRTC enabled the real IP leaks via ICE/STUN, bypassing the SOCKS proxy
- 🔄 **New circuit per request**: NEWNYM via ControlPort (Playwright doesn't support authentication on SOCKS5, so random username/password aren't used; `stem` requires a literal IP, hence `socket.gethostbyname`)
- 📝 **Text extraction**: Readability + html2text fallback (see [section 9](#9-intelligent-text-extraction))

---

### 3. browser-clear: normal navigation with stealth

📁 [`browser-clear/`](browser-clear/)

```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy
WORKDIR /app
RUN pip install fastapi uvicorn playwright-stealth httpx playwright==1.48.0 readability-lxml html2text lxml
COPY app.py /app/app.py
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
```

- 🥷 **Stealth**: `Stealth().use_async(async_playwright())` (playwright-stealth 2.x) masks the typical automation signals
- 📶 **WebRTC intentionally enabled**: a real Chrome always has it on; here the real IP isn't a secret to protect
- 🖼️ **`block_media` enabled by default** for speed and RAM saving; with `false` it loads everything like a real user (useful against aggressive anti-bots)

---

### 4. browser-i2p: Garlic Routing via I2P

📁 [`browser-i2p/`](browser-i2p/)

```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install firefox
COPY . .
EXPOSE 8083
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8083"]
```

What it does ([`browser-i2p/app.py`](browser-i2p/app.py)):

- 🧄 **Garlic Routing via `i2pd`**: all traffic goes through the dedicated `i2p-proxy` container (the `i2pd` router), never through your real IP
- 🛡️ **JavaScript control**: `js_enabled=false` turns JavaScript off completely, recommended on I2P against fingerprinting and hostile scripts
- 🪂 **"Airbag" error handling**: a `try...except` block gracefully handles offline `.i2p` eepsites (very common on I2P) instead of crashing
- 📝 **Text extraction**: same Readability + html2text pipeline as the other browsers (see [section 9](#9-intelligent-text-extraction))

> [!NOTE]
> I2P is intrinsically slow: that's why the tool uses a longer timeout (150 s) and encourages `block_media=true`.

---

### 5. docker-compose.yml

📄 [`docker-compose.yml`](docker-compose.yml)

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
    volumes:
      - ./i2p-data:/home/i2pd/data
    restart: unless-stopped

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

> [!IMPORTANT]
> `ai-net` is `external: true`: the network already exists and is shared with OpenWebUI.
> The ports are bound to `127.0.0.1`: **never publish Tor's 9150/9151 or the I2P proxy ports**.

---

### 6. Build and startup

```bash
cd ~/ai-stack
docker compose build
docker compose up -d
docker compose ps                      # all five containers "Up", no restart loop
docker compose logs -f tor-proxy       # wait for "Bootstrapped 100% (done)"
```

> [!NOTE]
> The first build takes a few minutes (Snowflake compilation + Playwright image download, about 2 GB).

> [!IMPORTANT]
> **I2P warm-up time:** the `i2pd` router needs about 3-5 minutes on its very first boot to build its tunnels and populate the addressbook. Test it with `http://stats.i2p` (see the test battery) only after that.

---

### 7. Verification: test battery

```bash
# 1) Tor's SOCKS works and the IP is anonymous
docker run --rm --network ai-net curlimages/curl -s --socks5-hostname tor-proxy:9150 https://check.torproject.org/api/ip

# 2) browser-clear: must show IsTor:false with the VPS's real IP
curl -s -X POST http://127.0.0.1:8082/browse -H "Content-Type: application/json" \
  -d '{"url": "https://check.torproject.org/api/ip"}'

# 3) browser-tor: must show IsTor:true with an exit node IP
curl -s -X POST http://127.0.0.1:8081/browse -H "Content-Type: application/json" \
  -d '{"url": "https://check.torproject.org/api/ip"}'

# 4) browser-tor on a real .onion (DuckDuckGo)
curl -s -X POST http://127.0.0.1:8081/browse -H "Content-Type: application/json" \
  -d '{"url": "http://duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion"}'

# 5) Circuit rotation: NEWNYM has a rate limit of ~10 s
curl -s -X POST http://127.0.0.1:8081/browse -H "Content-Type: application/json" \
  -d '{"url": "https://check.torproject.org/api/ip"}'; echo; sleep 12
curl -s -X POST http://127.0.0.1:8081/browse -H "Content-Type: application/json" \
  -d '{"url": "https://check.torproject.org/api/ip"}'

# 6) WebRTC diagnostic test (WebRTC deliberately re-enabled: must show the real IP leak)
curl -s http://127.0.0.1:8081/webrtc-leak-check

# 7) browser-i2p on an eepsite, JavaScript OFF (wait ~5 min after first boot)
curl -s -X POST http://127.0.0.1:8083/browse -H "Content-Type: application/json" \
  -d '{"url": "http://stats.i2p", "js_enabled": false}'
```

| Test | Expected result |
|---|---|
| Direct SOCKS | `{"IsTor":true,"IP":"..."}` |
| browser-clear | `IsTor:false` with the VPS's real IP |
| browser-tor | `IsTor:true`, exit node IP different from the VPS's |
| browser-tor on .onion | HTTP 200 with title and text of the page |
| Circuit rotation | Different exit IPs between the two requests |
| webrtc-leak-check | `leaked_ips` with the real IP: proof that WebRTC must stay disabled |
| browser-i2p on stats.i2p | HTTP 200 with title and text of the eepsite (after warm-up) |

> [!NOTE]
> Always use real URLs in tests: a placeholder URL returns a 404 that looks like a code problem.

---

### 8. Integration with OpenWebUI

#### 8.1 Network and reachability

```bash
docker inspect open-webui --format '{{json .NetworkSettings.Networks}}'   # ai-net must appear
docker network connect ai-net open-webui                                  # only if missing
docker exec open-webui curl -s -m 10 http://browser-clear:8080/health     # {"status":"ok"}
docker exec open-webui curl -s -m 10 http://browser-tor:8081/health       # {"status":"ok"}
docker exec open-webui curl -s -m 10 http://browser-i2p:8083/health       # {"status":"ok"}
```

#### 8.2 Tool 1: normal browser

In OpenWebUI: **Admin → Workspace → Tools → new tool**:

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
        """
        Browses a normal web page and extracts the text in Markdown.

        :param url: Full URL to visit (e.g. https://example.com)
        :param block_media: True blocks images/fonts/videos (faster). Set False if the site blocks bots.
        """
        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.post(f"{self.base_url}/browse", json={"url": url, "block_media": block_media})
            if r.status_code != 200:
                return f"Error from the browser-service: HTTP {r.status_code}"
            data = r.json()
            return f"Title: {data.get('title')}\nFinal URL: {data.get('final_url')}\n\n{data.get('text', '')[:4000]}"
```

#### 8.3 Tool 2: Tor browser

```python
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

                # Visual label to see at a glance whether JS was on or off
                status_js = (
                    "JS: OFF (Stealth/Anonymized)" if not js_enabled else "JS: ON"
                )
                text_content = data.get("text", "")[:4000]

                return f"[TOR NETWORK | {status_js}]\nTitolo: {data.get('title')}\nURL finale: {data.get('final_url')}\n\n{text_content}"
            except Exception as e:
                return f"Errore durante la navigazione Tor: {str(e)}"
```

#### 8.4 Tool 3: I2P browser

```python
"""
title: Web Browser (I2P Darknet)
description: Naviga esclusivamente la rete chiusa I2P (siti .i2p) in totale sicurezza. Controllo JavaScript integrato per massima OpSec.
"""

import httpx


class Tools:
    def __init__(self):
        # Points to port 8083 of the browser-i2p container
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
```

> [!NOTE]
> Inside Docker, services communicate on internal ports (`browser-clear:8080`, `browser-tor:8081`, `browser-i2p:8083`), not on those mapped to the host. The `[:4000]` limit keeps token usage under control: increase it if you need longer extracts.

#### 8.5 Avoiding conflicts with native Web Search

If the integrated Web Search is enabled, disable it (**Admin Panel → Settings → Web Search → OFF**): with competing tools, small models choose inconsistently. Then, in the global System Prompt:

```text
To browse normal websites ALWAYS use the browse_web tool.
For .onion sites, or when the user explicitly requests anonymity, ALWAYS use the browse_tor tool.
For .i2p eepsites ALWAYS use the browse_i2p tool.
You have no other way to access the internet.
Keep JavaScript enabled by default; disable it (js_enabled=false) only when the user asks for maximum security.
```

If the model doesn't call the tools, check that they are enabled in the chat and that the model supports function calling (model settings → Capabilities).

---

### 9. Intelligent text extraction

Four mechanisms, present in all the browsers:

1. **Resource blocking** (`block_media`): `page.route("**/*.{png,jpg,...}")` stops images, fonts and videos before they download → faster pages and less memory. On sites with serious anti-bot, disable it: a Chrome that never loads images is anomalous behavior.
2. **Cookie killer**: removes the containers of the main CMPs (OneTrust, Cookiebot, Quantcast, TrustArc...) from the DOM and restores scrolling. It doesn't bypass server-side paywalls.
3. **Two-level extraction**: level 1 Readability (structured article); level 2 fallback html2text on all the HTML (homepages, indexes, search results). You never get a hard error.
4. **`domcontentloaded` + fixed wait (2500 ms)** instead of `networkidle`: ad-filled sites never reach the "silent network" and would go into timeout.

> [!WARNING]
> Some CMPs have anti-tamper protection: on repubblica.it (Iubenda), removing the banner with `el.remove()` emptied the entire page (HTML from 496,335 to 15 characters). In those cases, hide with `el.style.setProperty('display','none','important')` instead of removing.

---

### 10. Troubleshooting

| Error / symptom | Cause | Solution |
|---|---|---|
| I2P container `Restarting (139)` | Permission denied on `/home/i2pd/data` | `chmod -R 777 i2p-data` |
| I2P `NS_ERROR_UNKNOWN_PROXY_HOST` | The `i2p-proxy` container is down or unreachable | Check permissions on `i2p-data`, then `docker compose restart i2p-proxy` |
| I2P `Host not found in addressbook` | The router is still warming up | Wait ~5 minutes, then test `http://stats.i2p` |
| I2P tool returns an error / timeout | Eepsite offline (very common) or slow tunnels | Retry later or try another eepsite |
| `Error parsing Bridge address 'auto'` | Incorrect or leftover torrc syntax | Rewrite the torrc from scratch |
| `general SOCKS server failure` (obfs4) | obfs4 bridge with made-up fingerprint/cert | Use Snowflake with the official bridge line |
| `invalid go version '1.25.12'` / `requires go >= 1.25.12` | Image's Go too old | Multi-stage with golang and `ENV GOTOOLCHAIN=auto` |
| `pip3: not found` | Node.js variant Playwright image | Use `mcr.microsoft.com/playwright/python` |
| `No module named 'playwright'` | The Python image doesn't include the package | Explicit `pip install playwright==1.48.0` |
| `Executable doesn't exist ... chrome-headless-shell` | Python package newer than the image's browsers | Pin `playwright==` to the image version |
| `port is already allocated` | Host port already used | Change the mapping (e.g. `8082:8080`) |
| `cannot import name 'stealth_async'` | playwright-stealth 2.x has a new API | `Stealth().use_async(async_playwright())` |
| `RTCPeerConnection is not defined` | With WebRTC disabled the API doesn't exist | Leak test with WebRTC re-enabled (dedicated endpoint) |
| `Browser does not support socks5 proxy authentication` | Playwright doesn't support user/password on SOCKS5 | Isolate circuits with ControlPort and NEWNYM |
| `Invalid IP address: tor-proxy` | stem requires a literal IP | `socket.gethostbyname("tor-proxy")` |
| `Document is empty` / `Unparseable` | Readability doesn't find an article | html2text fallback on all the HTML |
| Page emptied after the cookie killer | The CMP detects the banner removal (anti-tamper) | Hide with `display:none` instead of `remove()` |
| `Cannot read properties of null (reading 'style')` | `document.body` absent during a reload | `if (document.body)` + try/except |
| Cookie banner still in the text | Case-sensitive selectors or CMP not in the list | Add the site's CMP IDs (or selectors with the `i` flag) |
| 404 response in tests | Placeholder URL taken literally | Use a real URL |
| curl responds with 0 bytes | Error 500 hidden by `curl -s` | `curl -v` and `docker compose logs <service>` |

---

### 11. Useful commands

```bash
cd ~/ai-stack
docker compose ps                                        # container status
docker compose logs -f browser-tor                       # Tor browser logs in real time
docker compose logs -f i2p-proxy                         # monitor I2P tunnels
docker compose logs browser-clear --tail 30 | grep -i warn
# after modifying an app.py / Dockerfile:
docker compose build browser-clear browser-tor browser-i2p && docker compose up -d browser-clear browser-tor browser-i2p
docker compose restart tor-proxy                         # restart only Tor
docker compose restart i2p-proxy                         # restart only I2P
docker compose down                                      # stop everything (the ai-net network remains)
```

---

<div align="center">

⭐ If this project helps you, consider leaving a star on the repo!

</div>
