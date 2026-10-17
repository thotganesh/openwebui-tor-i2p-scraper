"""browser-tor-interactive: Tor Browser ufficiale dietro il sottoinsieme dell'API
REST per-tab di Camofox che Hermes usa (tabs, navigate, snapshot, click, type,
press, scroll, back, screenshot).

Scelte di progetto:
- Nessun JavaScript richiesto: lo snapshot si costruisce dal sorgente della
  pagina (page_source, analizzato lato server) e le azioni usano comandi nativi
  WebDriver. Funziona anche con javascript.enabled=false.
- Un browser (un Tor Browser) per userId, chiuso dopo IDLE_TIMEOUT secondi.
- Ogni ref (e1, e2, ...) punta a un elemento via XPath e viene VERIFICATO
  (tag, href, name) prima dell'azione: se la pagina e' cambiata, errore e non
  un click sull'elemento sbagliato.
"""
import os
import re
import threading
import time
import uuid
from collections import OrderedDict
from urllib.parse import urljoin

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from lxml import html as lhtml
from pydantic import BaseModel
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

import app as tb  # launcher condiviso con /browse (stesso browser, stesse pref)

JS = os.environ.get("INTERACTIVE_JS", "0") == "1"
BLOCK_MEDIA = os.environ.get("INTERACTIVE_BLOCK_MEDIA", "0") == "1"
MAX_TABS = int(os.environ.get("MAX_TABS", "2"))
IDLE_TIMEOUT = int(os.environ.get("IDLE_TIMEOUT", "600"))
SCROLL_PX = 600
MAX_REFS = 400
MAX_LINES = 3000

app = FastAPI()


class ApiError(Exception):
    def __init__(self, status: int, msg: str, **extra):
        super().__init__(msg)
        self.status, self.msg, self.extra = status, msg, extra


@app.exception_handler(ApiError)
async def _api_error(_req, exc: ApiError):
    return JSONResponse({"error": exc.msg, **exc.extra}, status_code=exc.status)


# ------------------------------------------------------------------ registro

class Tab:
    def __init__(self, tab_id, user_id, list_item_id, driver, profile_dir):
        self.id, self.user_id, self.list_item_id = tab_id, user_id, list_item_id
        self.driver, self.profile_dir = driver, profile_dir
        self.lock = threading.RLock()
        self.refs: dict = {}
        self.last_used = time.time()


REG = threading.Lock()          # protegge TABS/BY_USER/REAPED (sezioni brevi)
CREATE_LOCK = threading.Lock()  # serializza la creazione (avvio browser ~10 s)
TABS: dict = {}
BY_USER: dict = {}
REAPED: "OrderedDict[str, bool]" = OrderedDict()


def _forget(t: Tab, reaped: bool) -> None:
    with REG:
        TABS.pop(t.id, None)
        if BY_USER.get(t.user_id) == t.id:
            BY_USER.pop(t.user_id, None)
        if reaped:
            REAPED[t.id] = True
            while len(REAPED) > 200:
                REAPED.popitem(last=False)


def drop_tab(t: Tab, reaped: bool = False) -> None:
    _forget(t, reaped)
    tb._close(t.driver, t.profile_dir)


def get_tab(tab_id: str, user_id: str | None) -> Tab:
    with REG:
        t = TABS.get(tab_id)
        gone = tab_id in REAPED
    if t is None:
        raise ApiError(410 if gone else 404, "tab_gone" if gone else "tab_not_found")
    if user_id and t.user_id != user_id:
        raise ApiError(403, "user_mismatch")
    t.last_used = time.time()
    return t


_GONE_RE = re.compile(
    r"(invalid session|without establishing a connection|has been discarded|"
    r"connection refused|failed to decode response|no such window)", re.I)


def run(t: Tab, fn):
    """Esegue fn(driver) con il lock del tab; errori WebDriver -> ApiError."""
    with t.lock:
        try:
            out = fn(t.driver)
        except WebDriverException as e:
            msg = tb._short(e)
            if _GONE_RE.search(msg):
                drop_tab(t, reaped=True)
                raise ApiError(410, "tab_gone", detail=msg)
            raise ApiError(502, msg)
        t.last_used = time.time()
        return out


