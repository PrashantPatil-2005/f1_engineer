"""
F1 AI Race Engineer — Data Processor

Transforms raw FastF1 lap data into stint-level narrative chunks for RAG retrieval.

This is the most important technical module in the pipeline. Chunking strategy:
- NOT individual lap rows (produces garbage retrieval)
- Per-driver stint: one chunk = one driver's full stint narrative
- Each chunk is a natural-language summary the LLM can reason over
- Also generates a race summary chunk for high-level questions

Usage:
    from src.data_processor.process_data import process_session

    chunks = process_session(session_data)
    # Returns list of chunk dicts with 'chunk_id', 'text', 'metadata'
"""

import json
import time
import logging
from pathlib import Path
import pandas as pd
import numpy as np
from config import config

logger = logging.getLogger(__name__)


def _format_lap_time(td) -> str:
    """Convert a pandas Timedelta to a human-readable lap time string like '1:16.432'."""
    if pd.isna(td):
        return "N/A"
    total_seconds = td.total_seconds()
    if total_seconds <= 0 or total_seconds > 600:  # Sanity check: < 10 minutes
        return "N/A"
    minutes = int(total_seconds // 60)
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:06.3f}"


def _format_duration(td) -> str:
    """Convert a Timedelta to seconds string like '2.4s'."""
    if pd.isna(td):
        return "N/A"
    return f"{td.total_seconds():.1f}s"


def _detect_stints(driver_laps: pd.DataFrame) -> list[dict]:
    """
    Detect stint boundaries for a single driver based on tyre compound changes.

    A new stint begins when:
    1. The tyre compound changes, OR
    2. There's a pit stop (PitInTime is not NaT)

    Returns a list of stint dicts with lap ranges and compound info.
    """
    stints = []
    current_compound = None
    stint_start = None
    stint_number = 0

    for _, lap in driver_laps.iterrows():
        compound = lap.get("Compound", "UNKNOWN")

        # Detect stint boundary
        if compound != current_compound:
            # Close previous stint
            if stint_start is not None:
                stints.append({
                    "stint_number": stint_number,
                    "compound": current_compound,
                    "lap_start": stint_start,
                    "lap_end": int(prev_lap_number),
                })

            # Start new stint
            stint_number += 1
            current_compound = compound
            stint_start = int(lap["LapNumber"])

        prev_lap_number = lap["LapNumber"]

    # Close final stint
    if stint_start is not None:
        stints.append({
            "stint_number": stint_number,
            "compound": current_compound,
            "lap_start": stint_start,
            "lap_end": int(prev_lap_number),
        })

    return stints


def _compute_stint_stats(
    driver_laps: pd.DataFrame,
    stint_info: dict,
    results: pd.DataFrame,
    driver_code: str,
) -> dict:
    """
    Compute statistics for a single stint: avg/best lap, positions, pit time.
    """
    mask = (
        (driver_laps["LapNumber"] >= stint_info["lap_start"])
        & (driver_laps["LapNumber"] <= stint_info["lap_end"])
    )
    stint_laps = driver_laps[mask]

    if stint_laps.empty:
        return {}

    # Lap times — filter out outliers (pit in/out laps, safety car laps)
    # Use IsPersonalBest or just filter out extreme values
    lap_times = stint_laps["LapTime"].dropna()
    valid_times = lap_times[lap_times > pd.Timedelta(0)]

    avg_lap = valid_times.mean() if not valid_times.empty else pd.NaT
    best_lap = valid_times.min() if not valid_times.empty else pd.NaT

    # Position tracking
    positions = stint_laps["Position"].dropna()
    pos_start = int(positions.iloc[0]) if not positions.empty else None
    pos_end = int(positions.iloc[-1]) if not positions.empty else None
    pos_change = (pos_start - pos_end) if (pos_start and pos_end) else 0

    # Pit stop duration (time between PitInTime and PitOutTime)
    pit_time = pd.NaT
    pit_laps = stint_laps[stint_laps["PitInTime"].notna()]
    if not pit_laps.empty:
        last_pit = pit_laps.iloc[-1]
        if pd.notna(last_pit.get("PitOutTime")) and pd.notna(last_pit.get("PitInTime")):
            pit_time = last_pit["PitOutTime"] - last_pit["PitInTime"]

    # Driver full name from results
    driver_name = driver_code
    if results is not None and not results.empty:
        driver_row = results[results["Abbreviation"] == driver_code]
        if not driver_row.empty:
            first = driver_row.iloc[0].get("FirstName", "")
            last = driver_row.iloc[0].get("LastName", "")
            driver_name = f"{first} {last}".strip() or driver_code

    return {
        "driver_name": driver_name,
        "driver_code": driver_code,
        "lap_count": len(stint_laps),
        "avg_lap_time": avg_lap,
        "best_lap_time": best_lap,
        "position_start": pos_start,
        "position_end": pos_end,
        "positions_gained": pos_change,
        "pit_stop_duration": pit_time,
    }


