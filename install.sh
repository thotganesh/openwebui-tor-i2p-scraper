#!/bin/bash
# ============================================================
# Open WebUI Tor/I2P Scraper - Full Installation Script
# ============================================================
# Installs the entire v3.1 stack in one go:
#   - tor-proxy (Tor + Snowflake)
#   - browser-tor (Firefox + Playwright + Tor)
#   - browser-clear (Patchright - Chromium stealth)
#   - browser-camoufox (Camoufox - Firefox engine-level stealth)
#   - browser-http (curl_cffi - fast HTTP)
#   - browser-i2p (Firefox + I2P + eyedeekay prefs)
#   - i2p-proxy (i2pd router)
#   - solverr (Cloudflare/Turnstile solver)
#   - searxng (self-hosted meta search)
#
# Prerequisites:
#   - Docker + Docker Compose
#   - OpenWebUI already running (container named "open-webui")
#   - ~5 GB free disk space
#   - Outgoing UDP open (for Snowflake)
#
# OpenWebUI is NOT installed by this script. Only integrated.
# ============================================================

set -euo pipefail

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[x]${NC} $*" >&2; }
info() { echo -e "${BLUE}[i]${NC} $*"; }
step() { echo -e "\n${CYAN}===${NC} $* ${CYAN}===${NC}"; }

# --- Config ---
STACK_DIR="${STACK_DIR:-$HOME/ai-stack}"
DOCKER_NETWORK="${DOCKER_NETWORK:-ai-net}"
OPENWEBUI_CONTAINER="${OPENWEBUI_CONTAINER:-open-webui}"
GITHUB_REPO="${GITHUB_REPO:-thotganesh/openwebui-tor-i2p-scraper}"
GITHUB_BRANCH="${GITHUB_BRANCH:-main}"
RAW_BASE="https://raw.githubusercontent.com/${GITHUB_REPO}/${GITHUB_BRANCH}"

# ============================================================
# STEP 1: Check prerequisites
# ============================================================
step "1/9 Prerequisites check"

if ! command -v openssl >/dev/null 2>&1; then
    err "openssl not found. Install it: apt-get install -y openssl"
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    err "Docker not found. Install it first:"
    err "  curl -fsSL https://get.docker.com | sh"
    exit 1
fi
log "Docker: $(docker --version | head -1)"

if ! docker compose version >/dev/null 2>&1; then
    err "Docker Compose (v2) not found."
    exit 1
fi
log "Docker Compose: $(docker compose version --short)"

if ! docker ps --format '{{.Names}}' | grep -q "^${OPENWEBUI_CONTAINER}$"; then
    err "OpenWebUI container '${OPENWEBUI_CONTAINER}' not found in running containers."
    err ""
    err "Install OpenWebUI first: https://docs.openwebui.com/getting-started/"
    err ""
    err "If your container has a different name, run:"
    err "  OPENWEBUI_CONTAINER=your-name bash install.sh"
    exit 1
fi
log "OpenWebUI found: ${OPENWEBUI_CONTAINER}"

AVAIL_GB=$(df -BG "$HOME" | awk 'NR==2 {print $4}' | tr -d 'G')
if [ "$AVAIL_GB" -lt 35 ]; then
    warn "Only ${AVAIL_GB}GB free. Recommended: 35GB+ (14GB images + 12GB build cache + 6.5GB OpenWebUI if colocated). Continuing anyway..."
fi
log "Disk space: ${AVAIL_GB}GB available (need ~35GB for the first install)"

# ============================================================
# STEP 2: Create directories
# ============================================================
step "2/9 Creating directories"

mkdir -p "$STACK_DIR"/{tor-snowflake,browser-tor,browser-clear,browser-camoufox,browser-http,browser-i2p,searxng-config,openwebui-tools,i2p-data}
cd "$STACK_DIR"
chmod -R 777 i2p-data
log "Created $STACK_DIR with subdirectories"

# ============================================================
# STEP 3: Download all files from GitHub
# ============================================================
step "3/9 Downloading files from GitHub"

download() {
    local src="$1"
    local dst="$2"
    if curl -fsSL "${RAW_BASE}/${src}" -o "$dst"; then
        log "  ${src}"
    else
        err "  Failed: ${src}"
        return 1
    fi
}

download "docker-compose.yml"          "docker-compose.yml"
download ".env.example"                ".env.example"
download ".gitignore"                  ".gitignore"
download "README.md"                   "README.md"

