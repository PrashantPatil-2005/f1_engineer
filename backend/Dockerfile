# ──────────────────────────────────────────────
# F1 AI Race Engineer — Multi-Stage Dockerfile
# ──────────────────────────────────────────────
# Stage 1: Build React frontend
# Stage 2: Production Python server + built frontend

# ── Stage 1: Build frontend ──
FROM node:20-alpine AS frontend-build

WORKDIR /build

# Copy frontend package files
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --production=false

# Copy frontend source and build
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Production ──
FROM python:3.12-slim AS production

# System deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt && \
    pip install --no-cache-dir gunicorn

# Copy app source
COPY backend/config/ backend/config/
COPY backend/src/ backend/src/
COPY backend/app/ backend/app/
COPY backend/mcp_server/ backend/mcp_server/
COPY backend/wsgi.py backend/wsgi.py
COPY backend/gunicorn.conf.py backend/gunicorn.conf.py

# Copy built frontend
COPY --from=frontend-build /build/dist frontend/dist/

# Create backend data directories
RUN mkdir -p backend/data/cache backend/data/processed backend/data/faiss backend/data/metrics

# Environment
ENV PYTHONUNBUFFERED=1
ENV FLASK_HOST=0.0.0.0
ENV FLASK_PORT=5000

EXPOSE 5000

# Run backend modules relative to backend/ root
WORKDIR /app/backend

# Container-level liveness probe — uses /api/health (cheap, no deps touched).
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0) if urllib.request.urlopen('http://localhost:5000/api/health',timeout=5).status==200 else sys.exit(1)"

# Run with gunicorn for production (config in gunicorn.conf.py)
CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
