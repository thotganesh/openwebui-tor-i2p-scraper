"""browser-tor-real: Tor Browser ufficiale (Marionette) dietro lo stesso
contratto /browse del vecchio browser-tor.

Rete: Tor Browser NON lancia un proprio tor; usa il tor-proxy esistente
(Snowflake) via TOR_SKIP_LAUNCH + TOR_SOCKS_* + TOR_CONTROL_*.
"""
import asyncio
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
from urllib.parse import unquote, urlparse

import html2text
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from readability import Document
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

TB_DIR = os.environ.get("TB_DIR", "/opt/tor-browser")
TB_BINARY = f"{TB_DIR}/Browser/firefox"
TB_PROFILE_SRC = f"{TB_DIR}/Browser/TorBrowser/Data/Browser/profile.default"
GECKODRIVER = os.environ.get("GECKODRIVER", "/usr/local/bin/geckodriver")

TOR_HOST = os.environ.get("TOR_HOST", "tor-proxy")
TOR_SOCKS_PORT = int(os.environ.get("TOR_SOCKS_PORT", "9150"))
TOR_CONTROL_PORT = int(os.environ.get("TOR_CONTROL_PORT", "9151"))
CONTROL_PASSWORD = os.environ.get("TOR_CONTROL_PASSWORD")
if not CONTROL_PASSWORD:
    raise RuntimeError("TOR_CONTROL_PASSWORD is required.")

# Il Tor Browser isola i circuiti da solo (credenziali SOCKS casuali per
# ogni avvio/dominio). NEWNYM e' quindi opzionale: 1 = lo forza a ogni richiesta.
NEWNYM = os.environ.get("TOR_NEWNYM", "0") == "1"
DEBUG = os.environ.get("TB_DEBUG", "0") == "1"

_SEM = asyncio.Semaphore(int(os.environ.get("MAX_CONCURRENT", "1")))

app = FastAPI()


class BrowseRequest(BaseModel):
    url: str
    wait_selector: str | None = None
    extract_text: bool = True
    block_media: bool = True
    js_enabled: bool = False


# ------------------------------------------------------------------ utils

COOKIE_KILLER_JS = """
const CMP_SELECTORS = [
    '#onetrust-banner-sdk', '#onetrust-consent-sdk',
    '#cookiebot', '#CybotCookiebotDialog',
    '.qc-cmp2-container', '#qc-cmp2-container',
    '#truste-consent-track', '.truste_box_overlay',
    '.cc-window', '.fc-consent-root', '#cookie-notice',
    '.paywall', '[class*="cookie-banner"]', '[id*="cookie-consent"]',
    '#iubenda-cs-banner', '.iubenda-cs-container', '.iubenda-cs-visible',
    '[class*="iubenda"]', 'iframe[src*="iubenda"]',
    '#didomi-host', '#didomi-notice', '.didomi-popup-backdrop',
    '[class*="didomi"]',
    '.cmplz-cookiebanner', '.cmplz-manage-consent',
    '.cky-consent-container', '.cky-modal',
    '.cli-modal-backdrop', '#cookie-law-info-bar',
    '.termly-cookie-policy',
    '.klaro .cookie-modal', '.klaro .cookie-notice',
    '#ccpa-banner',
    '.fc-dialog-overlay',
    '#gdpr-banner', '.gdpr-banner',
];
CMP_SELECTORS.forEach(sel => {
    document.querySelectorAll(sel).forEach(el => {
        el.style.setProperty('display', 'none', 'important');
        el.style.setProperty('visibility', 'hidden', 'important');
    });
});
document.documentElement.style.setProperty('overflow', 'auto', 'important');
if (document.body) {
    document.body.style.setProperty('overflow', 'auto', 'important');
}
return 'cookie-killer: done';
"""

NUMERIC_HOST = re.compile(r"(0x[0-9a-f]+|\d+)(\.(0x[0-9a-f]+|\d+))*")


