"""
F1 AI Race Engineer — LLM Interface

Streaming and non-streaming Google Gemini chat completions.

Usage:
    from src.llm_interface.llm import stream_completion, complete

    # Streaming (for SSE)
    for delta in stream_completion(prompt):
        print(delta, end="", flush=True)

    # Non-streaming (for testing)
    response = complete(prompt)
"""

import time
import logging
from typing import Generator
from google import genai
from google.genai import types
from config import config

logger = logging.getLogger(__name__)


def _get_client() -> genai.Client:
    """Get a Google GenAI client instance."""
    return genai.Client(api_key=config.GOOGLE_API_KEY)


def stream_completion(
    prompt: str,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> Generator[str, None, None]:
    """
    Stream a chat completion from Gemini, yielding content deltas.

    This is the primary interface for the Flask SSE endpoint.
    Each yield is a text fragment from the stream.

    Args:
        prompt: The full prompt string (system + context + question).
        model: Override model. Defaults to config.GEMINI_MODEL.
        temperature: Override temperature. Defaults to config.LLM_TEMPERATURE.
        max_tokens: Override max tokens. Defaults to config.LLM_MAX_TOKENS.

    Yields:
        str content deltas (text fragments).

    Raises:
        RuntimeError: If the Gemini API call fails.
    """
    client = _get_client()
    model = model or config.GEMINI_MODEL
    temperature = temperature if temperature is not None else config.LLM_TEMPERATURE
    max_tokens = max_tokens or config.LLM_MAX_TOKENS

    logger.info(f"Streaming completion: model={model}, temp={temperature}")
    t_start = time.perf_counter()
    chunk_count = 0

    try:
        response_stream = client.models.generate_content_stream(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )

        for chunk in response_stream:
            if chunk.text:
                chunk_count += 1
                yield chunk.text

    except Exception as e:
        logger.error(f"Streaming completion failed: {e}")
        raise RuntimeError(f"LLM streaming failed: {e}") from e

    t_elapsed = time.perf_counter() - t_start
    if t_elapsed > 0:
        logger.info(
            f"Stream complete: {chunk_count} chunks in {t_elapsed:.2f}s"
        )
    else:
        logger.info(f"Stream complete: {chunk_count} chunks")


def complete(
    prompt: str,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> dict:
    """
    Non-streaming chat completion. Useful for testing and CLI usage.

    Returns:
        dict with keys:
            - content: str (the full response text)
            - model: str (model used)
            - time_s: float (elapsed time in seconds)
    """
    client = _get_client()
    model = model or config.GEMINI_MODEL
    temperature = temperature if temperature is not None else config.LLM_TEMPERATURE
    max_tokens = max_tokens or config.LLM_MAX_TOKENS

    logger.info(f"Non-streaming completion: model={model}, temp={temperature}")
    t_start = time.perf_counter()

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )
    except Exception as e:
        logger.error(f"Completion failed: {e}")
        raise RuntimeError(f"LLM completion failed: {e}") from e

    t_elapsed = time.perf_counter() - t_start
    content = response.text or ""

    logger.info(f"Completion done in {t_elapsed:.2f}s")

    return {
        "content": content,
        "model": model,
        "time_s": round(t_elapsed, 3),
    }
