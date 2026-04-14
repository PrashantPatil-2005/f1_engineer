"""
F1 AI Race Engineer — API Routes

POST /api/ask    — Main endpoint: question → MCP tool-use loop → streamed answer
GET  /api/health — Health check with cache stats

Full request flow:
  POST /ask → MCP client connects → Gemini tool-use loop (discovers & calls
  F1 data tools via MCP server) → streams final answer via SSE

SSE format:
  data: {"type": "token", "content": "Max"}
  data: {"type": "token", "content": " Verstappen"}
  data: {"type": "done", "answer": "...", "chart_data": {...}, "metrics": {...}}
"""

import asyncio
import importlib.util
import json
import logging
import threading
import time
from collections import defaultdict

from flask import Blueprint, Response, jsonify, request, stream_with_context

from config import config

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__)


# ──────────────────────────────────────────────
# Simple rate limiter (token bucket: 10 req/min)
# ──────────────────────────────────────────────

_rate_limits = defaultdict(lambda: {"tokens": 10, "last_refill": time.time()})
_rate_lock = threading.Lock()
RATE_LIMIT = 10        # requests per window
RATE_WINDOW = 60       # seconds


def _check_rate_limit(ip: str) -> bool:
    """Check and consume a rate limit token. Returns True if allowed."""
    with _rate_lock:
        bucket = _rate_limits[ip]
        now = time.time()

        # Refill tokens based on elapsed time
        elapsed = now - bucket["last_refill"]
        refill = int(elapsed / RATE_WINDOW * RATE_LIMIT)
        if refill > 0:
            bucket["tokens"] = min(RATE_LIMIT, bucket["tokens"] + refill)
            bucket["last_refill"] = now

        if bucket["tokens"] > 0:
            bucket["tokens"] -= 1
            return True
        return False


# ──────────────────────────────────────────────
# POST /api/ask — Main endpoint (MCP + Gemini tool-use)
# ──────────────────────────────────────────────

@api_bp.route("/ask", methods=["POST"])
def ask():
    """
    Process a natural language F1 question and stream the response.

    Uses MCP client → MCP server (stdio) → Gemini tool-use loop.

    Request body:
        { "question": "Why did Verstappen win Monza 2024?" }

    Response: SSE stream (text/event-stream)
    """
    # ── Rate limiting ──
    client_ip = request.remote_addr or "unknown"
    if not _check_rate_limit(client_ip):
        return jsonify({
            "error": "Rate limit exceeded. Please wait a moment before trying again.",
            "retry_after": RATE_WINDOW,
        }), 429

    data = request.get_json(silent=True)
    if not data or "question" not in data:
        return jsonify({"error": "Missing 'question' field in request body"}), 400

    question = data["question"].strip()
    if not question:
        return jsonify({"error": "Question cannot be empty"}), 400

    if len(question) > 500:
        return jsonify({"error": "Question too long (max 500 characters)"}), 400

    logger.info(f"━━━ New query: \"{question}\" ━━━")
    t_total_start = time.perf_counter()
    try:
        from src.mcp_client.client import F1MCPClient
    except ModuleNotFoundError as e:
        logger.error(f"Missing runtime dependency for chat: {e}")
        return jsonify({
            "error": "Chat backend dependency is missing.",
            "details": str(e),
            "hint": "Install backend dependencies: pip install -r backend/requirements.txt",
        }), 503

    def generate():
        """SSE generator — runs MCP tool-use loop and streams the result."""
        # Create a dedicated event loop for this request's async work
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Collect SSE events from the async generator
            async def run_mcp_stream():
                events = []
                client = F1MCPClient()
                await client.connect()
                try:
                    async for event in client.stream_with_tools(question):
                        events.append(event)
                finally:
                    await client.disconnect()
                return events

            sse_events = loop.run_until_complete(run_mcp_stream())

            # Parse the "done" event to inject metrics
            for i, event in enumerate(sse_events):
                if event.startswith("data: "):
                    payload_str = event[6:].strip()
                    try:
                        payload = json.loads(payload_str)
                        if payload.get("type") == "done":
                            # Inject timing metrics
                            t_total = time.perf_counter() - t_total_start
                            payload["metrics"] = {
                                "total_time": round(t_total, 3),
                                "pipeline": "mcp_tool_use",
                            }
                            _save_metrics(question, payload["metrics"])
                            sse_events[i] = f"data: {json.dumps(payload)}\n\n"
                    except json.JSONDecodeError:
                        pass

            for event in sse_events:
                yield event

        except Exception as e:
            logger.error(f"MCP pipeline failed: {e}")
            error_event = json.dumps({"type": "error", "content": str(e)})
            yield f"data: {error_event}\n\n"

        finally:
            loop.close()

        t_total = time.perf_counter() - t_total_start
        logger.info(f"━━━ Done: {t_total:.2f}s total (MCP tool-use pipeline) ━━━")

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ──────────────────────────────────────────────
# Health / readiness
# ──────────────────────────────────────────────
# /api/health — liveness: cheap, no I/O. "Is the process up?"
# /api/ready  — readiness: deeper checks (deps, API keys, cache, disk).
#               "Should this instance receive traffic?"