def validate_url(url: str) -> None:
    u = urlparse(url)
    if u.scheme not in ("http", "https"):
        raise ValueError("schema non consentito")
    host = (u.hostname or "").lower().rstrip(".")
    if not host or host == "localhost" or host.endswith((".local", ".internal", ".localhost")):
        raise ValueError("host non consentito")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None:
        if not ip.is_global:
            raise ValueError("IP non pubblico")
    elif NUMERIC_HOST.fullmatch(host):
        raise ValueError("host numerico ambiguo")
    elif "." not in host:
        raise ValueError("host senza dominio (rete interna?)")


def pulisci_testo(html_content: str) -> str:
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True
    h.body_width = 0
    try:
        doc = Document(html_content)
        testo = h.handle(doc.summary()).strip()
        if testo:
            return testo
    except Exception:
        pass
    try:
        return h.handle(html_content).strip()
    except Exception as e:
        return f"Extraction error: {e}"


def _short(e: Exception) -> str:
    return " ".join(str(e).split())[:300]


def _newnym() -> bool:
    """SIGNAL NEWNYM sulla ControlPort di tor-proxy (protocollo testuale, no stem)."""
    try:
        ip = socket.gethostbyname(TOR_HOST)
        pw = CONTROL_PASSWORD.replace("\\", "\\\\").replace('"', '\\"')
        with socket.create_connection((ip, TOR_CONTROL_PORT), timeout=10) as s:
            s.settimeout(10)
            s.sendall(f'AUTHENTICATE "{pw}"\r\n'.encode())
            if not s.recv(256).startswith(b"250"):
                return False
            s.sendall(b"SIGNAL NEWNYM\r\n")
            ok = s.recv(256).startswith(b"250")
            s.sendall(b"QUIT\r\n")
            return ok
    except Exception as e:
        print(f"[warn] NEWNYM failed: {_short(e)}", flush=True)
        return False


# ---------------------------------------------------------------- browser

def _prefs(js_enabled: bool, block_media: bool, tor_ip: str) -> dict:
    p = {
        # fallback esplicito: la fonte primaria sono le variabili TOR_* d'ambiente
        "network.proxy.type": 1,
        "network.proxy.socks": tor_ip,
        "network.proxy.socks_port": TOR_SOCKS_PORT,
        "network.proxy.socks_version": 5,
        "network.proxy.socks_remote_dns": True,
        # niente traffico di servizio inutile via Tor
        "app.update.enabled": False,
        "app.update.auto": False,
        "app.update.service.enabled": False,
        "browser.startup.homepage": "about:blank",
        "browser.startup.page": 0,
    }
    if not js_enabled:
        # livello "Safest" del Tor Browser + JS spento (come un utente reale)
        p["browser.security_level.security_slider"] = 1
        p["javascript.enabled"] = False
    if block_media:
        p["permissions.default.image"] = 2
        p["media.autoplay.default"] = 5
    extra = os.environ.get("TB_EXTRA_PREFS", "").strip()
    if extra:
        p.update(json.loads(extra))
    return p


def _launch(js_enabled: bool, block_media: bool):
    tor_ip = socket.gethostbyname(TOR_HOST)
    profile_dir = tempfile.mkdtemp(prefix="tbprofile-")
    if os.path.isdir(TB_PROFILE_SRC):
        shutil.copytree(TB_PROFILE_SRC, profile_dir, dirs_exist_ok=True)

    opts = Options()
    opts.binary_location = TB_BINARY
    opts.add_argument("-profile")
    opts.add_argument(profile_dir)
    if DEBUG:
        opts.add_argument("-remote-allow-system-access")  # solo debug: legge i pref
    opts.page_load_strategy = "eager"
    opts.accept_insecure_certs = False  # default di selenium e' True: da NON usare su Tor
    for k, v in _prefs(js_enabled, block_media, tor_ip).items():
        opts.set_preference(k, v)

    env = dict(os.environ)
    env.update({
        "TOR_SKIP_LAUNCH": "1",
        "TOR_SKIP_CONTROLPORTTEST": "1",
        "TOR_NO_DISPLAY_NETWORK_SETTINGS": "1",
        "TOR_SOCKS_HOST": tor_ip,
        "TOR_SOCKS_PORT": str(TOR_SOCKS_PORT),
        "TOR_CONTROL_HOST": tor_ip,
        "TOR_CONTROL_PORT": str(TOR_CONTROL_PORT),
        "TOR_CONTROL_PASSWD": CONTROL_PASSWORD,
    })
    service = Service(executable_path=GECKODRIVER, env=env, log_output=subprocess.DEVNULL)
    try:
        driver = webdriver.Firefox(options=opts, service=service)
    except Exception:
        shutil.rmtree(profile_dir, ignore_errors=True)
        raise
    driver.set_page_load_timeout(90)
    driver.set_script_timeout(30)
    return driver, profile_dir