download "tor-snowflake/Dockerfile"    "tor-snowflake/Dockerfile"
download "tor-snowflake/torrc"         "tor-snowflake/torrc"

download "browser-tor/Dockerfile"      "browser-tor/Dockerfile"
download "browser-tor/app.py"          "browser-tor/app.py"

download "browser-clear/Dockerfile"    "browser-clear/Dockerfile"
download "browser-clear/app.py"        "browser-clear/app.py"

download "browser-camoufox/Dockerfile" "browser-camoufox/Dockerfile"
download "browser-camoufox/app.py"     "browser-camoufox/app.py"

download "browser-http/Dockerfile"     "browser-http/Dockerfile"
download "browser-http/requirements.txt" "browser-http/requirements.txt"
download "browser-http/app.py"         "browser-http/app.py"

download "browser-i2p/Dockerfile"      "browser-i2p/Dockerfile"
download "browser-i2p/requirements.txt" "browser-i2p/requirements.txt"
download "browser-i2p/app.py"          "browser-i2p/app.py"

download "searxng-config/settings.yml.example" "searxng-config/settings.yml.example"

download "openwebui-tools/web_tool.py"     "openwebui-tools/web_tool.py"
download "openwebui-tools/darknet_tool.py" "openwebui-tools/darknet_tool.py"

log "All files downloaded"

# ============================================================
# STEP 4: Generate secrets
# ============================================================
step "4/9 Generating secrets"

if [ -f .env ]; then
    info ".env already exists, skipping generation"
else
    info "Generating Tor ControlPort password (24 chars)..."
    TOR_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)

    info "Computing Tor ControlPort hash (this takes ~20s)..."
    TOR_HASH=$(docker run --rm debian:bookworm-slim bash -c \
        "apt-get update -qq && apt-get install -y -qq tor >/dev/null 2>&1 && tor --hash-password '$TOR_PASSWORD'" \
        | tail -1)

    if [ -z "$TOR_HASH" ] || [[ ! "$TOR_HASH" =~ ^16: ]]; then
        err "Failed to compute Tor ControlPort hash. Check Docker/network."
        exit 1
    fi
    log "Tor hash computed: ${TOR_HASH:0:20}..."

    cat > .env << EOF
TOR_CONTROL_PASSWORD=$TOR_PASSWORD
TOR_CONTROL_HASH=$TOR_HASH
EOF
    chmod 600 .env
    log ".env created with random Tor credentials"
fi

if [ -f searxng-config/settings.yml ]; then
    info "searxng-config/settings.yml already exists, skipping"
else
    info "Generating SearXNG secret key (64 hex chars)..."
    SEARXNG_KEY=$(openssl rand -hex 32)
    cp searxng-config/settings.yml.example searxng-config/settings.yml
    sed -i "s/CHANGE_ME_generate_with_openssl_rand_hex_32/$SEARXNG_KEY/" searxng-config/settings.yml
    log "searxng-config/settings.yml created with random secret"
fi

touch searxng-config/limiter.toml

# ============================================================
# STEP 5: Docker network
# ============================================================
step "5/9 Docker network setup"

if ! docker network inspect "$DOCKER_NETWORK" >/dev/null 2>&1; then
    docker network create "$DOCKER_NETWORK"
    log "Network '$DOCKER_NETWORK' created"
else
    info "Network '$DOCKER_NETWORK' already exists"
fi

if ! docker inspect "$OPENWEBUI_CONTAINER" --format '{{json .NetworkSettings.Networks}}' | grep -q "$DOCKER_NETWORK"; then
    docker network connect "$DOCKER_NETWORK" "$OPENWEBUI_CONTAINER"
    log "OpenWebUI connected to '$DOCKER_NETWORK'"
else
    info "OpenWebUI already connected to '$DOCKER_NETWORK'"
fi

# ============================================================
# STEP 6: Verify compose
# ============================================================
step "6/9 Verifying docker-compose.yml"

if ! docker compose config > /dev/null 2>&1; then
    err "docker-compose.yml has syntax errors"
    docker compose config 2>&1 | head -20
    exit 1
fi
log "docker-compose.yml is valid"
SERVICE_COUNT=$(docker compose config --services | wc -l)
log "Services: $SERVICE_COUNT"

