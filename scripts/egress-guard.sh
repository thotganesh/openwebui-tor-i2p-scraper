#!/usr/bin/env bash
CONTAINERS="browser-http browser-clear browser-camoufox camofox solverr"
NETS="10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 169.254.0.0/16 100.64.0.0/10 192.0.0.0/24 198.18.0.0/15 224.0.0.0/4"
pid_of() { docker inspect -f '{{.State.Pid}}' "$1" 2>/dev/null; }
apply() {
  local c="$1" pid ip=""
  pid=$(pid_of "$c"); [ "${pid:-0}" -gt 0 ] 2>/dev/null || return 0
  if [ "$c" = "browser-clear" ]; then
    ip=$(docker inspect -f '{{(index .NetworkSettings.Networks "ai-net").IPAddress}}' solverr 2>/dev/null)
  fi
  if nsenter -t "$pid" -n iptables -C OUTPUT -j EGRESS_GUARD 2>/dev/null \
     && { [ -z "$ip" ] || nsenter -t "$pid" -n iptables -C EGRESS_GUARD -d "$ip" -p tcp --dport 8191 -j RETURN 2>/dev/null; }; then
    return 0
  fi
  nsenter -t "$pid" -n iptables -N EGRESS_GUARD 2>/dev/null
  nsenter -t "$pid" -n iptables -F EGRESS_GUARD
  nsenter -t "$pid" -n iptables -A EGRESS_GUARD -o lo -j RETURN
  nsenter -t "$pid" -n iptables -A EGRESS_GUARD -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
  if [ -n "$ip" ]; then nsenter -t "$pid" -n iptables -A EGRESS_GUARD -d "$ip" -p tcp --dport 8191 -j RETURN; fi
  for n in $NETS; do nsenter -t "$pid" -n iptables -A EGRESS_GUARD -d "$n" -j REJECT; done
  nsenter -t "$pid" -n iptables -C OUTPUT -j EGRESS_GUARD 2>/dev/null || nsenter -t "$pid" -n iptables -I OUTPUT 1 -j EGRESS_GUARD
  echo "[egress-guard] regole applicate a $c (pid $pid)"
}
off() {
  for c in $CONTAINERS; do
    pid=$(pid_of "$c"); [ "${pid:-0}" -gt 0 ] 2>/dev/null || continue
    nsenter -t "$pid" -n iptables -D OUTPUT -j EGRESS_GUARD 2>/dev/null
    nsenter -t "$pid" -n iptables -F EGRESS_GUARD 2>/dev/null
    nsenter -t "$pid" -n iptables -X EGRESS_GUARD 2>/dev/null
  done
}
case "${1:-once}" in
  loop) while true; do for c in $CONTAINERS; do apply "$c"; done; sleep 15; done ;;
  off)  off ;;
  *)    for c in $CONTAINERS; do apply "$c"; done ;;
esac