def _close(driver, profile_dir):
    if driver is not None:
        try:
            driver.quit()
        except Exception:
            pass
    if profile_dir:
        shutil.rmtree(profile_dir, ignore_errors=True)


def _browse_sync(req: BrowseRequest) -> dict:
    renewed = _newnym() if NEWNYM else False
    driver, profile_dir = None, None
    try:
        try:
            driver, profile_dir = _launch(req.js_enabled, req.block_media)
        except Exception as e:
            return {"error": f"Tor Browser launch failed: {_short(e)}", "circuit_renewed": renewed,
                    "title": "", "final_url": req.url, "text": ""}
        try:
            driver.get(req.url)
        except Exception as e:
            return {"error": f"Navigation failed: {_short(e)}", "circuit_renewed": renewed,
                    "title": "", "final_url": req.url, "text": ""}
        if req.wait_selector:
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, req.wait_selector)))
            except Exception as e:
                print(f"[warn] wait_selector '{req.wait_selector}' not found: {_short(e)}", flush=True)
        time.sleep(2.5)
        if req.js_enabled:
            try:
                driver.execute_script(COOKIE_KILLER_JS)
            except Exception as e:
                print(f"[warn] Cookie killer failed: {_short(e)}", flush=True)
        final_url = driver.current_url
        if final_url.startswith(("about:neterror", "about:certerror", "about:blocked")):
            return {"error": f"Reached error page: {final_url[:200]}", "circuit_renewed": renewed,
                    "title": driver.title, "final_url": req.url, "text": ""}
        result = {"title": driver.title, "final_url": final_url, "circuit_renewed": renewed}
        if req.extract_text:
            result["text"] = pulisci_testo(driver.page_source)
        return result
    finally:
        _close(driver, profile_dir)


