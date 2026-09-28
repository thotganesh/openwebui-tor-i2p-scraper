# Open WebUI Tor & Stealth Web Scraper 🕵️‍♂️🕷️

A robust, dual-path web scraping infrastructure built for local AI models (specifically designed as tools for **Open WebUI**). It provides two distinct Playwright-based browser containers that feed clean, optimized Markdown text to your LLM, saving RAM, reducing token usage, and bypassing anti-bot measures.

## 🌟 Core Features

1. **Dual Browsing Paths:**
   * **Clear Browser (Chromium):** Uses `playwright-stealth` and dynamic media blocking to bypass common anti-bot challenges (like Cloudflare) using your real IP.
   * **Tor Browser (Firefox):** Hardened against WebRTC leaks, routes traffic exclusively through the Tor network using the **Snowflake** pluggable transport (bypassing ISP Tor blocks). Generates a new Tor circuit on demand via `stem`.
2. **GDPR/Cookie Killer:** Injects JavaScript to dynamically detect and destroy intrusive Consent Management Platforms (CMPs) and paywalls before text extraction.
3. **Smart Extraction:** Uses Mozilla Readability and `html2text` to strip away menus, ads, and sidebars, delivering only the core article in pure Markdown. Includes a fallback mechanism for homepages and search engines.
4. **Token & RAM Optimized:** Conditionally blocks heavy media (images, videos, fonts) at the network level via Playwright routing.

## 🏗️ Architecture

```text
                    ┌─────────────────────┐
                    │   OpenWebUI (AI)    │
                    └──────────┬──────────┘
                               │ ai-net (Docker bridge)
              ┌────────────────┼────────────────┐
              │                │                │
    ┌─────────▼──────┐  ┌──────▼───────┐  ┌─────▼─────────┐
    │ browser-clear  │  │ browser-tor  │  │   tor-proxy   │
    │ Chromium       │  │ Firefox      │──▶ Snowflake     │
    │ port 8080/8082 │  │ port 8081    │  │ SOCKS :9150   │
    └────────────────┘  └──────────────┘  └───────────────┘


## 📖 Complete Tutorial

> Build the stack from scratch: Tor with Snowflake, anonymous browser and "clear" browser
> with intelligent text extraction, integrated as tools for a local AI on OpenWebUI.

### Prerequisites

- A VPS with Docker and Docker Compose (the `docker compose` command)
- **Outgoing UDP open**: Snowflake negotiates via WebRTC/ICE, which uses UDP. If the provider blocks it, Tor stays stuck in bootstrap
- A Docker network shared with OpenWebUI, here called `ai-net`. If it doesn't exist: `docker network create ai-net`
- Free ports on the host: `8081` (browser-tor) and `8082` (browser-clear)
- OpenWebUI already running and connected to `ai-net`

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
└── browser-clear/
    ├── Dockerfile
    └── app.py
```

```bash
mkdir -p ~/ai-stack/{tor-snowflake,browser-tor,browser-clear}
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
> The Snowflake repo requires a very recent Go (1.25.x). With `golang:1.23` +
> `GOTOOLCHAIN=auto`, Go downloads the right toolchain by itself. The final stage
> contains only the compiled binary: the image stays lightweight.

#### 1.2 ControlPort password

The ControlPort is used to ask Tor for a new circuit (NEWNYM) before each request. Generate the hash:

```bash
docker run --rm debian:bookworm-slim bash -c \
  "apt-get update -qq && apt-get install -y -qq tor >/dev/null && tor --hash-password 'YourSecurePassword'"
# the last printed line is the hash, like: 16:AF97...  (copy it into the torrc)
```

Copy the hash (`16:...`) into the torrc. The same password in plain text goes into
`CONTROL_PASSWORD` inside [`browser-tor/app.py`](browser-tor/app.py).

#### 1.3 torrc — [`tor-snowflake/torrc`](tor-snowflake/torrc)

```bash
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
> The `-ice` and `Bridge` lines are **one single line each**. Replace
> `PASTE_THE_GENERATED_HASH_HERE` with the generated hash. The IP `192.0.2.3` in the
> Bridge line is a placeholder from the official documentation: with Snowflake it doesn't
> matter, because the client connects to the broker via domain fronting and then negotiates
> with a volunteer proxy via WebRTC.

---

### 2. browser-tor: anonymity via Tor — [`browser-tor/`](browser-tor/)

```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy
WORKDIR /app
RUN pip install fastapi uvicorn httpx playwright==1.48.0 stem readability-lxml html2text lxml
COPY app.py /app/app.py
EXPOSE 8081
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8081"]
```

What it does ([`browser-tor/app.py`](browser-tor/app.py)):

- **Hardened Firefox**: `privacy.resistFingerprinting` + letterboxing reduce the browser's uniqueness; viewport 1000x900, UTC timezone and en-US language are values common among Tor users
- **WebRTC disabled**: with WebRTC enabled the real IP leaks via ICE/STUN, bypassing the SOCKS proxy
- **New circuit per request**: NEWNYM via ControlPort (Playwright doesn't support authentication on SOCKS5, so random username/password aren't used; `stem` requires a literal IP, hence `socket.gethostbyname`)
- **Text extraction**: Readability + html2text fallback (see section 6)

---

### 3. browser-clear: normal navigation with stealth — [`browser-clear/`](browser-clear/)

```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy
WORKDIR /app
RUN pip install fastapi uvicorn playwright-stealth httpx playwright==1.48.0 readability-lxml html2text lxml
COPY app.py /app/app.py
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
```

