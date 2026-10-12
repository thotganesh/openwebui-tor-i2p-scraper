#!/usr/bin/env bash
# Update ai-stack from origin/main.
# Idempotent: safe to re-run. Creates a dated backup first.
set -euo pipefail

cd "$(dirname "$0")"

log()  { printf '\033[0;32m[+]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
err()  { printf '\033[0;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

[ -d .git ] || err "not a git checkout: run from the ai-stack repo"

# ---------- 1. refuse if working tree is dirty ----------
if ! git diff --quiet || ! git diff --cached --quiet; then
    err "working tree has local changes. Commit or stash them first:
    git -C $(pwd) status"
fi

# ---------- 2. backup ----------
BK="$HOME/stack-backup-$(date +%Y%m%d-%H%M%S)-ai-stack"
log "backup -> $BK"
mkdir -p "$BK"
cp -a .env "$BK/.env" 2>/dev/null || true
git rev-parse HEAD > "$BK/HEAD"
log "backup done"

# ---------- 3. pull ----------
log "git fetch + pull --ff-only"
git fetch origin
BEFORE=$(git rev-parse HEAD)
git pull --ff-only origin main
AFTER=$(git rev-parse HEAD)
if [ "$BEFORE" = "$AFTER" ]; then
    log "already up to date ($AFTER)"
else
    log "updated $BEFORE -> $AFTER"
    git log --oneline "$BEFORE..$AFTER" | head -20
fi

# ---------- 4. build ----------
log "docker compose build"
docker compose build

# ---------- 5. up ----------
log "docker compose up -d --remove-orphans"
docker compose up -d --remove-orphans

# ---------- 6. wait for Tor ----------
log "waiting for Tor to bootstrap (max 240s)"
ok=0
for i in $(seq 1 80); do
    if docker logs tor-proxy 2>&1 | grep -q "Bootstrapped 100%"; then
        ok=1; log "Tor bootstrapped after ~$((i*3))s"; break
    fi
    sleep 3
done
[ "$ok" = "1" ] || warn "Tor did not report 100% in 240s — check 'docker logs tor-proxy'"

# ---------- 7. status ----------
log "container status"
docker compose ps

log "ai-stack update complete. Backup at $BK"