def _build_stint_text(stint_info: dict, stats: dict) -> str:
    """
    Build a natural-language narrative for a single stint.

    Example output:
    "Max Verstappen Stint 2 (Hard tyres, Laps 23-48): Averaged 1:16.432,
     best lap 1:15.891. Started stint P3, ended P2 (+1 position).
     Pit stop: 2.4s. 26 laps completed."
    """
    parts = []

    # Header
    driver = stats.get("driver_name", stats.get("driver_code", "Unknown"))
    compound = stint_info["compound"] or "Unknown"
    parts.append(
        f"{driver} Stint {stint_info['stint_number']} "
        f"({compound} tyres, Laps {stint_info['lap_start']}-{stint_info['lap_end']})"
    )

    # Lap times
    time_parts = []
    avg = stats.get("avg_lap_time")
    best = stats.get("best_lap_time")
    if pd.notna(avg):
        time_parts.append(f"averaged {_format_lap_time(avg)}")
    if pd.notna(best):
        time_parts.append(f"best lap {_format_lap_time(best)}")
    if time_parts:
        parts.append(": " + ", ".join(time_parts) + ".")
    else:
        parts.append(".")

    # Positions
    pos_start = stats.get("position_start")
    pos_end = stats.get("position_end")
    pos_gained = stats.get("positions_gained", 0)
    if pos_start and pos_end:
        pos_str = f"Started stint P{pos_start}, ended P{pos_end}"
        if pos_gained > 0:
            pos_str += f" (+{pos_gained} position{'s' if pos_gained != 1 else ''})"
        elif pos_gained < 0:
            pos_str += f" ({pos_gained} position{'s' if abs(pos_gained) != 1 else ''})"
        parts.append(f" {pos_str}.")

    # Pit stop
    pit = stats.get("pit_stop_duration")
    if pd.notna(pit):
        parts.append(f" Pit stop: {_format_duration(pit)}.")

    # Lap count
    parts.append(f" {stats.get('lap_count', 0)} laps completed.")

    return "".join(parts)


def _build_race_summary(event: dict, results: pd.DataFrame, laps: pd.DataFrame) -> str:
    """
    Build a race summary narrative chunk.

    Example:
    "2024 Monza Grand Prix Race Summary: Winner — Charles Leclerc (Ferrari),
     P2 — Oscar Piastri (+2.6s), P3 — Lando Norris (+6.1s). 53 laps.
     Fastest lap: Leclerc 1:15.423 (Lap 47)."
    """
    parts = []

    race_name = event.get("race_name", "Unknown Grand Prix")
    year = event.get("year", "")
    parts.append(f"{year} {race_name} {event.get('session_name', 'Race')} Summary")

    # Top 3 finishers
    if results is not None and not results.empty:
        # Sort results by position
        sorted_results = results.sort_values("Position")
        podium = []
        for i, (_, row) in enumerate(sorted_results.head(10).iterrows()):
            pos = int(row["Position"]) if pd.notna(row.get("Position")) else i + 1
            name = f"{row.get('FirstName', '')} {row.get('LastName', '')}".strip()
            team = row.get("TeamName", "")
            time_str = ""

            if pos == 1:
                podium.append(f"Winner — {name} ({team})")
            else:
                # Try to get time gap
                status = row.get("Status", "")
                if status and "+" in str(status):
                    time_str = f" ({status})"
                elif pd.notna(row.get("Time")):
                    time_str = f" (+{_format_duration(row['Time'])})"
                podium.append(f"P{pos} — {name}{time_str}")

        parts.append(": " + ", ".join(podium) + ".")

    # Total laps
    total_laps = event.get("total_laps", 0)
    if total_laps:
        parts.append(f" {total_laps} laps.")

    # Fastest lap
    if laps is not None and not laps.empty:
        valid_laps = laps[laps["LapTime"].notna() & (laps["LapTime"] > pd.Timedelta(0))]
        if not valid_laps.empty:
            fastest = valid_laps.loc[valid_laps["LapTime"].idxmin()]
            fl_driver = fastest["Driver"]
            fl_time = _format_lap_time(fastest["LapTime"])
            fl_lap = int(fastest["LapNumber"])
            parts.append(f" Fastest lap: {fl_driver} {fl_time} (Lap {fl_lap}).")

    return "".join(parts)


