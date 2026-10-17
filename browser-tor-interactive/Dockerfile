# Riusa l'immagine di browser-tor-real (stesso Tor Browser, stesso launcher).
# In Compose BASE_IMAGE vale "base" = il servizio browser-tor-real (costruito prima).
# A mano: docker build --build-arg BASE_IMAGE=ai-stack-browser-tor-real:latest .
ARG BASE_IMAGE=ai-stack-browser-tor-real:latest
FROM ${BASE_IMAGE}
USER root
COPY interactive.py interactive_entrypoint.sh /app/
RUN chmod +x /app/interactive_entrypoint.sh
USER tb
EXPOSE 9377
ENTRYPOINT ["/app/interactive_entrypoint.sh"]
