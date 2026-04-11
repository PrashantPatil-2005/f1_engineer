"""
MCP Server — Race Data Tools

Tools for listing races and getting race results via FastF1.
"""

import json
import logging
import pandas as pd

logger = logging.getLogger(__name__)


async def list_races_tool(year: int) -> str:
    """List all available F1 races for a given year."""
    try:
        from src.data_loader.load_race import get_available_races

        races = get_available_races(year)
        return json.dumps({"year": year, "races": races})
    except Exception as e:
        logger.error(f"list_races_tool failed: {e}")
        return json.dumps({"error": str(e), "tool": "list_available_races"})


async def get_race_results_tool(
    year: int, race: str, session_type: str = "R"
) -> str:
    """Get final race results and finishing positions."""
    try:
        from src.data_loader.load_race import load_session

        session_data = load_session(year, race, session_type)
        results = session_data["results"]
        event = session_data["event"]

        if results is None or results.empty:
            return json.dumps({"error": "No results available", "tool": "get_race_results"})

        sorted_results = results.sort_values("Position")
        rows = []
        for _, row in sorted_results.iterrows():
            position = int(row["Position"]) if pd.notna(row.get("Position")) else None
            name = f"{row.get('FirstName', '')} {row.get('LastName', '')}".strip()
            team = row.get("TeamName", "")
            abbreviation = row.get("Abbreviation", "")

            # Format time/gap
            gap = None
            if pd.notna(row.get("Time")):
                gap = f"+{row['Time'].total_seconds():.3f}s"
            status = str(row.get("Status", "")) if pd.notna(row.get("Status")) else None

            rows.append({
                "position": position,
                "driver": name,
                "abbreviation": abbreviation,
                "team": team,
                "gap": gap,
                "status": status,
            })

        return json.dumps({
            "event": event,
            "results": rows,
        })
    except Exception as e:
        logger.error(f"get_race_results_tool failed: {e}")
        return json.dumps({"error": str(e), "tool": "get_race_results"})
