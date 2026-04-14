"""
F1 AI Race Engineer — Data Loader

Fetches race session data from FastF1 with local caching and performance timing.
This is the first step in the data pipeline: raw F1 data ingestion.

Usage:
    from src.data_loader.load_race import load_session

    session_data = load_session(2024, "Monza", "R")
    laps = session_data["laps"]
    results = session_data["results"]
"""

import time
import logging
import fastf1
import pandas as pd
from config import config

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Enable FastF1 cache on module load
# ──────────────────────────────────────────────
fastf1.Cache.enable_cache(str(config.FASTF1_CACHE_DIR))


def load_session(
    year: int,
    race_name: str,
    session_type: str = "R",
) -> dict:
    """
    Load a complete F1 session from FastF1.

    Args:
        year: Season year (2018–2024).
        race_name: Grand Prix name (e.g. "Monza", "Bahrain", "Monaco").
                   FastF1 is fuzzy — "monza", "Italian Grand Prix", "Monza" all work.
        session_type: One of "R" (Race), "Q" (Qualifying), "S" (Sprint),
                      "FP1", "FP2", "FP3".

    Returns:
        dict with keys:
            - laps: pd.DataFrame of all laps
            - results: pd.DataFrame of final classification
            - event: dict of event metadata (name, date, country, etc.)
            - timing: dict of performance metrics

    Raises:
        ValueError: If year is unsupported or session_type is invalid.
        RuntimeError: If FastF1 fails to load the session.
    """
    # ── Validate inputs ──
    if year not in config.SUPPORTED_YEARS:
        raise ValueError(
            f"Year {year} not supported. Supported: {config.SUPPORTED_YEARS[0]}–{config.SUPPORTED_YEARS[-1]}"
        )

    if session_type not in config.SESSION_TYPES:
        raise ValueError(
            f"Session type '{session_type}' not valid. Use one of: {list(config.SESSION_TYPES.keys())}"
        )

    logger.info(
        f"Loading session: {year} {race_name} ({config.SESSION_TYPES[session_type]})"
    )

    # ── Fetch with timing ──
    t_start = time.perf_counter()

    try:
        session = fastf1.get_session(year, race_name, session_type)
        session.load(
            laps=True,
            telemetry=False,   # Skip telemetry — we don't need 300Hz data for RAG
            weather=False,     # Skip weather to speed up load
            messages=False,    # Skip team radio messages
        )
    except Exception as e:
        raise RuntimeError(
            f"Failed to load {year} {race_name} {session_type}: {e}"
        ) from e

    t_elapsed = time.perf_counter() - t_start
    logger.info(f"Session loaded in {t_elapsed:.2f}s")

    # ── Extract laps ──
    laps: pd.DataFrame = session.laps
    if laps is None or laps.empty:
        raise RuntimeError(
            f"No lap data found for {year} {race_name} {session_type}. "
            f"The session may not exist or data may not be available."
        )

    # ── Extract results ──
    results: pd.DataFrame = session.results

    # ── Build event metadata ──
    event_info = {
        "year": year,
        "race_name": session.event["EventName"],
        "country": session.event["Country"],
        "location": session.event["Location"],
        "session_type": session_type,
        "session_name": config.SESSION_TYPES[session_type],
        "date": str(session.event["EventDate"]),
        "total_laps": int(laps["LapNumber"].max()) if not laps.empty else 0,
    }

    # ── Timing metrics ──
    timing = {
        "fetch_time_s": round(t_elapsed, 3),
        "lap_count": len(laps),
        "driver_count": laps["Driver"].nunique() if not laps.empty else 0,
        "cache_hit": t_elapsed < 2.0,  # Warm cache is typically < 1s
    }

    logger.info(
        f"  → {timing['lap_count']} laps, {timing['driver_count']} drivers, "
        f"cache_hit={timing['cache_hit']}"
    )

    return {
        "laps": laps,
        "results": results,
        "event": event_info,
        "timing": timing,
    }


def get_available_races(year: int) -> list[dict]:
    """
    Get the list of race events for a given season.

    Returns a list of dicts with keys: round_number, event_name, country, location.
    Used by the query classifier to validate race names.
    """
    if year not in config.SUPPORTED_YEARS:
        raise ValueError(f"Year {year} not supported.")

    schedule = fastf1.get_event_schedule(year)

    races = []
    for _, row in schedule.iterrows():
        # Skip testing events
        if row["EventFormat"] == "testing":
            continue
        races.append({
            "round_number": int(row["RoundNumber"]),
            "event_name": row["EventName"],
            "country": row["Country"],
            "location": row["Location"],
        })

    return races


def get_race_names_for_year(year: int) -> list[str]:
    """
    Get just the race names for a year. Convenience wrapper for the query classifier.

    Returns:
        List of event names, e.g. ["Bahrain Grand Prix", "Saudi Arabian Grand Prix", ...]
    """
    races = get_available_races(year)
    return [r["event_name"] for r in races]
