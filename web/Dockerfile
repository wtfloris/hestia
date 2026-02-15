FROM python:3.13-slim-bookworm

LABEL maintainer="hello@hestia.bot" \
      description="Hestia housing notification web portal"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd -g 1000 hestia && \
    useradd -u 1000 -g hestia -s /bin/bash -m hestia

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/*

COPY --chown=hestia:hestia requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=hestia:hestia hestia_web/ hestia_web/
COPY --chown=hestia:hestia templates/ templates/
COPY --chown=hestia:hestia static/ static/

USER hestia
EXPOSE 5050

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5050/health').read()" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5050", "--workers", "2", "--threads", "4", \
     "--worker-class", "gthread", "--timeout", "60", \
     "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info", "hestia_web.app:app"]
