#!/usr/bin/env bash
B="${1:-http://127.0.0.1:8086}"
post() { curl -s -m 200 -X POST "$B/browse" -H 'Content-Type: application/json' -d "$1"; echo; }
echo "== health"; curl -s -m 10 "$B/health"; echo
echo "== 1) IsTor + exit IP (JS off)"; time post '{"url":"https://check.torproject.org/api/ip"}'
echo "== 2) exit IP (run 2): deve essere diverso"; post '{"url":"https://check.torproject.org/api/ip"}'
echo "== 3) pref e fingerprint JS ON"; curl -s -m 200 "$B/debug/fingerprint?js=true" | python3 -m json.tool
echo "== 4) pref JS OFF (security level)"; curl -s -m 200 "$B/debug/fingerprint?js=false" | python3 -m json.tool
echo "== 5) header inviati dal browser (JS off)"; post '{"url":"https://httpbin.org/headers"}' | head -c 700; echo
echo "== 6) ricerca Ahmia 'library' (form reale via Tor)"; time curl -s -m 200 -X POST "$B/search/ahmia" -H 'Content-Type: application/json' -d '{"query":"library","max_results":8}' | python3 -m json.tool
