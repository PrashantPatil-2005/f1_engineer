"""
F1 AI Race Engineer — MCP Server

A proper Model Context Protocol server using stdio transport.
Exposes F1 data tools that an MCP client can discover and call.

Usage (standalone):
    python mcp_server/server.py

The server communicates over stdin/stdout using JSON-RPC (MCP protocol).
"""

import sys
import asyncio
import json
import logging
from pathlib import Path

# Ensure project root is on sys.path so src.* imports work
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from mcp_server.tools.race_data import list_races_tool, get_race_results_tool
from mcp_server.tools.stints import (
    get_driver_stints_tool,
    get_lap_times_tool,
    compare_drivers_tool,
)
from mcp_server.tools.search import search_race_data_tool

# ── Logging to stderr (stdout is the MCP transport) ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [MCP] %(name)s — %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ── Create MCP Server ──
app = Server("f1-race-engineer")


# ──────────────────────────────────────────────
# Tool Registration
# ──────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[Tool]:
    """Return all available F1 tools with JSON schemas."""
    return [
        Tool(
            name="list_available_races",
            description="List all available F1 races for a given year",
            inputSchema={
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "The F1 season year (2018-2024)",
                    },
                },
                "required": ["year"],
            },
        ),
        Tool(
            name="get_race_results",
            description="Get the final race results and finishing positions for an F1 race",
            inputSchema={
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "The F1 season year",
                    },
                    "race": {
                        "type": "string",
                        "description": "Grand Prix name (e.g. 'Italian Grand Prix', 'British Grand Prix')",
                    },
                    "session_type": {
                        "type": "string",
                        "description": "Session type: R (Race), Q (Qualifying), S (Sprint), FP1, FP2, FP3",
                        "default": "R",
                    },
                },
                "required": ["year", "race"],
            },
        ),
        Tool(
            name="get_driver_stints",
            description="Get tyre stint breakdown and strategy for a specific driver in a race",
            inputSchema={
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "The F1 season year",
                    },
                    "race": {
                        "type": "string",
                        "description": "Grand Prix name",
                    },
                    "driver": {
                        "type": "string",
                        "description": "3-letter driver code (e.g. VER, HAM, LEC)",
                    },
                    "session_type": {
                        "type": "string",
                        "description": "Session type: R, Q, S, FP1, FP2, FP3",
                        "default": "R",
                    },
                },
                "required": ["year", "race", "driver"],
            },
        ),
        Tool(
            name="get_lap_times",
            description="Get lap-by-lap times for a driver in a race",
            inputSchema={
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "The F1 season year",
                    },
                    "race": {
                        "type": "string",
                        "description": "Grand Prix name",
                    },
                    "driver": {
                        "type": "string",
                        "description": "3-letter driver code",
                    },
                    "session_type": {
                        "type": "string",
                        "description": "Session type: R, Q, S, FP1, FP2, FP3",
                        "default": "R",
                    },
                    "lap_start": {
                        "type": "integer",
                        "description": "First lap number to include (optional)",
                    },
                    "lap_end": {
                        "type": "integer",
                        "description": "Last lap number to include (optional)",
                    },
                },
                "required": ["year", "race", "driver"],
            },
        ),
        Tool(
            name="compare_drivers",
            description="Compare lap times and race performance between two or more drivers",
            inputSchema={
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "The F1 season year",
                    },
                    "race": {
                        "type": "string",
                        "description": "Grand Prix name",
                    },
                    "drivers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of 3-letter driver codes to compare",
                    },
                    "session_type": {
                        "type": "string",
                        "description": "Session type: R, Q, S, FP1, FP2, FP3",
                        "default": "R",
                    },
                },
                "required": ["year", "race", "drivers"],
            },
        ),
        Tool(
            name="search_race_data",
            description="Semantic search through processed race data chunks to find relevant information",
            inputSchema={
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "The F1 season year",
                    },
                    "race": {
                        "type": "string",
                        "description": "Grand Prix name",
                    },
                    "query": {
                        "type": "string",
                        "description": "Natural language search query",
                    },
                    "session_type": {
                        "type": "string",
                        "description": "Session type: R, Q, S, FP1, FP2, FP3",
                        "default": "R",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return",
                        "default": 5,
                    },
                },
                "required": ["year", "race", "query"],
            },
        ),
    ]


# ──────────────────────────────────────────────
# Tool Dispatch
# ──────────────────────────────────────────────

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Route tool calls to the appropriate handler."""
    logger.info(f"Tool call: {name}({arguments})")

    if name == "list_available_races":
        result = await list_races_tool(arguments["year"])

    elif name == "get_race_results":
        result = await get_race_results_tool(
            arguments["year"],
            arguments["race"],
            arguments.get("session_type", "R"),
        )

    elif name == "get_driver_stints":
        result = await get_driver_stints_tool(
            arguments["year"],
            arguments["race"],
            arguments["driver"],
            arguments.get("session_type", "R"),
        )

    elif name == "get_lap_times":
        result = await get_lap_times_tool(
            arguments["year"],
            arguments["race"],
            arguments["driver"],
            arguments.get("session_type", "R"),
            arguments.get("lap_start"),
            arguments.get("lap_end"),
        )

    elif name == "compare_drivers":
        result = await compare_drivers_tool(
            arguments["year"],
            arguments["race"],
            arguments["drivers"],
            arguments.get("session_type", "R"),
        )

    elif name == "search_race_data":
        result = await search_race_data_tool(
            arguments["year"],
            arguments["race"],
            arguments["query"],
            arguments.get("session_type", "R"),
            arguments.get("top_k", 5),
        )

    else:
        result = json.dumps({"error": f"Unknown tool: {name}"})

    return [TextContent(type="text", text=result)]


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────

async def main():
    """Run the MCP server over stdio."""
    logger.info("Starting F1 Race Engineer MCP server (stdio)")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())
    logger.info("MCP server stopped")


if __name__ == "__main__":
    asyncio.run(main())