- **Stealth**: `Stealth().use_async(async_playwright())` (playwright-stealth 2.x) masks the typical automation signals
- **WebRTC intentionally enabled**: a real Chrome always has it on; here the real IP isn't a secret to protect
- **`block_media` enabled by default** for speed and RAM saving; with `false` it loads everything like a real user (useful against aggressive anti-bots)

---

### 4. docker-compose.yml — [`docker-compose.yml`](docker-compose.yml)

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

networks:
  ai-net:
    external: true
```

> [!IMPORTANT]
> `ai-net` is `external: true`: the network already exists and is shared with OpenWebUI.
> The ports are bound to `127.0.0.1`: **never publish Tor's 9150/9151**.

---

### 5. Build and startup

```bash
cd ~/ai-stack
docker compose build
docker compose up -d
docker compose ps                      # all three "Up", no restart loop
docker compose logs -f tor-proxy       # wait for "Bootstrapped 100% (done)"
```

The first build takes a few minutes (Snowflake compilation + Playwright image download, about 2 GB).

---

### 6. Verification: test battery

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
```

| Test | Expected result |
|---|---|
| Direct SOCKS | `{"IsTor":true,"IP":"..."}` |
| browser-clear | `IsTor:false` with the VPS's real IP |
| browser-tor | `IsTor:true`, exit node IP different from the VPS's |
| browser-tor on .onion | HTTP 200 with title and text of the page |
| Circuit rotation | Different exit IPs between the two requests |
| webrtc-leak-check | `leaked_ips` with the real IP: proof that WebRTC must stay disabled |

> [!NOTE]
> Always use real URLs in tests: a placeholder URL returns a 404 that looks like a code problem.

---

### 7. Integration with OpenWebUI

#### 7.1 Network and reachability

```bash
docker inspect open-webui --format '{{json .NetworkSettings.Networks}}'   # ai-net must appear
docker network connect ai-net open-webui                                  # only if missing
docker exec open-webui curl -s -m 10 http://browser-clear:8080/health     # {"status":"ok"}
docker exec open-webui curl -s -m 10 http://browser-tor:8081/health       # {"status":"ok"}
```

#### 7.2 Tool 1: normal browser

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

#### 7.3 Tool 2: Tor browser

```python
"""
title: Web Browser (Tor/Anonymous)
description: Browses .onion or normal sites anonymously via Tor (Snowflake), with a new circuit per request
"""
import httpx

class Tools:
    def __init__(self):
        self.base_url = "http://browser-tor:8081"

    async def browse_tor(self, url: str, block_media: bool = True) -> str:
        """
        Browses a web page (including .onion) via the Tor network for complete anonymity.

        :param url: Full URL to visit, including .onion addresses
        :param block_media: True blocks images/fonts/videos (faster and lighter on Tor).
        """
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(f"{self.base_url}/browse", json={"url": url, "block_media": block_media})
            if r.status_code != 200:
                return f"Error from the browser-service: HTTP {r.status_code}"
            data = r.json()
            return f"Title: {data.get('title')}\nFinal URL: {data.get('final_url')}\n\n{data.get('text', '')[:4000]}"
```

> [!NOTE]
> Inside Docker, services communicate on internal ports (`browser-clear:8080`,
> `browser-tor:8081`), not on those mapped to the host. The `[:4000]` limit keeps token
> usage under control: increase it if you need longer extracts.

#### 7.4 Avoiding conflicts with native Web Search

If the integrated Web Search is enabled, disable it (Admin Panel → Settings → Web Search → OFF): with two competing tools, small models choose inconsistently. Then, in the global System Prompt:

```text
To browse normal websites ALWAYS use the browse_web tool.
For .onion sites, or when the user explicitly requests anonymity, ALWAYS use the browse_tor tool.
You have no other way to access the internet.
```

---

### 8. Intelligent text extraction

Four mechanisms, present in both browsers:

1. **Resource blocking** (`block_media`): `page.route("**/*.{png,jpg,...}")` stops images, fonts and videos before they download → faster pages and less memory. On sites with serious anti-bot, disable it: a Chrome that never loads images is anomalous behavior.
2. **Cookie killer**: removes the containers of the main CMPs (OneTrust, Cookiebot, Quantcast, TrustArc...) from the DOM and restores scrolling. It doesn't bypass server-side paywalls.
3. **Two-level extraction**: level 1 Readability (structured article); level 2 fallback html2text on all the HTML (homepages, indexes, search results). You never get a hard error.
4. **`domcontentloaded` + fixed wait (2500 ms)** instead of `networkidle`: ad-filled sites never reach the "silent network" and would go into timeout.

> [!WARNING]
> Some CMPs have anti-tamper protection: on repubblica.it (Iubenda), removing the banner
> with `el.remove()` emptied the entire page (HTML from 496,335 to 15 characters). In those
> cases, hide with `el.style.setProperty('display','none','important')` instead of removing.

---

### 9. Troubleshooting

| Error / symptom | Cause | Solution |
|---|---|---|
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

### 10. Useful commands

```bash
cd ~/ai-stack
docker compose ps                                        # container status
docker compose logs -f browser-tor                       # logs in real time
docker compose logs browser-clear --tail 30 | grep -i warn
# after modifying an app.py / Dockerfile:
docker compose build browser-clear browser-tor && docker compose up -d browser-clear browser-tor
docker compose restart tor-proxy                         # restart only Tor
docker compose down                                      # stop everything (the ai-net network remains)
```
