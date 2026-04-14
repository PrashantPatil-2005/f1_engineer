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

import json
import time
import asyncio
import logging
import threading
import importlib.util
from collections import defaultdict
from flask import Blueprint, request, Response, jsonify, stream_with_context
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
# GET /api/health — Health check
# ──────────────────────────────────────────────

@api_bp.route("/health", methods=["GET"])
def health():
    """Health check endpoint with cache stats."""
    from flask import current_app
    # Check for config errors
    config_error = current_app.config.get("CONFIG_ERROR")

    # Count cached files
    processed_count = len(list(config.PROCESSED_DIR.glob("*.json")))
    faiss_count = len(list(config.FAISS_DIR.glob("*.index")))

    dependency_status = {
        "mcp": importlib.util.find_spec("mcp") is not None,
        "groq": importlib.util.find_spec("groq") is not None,
        "fastf1": importlib.util.find_spec("fastf1") is not None,
        "faiss": importlib.util.find_spec("faiss") is not None,
    }
    dependencies_ok = all(dependency_status.values())
    has_api_key = bool(config.GROQ_API_KEY)

    status = "unhealthy" if config_error else "healthy"
    if not dependencies_ok:
        status = "degraded" if not config_error else status
    if not has_api_key:
        status = "degraded" if not config_error else status

    return jsonify({
        "status": status,
        "config_error": config_error,
        "checks": {
            "dependencies_ok": dependencies_ok,
            "dependency_status": dependency_status,
            "groq_api_key_present": has_api_key,
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
    })


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
