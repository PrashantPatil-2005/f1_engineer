#!/usr/bin/env python3
"""Standalone runner for the F1 MCP server (for testing)."""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mcp_server.server import main

asyncio.run(main())
