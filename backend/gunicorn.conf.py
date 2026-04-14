"""Gunicorn configuration for the F1 AI Race Engineer backend.

Tuned for an SSE-streaming Flask app that fans out to an MCP subprocess and
an LLM provider per request. Defaults can be overridden via env vars so the
same image works across local, staging, and prod.
"""

import multiprocessing
import os

# ── Bind ──
bind = f"{os.getenv('FLASK_HOST', '0.0.0.0')}:{os.getenv('FLASK_PORT', '5000')}"

# ── Workers ──
# SSE requests hold a worker thread for the duration of the LLM call, so favor
# threads over processes (cheaper, shared FAISS/embeddings memory).
workers = int(os.getenv("GUNICORN_WORKERS", "2"))
threads = int(os.getenv("GUNICORN_THREADS", "8"))
worker_class = "gthread"
worker_connections = 100

# ── Timeouts ──
# LLM tool-use loops can legitimately take >60s; keep generous timeouts.
timeout = int(os.getenv("GUNICORN_TIMEOUT", "180"))
graceful_timeout = 30
keepalive = 5

# ── Recycling ──
# Recycle workers periodically to bound memory growth from FAISS/torch.
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "500"))
max_requests_jitter = 50

# ── Logging ──
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(L)ss "%(a)s"'

# ── Process naming ──
proc_name = "f1-engineer"

# Avoid a no-op CPU detection for very small boxes.
_cpu = multiprocessing.cpu_count()
if workers > _cpu * 2 + 1:
    workers = _cpu * 2 + 1
