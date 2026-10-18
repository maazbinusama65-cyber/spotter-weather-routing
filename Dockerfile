# One image serves everything: Django on gunicorn, with the built React app served by WhiteNoise.

# ---- Stage 1: build the frontend
FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: runtime
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_ENV=production

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend/ backend/
# settings.py looks for the built app at <repo root>/frontend/dist
COPY --from=frontend /build/dist frontend/dist

RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

WORKDIR /app/backend
EXPOSE 10000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','10000')+'/api/health',timeout=4)" || exit 1

# One worker with threads: rate-limit counters live in process memory, so a second
# worker process would double every limit. Requests are I/O bound, so threads suffice.
CMD ["sh", "-c", "exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 8 --timeout 120 --access-logfile -"]
