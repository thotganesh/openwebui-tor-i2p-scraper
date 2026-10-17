#!/bin/bash
set -e
export DISPLAY=:99
mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix 2>/dev/null || true
rm -f /tmp/.X99-lock
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &
for _ in $(seq 1 50); do
  [ -e /tmp/.X11-unix/X99 ] && break
  sleep 0.1
done
exec uvicorn app:app --host 0.0.0.0 --port 8081
