"""
F1 AI Race Engineer — Query Classifier

Extracts structured entities (year, race, driver, session type) from natural
language questions BEFORE any data fetching happens.

Uses Google Gemini structured output (Pydantic schema) for reliable extraction.

Usage:
    from src.mcp_engine.query_classifier import classify_query

    entities = classify_query("Why did Verstappen win Monza 2024?")
    # QueryEntities(year=2024, race="Italian Grand Prix", driver="VER", ...)
"""

import time
import logging
from typing import Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from config import config
from src.data_loader.load_race import get_race_names_for_year

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Pydantic schema for structured extraction
# ──────────────────────────────────────────────

class QueryEntities(BaseModel):
    """Structured entities extracted from a natural language F1 question."""

    year: int = Field(
        description="The F1 season year (e.g. 2024). If not specified, default to 2024."
    )
    race: str = Field(
        description=(
            "The official Grand Prix name as it appears in the F1 calendar "
            "(e.g. 'Italian Grand Prix', 'Bahrain Grand Prix'). "
            "Normalize common aliases: 'Monza' → 'Italian Grand Prix', "
            "'Silverstone' → 'British Grand Prix', 'Spa' → 'Belgian Grand Prix', "
            "'Monaco' → 'Monaco Grand Prix', etc."
        )
    )
    driver: Optional[str] = Field(
        default=None,
        description=(
            "The 3-letter driver abbreviation (e.g. 'VER', 'HAM', 'LEC'). "
            "Set to null for general race questions or multi-driver comparisons. "
            "Common mappings: Verstappen→VER, Hamilton→HAM, Leclerc→LEC, "
            "Norris→NOR, Piastri→PIA, Sainz→SAI, Russell→RUS, Perez→PER, "
            "Alonso→ALO, Stroll→STR, Gasly→GAS, Ocon→OCO, Tsunoda→TSU, "
            "Ricciardo→RIC, Hulkenberg→HUL, Magnussen→MAG, Bottas→BOT, "
            "Zhou→ZHO, Sargeant→SAR, Albon→ALB, De Vries→DEV, Lawson→LAW, "
            "Bearman→BEA, Colapinto→COL."
        )
    )
    session_type: str = Field(
        default="R",
        description=(
            "The session type: 'R' for Race (default), 'Q' for Qualifying, "
            "'S' for Sprint, 'FP1'/'FP2'/'FP3' for practice. "
            "If not mentioned, default to 'R'."
        )
    )
    query_type: str = Field(
        description=(
            "The type of question being asked. One of: "
            "'comparison' (comparing two or more drivers), "
            "'strategy' (tyre strategy, pit stops, stint analysis), "
            "'lap_time' (specific lap times, fastest laps), "
            "'result' (race winner, podium, finishing positions), "
            "'general' (anything else)."
        )
    )
    comparison_drivers: Optional[list[str]] = Field(
        default=None,
        description=(
            "If query_type is 'comparison', list the driver abbreviations "
            "being compared (e.g. ['HAM', 'LEC']). Otherwise null."
        )
    )


# ──────────────────────────────────────────────
# System prompt for the classifier
# ──────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an F1 query classifier. Extract structured entities from the user's
natural language question about Formula 1.

Key rules:
1. YEAR: Default to 2024 if not specified. Supported range: 2018-2024.
2. RACE: Always return the official Grand Prix name. Common aliases:
   - "Monza" → "Italian Grand Prix"
   - "Silverstone" → "British Grand Prix"
   - "Spa" → "Belgian Grand Prix"
   - "Monaco" → "Monaco Grand Prix"
   - "Jeddah" → "Saudi Arabian Grand Prix"
   - "Baku" → "Azerbaijan Grand Prix"
   - "COTA"/"Austin" → "United States Grand Prix"
   - "Interlagos"/"São Paulo" → "São Paulo Grand Prix"
   - "Suzuka" → "Japanese Grand Prix"
   - "Singapore" → "Singapore Grand Prix"
   - "Bahrain" → "Bahrain Grand Prix"
   - "Abu Dhabi"/"Yas Marina" → "Abu Dhabi Grand Prix"
   - "Imola" → "Emilia Romagna Grand Prix"
   - "Barcelona"/"Catalunya" → "Spanish Grand Prix"
   - "Zandvoort" → "Dutch Grand Prix"
   - "Hungaroring" → "Hungarian Grand Prix"
   - "Melbourne"/"Albert Park" → "Australian Grand Prix"
   - "Montreal" → "Canadian Grand Prix"
   - "Red Bull Ring"/"Spielberg" → "Austrian Grand Prix"
3. DRIVER: Use 3-letter abbreviation. Set to null for general questions or multi-driver comparisons.
4. SESSION: Default to "R" (Race) unless qualifying, sprint, or practice is mentioned.
5. QUERY_TYPE: Classify as comparison/strategy/lap_time/result/general.
6. For "X vs Y" queries: set driver=null, query_type="comparison", and list drivers in comparison_drivers.

AVAILABLE RACES FOR EACH YEAR:
{race_list}
"""


def _build_system_prompt() -> str:
    """Build the system prompt with the list of available races per year."""
    race_list_parts = []
    for year in config.SUPPORTED_YEARS:
        try:
            names = get_race_names_for_year(year)
            race_list_parts.append(f"{year}: {', '.join(names)}")
        except Exception:
            race_list_parts.append(f"{year}: (schedule unavailable)")

    race_list = "\n".join(race_list_parts)
    return _SYSTEM_PROMPT.format(race_list=race_list)


# ──────────────────────────────────────────────
# Main classifier function
# ──────────────────────────────────────────────

# Cache the system prompt (expensive to build — loads FastF1 schedules)
_cached_system_prompt: str | None = None


def _get_system_prompt() -> str:
    """Get or build the cached system prompt."""
    global _cached_system_prompt
    if _cached_system_prompt is None:
        logger.info("Building query classifier system prompt (loading race schedules)...")
        _cached_system_prompt = _build_system_prompt()
        logger.info("System prompt built and cached.")
    return _cached_system_prompt


def classify_query(question: str) -> QueryEntities:
    """
    Classify a natural language F1 question into structured entities.

    Args:
        question: The user's natural language question.
                  e.g. "Why did Verstappen win Monza 2024?"

    Returns:
        QueryEntities with year, race, driver, session_type, query_type.

    Raises:
        RuntimeError: If Gemini fails to return a valid classification.
    """
    t_start = time.perf_counter()

    client = genai.Client(api_key=config.GOOGLE_API_KEY)
    system_prompt = _get_system_prompt()

    try:
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=f"{system_prompt}\n\nUser question: {question}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=QueryEntities,
                temperature=0,
            ),
        )

        entities = response.parsed

    except Exception as e:
        raise RuntimeError(f"Query classification failed: {e}") from e

    if entities is None:
        raise RuntimeError("Query classification returned empty result")

    t_elapsed = time.perf_counter() - t_start

    logger.info(
        f"Classified in {t_elapsed:.2f}s: year={entities.year}, race={entities.race}, "
        f"driver={entities.driver}, session={entities.session_type}, "
        f"type={entities.query_type}"
    )

    return entities