@app.post("/browse")
async def browse(req: BrowseRequest):
    try:
        validate_url(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    async with _SEM:
        return await asyncio.to_thread(_browse_sync, req)


# ------------------------------------------------------------------ debug

FP_JS = """
let gl = null;
try { gl = document.createElement('canvas').getContext('webgl'); } catch (e) {}
return {
  userAgent: navigator.userAgent,
  platform: navigator.platform,
  language: navigator.language,
  languages: navigator.languages,
  hardwareConcurrency: navigator.hardwareConcurrency,
  webdriver: navigator.webdriver,
  doNotTrack: navigator.doNotTrack,
  maxTouchPoints: navigator.maxTouchPoints,
  plugins: navigator.plugins.length,
  screen: [screen.width, screen.height, screen.availWidth, screen.availHeight, screen.colorDepth],
  inner: [window.innerWidth, window.innerHeight],
  devicePixelRatio: window.devicePixelRatio,
  timezoneOffset: new Date().getTimezoneOffset(),
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  rtcPeerConnection: typeof RTCPeerConnection,
  webgl: gl ? 'available' : 'unavailable'
};
"""

CHROME_JS = """
const P = Services.prefs;
const g = (n) => {
  const t = P.getPrefType(n);
  if (t === 0) return 'missing';
  if (t === 32) return P.getStringPref(n);
  if (t === 64) return P.getIntPref(n);
  return P.getBoolPref(n);
};
const names = [
  'privacy.resistFingerprinting',
  'privacy.resistFingerprinting.letterboxing',
  'privacy.fingerprintingProtection',
  'privacy.fingerprintingProtection.pbmode',
  'privacy.fingerprintingProtection.overrides',
  'general.useragent.override',
  'general.platform.override',
  'browser.security_level.security_slider',
  'browser.security_level.security_custom',
  'javascript.enabled',
  'webgl.disabled',
  'media.peerconnection.enabled',
  'privacy.firstparty.isolate',
  'network.proxy.socks',
  'network.proxy.socks_port',
  'network.proxy.socks_remote_dns',
  'network.proxy.type',
  'layout.css.devPixelsPerPx',
  'dom.maxHardwareConcurrency',
  'privacy.resistFingerprinting.exemptedDomains',
  'privacy.resistFingerprinting.testing.setTZtoUTC',
  'privacy.globalprivacycontrol.enabled'
];
const out = {app: Services.appinfo.name + ' ' + Services.appinfo.version};
for (const n of names) out[n] = g(n);
return out;
"""


def _fp_sync(js_enabled: bool) -> dict:
    driver, profile_dir = None, None
    try:
        driver, profile_dir = _launch(js_enabled, False)
        out = {}
        try:
            driver.set_context("chrome")
            out["chrome"] = driver.execute_script(CHROME_JS)
        except Exception as e:
            out["chrome"] = f"non leggibile: {_short(e)}"
        finally:
            try:
                driver.set_context("content")
            except Exception:
                pass
        if js_enabled:
            driver.get("data:text/html,<html><body>fp</body></html>")
            out["content"] = driver.execute_script(FP_JS)
        return out
    except Exception as e:
        return {"error": _short(e)}
    finally:
        _close(driver, profile_dir)


@app.get("/debug/fingerprint")
async def debug_fingerprint(js: bool = True):
    if not DEBUG:
        raise HTTPException(status_code=404)
    async with _SEM:
        return await asyncio.to_thread(_fp_sync, js)


# ------------------------------------------------------------ ricerca Ahmia

class AhmiaRequest(BaseModel):
    query: str
    max_results: int = 15


ONION_RE = re.compile(r'redirect_url=(https?://[a-z0-9]+\.onion[^"&\s]*)')


def _ahmia_sync(query: str, max_results: int) -> dict:
    """Apre Ahmia via Tor, compila e invia il form come un utente (il token
    nascosto viene inviato dal browser stesso), poi estrae i link .onion."""
    driver, profile_dir = None, None
    try:
        try:
            driver, profile_dir = _launch(False, True)
        except Exception as e:
            return {"error": f"Tor Browser launch failed: {_short(e)}", "results": []}
        try:
            driver.get("https://ahmia.fi/")
            box = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='q']")))
            box.send_keys(query)
            box.send_keys(Keys.ENTER)
            WebDriverWait(driver, 60).until(lambda d: "/search" in d.current_url)
        except Exception as e:
            return {"error": f"Ahmia navigation failed: {_short(e)}", "results": []}
        time.sleep(1.5)
        html = driver.page_source
        found = ONION_RE.findall(html) or ONION_RE.findall(unquote(html))
        seen, results = set(), []
        for u in found:
            if u not in seen:
                seen.add(u)
                results.append(u)
        out = {"query": query, "final_url": driver.current_url, "count": len(results),
               "results": results[:max(1, min(max_results, 50))]}
        if not results:
            out["note"] = pulisci_testo(html)[:400]
        return out
    finally:
        _close(driver, profile_dir)


@app.post("/search/ahmia")
async def search_ahmia(req: AhmiaRequest):
    q = req.query.strip()
    if not q or len(q) > 200:
        raise HTTPException(status_code=400, detail="query non valida")
    async with _SEM:
        return await asyncio.to_thread(_ahmia_sync, q, req.max_results)


@app.get("/health")
async def health():
    return {"status": "ok"}
