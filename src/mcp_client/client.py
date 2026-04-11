"""
F1 AI Race Engineer — MCP Client

Connects to the MCP server over stdio, discovers tools, and runs a
Gemini tool-use loop that streams the final answer back via SSE events.

Usage:
    from src.mcp_client.client import F1MCPClient

    client = F1MCPClient()
    await client.connect()
    async for event in client.stream_with_tools("Who won the 2024 British GP?"):
        print(event)
    await client.disconnect()
"""

import sys
import json
import logging
from pathlib import Path
from typing import AsyncGenerator

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from google import genai
from google.genai import types

from config import config

logger = logging.getLogger(__name__)

# System prompt given to Gemini for the tool-use conversation
_SYSTEM_PROMPT = """You are an expert Formula 1 race engineer and analyst. You have access to
tools that can fetch real F1 data from the FastF1 database. Use these tools to answer
the user's question with data-grounded analysis.

CRITICAL RULES:
1. ALWAYS call the appropriate tool(s) to get data before answering. Do NOT guess or hallucinate data.
2. If a tool returns an error, explain what went wrong and suggest alternatives.
3. Reference specific data points (lap times, stint lengths, position changes) to support your analysis.
4. Use F1 terminology naturally: stint, compound, undercut, overcut, degradation, delta, etc.
5. Be concise but thorough. Engineers want signal, not padding.

CHART DATA INSTRUCTION:
If the question involves comparing drivers or analysing lap times / strategy,
include a JSON block at the END of your response in this format:
```chart_data
{
  "type": "lap_time_comparison" | "tyre_strategy" | "lap_times",
  "title": "...",
  ...driver/lap/stint data...
}
```
Use actual lap times in SECONDS (e.g., 76.5 means 1:16.500)."""


