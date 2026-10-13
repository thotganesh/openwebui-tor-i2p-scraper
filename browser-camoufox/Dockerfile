FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg ca-certificates \
    libgtk-3-0 libdbus-glib-1-2 libxt6 libasound2 \
    libx11-xcb1 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2 \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    'camoufox[geoip]==0.4.11' \
    fastapi==0.115.6 \
    uvicorn==0.34.0 \
    readability-lxml==0.8.1 \
    lxml_html_clean==0.4.1 \
    html2text==2024.2.26 \
    lxml==5.3.0

RUN python -m camoufox fetch

COPY app.py /app/app.py
WORKDIR /app
EXPOSE 8085
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8085"]
