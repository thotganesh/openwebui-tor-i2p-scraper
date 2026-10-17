#!/usr/bin/env bash
# Rotate the Tor ControlPort password and hash in .env.
# Usage: sudo bash scripts/rotate-tor-password.sh
# Regenerates TOR_CONTROL_PASSWORD and TOR_CONTROL_HASH, then restarts
# tor-proxy. Brief Tor downtime (10-40 s bootstrap).
set -euo pipefail

STACK_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$STACK_DIR"

[ -f .env ] || { echo "manca .env in $STACK_DIR" >&2; exit 1; }
command -v openssl >/dev/null || { echo "openssl non trovato" >&2; exit 1; }

BK="$HOME/stealth-backup-$(date +%Y%m%d-%H%M%S)/rotate-tor-password"
mkdir -p "$BK"
cp -a .env "$BK/.env"
echo "backup: $BK/.env"

NEW_PW="$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')"
NEW_HASH="$(docker run --rm debian:bookworm-slim bash -c \
    "apt-get update -qq && apt-get install -y -qq tor >/dev/null 2>&1 && tor --hash-password '$NEW_PW'" \
    | tail -1)"

case "$NEW_HASH" in
  16:*) ;;
  *) echo "hash generation failed" >&2; exit 1 ;;
esac

# Riscrive solo le due righe
python3 - <<PY
import pathlib, re
p = pathlib.Path("$STACK_DIR/.env")
s = p.read_text()
s = re.sub(r"^TOR_CONTROL_PASSWORD=.*$", "TOR_CONTROL_PASSWORD=$NEW_PW", s, flags=re.MULTILINE)
s = re.sub(r"^TOR_CONTROL_HASH=.*$", "TOR_CONTROL_HASH=$NEW_HASH", s, flags=re.MULTILINE)
p.write_text(s)
PY
chmod 600 .env

echo "restarting tor-proxy..."
docker compose up -d --force-recreate tor-proxy

echo "waiting for Tor bootstrap (max 180s)..."
for i in $(seq 1 90); do
  if docker logs tor-proxy 2>&1 | grep -q "Bootstrapped 100%"; then
    echo "Tor bootstrapped after ~$((i*2))s"
    break
  fi
  sleep 2
done

echo "test browse..."
docker run --rm --network ai-net curlimages/curl:latest -m 90 -s \
echo
echo "done. Password ruotata."
