# Riusa l'immagine gia' costruita di browser-tor-real (stesso Tor Browser, stesso launcher).
FROM ai-stack-browser-tor-real:latest
USER root
COPY interactive.py interactive_entrypoint.sh /app/
RUN chmod +x /app/interactive_entrypoint.sh
USER tb
EXPOSE 9377
ENTRYPOINT ["/app/interactive_entrypoint.sh"]