class F1MCPClient:
    """MCP client that bridges MCP tools with Gemini's tool-use API."""

    def __init__(self):
        self._server_script = Path(__file__).resolve().parent.parent.parent / "mcp_server" / "server.py"
        self._session: ClientSession | None = None
        self._stdio_context = None
        self._session_context = None
        self._mcp_tools: list = []
        self._gemini_tools: list = []

    # ──────────────────────────────────────────────
    # Connection lifecycle
    # ──────────────────────────────────────────────

    async def connect(self) -> None:
        """Start the MCP server subprocess and initialize the session."""
        logger.info(f"Connecting to MCP server: {self._server_script}")

        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(self._server_script)],
        )

        # Enter the stdio_client context manager
        self._stdio_context = stdio_client(server_params)
        read_stream, write_stream = await self._stdio_context.__aenter__()

        # Enter the ClientSession context manager
        self._session_context = ClientSession(read_stream, write_stream)
        self._session = await self._session_context.__aenter__()

        await self._session.initialize()

        # Discover tools
        tools_response = await self._session.list_tools()
        self._mcp_tools = tools_response.tools
        self._gemini_tools = self._mcp_tools_to_gemini(self._mcp_tools)

        tool_names = [t.name for t in self._mcp_tools]
        logger.info(f"MCP connected. Available tools: {tool_names}")

    async def disconnect(self) -> None:
        """Shut down the MCP session and server subprocess."""
        try:
            if self._session_context is not None:
                await self._session_context.__aexit__(None, None, None)
        except Exception as e:
            logger.warning(f"Error closing MCP session: {e}")

        try:
            if self._stdio_context is not None:
                await self._stdio_context.__aexit__(None, None, None)
        except Exception as e:
            logger.warning(f"Error closing stdio transport: {e}")

        self._session = None
        self._session_context = None
        self._stdio_context = None
        logger.info("MCP client disconnected")

    # ──────────────────────────────────────────────
    # Tool conversion: MCP → Gemini format
    # ──────────────────────────────────────────────

    def _mcp_tools_to_gemini(self, mcp_tools) -> list:
        """Convert MCP tool definitions to Gemini FunctionDeclaration format."""
        declarations = []

        for tool in mcp_tools:
            schema = tool.inputSchema
            properties = {}
            required = schema.get("required", [])

            for prop_name, prop_def in schema.get("properties", {}).items():
                gemini_prop = {}

                # Map JSON Schema types to Gemini types
                json_type = prop_def.get("type", "string")
                type_map = {
                    "string": "STRING",
                    "integer": "INTEGER",
                    "number": "NUMBER",
                    "boolean": "BOOLEAN",
                    "array": "ARRAY",
                }
                gemini_prop["type"] = type_map.get(json_type, "STRING")

                if "description" in prop_def:
                    gemini_prop["description"] = prop_def["description"]

                # Handle array items
                if json_type == "array" and "items" in prop_def:
                    item_type = prop_def["items"].get("type", "string")
                    gemini_prop["items"] = {
                        "type": type_map.get(item_type, "STRING"),
                    }

                properties[prop_name] = gemini_prop

            decl = types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters={
                    "type": "OBJECT",
                    "properties": properties,
                    "required": required,
                },
            )
            declarations.append(decl)

        return [types.Tool(function_declarations=declarations)]

    # ──────────────────────────────────────────────
    # Tool execution
    # ──────────────────────────────────────────────

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute an MCP tool and return the text result."""
        logger.info(f"Calling MCP tool: {tool_name}({arguments})")
        result = await self._session.call_tool(tool_name, arguments)
        text = result.content[0].text
        logger.info(f"Tool {tool_name} returned {len(text)} chars")
        return text

    # ──────────────────────────────────────────────
    # Gemini tool-use loop with streaming
    # ──────────────────────────────────────────────

    async def stream_with_tools(self, question: str) -> AsyncGenerator[str, None]:
        """
        Run Gemini tool-use loop and yield SSE event strings.

        Yields lines in the format:
            data: {"type": "token", "content": "..."}\n\n
            data: {"type": "done", "answer": "...", "chart_data": {...}, "metrics": {...}}\n\n
        """
        client = genai.Client(api_key=config.GOOGLE_API_KEY)

        messages = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(_SYSTEM_PROMPT + "\n\nQuestion: " + question)],
            ),
        ]

        max_tool_rounds = 10

        for round_num in range(max_tool_rounds):
            logger.info(f"Gemini tool-use round {round_num + 1}")

            # Non-streaming call to check for tool use
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=messages,
                config=types.GenerateContentConfig(
                    tools=self._gemini_tools,
                    temperature=config.LLM_TEMPERATURE,
                    max_output_tokens=config.LLM_MAX_TOKENS,
                ),
            )

            candidate = response.candidates[0]

            # Check if any part contains a function call
            has_tool_calls = any(
                part.function_call is not None for part in candidate.content.parts
            )

            if not has_tool_calls:
                # No tool calls — this is the final answer. Stream it.
                break

            # Execute tool calls
            tool_call_parts = [
                part for part in candidate.content.parts if part.function_call is not None
            ]

            # Add the model's response (with tool calls) to the conversation
            messages.append(candidate.content)

            # Execute each tool call and collect results
            function_response_parts = []
            for part in tool_call_parts:
                fc = part.function_call
                tool_name = fc.name
                tool_args = dict(fc.args) if fc.args else {}

                try:
                    tool_result = await self.call_tool(tool_name, tool_args)
                except Exception as e:
                    tool_result = json.dumps({"error": str(e), "tool": tool_name})

                function_response_parts.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response={"result": tool_result},
                    )
                )

            # Add tool results to conversation
            messages.append(
                types.Content(role="user", parts=function_response_parts)
            )
        else:
            # Exhausted all rounds — generate a final answer without tools
            logger.warning("Max tool-use rounds reached, generating final answer")

        # Stream the final text response
        full_response = []

        stream = client.models.generate_content_stream(
            model=config.GEMINI_MODEL,
            contents=messages,
            config=types.GenerateContentConfig(
                temperature=config.LLM_TEMPERATURE,
                max_output_tokens=config.LLM_MAX_TOKENS,
            ),
        )

        for chunk in stream:
            if chunk.text:
                full_response.append(chunk.text)
                event = json.dumps({"type": "token", "content": chunk.text})
                yield f"data: {event}\n\n"

        # Build final "done" event
        answer = "".join(full_response)
        chart_data = self._extract_chart_data(answer)

        # Clean chart_data block from the displayed answer
        clean_answer = answer
        if chart_data:
            marker = "```chart_data"
            idx = clean_answer.find(marker)
            if idx != -1:
                end_idx = clean_answer.find("```", idx + len(marker))
                if end_idx != -1:
                    clean_answer = (
                        clean_answer[:idx].rstrip()
                        + clean_answer[end_idx + 3 :].lstrip()
                    )

        done_event = json.dumps({
            "type": "done",
            "answer": clean_answer,
            "chart_data": chart_data,
            "metrics": {},
        })
        yield f"data: {done_event}\n\n"

    # ──────────────────────────────────────────────
    # Chart data extraction
    # ──────────────────────────────────────────────

    @staticmethod
    def _extract_chart_data(text: str) -> dict | None:
        """Extract a ```chart_data JSON block from the LLM response."""
        marker_start = "```chart_data"
        marker_end = "```"

        start_idx = text.find(marker_start)
        if start_idx == -1:
            return None

        content_start = start_idx + len(marker_start)
        end_idx = text.find(marker_end, content_start)
        if end_idx == -1:
            return None

        json_str = text[content_start:end_idx].strip()

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse chart_data JSON: {e}")
            return None
