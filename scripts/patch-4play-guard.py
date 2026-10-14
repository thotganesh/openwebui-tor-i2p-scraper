#!/usr/bin/env python3
"""Aggiunge un guard SSRF a page-render.js di 4play (idempotente)."""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else "4play-build/page-render.js"
s = open(p).read()
if "function url_blocked" in s:
    print("guard gia' presente"); sys.exit(0)
a1 = 'if(url === null){ errors.push("url"); }'
a2 = 'const server = http.createServer('
if a1 not in s or a2 not in s:
    sys.exit("anchor non trovati: upstream cambiato, patch NON applicata")
FN = r'''function url_blocked(u){
    try{
        const p = new URL(u);
        if(p.protocol !== "http:" && p.protocol !== "https:"){ return "scheme"; }
        const h = p.hostname.toLowerCase().replace(/\.$/, "");
        if(!h || h === "localhost" || h.startsWith("[")){ return "host"; }
        if(!h.includes(".")){ return "host senza dominio"; }
        if(/\.(local|internal|localhost|lan|home\.arpa|docker|svc|onion|i2p)$/.test(h)){ return "host"; }
        if(/^(\d+|0x[0-9a-f]+)(\.(\d+|0x[0-9a-f]+))*$/i.test(h)){
            const m = h.match(/^(\d+)\.(\d+)\.(\d+)\.(\d+)$/);
            if(!m){ return "numerico ambiguo"; }
            const a = +m[1], b = +m[2];
            if(a === 0 || a === 10 || a === 127 || a >= 224 ||
               (a === 169 && b === 254) || (a === 172 && b >= 16 && b <= 31) ||
               (a === 192 && b === 168) || (a === 100 && b >= 64 && b <= 127)){ return "IP non pubblico"; }
        }
        return null;
    }catch(e){ return "url non valido"; }
}
'''
s = s.replace(a2, FN + "\n" + a2, 1)
s = s.replace(a1, a1 + '\n        if(url !== null && url_blocked(url) !== null){ errors.push("url"); }', 1)
open(p, "w").write(s)
print("guard SSRF applicato a", p)