def process_session(session_data: dict) -> list[dict]:
    """
    Process a loaded FastF1 session into stint-level narrative chunks.

    Args:
        session_data: Output from load_race.load_session()

    Returns:
        List of chunk dicts, each with:
            - chunk_id: str (unique identifier)
            - text: str (natural language narrative)
            - metadata: dict (structured fields for filtering)
    """
    t_start = time.perf_counter()

    laps = session_data["laps"]
    results = session_data["results"]
    event = session_data["event"]

    year = event["year"]
    race = event["race_name"]
    session_type = event["session_type"]

    # Normalize race name for IDs (remove spaces, lowercase)
    race_slug = race.lower().replace(" ", "_").replace("grand_prix", "gp")

    chunks = []
    drivers = laps["Driver"].unique()

    logger.info(f"Processing {len(drivers)} drivers for {year} {race} {session_type}")

    for driver_code in drivers:
        driver_laps = laps[laps["Driver"] == driver_code].sort_values("LapNumber")

        if driver_laps.empty:
            continue

        # Detect stints for this driver
        stints = _detect_stints(driver_laps)

        for stint_info in stints:
            # Compute statistics
            stats = _compute_stint_stats(driver_laps, stint_info, results, driver_code)
            if not stats:
                continue

            # Build narrative text
            text = _build_stint_text(stint_info, stats)

            chunk_id = (
                f"{year}_{race_slug}_{session_type}_{driver_code}_stint_{stint_info['stint_number']}"
            )

            chunks.append({
                "chunk_id": chunk_id,
                "text": text,
                "metadata": {
                    "year": year,
                    "race": race,
                    "session": session_type,
                    "driver": driver_code,
                    "driver_name": stats.get("driver_name", driver_code),
                    "stint_number": stint_info["stint_number"],
                    "compound": stint_info["compound"],
                    "lap_start": stint_info["lap_start"],
                    "lap_end": stint_info["lap_end"],
                    "avg_lap_time": _format_lap_time(stats.get("avg_lap_time")),
                    "best_lap_time": _format_lap_time(stats.get("best_lap_time")),
                    "positions_gained": stats.get("positions_gained", 0),
                },
            })

    # ── Race summary chunk ──
    summary_text = _build_race_summary(event, results, laps)
    chunks.append({
        "chunk_id": f"{year}_{race_slug}_{session_type}_summary",
        "text": summary_text,
        "metadata": {
            "year": year,
            "race": race,
            "session": session_type,
            "driver": None,
            "stint_number": None,
            "compound": None,
            "type": "race_summary",
        },
    })

    t_elapsed = time.perf_counter() - t_start
    logger.info(
        f"Processed {len(chunks)} chunks ({len(chunks)-1} stints + 1 summary) "
        f"in {t_elapsed:.3f}s"
    )

    return chunks


def save_chunks(chunks: list[dict], year: int, race: str, session_type: str) -> Path:
    """
    Save processed chunks to JSON on disk.

    Returns the path to the saved file.
    """
    race_slug = race.lower().replace(" ", "_").replace("grand_prix", "gp")
    filename = f"{year}_{race_slug}_{session_type}.json"
    filepath = config.PROCESSED_DIR / filename

    # Convert to JSON-serializable format
    serializable = []
    for chunk in chunks:
        serializable.append({
            "chunk_id": chunk["chunk_id"],
            "text": chunk["text"],
            "metadata": chunk["metadata"],
        })

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False, default=str)

    logger.info(f"Saved {len(chunks)} chunks to {filepath}")
    return filepath


def load_chunks(year: int, race: str, session_type: str) -> list[dict] | None:
    """
    Load previously processed chunks from disk.

    Returns None if file doesn't exist (cold cache).
    """
    race_slug = race.lower().replace(" ", "_").replace("grand_prix", "gp")
    filename = f"{year}_{race_slug}_{session_type}.json"
    filepath = config.PROCESSED_DIR / filename

    if not filepath.exists():
        return None

    with open(filepath, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    logger.info(f"Loaded {len(chunks)} cached chunks from {filepath}")
    return chunks
