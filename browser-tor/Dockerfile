FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

WORKDIR /app
RUN apt-get update && apt-get install -y libxml2-dev libxslt1-dev python3-dev && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir \
    fastapi==0.115.6 \
    uvicorn==0.34.0 \
    httpx==0.28.1 \
    playwright==1.48.0 \
    stem==1.8.2 \
    readability-lxml==0.8.1 \
    lxml_html_clean==0.4.1 \
    html2text==2024.2.26 \
    lxml==5.3.0
COPY app.py /app/app.py

EXPOSE 8081
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8081"]
