# --- Stage 1: build snowflake-client ---
FROM golang:1.23-bookworm AS builder

# Permette a Go di scaricare automaticamente la toolchain richiesta dal go.mod
ENV GOTOOLCHAIN=auto

RUN git clone https://git.torproject.org/pluggable-transports/snowflake.git /tmp/snowflake \
    && cd /tmp/snowflake/client \
    && go build -o /usr/local/bin/snowflake-client .

# --- Stage 2: immagine finale, solo runtime ---
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    tor obfs4proxy ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/bin/snowflake-client /usr/local/bin/snowflake-client
RUN chmod +x /usr/local/bin/snowflake-client

EXPOSE 9150
CMD ["tor", "-f", "/etc/tor/torrc"]