# ============================================================
# STEP 7: Build images
# ============================================================
step "7/9 Building Docker images (5-15 min on first run)"

docker compose build

log "All images built"

# ============================================================
# STEP 8: Start containers
# ============================================================
step "8/9 Starting containers"

docker compose up -d
info "Waiting for services to stabilize (30 seconds)..."
sleep 30
log "Containers status:"
docker compose ps

# ============================================================
# STEP 9: Wait for Tor + health checks
# ============================================================
step "9/9 Health checks"

info "Waiting for Tor to bootstrap (up to 120s)..."
for i in $(seq 1 60); do
    if docker compose logs tor-proxy 2>&1 | grep -q "Bootstrapped 100%"; then
        log "Tor bootstrapped 100%"
        break
    fi
    sleep 2
done

echo ""
info "Running health checks..."

check_http() {
    local name="$1"
    local url="$2"
    if curl -sf -m 10 "$url" >/dev/null 2>&1; then
        log "  ${name} OK"
    else
        warn "  ${name} NOT RESPONDING (${url})"
    fi
}

check_http "browser-clear"    "http://127.0.0.1:8082/health"
check_http "browser-tor"      "http://127.0.0.1:8081/health"
check_http "browser-i2p"      "http://127.0.0.1:8083/health"
check_http "browser-http"     "http://127.0.0.1:8084/health"
check_http "browser-camoufox" "http://127.0.0.1:8085/health"
check_http "solverr"          "http://127.0.0.1:8191/"
check_http "searxng"          "http://127.0.0.1:8888/"

echo ""
echo "============================================================"
log "Installation complete!"
echo "============================================================"
echo ""
info "Stack directory:   $STACK_DIR"
info "Docker network:    $DOCKER_NETWORK"
info "OpenWebUI:         $OPENWEBUI_CONTAINER"
echo ""
info "Services:"
echo "  browser-clear    -> http://127.0.0.1:8082  (Patchright / Chromium)"
echo "  browser-tor      -> http://127.0.0.1:8081  (Firefox + Tor)"
echo "  browser-i2p      -> http://127.0.0.1:8083  (Firefox + I2P)"
echo "  browser-http     -> http://127.0.0.1:8084  (curl_cffi)"
echo "  browser-camoufox -> http://127.0.0.1:8085  (Camoufox / Firefox C++)"
echo "  solverr          -> http://127.0.0.1:8191  (Cloudflare solver)"
echo "  searxng          -> http://127.0.0.1:8888  (meta search)"
echo ""
warn "NEXT STEPS (manual, ~5 minutes):"
echo ""
echo "  1. Wait 3-5 minutes for I2P to warm up"
echo "  2. Open OpenWebUI in browser"
echo "  3. Import tools: Admin -> Workspace -> Tools -> New Tool"
echo "     - Name: Web       -> paste ${STACK_DIR}/openwebui-tools/web_tool.py"
echo "     - Name: Darknet   -> paste ${STACK_DIR}/openwebui-tools/darknet_tool.py"
echo "  4. Disable Web Search: Admin -> Settings -> Web Search -> OFF"
echo "  5. Set System Prompt: Admin -> Settings -> General -> System Prompt"
echo "     (copy from ${STACK_DIR}/README.md section 11.5)"
echo "  6. In chat, click wrench icon and enable Web + Darknet"
echo ""
info "To view logs:"
echo "  cd $STACK_DIR && docker compose logs -f browser-camoufox"
echo ""
info "To update in the future (re-run the installer):"
echo "  bash install.sh"
echo "  (the directory was created with curl, not git clone)"
echo "  (existing .env and settings.yml are preserved)"
echo ""
log "Done."

# Disk space hint
echo ""
info "Disk usage:"
DISK_AVAIL=$(df -BG / | awk 'NR==2 {print $4}' | tr -d 'G')
echo "  Free: ${DISK_AVAIL}GB"
if docker system df >/dev/null 2>&1; then
    BUILD_CACHE=$(docker system df 2>/dev/null | grep -i "build cache" | awk '{print $4}')
    [ -n "$BUILD_CACHE" ] && echo "  Docker build cache: ${BUILD_CACHE}"
fi
echo ""
info "To reclaim ~12 GB of build cache (next rebuild will be slower):"
echo "  docker builder prune -f"
echo ""
info "To reclaim unused images:"
echo "  docker image prune -f"
