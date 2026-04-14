#!/usr/bin/env python3
"""Standalone runner for the F1 MCP server (for testing)."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mcp_server.server import main  # noqa: E402  (path setup must precede import)

asyncio.run(main())