def _reaper() -> None:
    while True:
        time.sleep(30)
        try:
            now = time.time()
            with REG:
                idle = [t for t in TABS.values() if now - t.last_used > IDLE_TIMEOUT]
            for t in idle:
                with t.lock:
                    if t.id in TABS:
                        drop_tab(t, reaped=True)
        except Exception as e:  # il reaper non deve mai morire
            print(f"[warn] reaper: {tb._short(e)}", flush=True)


threading.Thread(target=_reaper, daemon=True).start()


@app.on_event("shutdown")
def _shutdown() -> None:
    with REG:
        tabs = list(TABS.values())
    for t in tabs:
        drop_tab(t)


# ------------------------------------------------------------------ utilita'

def check_url(url: str) -> None:
    try:
        tb.validate_url(url)
    except ValueError as e:
        raise ApiError(400, f"url_rejected: {e}")


def nav_error(url: str) -> bool:
    return url.startswith(("about:neterror", "about:certerror", "about:blocked"))


def settle(d) -> None:
    """Dopo un click: lascia caricare e tiene UNA sola finestra."""
    time.sleep(1.0)
    hs = d.window_handles
    if len(hs) > 1:
        for h in hs[:-1]:
            d.switch_to.window(h)
            d.close()
        d.switch_to.window(hs[-1])


# ------------------------------------------------------------------ snapshot

SKIP_TAGS = {"script", "style", "head", "template", "svg", "math", "canvas", "iframe", "object", "embed"}
BUTTON_TYPES = {"submit", "button", "reset", "image"}
TEXT_TYPES = {"", "text", "email", "url", "tel", "number", "password", "date", "datetime-local", "time", "month", "week", "color", "range"}


def norm(s: str | None, limit: int = 300) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= limit else s[:limit] + "..."


def _hidden(el) -> bool:
    if el.get("hidden") is not None:
        return True
    st = (el.get("style") or "").replace(" ", "").lower()
    if "display:none" in st or "visibility:hidden" in st:
        return True
    return el.tag == "input" and (el.get("type") or "").lower() == "hidden"


