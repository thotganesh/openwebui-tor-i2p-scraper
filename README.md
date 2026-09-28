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


