"""Stampa su stdout l'URL del tarball Tor Browser stabile per Linux x86_64.
Legge il manifest ufficiale del Tor Project; se la struttura non e' quella
attesa si ferma con un errore leggibile (nessun fallback silenzioso)."""
import json
import sys
import urllib.request

DL = "https://aus1.torproject.org/torbrowser/update_3/release/downloads.json"


def walk(obj, path=()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, path + (str(k),))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, path + (str(i),))
    elif isinstance(obj, str):
        yield path, obj


with urllib.request.urlopen(DL, timeout=30) as r:
    data = json.load(r)

cands = []
for path, val in walk(data):
    hay = "/".join(path).lower() + " " + val.lower()
    if val.startswith("https://") and val.endswith(".tar.xz") and (
        "linux-x86_64" in hay or "linux64" in hay
    ):
        cands.append((path, val))

if not cands:
    top = list(data.keys()) if isinstance(data, dict) else type(data).__name__
    sys.exit("ERRORE: nessun tarball linux-x86_64 trovato. Chiavi top-level: %s" % top)

# se ci sono piu' localizzazioni, preferisci en-US / ALL
cands.sort(key=lambda c: (0 if ("en-us" in c[1].lower() or "all" in "/".join(c[0]).lower()) else 1, c[1]))
print("candidati: %s" % [c[1] for c in cands], file=sys.stderr)
print(cands[0][1])