def build_snapshot(source: str, base_url: str, title: str):
    """Albero in stile accessibilita' + mappa ref -> descrittore dell'elemento."""
    source = re.sub(r"^\s*<\?xml[^>]*\?>", "", source or "")
    parser = lhtml.HTMLParser(encoding="utf-8")
    root = lhtml.document_fromstring(source.encode("utf-8", "replace"), parser=parser)
    tree = root.getroottree()
    labels = {l.get("for"): norm(l.text_content(), 100) for l in root.iter("label") if l.get("for")}

    out = [f"- page {norm(title, 150)!r} ({base_url})"]
    refs: dict = {}

    def add_ref(el, **desc):
        if len(refs) >= MAX_REFS:
            return None
        ref = f"e{len(refs) + 1}"
        refs[ref] = {"xpath": tree.getpath(el), "tag": el.tag, **desc}
        return ref

    def emit_text(s, indent):
        s = norm(s)
        if s:
            out.append(f"{indent}- text: {s}")

    def img_lines(img, indent):
        alt = norm(img.get("alt") or img.get("title"), 150)
        src = (img.get("src") or "").strip()
        src = "" if src.startswith("data:") else urljoin(base_url, src) if src else ""
        if alt or src:
            out.append(f'{indent}- img "{alt}"')
            if src:
                out.append(f"{indent}  - /url: {src}")

    def handle(el, depth):
        indent = "  " * min(depth, 6)
        tag = el.tag.lower()
        if tag in SKIP_TAGS or _hidden(el):
            return
        if tag == "a" and el.get("href") is not None:
            href = el.get("href")
            name = norm(el.text_content(), 150)
            if not name:
                im = next(iter(el.iter("img")), None)
                name = norm((im.get("alt") if im is not None else "") or el.get("title") or el.get("aria-label") or href, 150)
            ref = add_ref(el, href=href, target=(el.get("target") or "").lower())
            if ref:
                out.append(f'{indent}- link "{name}" [{ref}]:')
                out.append(f"{indent}  - /url: {urljoin(base_url, href)}")
            else:
                out.append(f'{indent}- link "{name}"')
            for im in el.iter("img"):
                img_lines(im, indent + "  ")
            return
        if tag == "button":
            name = norm(el.text_content(), 100) or norm(el.get("value") or el.get("aria-label") or el.get("title") or el.get("name"), 100)
            ref = add_ref(el, name=el.get("name"))
            out.append(f'{indent}- button "{name}"' + (f" [{ref}]" if ref else "") + (" [disabled]" if el.get("disabled") is not None else ""))
            return
        if tag == "input":
            typ = (el.get("type") or "").lower()
            ident = el.get("id")
            if typ in BUTTON_TYPES:
                name = norm(el.get("value") or el.get("alt") or el.get("title") or typ, 100)
                role = "button"
            elif typ in ("checkbox", "radio"):
                name = norm(labels.get(ident) or el.get("aria-label") or el.get("title") or el.get("name") or el.get("value"), 100)
                role = typ
            elif typ == "file":
                return
            else:
                name = norm(el.get("aria-label") or labels.get(ident) or el.get("placeholder") or el.get("title") or el.get("name"), 100)
                role = "searchbox" if typ == "search" else "textbox" if typ in TEXT_TYPES else typ
            ref = add_ref(el, name=el.get("name"))
            extra = ""
            if typ in ("checkbox", "radio") and el.get("checked") is not None:
                extra = " [checked]"
            if el.get("disabled") is not None:
                extra += " [disabled]"
            val = "" if typ in ("password", "checkbox", "radio") or typ in BUTTON_TYPES else norm(el.get("value"), 80)
            out.append(f'{indent}- {role} "{name}"' + (f" [{ref}]" if ref else "") + extra + (f": {val}" if val else ""))
            return
        if tag == "textarea":
            name = norm(el.get("aria-label") or labels.get(el.get("id")) or el.get("placeholder") or el.get("name"), 100)
            ref = add_ref(el, name=el.get("name"))
            val = norm(el.text_content(), 80)
            out.append(f'{indent}- textbox "{name}"' + (f" [{ref}]" if ref else "") + (f": {val}" if val else ""))
            return
        if tag == "select":
            name = norm(el.get("aria-label") or labels.get(el.get("id")) or el.get("name"), 100)
            ref = add_ref(el, name=el.get("name"))
            out.append(f'{indent}- combobox "{name}"' + (f" [{ref}]" if ref else ""))
            for o in list(el.iter("option"))[:30]:
                sel = " [selected]" if o.get("selected") is not None else ""
                out.append(f'{indent}  - option "{norm(o.text_content(), 80)}"{sel}')
            return
        if tag == "img":
            img_lines(el, indent)
            return
        if re.fullmatch(r"h[1-6]", tag):
            out.append(f"{indent}- heading [level={tag[1]}]:")
            walk(el, depth + 1)
        else:
            walk(el, depth)

    def walk(el, depth):
        indent = "  " * min(depth, 6)
        emit_text(el.text, indent)
        for child in el:
            if len(out) >= MAX_LINES:
                return
            if isinstance(child.tag, str):
                handle(child, depth)
            emit_text(child.tail, indent)

    body = root.find("body")
    walk(body if body is not None else root, 0)
    if len(out) >= MAX_LINES or len(refs) >= MAX_REFS:
        out.append("- note: snapshot troncato (pagina molto lunga)")
    return "\n".join(out), refs


def resolve(t: Tab, d, ref: str):
    desc = t.refs.get(ref)
    if not desc:
        raise ApiError(409, "ref_unknown", hint="prendi un nuovo snapshot: i ref valgono solo per l'ultimo")
    try:
        el = d.find_element(By.XPATH, desc["xpath"])
    except WebDriverException:
        raise ApiError(409, "ref_stale", hint="elemento non piu' presente: prendi un nuovo snapshot")
    ok = el.tag_name.lower() == desc["tag"]
    if ok and desc.get("href") is not None:
        ok = (el.get_dom_attribute("href") or "") == desc["href"]
    if ok and desc.get("name") is not None:
        ok = (el.get_dom_attribute("name") or "") == desc["name"]
    if not ok:
        raise ApiError(409, "ref_mismatch", hint="la pagina e' cambiata: prendi un nuovo snapshot")
    return el, desc


# ------------------------------------------------------------------ rotte

class CreateBody(BaseModel):
    userId: str
    listItemId: str | None = None
    sessionKey: str | None = None
    url: str | None = None


class UrlBody(BaseModel):
    userId: str | None = None
    url: str


class RefBody(BaseModel):
    userId: str | None = None
    ref: str


