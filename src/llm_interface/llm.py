"""
F1 AI Race Engineer — LLM Interface

Streaming and non-streaming OpenAI chat completions.

Usage:
    from src.llm_interface.llm import stream_completion, complete

    # Streaming (for SSE)
    for delta in stream_completion(messages):
        print(delta, end="", flush=True)

    # Non-streaming (for testing)
    response = complete(messages)
"""

import time
import logging
from typing import Generator
from openai import OpenAI
from config import config

logger = logging.getLogger(__name__)


def _get_client() -> OpenAI:
    """Get an OpenAI client instance."""
    return OpenAI(api_key=config.OPENAI_API_KEY)


def stream_completion(
    messages: list[dict],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> Generator[str, None, None]:
    """
    Stream a chat completion from OpenAI, yielding content deltas.

    This is the primary interface for the Flask SSE endpoint.
    Each yield is a token-level string fragment.

    Args:
        messages: List of message dicts (system + user).
        model: Override model. Defaults to config.OPENAI_MODEL.
        temperature: Override temperature. Defaults to config.LLM_TEMPERATURE.
        max_tokens: Override max tokens. Defaults to config.LLM_MAX_TOKENS.

    Yields:
        str content deltas (individual tokens/fragments).

    Raises:
        RuntimeError: If the OpenAI API call fails.
    """
    client = _get_client()
    model = model or config.OPENAI_MODEL
    temperature = temperature if temperature is not None else config.LLM_TEMPERATURE
    max_tokens = max_tokens or config.LLM_MAX_TOKENS

    logger.info(f"Streaming completion: model={model}, temp={temperature}")
    t_start = time.perf_counter()
    token_count = 0

    try:
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                token_count += 1  # Approximate — each delta ≈ 1 token
                yield content

    except Exception as e:
        logger.error(f"Streaming completion failed: {e}")
        raise RuntimeError(f"LLM streaming failed: {e}") from e

    t_elapsed = time.perf_counter() - t_start
    logger.info(
        f"Stream complete: ~{token_count} tokens in {t_elapsed:.2f}s "
        f"({token_count / t_elapsed:.0f} tok/s)" if t_elapsed > 0 else
        f"Stream complete: ~{token_count} tokens"
    )


def complete(
    messages: list[dict],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> dict:
    """
    Non-streaming chat completion. Useful for testing and CLI usage.

    Returns:
        dict with keys:
            - content: str (the full response text)
            - usage: dict (prompt_tokens, completion_tokens, total_tokens)
            - model: str (model used)
            - time_s: float (elapsed time in seconds)
    """
    client = _get_client()
    model = model or config.OPENAI_MODEL
    temperature = temperature if temperature is not None else config.LLM_TEMPERATURE
    max_tokens = max_tokens or config.LLM_MAX_TOKENS

    logger.info(f"Non-streaming completion: model={model}, temp={temperature}")
    t_start = time.perf_counter()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )
    except Exception as e:
        logger.error(f"Completion failed: {e}")
        raise RuntimeError(f"LLM completion failed: {e}") from e

    t_elapsed = time.perf_counter() - t_start
    content = response.choices[0].message.content or ""

    usage = {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
    }

    logger.info(
        f"Completion done: {usage['total_tokens']} tokens in {t_elapsed:.2f}s"
    )

    return {
        "content": content,
        "usage": usage,
        "model": response.model,
        "time_s": round(t_elapsed, 3),
    }
