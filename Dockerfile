# --- Stage 1: build the PWA -------------------------------------------------
FROM node:22-alpine AS webbuild
WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./ 
RUN npm run build

# --- Stage 2: backend -------------------------------------------------------
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv/aegis

# deterministic wheels from the frozen manifest
COPY requirements-server.txt ./
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache-dir -r requirements-server.txt

COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY backend/ ./backend/
COPY models/insightface/ ./models/insightface/
COPY --from=webbuild /build/web/dist/ ./web/dist/

ENV PYTHONPATH=/srv/aegis
ENV OWNERAI_HOST=0.0.0.0 OWNERAI_PORT=8000
ENV OWNERAI_FACE_MODEL_DIR=/srv/aegis/models/insightface

# DB + logs live outside the image layer; mount them in compose.
VOLUME ["/srv/aegis/var"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)"

CMD ["sh", "-c", "python -m alembic upgrade head && python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"]
