# Flood payout calculator: one image with the React page and the FastAPI service.
# Build from the repository root:   docker build -t flood-payout:2.0.0 .
# Run on its own:                   docker run -p 8000:8000 flood-payout:2.0.0     then open http://localhost:8000

# Stage 1: build the React app into static files.
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime. Library versions are pinned to the ones the model file was built with
# (a joblib model file should be loaded with the same scikit-learn version that saved it).
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    MODEL_PATH=/srv/models/flood_payout_v2.joblib STATIC_DIR=/srv/static
WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY app/ app/
COPY models/ models/
COPY --from=web /web/dist/ static/

# Files copied from some computers keep owner-only permissions (for example 600). The app runs as a
# non-root user, so make everything under /srv readable.
RUN chmod -R a+rX /srv

RUN useradd --create-home appuser
USER appuser

# Fail the build if the model file does not load with these library versions. This runs as the same
# non-root user as the service, so a permission problem fails the build instead of the start-up.
RUN python -c "from app import model; print('model loads:', model.info())"
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
# --proxy-headers: the client IP (for the rate limit) comes from Caddy's X-Forwarded-For header. This is safe
# only because the app container is reachable from Caddy alone (see docker-compose.yml: expose, not ports).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
