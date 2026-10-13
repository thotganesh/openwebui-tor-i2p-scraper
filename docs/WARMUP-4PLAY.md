# 4play warm-up (required, one-time)

Google aggressively challenges datacenter IPs and headless browsers. The `4play`
bridge solves this by driving a real Firefox through a WebSocket, but only
after the browser profile has "warmed up" — a single real search that Google
records as human.

Without this warm-up, every query through `fourget` returns a CAPTCHA.

## Procedure (5 minutes, once per install)

### 1. Start the containers

    cd ~/ai-stack
    docker compose up -d fourget fourplay firefox-4play

### 2. Open a VNC tunnel from your local machine

    ssh -L 5900:127.0.0.1:5900 root@<your-vps-ip>

Keep the SSH session open.

### 3. Connect with a VNC client

Connect to `localhost:5900`. Password: `cnc`.

- macOS: Finder → Cmd+K → `vnc://localhost:5900`
- Linux: `vncviewer localhost:5900` (or `remmina`)
- Windows: TightVNC or RealVNC Viewer

### 4. Inside Firefox (in the VNC window)

1. Go to: `https://addons.mozilla.org/firefox/addon/4play/`
2. Install the extension (Add to Firefox -> Add)
3. Click the 4play icon in the toolbar
4. Fill in:
   - **C&C server**: `ws://fourplay:3030/cnc`
   - **Connect timeout**: `5000`
5. Click **Connect** — the icon should turn green
6. Go to `https://www.google.com`
7. Search anything (e.g. `test`) — wait for the results page to load fully
8. If a CAPTCHA appears, solve it manually
9. Close the VNC window (not Firefox — Firefox stays running in the container)

### 5. Verify from the VPS

    docker logs fourplay --tail 10
    # Expected: "New browser instance connected: Firefox/..."

    docker exec fourget curl -s "http://localhost/api/v1/web?s=test&scraper=google" | head -c 200
    # Expected: {"status":"ok",...,"web":[{"title":"..."}]}

If you see Google results, the warm-up succeeded.

## When to redo it

- Google starts returning CAPTCHA consistently
- You delete `~/ai-stack/firefox-4play-data/`
- You recreate the `firefox-4play` container with `--force-recreate`

The Firefox profile (cookies, history, session) is stored in
`firefox-4play-data/` on the host and survives container restarts. It is
**not** committed to git.

## If the extension shows "unreachable"

- Confirm the container is up: `docker ps --filter name=fourplay`
- Confirm the URL: it must be `ws://fourplay:3030/cnc` (the container name, not `localhost`)
- Check that Firefox and fourplay are on the same network:
  `docker network inspect ai-net --format '{{range .Containers}}{{.Name}} {{end}}'`
