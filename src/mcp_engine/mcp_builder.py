"""
F1 AI Race Engineer — MCP Prompt Builder

Assembles the final structured prompt for the LLM with:
- SYSTEM: Expert F1 race engineer persona + instructions
- CONTEXT: Top-k retrieved chunks, packed within a hard token budget
- USER: Original question

The MCP (Model Context Protocol) contract ensures:
1. The LLM only sees structured context, never raw CSVs
2. Token budget is enforced — context is greedily packed by similarity
3. Chart data instructions are injected based on query type

Usage:
    from src.mcp_engine.mcp_builder import build_prompt

    messages = build_prompt(question, retrieved_chunks, query_entities)
"""

import logging
import tiktoken
from config import config

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Token counting
# ──────────────────────────────────────────────

# Use cl100k_base encoding (used by GPT-4, GPT-4o)
_ENCODER: tiktoken.Encoding | None = None


def _get_encoder() -> tiktoken.Encoding:
    global _ENCODER
    if _ENCODER is None:
        _ENCODER = tiktoken.encoding_for_model("gpt-4o")
    return _ENCODER


def count_tokens(text: str) -> int:
    """Count the number of tokens in a text string."""
    return len(_get_encoder().encode(text))


# ──────────────────────────────────────────────
# System prompt
# ──────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an expert Formula 1 race engineer and analyst. You provide detailed,
data-grounded analysis of F1 races, strategies, and driver performance.

CRITICAL RULES:
1. ONLY use the data provided in the CONTEXT section below. Do NOT hallucinate or invent data.
2. If the context doesn't contain enough information to fully answer, say so explicitly.
3. Reference specific data points (lap times, stint lengths, position changes) to support your analysis.
4. Use F1 terminology naturally: stint, compound, undercut, overcut, degradation, delta, etc.
5. Be concise but thorough. Engineers want signal, not padding.

{chart_instructions}"""

_CHART_INSTRUCTIONS = {
    "comparison": """
CHART DATA INSTRUCTION:
Since this is a comparison query, include a JSON block at the END of your response with the following format:
```chart_data
{
  "type": "lap_time_comparison",
  "title": "Lap Time Comparison",
  "drivers": ["DRIVER1", "DRIVER2"],
  "labels": ["Stint 1 Avg", "Stint 2 Avg", "Best Lap"],
  "datasets": [
    {"driver": "DRIVER1", "values": [76.5, 77.2, 75.8]},
    {"driver": "DRIVER2", "values": [76.8, 77.0, 76.1]}
  ]
}
```
Use actual lap times in SECONDS (e.g., 76.5 means 1:16.500).
""",

    "strategy": """
CHART DATA INSTRUCTION:
Since this is a strategy query, include a JSON block at the END of your response with the following format:
```chart_data
{
  "type": "tyre_strategy",
  "title": "Tyre Strategy Timeline",
  "drivers": [
    {
      "driver": "VER",
      "stints": [
        {"compound": "SOFT", "lap_start": 1, "lap_end": 18},
        {"compound": "HARD", "lap_start": 19, "lap_end": 53}
      ]
    }
  ]
}
```
Include all relevant drivers in the analysis.
""",

    "lap_time": """
CHART DATA INSTRUCTION:
If comparing lap times across laps or stints, include a JSON block at the END of your response:
```chart_data
{
  "type": "lap_times",
  "title": "Lap Time Progression",
  "driver": "VER",
  "laps": [1, 2, 3, 4, 5],
  "times": [78.2, 76.8, 76.5, 76.4, 76.6]
}
```
Use actual lap times in SECONDS.
""",
}


# ──────────────────────────────────────────────
# Prompt builder
# ──────────────────────────────────────────────

def build_prompt(
    question: str,
    retrieved_chunks: list[dict],
    query_type: str = "general",
) -> list[dict]:
    """
    Build the final prompt messages for the LLM.

    Args:
        question: The user's original question.
        retrieved_chunks: List of dicts with 'chunk' and 'score' keys
                         (output from retriever.query).
        query_type: One of "comparison", "strategy", "lap_time", "result", "general".

    Returns:
        List of message dicts for the OpenAI chat API:
        [{"role": "system", ...}, {"role": "user", ...}]
    """
    # ── Build context block with token budget ──
    context_parts = []
    token_count = 0
    max_tokens = config.MAX_CONTEXT_TOKENS
    chunks_included = 0

    for item in retrieved_chunks:
        chunk = item["chunk"]
        text = chunk["text"]
        chunk_tokens = count_tokens(text)

        if token_count + chunk_tokens > max_tokens:
            logger.info(
                f"Token budget reached ({token_count}/{max_tokens}). "
                f"Included {chunks_included}/{len(retrieved_chunks)} chunks."
            )
            break

        score = item.get("score", 0)
        context_parts.append(f"[Relevance: {score:.3f}] {text}")
        token_count += chunk_tokens
        chunks_included += 1

    context_block = "\n\n".join(context_parts)

    logger.info(
        f"Context: {chunks_included} chunks, {token_count} tokens "
        f"(budget: {max_tokens})"
    )

    # ── Build system prompt with chart instructions ──
    chart_instructions = _CHART_INSTRUCTIONS.get(query_type, "")
    system_prompt = _SYSTEM_PROMPT.format(chart_instructions=chart_instructions)

    # ── Assemble messages ──
    user_content = f"""CONTEXT (retrieved F1 data — use ONLY this data):
{context_block}

QUESTION:
{question}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    total_tokens = count_tokens(system_prompt) + count_tokens(user_content)
    logger.info(f"Total prompt tokens: {total_tokens}")

    return messages


def extract_chart_data(response_text: str) -> dict | None:
    """
    Extract chart_data JSON from the LLM response.

    Looks for a fenced block:
    ```chart_data
    { ... }
    ```

    Returns the parsed dict, or None if not found.
    """
    import json

    marker_start = "```chart_data"
    marker_end = "```"

    start_idx = response_text.find(marker_start)
    if start_idx == -1:
        return None

    # Find the content after the opening marker
    content_start = start_idx + len(marker_start)
    # Find the closing ```
    end_idx = response_text.find(marker_end, content_start)
    if end_idx == -1:
        return None

    json_str = response_text[content_start:end_idx].strip()

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse chart_data JSON: {e}")
        return None
