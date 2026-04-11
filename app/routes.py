"""
F1 AI Race Engineer — API Routes

POST /api/ask    — Main endpoint: question → streamed answer + chart_data
GET  /api/health — Health check with cache stats

Full request flow:
  POST /ask → Query classifier → Cache check → FastF1 fetch (if miss) →
  Processor → FAISS retrieval → MCP builder → LLM stream → SSE response

SSE format:
  data: {"type": "token", "content": "Max"}
  data: {"type": "token", "content": " Verstappen"}
  data: {"type": "done", "answer": "...", "chart_data": {...}, "metrics": {...}}
"""

import json
import time
import logging
import threading
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
# POST /api/ask — Main endpoint
# ──────────────────────────────────────────────

@api_bp.route("/ask", methods=["POST"])
def ask():
    """
    Process a natural language F1 question and stream the response.

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

    # ── Step 1: Classify query ──
    from src.mcp_engine.query_classifier import classify_query

    try:
        t_classify_start = time.perf_counter()
        entities = classify_query(question)
        t_classify = time.perf_counter() - t_classify_start
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        return jsonify({"error": f"Failed to understand your question: {e}"}), 500

    logger.info(
        f"Step 1 — Classified: year={entities.year}, race={entities.race}, "
        f"driver={entities.driver}, type={entities.query_type} ({t_classify:.2f}s)"
    )

    # ── Step 2: Load or fetch data ──
    from src.data_processor.process_data import load_chunks, process_session, save_chunks
    from src.data_loader.load_race import load_session

    t_data_start = time.perf_counter()
    cache_hit = True

    chunks = load_chunks(entities.year, entities.race, entities.session_type)
    if chunks is None:
        cache_hit = False
        logger.info("Cache miss — fetching from FastF1...")
        try:
            session_data = load_session(
                entities.year, entities.race, entities.session_type
            )
            chunks = process_session(session_data)
            save_chunks(chunks, entities.year, entities.race, entities.session_type)
        except Exception as e:
            logger.error(f"Data loading failed: {e}")
            return jsonify({"error": f"Failed to load race data: {e}"}), 500
    else:
        logger.info("Cache hit — using processed chunks from disk.")

    t_data = time.perf_counter() - t_data_start

    # ── Step 3: FAISS retrieval ──
    from src.retrieval.retriever import Retriever

    t_retrieval_start = time.perf_counter()
    retriever = Retriever()

    try:
        index, indexed_chunks = retriever.load_or_build(
            chunks, entities.year, entities.race, entities.session_type
        )
        retrieved = retriever.query(question, index, indexed_chunks)
    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        return jsonify({"error": f"Failed to search race data: {e}"}), 500

    t_retrieval = time.perf_counter() - t_retrieval_start

    # ── Step 4: Build MCP prompt ──
    from src.mcp_engine.mcp_builder import build_prompt, extract_chart_data

    prompt = build_prompt(question, retrieved, entities.query_type)

    # ── Step 5: Stream LLM response via SSE ──
    from src.llm_interface.llm import stream_completion

    def generate():
        """SSE generator — streams tokens, then sends final summary event."""
        full_response = []
        t_llm_start = time.perf_counter()

        try:
            for delta in stream_completion(prompt):
                full_response.append(delta)
                event = json.dumps({"type": "token", "content": delta})
                yield f"data: {event}\n\n"

        except Exception as e:
            logger.error(f"LLM streaming failed: {e}")
            error_event = json.dumps({"type": "error", "content": str(e)})
            yield f"data: {error_event}\n\n"
            return

        t_llm = time.perf_counter() - t_llm_start
        t_total = time.perf_counter() - t_total_start

        # ── Extract chart data from response ──
        answer = "".join(full_response)
        chart_data = extract_chart_data(answer)

        # ── Clean answer (remove chart_data block from display text) ──
        clean_answer = answer
        if chart_data:
            marker = "```chart_data"
            idx = clean_answer.find(marker)
            if idx != -1:
                # Find closing ```
                end_idx = clean_answer.find("```", idx + len(marker))
                if end_idx != -1:
                    clean_answer = (
                        clean_answer[:idx].rstrip() +
                        clean_answer[end_idx + 3:].lstrip()
                    )

        # ── Build metrics ──
        metrics = {
            "classify_time": round(t_classify, 3),
            "data_time": round(t_data, 3),
            "retrieval_time": round(t_retrieval, 3),
            "llm_time": round(t_llm, 3),
            "total_time": round(t_total, 3),
            "cache_hit": cache_hit,
            "chunks_retrieved": len(retrieved),
            "year": entities.year,
            "race": entities.race,
            "session": entities.session_type,
            "query_type": entities.query_type,
        }

        # ── Save metrics to disk ──
        _save_metrics(question, metrics)

        # ── Final done event ──
        done_event = json.dumps({
            "type": "done",
            "answer": clean_answer,
            "chart_data": chart_data,
            "metrics": metrics,
        })
        yield f"data: {done_event}\n\n"

        logger.info(
            f"━━━ Done: {t_total:.2f}s total "
            f"(classify={t_classify:.2f}s, data={t_data:.2f}s, "
            f"retrieval={t_retrieval:.2f}s, llm={t_llm:.2f}s) ━━━"
        )

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
        },
    )


# ──────────────────────────────────────────────
# GET /api/health — Health check
# ──────────────────────────────────────────────

@api_bp.route("/health", methods=["GET"])
def health():
    """Health check endpoint with cache stats."""
    from flask import current_app
    import os

    # Check for config errors
    config_error = current_app.config.get("CONFIG_ERROR")

    # Count cached files
    processed_count = len(list(config.PROCESSED_DIR.glob("*.json")))
    faiss_count = len(list(config.FAISS_DIR.glob("*.index")))

    status = "unhealthy" if config_error else "healthy"

    return jsonify({
        "status": status,
        "config_error": config_error,
        "cache": {
            "processed_sessions": processed_count,
            "faiss_indices": faiss_count,
        },
        "config": {
            "model": config.GEMINI_MODEL,
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
