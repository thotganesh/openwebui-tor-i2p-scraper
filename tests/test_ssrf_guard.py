"""Unit tests for shared/ssrf_guard.py.

These run in CI with no container: the module has no external dependency.
"""

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from shared.ssrf_guard import (
    blocked_reason_clearnet,
    blocked_reason_anon,
    check_redirect_chain_clearnet,
)


# ---------- clearnet ----------
CLEARNET_ACCEPT = [
    "https://example.com/",
    "http://1.1.1.1/",
    "https://www.google.com/search?q=test",
]

CLEARNET_REJECT = [
    ("http://127.0.0.1/",                "IP non pubblico"),
    ("http://10.0.0.5/",                 "IP non pubblico"),
    ("http://169.254.169.254/",          "IP non pubblico"),
    ("http://192.168.1.1/",              "IP non pubblico"),
    ("http://172.16.0.1/",               "IP non pubblico"),
    ("http://100.64.0.1/",               "IP non pubblico"),
    ("http://localhost/",                "host non consentito"),
    ("http://foo.local/",                "host non consentito"),
    ("http://foo.internal/",             "host non consentito"),
    ("http://stats.i2p/",                ".onion/.i2p"),
    ("http://abc.onion/",                ".onion/.i2p"),
    ("file:///etc/passwd",               "schema non consentito"),
    ("ftp://example.com/",               "schema non consentito"),
    ("http://0x7f.1/",                   "host numerico"),
    ("http://internalservice/",          "senza dominio"),
    ("",                                 "url non valido"),
]


@pytest.mark.parametrize("url", CLEARNET_ACCEPT)
def test_clearnet_accepts(url):
    assert blocked_reason_clearnet(url) is None


@pytest.mark.parametrize("url,expected", CLEARNET_REJECT)
def test_clearnet_rejects(url, expected):
    why = blocked_reason_clearnet(url)
    assert why is not None, f"{url} should be rejected"
    assert expected in why, f"{url}: got {why!r}"


# ---------- anon .i2p ----------
ANON_I2P_ACCEPT = [
    "http://stats.i2p/",
    "http://legwork.i2p/",
    "http://something.deep.i2p/",
]

ANON_I2P_REJECT = [
    ("http://example.com/",              "host non .i2p"),
    ("http://127.0.0.1/",                "host non .i2p"),
    ("http://abc.onion/",                "host non .i2p"),
    ("file:///etc/passwd",               "schema non consentito"),
    ("http://a@stats.i2p/",              "userinfo non consentito"),
]


@pytest.mark.parametrize("url", ANON_I2P_ACCEPT)
def test_anon_i2p_accepts(url):
    assert blocked_reason_anon(url, ".i2p") is None


@pytest.mark.parametrize("url,expected", ANON_I2P_REJECT)
def test_anon_i2p_rejects(url, expected):
    why = blocked_reason_anon(url, ".i2p")
    assert why is not None, f"{url} should be rejected"
    assert expected in why


# ---------- anon .onion ----------
def test_anon_onion_accepts():
    assert blocked_reason_anon("http://abc.onion/", ".onion") is None


def test_anon_onion_rejects_i2p():
    assert blocked_reason_anon("http://stats.i2p/", ".onion") is not None


# ---------- redirect chain ----------
def test_redirect_chain_all_public():
    assert check_redirect_chain_clearnet([
        "https://example.com/",
        "https://1.1.1.1/",
    ]) is None


def test_redirect_chain_with_private():
    why = check_redirect_chain_clearnet([
        "https://example.com/",
        "http://10.0.0.5/",
    ])
    assert why is not None
    assert "IP non pubblico" in why


def test_redirect_chain_with_localhost():
    why = check_redirect_chain_clearnet([
        "https://example.com/",
        "http://localhost/",
    ])
    assert why is not None
    assert "host non consentito" in why
