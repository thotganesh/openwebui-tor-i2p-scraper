import json, re, sys, urllib.request, urllib.parse
B = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:9387"
U = "test-user"
def call(method, path, body=None, params=None, raw=False):
    url = B + path + ("?" + urllib.parse.urlencode(params) if params else "")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=200) as r:
            c = r.read()
            return r.status, (c if raw else json.loads(c))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]
print("health:", call("GET", "/health"))
st, r = call("POST", "/tabs", {"userId": U, "listItemId": "t1",
    "url": "http://duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion/html"})
print("create:", st, r)
tab = r["tabId"]
st, s = call("GET", f"/tabs/{tab}/snapshot", params={"userId": U})
print("snapshot refs:", s["refsCount"]); print("\n".join(s["snapshot"].split("\n")[:25]))
box = re.search(r'(?:textbox|searchbox) "[^"]*" \[(e\d+)\]', s["snapshot"])
btn = re.search(r'button "[^"]*" \[(e\d+)\]', s["snapshot"])
print("textbox:", box and box.group(1), "| button:", btn and btn.group(1))
print("type:", call("POST", f"/tabs/{tab}/type", {"userId": U, "ref": box.group(1), "text": "tor browser"}))
if btn: print("click:", call("POST", f"/tabs/{tab}/click", {"userId": U, "ref": btn.group(1)}))
else:   print("press:", call("POST", f"/tabs/{tab}/press", {"userId": U, "key": "Enter"}))
st, s2 = call("GET", f"/tabs/{tab}/snapshot", params={"userId": U})
print("dopo la ricerca ->", s2["url"], "| link:", s2["snapshot"].count("- link "))
print("scroll:", call("POST", f"/tabs/{tab}/scroll", {"userId": U, "direction": "down"}))
st, png = call("GET", f"/tabs/{tab}/screenshot", params={"userId": U}, raw=True)
print("screenshot:", st, len(png), "byte", png[:4])
print("back:", call("POST", f"/tabs/{tab}/back", {"userId": U}))
print("evaluate:", call("POST", f"/tabs/{tab}/evaluate", {"userId": U, "expression": "window.location.href"}))
print("close:", call("DELETE", f"/sessions/{U}"))