REQUIRED_DEPENDENCIES = ("mcp", "groq", "fastf1", "faiss")


def _dependency_status() -> dict:
    return {
        name: importlib.util.find_spec(name) is not None
        for name in REQUIRED_DEPENDENCIES
    }


@api_bp.route("/health", methods=["GET"])
def health():
    """Liveness probe — always returns 200 if the process is responsive.

    Used by container orchestrators and the Docker HEALTHCHECK to detect
    a wedged process. Intentionally does no I/O so it stays fast.
    """
    return jsonify({
        "status": "ok",
        "service": "f1-engineer",
    }), 200


@api_bp.route("/ready", methods=["GET"])
def ready():
    """Readiness probe — verifies the instance can actually serve traffic.

    Returns 503 when:
      - config validation failed at startup
      - a required python dependency is missing
      - the LLM API key is not set
      - the data directories are not writable
    """
    from flask import current_app

    config_error = current_app.config.get("CONFIG_ERROR")
    dep_status = _dependency_status()
    deps_ok = all(dep_status.values())
    has_api_key = bool(config.GROQ_API_KEY)

    # Cheap writability check — the metrics file gets appended on every query,
    # so a non-writable data dir is a real outage.
    data_writable = True
    try:
        probe = config.METRICS_DIR / ".ready_probe"
        probe.touch(exist_ok=True)
        probe.unlink(missing_ok=True)
    except Exception as e:
        data_writable = False
        logger.warning(f"Readiness: data dir not writable: {e}")

    processed_count = len(list(config.PROCESSED_DIR.glob("*.json")))
    faiss_count = len(list(config.FAISS_DIR.glob("*.index")))

    failing = []
    if config_error:
        failing.append("config")
    if not deps_ok:
        failing.append("dependencies")
    if not has_api_key:
        failing.append("api_key")
    if not data_writable:
        failing.append("data_writable")

    ready_ok = not failing
    status_code = 200 if ready_ok else 503

    return jsonify({
        "status": "ready" if ready_ok else "not_ready",
        "failing": failing,
        "config_error": config_error,
        "checks": {
            "dependencies_ok": deps_ok,
            "dependency_status": dep_status,
            "groq_api_key_present": has_api_key,
            "data_writable": data_writable,
        },
        "cache": {
            "processed_sessions": processed_count,
            "faiss_indices": faiss_count,
        },
        "config": {
            "model": config.GROQ_MODEL,
            "embedding_model": config.EMBEDDING_MODEL,
            "top_k": config.TOP_K,
            "max_context_tokens": config.MAX_CONTEXT_TOKENS,
        },
    }), status_code


# ──────────────────────────────────────────────
# Metrics persistence
# ──────────────────────────────────────────────

def _save_metrics(question: str, metrics: dict):
    """Append query metrics to a JSON-lines file."""
    import datetime

    metrics_file = config.METRICS_DIR / "query_log.jsonl"
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "question": question,
        **metrics,
    }

    try:
        with open(metrics_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.warning(f"Failed to save metrics: {e}")
