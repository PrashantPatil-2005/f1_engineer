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

# Run with gunicorn for production
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "1", \
     "--threads", "4", \
     "--timeout", "120", \
     "--worker-class", "gthread", \
     "app.server:create_app()"]