class TypeBody(RefBody):
    text: str
    submit: bool = False


class KeyBody(BaseModel):
    userId: str | None = None
    key: str


class ScrollBody(BaseModel):
    userId: str | None = None
    direction: str = "down"


class UserBody(BaseModel):
    userId: str | None = None


class EvalBody(BaseModel):
    userId: str | None = None
    expression: str = ""


@app.get("/health")
def health():
    with REG:
        n = len(TABS)
    return {"status": "ok", "tabs": n, "maxTabs": MAX_TABS, "js": JS}


def _tab_info(t: Tab, d) -> dict:
    return {"tabId": t.id, "listItemId": t.list_item_id, "url": d.current_url, "title": d.title}


@app.get("/tabs")
def list_tabs(userId: str | None = None):
    with REG:
        tabs = [t for t in TABS.values() if not userId or t.user_id == userId]
    out = []
    for t in tabs:
        try:
            out.append(run(t, lambda d, t=t: _tab_info(t, d)))
        except ApiError:
            continue
    return {"tabs": out}


@app.post("/tabs")
def create_tab(b: CreateBody):
    url = (b.url or "about:blank").strip() or "about:blank"
    if url != "about:blank":
        check_url(url)
    with CREATE_LOCK:
        with REG:
            existing = TABS.get(BY_USER.get(b.userId, ""))
            full = existing is None and len(TABS) >= MAX_TABS
        if full:
            raise ApiError(503, "too_many_sessions", hint=f"massimo {MAX_TABS} sessioni: chiudine una o attendi il timeout")
        if existing is None:
            try:
                driver, profile_dir = tb._launch(JS, BLOCK_MEDIA)
            except Exception as e:
                raise ApiError(502, f"Tor Browser launch failed: {tb._short(e)}")
            t = Tab(uuid.uuid4().hex, b.userId, b.listItemId or b.sessionKey, driver, profile_dir)
            with REG:
                TABS[t.id] = t
                BY_USER[b.userId] = t.id
        else:
            t = existing
            t.list_item_id = b.listItemId or b.sessionKey or t.list_item_id
    if url != "about:blank":
        def go(d):
            d.get(url)
            time.sleep(1.5)
            if nav_error(d.current_url):
                raise ApiError(502, f"Reached error page: {d.current_url[:200]}")
        run(t, go)
    return run(t, lambda d: _tab_info(t, d))


@app.post("/tabs/{tab_id}/navigate")
def navigate(tab_id: str, b: UrlBody):
    t = get_tab(tab_id, b.userId)
    check_url(b.url)

    def go(d):
        d.get(b.url)
        time.sleep(1.5)
        if nav_error(d.current_url):
            raise ApiError(502, f"Reached error page: {d.current_url[:200]}")
        return {"ok": True, "url": d.current_url, "title": d.title}
    return run(t, go)


@app.get("/tabs/{tab_id}/snapshot")
def snapshot(tab_id: str, userId: str | None = None):
    t = get_tab(tab_id, userId)

    def go(d):
        url, title = d.current_url, d.title
        text, refs = build_snapshot(d.page_source, url, title)
        t.refs = refs
        return {"url": url, "title": title, "snapshot": text, "refsCount": len(refs)}
    return run(t, go)


@app.post("/tabs/{tab_id}/click")
def click(tab_id: str, b: RefBody):
    t = get_tab(tab_id, b.userId)

    def go(d):
        el, desc = resolve(t, d, b.ref)
        if desc["tag"] == "a" and desc.get("target") == "_blank" and desc.get("href"):
            target = urljoin(d.current_url, desc["href"])
            check_url(target)
            d.get(target)
        else:
            el.click()
        settle(d)
        return {"ok": True, "url": d.current_url}
    return run(t, go)


@app.post("/tabs/{tab_id}/type")
def type_text(tab_id: str, b: TypeBody):
    t = get_tab(tab_id, b.userId)

    def go(d):
        el, _ = resolve(t, d, b.ref)
        try:
            el.clear()
        except WebDriverException:
            pass  # campo non svuotabile: si scrive comunque
        el.send_keys(b.text)
        if b.submit:
            el.send_keys(Keys.ENTER)
            settle(d)
        return {"ok": True}
    return run(t, go)


