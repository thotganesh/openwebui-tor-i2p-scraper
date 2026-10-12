#!/usr/bin/env bash
# Install / uninstall the egress-guard (systemd unit + script).
# Idempotent: safe to re-run.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SRC_SH="$HERE/egress-guard.sh"
SRC_SVC="$HERE/egress-guard.service"
DST_SH="/usr/local/sbin/egress-guard.sh"
DST_SVC="/etc/systemd/system/egress-guard.service"
UNIT="egress-guard"

if [ "$(id -u)" -ne 0 ]; then
    echo "serve root: sudo $0 $*" >&2
    exit 1
fi

cmd="${1:-install}"

case "$cmd" in
  install)
    [ -f "$SRC_SH" ]  || { echo "manca $SRC_SH" >&2;  exit 1; }
    [ -f "$SRC_SVC" ] || { echo "manca $SRC_SVC" >&2; exit 1; }

    install -m 0755 "$SRC_SH"  "$DST_SH"
    install -m 0644 "$SRC_SVC" "$DST_SVC"
    systemctl daemon-reload
    systemctl enable --now "$UNIT" >/dev/null
    echo "[+] egress-guard installato e attivo"
    systemctl --no-pager -n 4 status "$UNIT" | sed -n '1,8p' || true
    ;;

  uninstall)
    systemctl disable --now "$UNIT" 2>/dev/null || true
    rm -f "$DST_SH" "$DST_SVC"
    systemctl daemon-reload
    echo "[+] egress-guard rimosso"
    ;;

  status)
    systemctl --no-pager status "$UNIT" || true
    ;;

  *)
    echo "uso: $0 [install|uninstall|status]" >&2
    exit 1
    ;;
esac
