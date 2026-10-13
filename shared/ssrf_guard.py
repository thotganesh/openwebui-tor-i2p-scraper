"""URL validation helpers shared by the reader containers.

Two entry points:

- ``blocked_reason_clearnet(url)``: full validation for readers that exit
  with the host IP (browser-clear, browser-camoufox, browser-http). It
  resolves the hostname and rejects every record that is not global.

- ``blocked_reason_anon(url, allow_suffix)``: validation for readers that
  exit through an anonymity network (browser-i2p, browser-tor). It does
  **not** resolve the hostname (that would leak the destination to the
  local resolver and defeat the purpose of the network). It only checks
  the literal IP, the private suffixes and that the host ends with the
  expected suffix (``.i2p`` or ``.onion``).

Both return ``None`` if the URL is acceptable, otherwise a short reason
string.

This module has no external dependency beyond the Python stdlib, so it
can be imported and unit-tested in CI without any container.
"""

from __future__ import annotations

import ipaddress
import re
import socket
import time
from urllib.parse import urlparse

__all__ = [
    "blocked_reason_clearnet",
    "blocked_reason_anon",
    "check_redirect_chain_clearnet",
]

# ---- shared constants --------------------------------------------------

# Decimal and hex forms of an IPv4 address (127.0.0.1, 0x7f000001, 127.1)
NUMERIC_HOST = re.compile(r"(0x[0-9a-f]+|\d+)(\.(0x[0-9a-f]+|\d+))*")

# Suffixes that are never routable on the public internet.
PRIVATE_SUFFIXES = (
    ".local", ".internal", ".localhost",
    ".lan", ".home.arpa", ".docker", ".svc",
)

# Small TTL cache so a burst of requests to the same host does not hammer
# the resolver. Cleared when it grows past _DNS_CACHE_MAX entries.
_DNS_TTL = 60
_DNS_CACHE_MAX = 2000
_DNS_CACHE: dict[str, tuple[float, list[ipaddress._BaseAddress]]] = {}


def _resolve_sync(host: str) -> list | None:
    """Resolve ``host`` to a list of ipaddress objects, or None if it fails."""
    now = time.time()
    hit = _DNS_CACHE.get(host)
    if hit and now - hit[0] < _DNS_TTL:
        return hit[1]
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return None
    ips = []
    for _, _, _, _, sockaddr in infos:
        try:
            ips.append(ipaddress.ip_address(sockaddr[0].split("%")[0]))
        except ValueError:
            continue
    if len(_DNS_CACHE) > _DNS_CACHE_MAX:
        _DNS_CACHE.clear()
    _DNS_CACHE[host] = (now, ips)
    return ips


def _normalize_ip(ip):
    """Collapse an IPv4-mapped IPv6 (::ffff:a.b.c.d) to its IPv4 form."""
    if ip.version == 6 and getattr(ip, "ipv4_mapped", None):
        return ip.ipv4_mapped
    return ip


def _parse(url):
    """Return (scheme, host) or raise ValueError with a reason."""
    if not isinstance(url, str) or not url:
        raise ValueError("url non valido")
    try:
        u = urlparse(url)
        host = (u.hostname or "").lower().rstrip(".")
    except (ValueError, TypeError):
        raise ValueError("url non valido")
    if u.scheme not in ("http", "https"):
        raise ValueError("schema non consentito")
    if not host:
        raise ValueError("host mancante")
    return u, host


# ---- public API --------------------------------------------------------

def blocked_reason_clearnet(url):
    """None if OK, else reason. Resolves the hostname and checks every IP."""
    try:
        _, host = _parse(url)
    except ValueError as e:
        return str(e)

    if host == "localhost" or host.endswith(PRIVATE_SUFFIXES):
        return "host non consentito"
    if host.endswith(".onion") or host.endswith(".i2p"):
        return "host .onion/.i2p non gestito da questo container"

    # Literal IP: check directly, no DNS lookup needed.
    try:
        ip = _normalize_ip(ipaddress.ip_address(host))
        if not ip.is_global:
            return f"IP non pubblico ({ip})"
        return None
    except ValueError:
        pass

    if NUMERIC_HOST.fullmatch(host):
        return "host numerico ambiguo"
    if "." not in host:
        return "host senza dominio (rete interna?)"

    ips = _resolve_sync(host)
    if ips is None:
        return "DNS non risolvibile"
    if not ips:
        return "DNS non risolvibile"
    for raw in ips:
        ip = _normalize_ip(raw)
        if not ip.is_global:
            return f"IP non pubblico ({ip})"
    return None


def blocked_reason_anon(url, allow_suffix):
    """None if OK, else reason. No DNS resolution.

    ``allow_suffix`` is the only suffix accepted (e.g. ".i2p" or ".onion").
    Literal private IPs are still rejected. Userinfo is rejected.
    """
    try:
        u, host = _parse(url)
    except ValueError as e:
        return str(e)

    if u.username or u.password:
        return "userinfo non consentito"

    if not host.endswith(allow_suffix):
        return f"host non {allow_suffix}"

    # If it's a literal IP (rare but possible), still reject private ones.
    try:
        ip = _normalize_ip(ipaddress.ip_address(host))
        if not ip.is_global:
            return f"IP non pubblico ({ip})"
    except ValueError:
        pass
    return None


def check_redirect_chain_clearnet(urls):
    """Return a reason string if any URL in the chain is blocked, else None."""
    for u in urls:
        why = blocked_reason_clearnet(u)
        if why:
            return f"{why}: {u[:120]}"
    return None