_KEYS = {
    "enter": Keys.ENTER, "return": Keys.ENTER, "tab": Keys.TAB, "escape": Keys.ESCAPE, "esc": Keys.ESCAPE,
    "backspace": Keys.BACKSPACE, "delete": Keys.DELETE, "space": Keys.SPACE,
    "arrowdown": Keys.ARROW_DOWN, "down": Keys.ARROW_DOWN, "arrowup": Keys.ARROW_UP, "up": Keys.ARROW_UP,
    "arrowleft": Keys.ARROW_LEFT, "left": Keys.ARROW_LEFT, "arrowright": Keys.ARROW_RIGHT, "right": Keys.ARROW_RIGHT,
    "pagedown": Keys.PAGE_DOWN, "pageup": Keys.PAGE_UP, "home": Keys.HOME, "end": Keys.END,
    "control": Keys.CONTROL, "ctrl": Keys.CONTROL, "shift": Keys.SHIFT, "alt": Keys.ALT, "meta": Keys.META,
}


@app.post("/tabs/{tab_id}/press")
def press(tab_id: str, b: KeyBody):
    t = get_tab(tab_id, b.userId)
    parts = [_KEYS.get(p.strip().lower(), p.strip()) for p in b.key.split("+") if p.strip()]
    if not parts:
        raise ApiError(400, "key_required")

    def go(d):
        ac = ActionChains(d)
        for k in parts[:-1]:
            ac.key_down(k)
        ac.send_keys(parts[-1])
        for k in reversed(parts[:-1]):
            ac.key_up(k)
        ac.perform()
        settle(d)
        return {"ok": True, "url": d.current_url}
    return run(t, go)


@app.post("/tabs/{tab_id}/scroll")
def scroll(tab_id: str, b: ScrollBody):
    t = get_tab(tab_id, b.userId)
    dx, dy = {"down": (0, SCROLL_PX), "up": (0, -SCROLL_PX),
              "right": (SCROLL_PX, 0), "left": (-SCROLL_PX, 0)}.get(b.direction.lower(), (0, SCROLL_PX))

    def go(d):
        try:
            ActionChains(d).scroll_by_amount(dx, dy).perform()
        except WebDriverException:
            ActionChains(d).send_keys(Keys.PAGE_UP if dy < 0 else Keys.PAGE_DOWN).perform()
        return {"ok": True}
    return run(t, go)


@app.post("/tabs/{tab_id}/back")
def back(tab_id: str, b: UserBody):
    t = get_tab(tab_id, b.userId)

    def go(d):
        d.back()
        time.sleep(1.0)
        return {"ok": True, "url": d.current_url}
    return run(t, go)


@app.get("/tabs/{tab_id}/screenshot")
def screenshot(tab_id: str, userId: str | None = None):
    t = get_tab(tab_id, userId)
    png = run(t, lambda d: d.get_screenshot_as_png())
    return Response(content=png, media_type="image/png")


@app.post("/tabs/{tab_id}/evaluate")
def evaluate(tab_id: str, b: EvalBody):
    """Solo la sonda di Hermes sull'URL corrente (guard SSRF). Niente JS arbitrario."""
    t = get_tab(tab_id, b.userId)
    if b.expression.strip() != "window.location.href":
        raise ApiError(501, "evaluate_not_supported")
    return {"ok": True, "result": run(t, lambda d: d.current_url)}


@app.post("/tabs/{tab_id}/{action}")
def unsupported(tab_id: str, action: str):
    raise ApiError(501, "action_not_supported", action=action)


@app.delete("/tabs/{tab_id}")
def close_tab(tab_id: str, userId: str | None = None):
    try:
        t = get_tab(tab_id, userId)
    except ApiError as e:
        if e.status in (404, 410):
            return {"ok": True, "closed": 0}
        raise
    with t.lock:
        drop_tab(t)
    return {"ok": True, "closed": 1}


@app.delete("/sessions/{user_id}")
def close_session(user_id: str):
    with REG:
        tabs = [t for t in TABS.values() if t.user_id == user_id]
    for t in tabs:
        with t.lock:
            if t.id in TABS:
                drop_tab(t)
    return {"ok": True, "closed": len(tabs)}


@app.post("/sessions/{user_id}/cookies")
def cookies_unsupported(user_id: str):
    raise ApiError(501, "cookies_not_supported")
