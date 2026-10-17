FROM python:3.11-slim-bookworm

ARG GECKODRIVER_VERSION=0.36.0
# Fingerprint della chiave "Tor Browser Developers": VERIFICALA su
# https://support.torproject.org/tbb/how-to-verify-signature/
# Se non coincide, la build si ferma (fail-closed).
ARG TB_FPR=EF6E286DDA85EA2A4BA7DE684E2C6E8793298290

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg xz-utils procps xvfb xauth \
    libgtk-3-0 libdbus-glib-1-2 libasound2 libx11-xcb1 libxt6 libxtst6 \
    libxcomposite1 libxdamage1 libxrandr2 libgbm1 libxkbcommon0 libpci3 \
    && rm -rf /var/lib/apt/lists/*

# --- Tor Browser ufficiale, con verifica firma GPG ---
COPY fetch_tb.py /tmp/fetch_tb.py
RUN set -eux; cd /tmp; \
    URL="$(python3 /tmp/fetch_tb.py)"; \
    echo "Tor Browser: $URL"; \
    curl -fsSL "$URL" -o tb.tar.xz; \
    curl -fsSL "$URL.asc" -o tb.tar.xz.asc; \
    export GNUPGHOME="$(mktemp -d)"; \
    ( gpg --batch --auto-key-locate nodefault,wkd --locate-keys torbrowser@torproject.org \
      || gpg --batch --keyserver hkps://keys.openpgp.org --recv-keys "$TB_FPR" \
      || gpg --batch --keyserver hkps://keyserver.ubuntu.com --recv-keys "$TB_FPR" ); \
    gpg --batch --status-fd 1 --verify tb.tar.xz.asc tb.tar.xz | tee verify.txt; \
    grep -E '^\[GNUPG:\] VALIDSIG ' verify.txt | awk '{print $NF}' | grep -qx "$TB_FPR"; \
    tar -xJf tb.tar.xz -C /opt; \
    chmod -R a+rX /opt/tor-browser; \
    test -x /opt/tor-browser/Browser/firefox \
      || { ls -la /opt/tor-browser /opt/tor-browser/Browser | head -60; exit 1; }; \
    rm -rf /tmp/tb.tar.xz* /tmp/verify.txt "$GNUPGHOME"

# --- geckodriver (Marionette) ---
RUN set -eux; \
    curl -fsSL "https://github.com/mozilla/geckodriver/releases/download/v${GECKODRIVER_VERSION}/geckodriver-v${GECKODRIVER_VERSION}-linux64.tar.gz" \
      | tar -xz -C /usr/local/bin geckodriver; \
    chmod +x /usr/local/bin/geckodriver; \
    sha256sum /usr/local/bin/geckodriver; \
    geckodriver --version | head -1

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Tor Browser rifiuta di girare come root
RUN useradd -m -u 10001 tb
WORKDIR /app
COPY app.py entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh
USER tb
EXPOSE 8081
ENTRYPOINT ["/app/entrypoint.sh"]
