#!/bin/bash
set -e

echo "[entrypoint] Attendo che tor-proxy sia raggiungibile..."
for i in $(seq 1 30); do
    if curl -s -m 2 --socks5-hostname tor-proxy:9150 https://check.torproject.org/api/ip > /dev/null 2>&1; then
        echo "[entrypoint] tor-proxy raggiungibile."
        break
    fi
    sleep 2
done

python3 /app/startup_check.py
if [ $? -ne 0 ]; then
    echo "[entrypoint] Self-check fallito. Uscita."
    exit 1
fi

echo "[entrypoint] Self-check superato, avvio uvicorn..."
exec uvicorn app:app --host 0.0.0.0 --port 8081
