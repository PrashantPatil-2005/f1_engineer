"""
MCP Server — Stint & Driver Comparison Tools

Tools for analysing tyre stints and comparing drivers.
"""

import json
import logging
import pandas as pd

logger = logging.getLogger(__name__)


def _timedelta_to_seconds(td):
    """Safely convert a Timedelta to float seconds, or None."""
    if pd.isna(td):
        return None
    return round(td.total_seconds(), 3)


async def get_driver_stints_tool(
    year: int, race: str, driver: str, session_type: str = "R"
) -> str:
    """Get tyre stint breakdown and strategy for a specific driver."""
    try:
        from src.data_loader.load_race import load_session
        from src.data_processor.process_data import _detect_stints

        session_data = load_session(year, race, session_type)
        laps = session_data["laps"]

        driver_laps = laps[laps["Driver"] == driver].sort_values("LapNumber")
        if driver_laps.empty:
            return json.dumps({
                "error": f"No lap data found for driver {driver}",
                "tool": "get_driver_stints",
            })

        stints = _detect_stints(driver_laps)
        stint_details = []

        for stint in stints:
            mask = (
                (driver_laps["LapNumber"] >= stint["lap_start"])
                & (driver_laps["LapNumber"] <= stint["lap_end"])
            )
            stint_laps = driver_laps[mask]
            lap_times = stint_laps["LapTime"].dropna()
            valid = lap_times[lap_times > pd.Timedelta(0)]

            avg_time = _timedelta_to_seconds(valid.mean()) if not valid.empty else None
            best_time = _timedelta_to_seconds(valid.min()) if not valid.empty else None

            stint_details.append({
                "stint_number": stint["stint_number"],
                "compound": stint["compound"],
                "lap_start": stint["lap_start"],
                "lap_end": stint["lap_end"],
                "num_laps": stint["lap_end"] - stint["lap_start"] + 1,
                "avg_lap_time_s": avg_time,
                "best_lap_time_s": best_time,
            })

        return json.dumps({
            "driver": driver,
            "year": year,
            "race": race,
            "session_type": session_type,
            "stints": stint_details,
        })
    except Exception as e:
        logger.error(f"get_driver_stints_tool failed: {e}")
        return json.dumps({"error": str(e), "tool": "get_driver_stints"})


async def get_lap_times_tool(
    year: int,
    race: str,
    driver: str,
    session_type: str = "R",
    lap_start: int | None = None,
    lap_end: int | None = None,
) -> str:
    """Get lap-by-lap times for a driver."""
    try:
        from src.data_loader.load_race import load_session

        session_data = load_session(year, race, session_type)
        laps = session_data["laps"]

        driver_laps = laps[laps["Driver"] == driver].sort_values("LapNumber")
        if driver_laps.empty:
            return json.dumps({
                "error": f"No lap data found for driver {driver}",
                "tool": "get_lap_times",
            })

        if lap_start is not None:
            driver_laps = driver_laps[driver_laps["LapNumber"] >= lap_start]
        if lap_end is not None:
            driver_laps = driver_laps[driver_laps["LapNumber"] <= lap_end]

        lap_numbers = driver_laps["LapNumber"].astype(int).tolist()
        times = [
            _timedelta_to_seconds(t) for t in driver_laps["LapTime"]
        ]

        return json.dumps({
            "driver": driver,
            "year": year,
            "race": race,
            "session_type": session_type,
            "laps": lap_numbers,
            "times": times,
        })
    except Exception as e:
        logger.error(f"get_lap_times_tool failed: {e}")
        return json.dumps({"error": str(e), "tool": "get_lap_times"})


async def compare_drivers_tool(
    year: int, race: str, drivers: list[str], session_type: str = "R"
) -> str:
    """Compare lap times and race performance between drivers."""
    try:
        from src.data_loader.load_race import load_session
        from src.data_processor.process_data import _detect_stints

        session_data = load_session(year, race, session_type)
        laps = session_data["laps"]
        results = session_data["results"]

        comparison = []

        for drv in drivers:
            driver_laps = laps[laps["Driver"] == drv].sort_values("LapNumber")
            if driver_laps.empty:
                comparison.append({"driver": drv, "error": "No data found"})
                continue

            # Overall stats
            all_times = driver_laps["LapTime"].dropna()
            valid = all_times[all_times > pd.Timedelta(0)]
            overall_avg = _timedelta_to_seconds(valid.mean()) if not valid.empty else None
            overall_best = _timedelta_to_seconds(valid.min()) if not valid.empty else None

            # Finishing position from results
            finish_pos = None
            if results is not None and not results.empty:
                drv_row = results[results["Abbreviation"] == drv]
                if not drv_row.empty and pd.notna(drv_row.iloc[0].get("Position")):
                    finish_pos = int(drv_row.iloc[0]["Position"])

            # Stint breakdown
            stints = _detect_stints(driver_laps)
            stint_summaries = []
            for stint in stints:
                mask = (
                    (driver_laps["LapNumber"] >= stint["lap_start"])
                    & (driver_laps["LapNumber"] <= stint["lap_end"])
                )
                stint_laps = driver_laps[mask]
                st_times = stint_laps["LapTime"].dropna()
                st_valid = st_times[st_times > pd.Timedelta(0)]

                stint_summaries.append({
                    "stint_number": stint["stint_number"],
                    "compound": stint["compound"],
                    "lap_start": stint["lap_start"],
                    "lap_end": stint["lap_end"],
                    "avg_lap_time_s": _timedelta_to_seconds(st_valid.mean()) if not st_valid.empty else None,
                    "best_lap_time_s": _timedelta_to_seconds(st_valid.min()) if not st_valid.empty else None,
                })

            comparison.append({
                "driver": drv,
                "finish_position": finish_pos,
                "overall_avg_lap_s": overall_avg,
                "overall_best_lap_s": overall_best,
                "stints": stint_summaries,
            })

        return json.dumps({
            "year": year,
            "race": race,
            "session_type": session_type,
            "comparison": comparison,
        })
    except Exception as e:
        logger.error(f"compare_drivers_tool failed: {e}")
        return json.dumps({"error": str(e), "tool": "compare_drivers"})
