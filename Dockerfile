FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    NHLGM_DB=/var/lib/nhlgm/nhl_gm.sqlite3

WORKDIR /app
COPY . /app
RUN mkdir -p /var/lib/nhlgm && chmod +x /app/scripts/start-public.sh

EXPOSE 8000
VOLUME ["/var/lib/nhlgm"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/health',timeout=3)"

CMD ["/app/scripts/start-public.sh"]

