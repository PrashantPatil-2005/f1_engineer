"""
F1 AI Race Engineer — MCP Client

Connects to the MCP server over stdio, discovers tools, and runs a
Groq tool-use loop that streams the final answer back via SSE events.

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
# from google import genai
# from google.genai import types
from groq import Groq

from config import config

logger = logging.getLogger(__name__)

# System prompt given to the LLM for the tool-use conversation
_SYSTEM_PROMPT = """You are an expert Formula 1 race engineer and analyst. You have access to
tools that can fetch real F1 data from the FastF1 database. Use these tools to answer
the user's question with data-grounded analysis.

CRITICAL RULES:
1. ALWAYS call the appropriate tool(s) to get data before answering. Do NOT guess or hallucinate data.
2. If a tool returns an error, explain what went wrong and suggest alternatives.
3. Reference specific data points (lap times, stint lengths, position changes) to support your analysis.
4. Use F1 terminology naturally: stint, compound, undercut, overcut, degradation, delta, etc.
5. Be concise but thorough. Engineers want signal, not padding.

CHART OUTPUT RULES — MANDATORY, NOT OPTIONAL:
You MUST include a ```chart_data block at the end of your response when the question
involves ANY of: lap times, tyre strategy, driver comparison, race pace, stint analysis.

Choose exactly ONE chart type based on the question:

TYPE 1 — "lap_time_comparison" (use when comparing average/best lap times across drivers):
```chart_data
{
  "type": "lap_time_comparison",
  "title": "<descriptive title>",
  "labels": ["Stint 1 Avg", "Stint 2 Avg", "Best Lap"],
  "datasets": [
    {"driver": "VER", "values": [76.5, 77.2, 75.8]},
    {"driver": "LEC", "values": [76.9, 77.5, 76.1]}
  ]
}
```

TYPE 2 — "tyre_strategy" (use when question is about pit stops, strategy, or tyre choices):
```chart_data
{
  "type": "tyre_strategy",
  "title": "<descriptive title>",
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
compound must be one of: SOFT, MEDIUM, HARD, INTERMEDIATE, WET

TYPE 3 — "lap_times" (use when showing lap-by-lap progression for one or two drivers):
```chart_data
{
  "type": "lap_times",
  "title": "<descriptive title>",
  "datasets": [
    {
      "driver": "VER",
      "laps": [1, 2, 3, 4, 5],
      "values": [76.5, 76.3, 76.8, 77.1, 76.4]
    }
  ]
}
```

RULES:
- All lap time values must be in SECONDS as floats (e.g., 76.5 = 1:16.500)
- The ```chart_data block must be the LAST thing in your response
- Use ONLY driver abbreviations (VER, LEC, HAM, etc.), never full names in chart data
- If the question has no data to chart (e.g., "who won in 2024?"), omit the block"""


class F1MCPClient:
    """MCP client that bridges MCP tools with Groq's tool-use API."""

    def __init__(self):
        self._server_script = Path(__file__).resolve().parent.parent.parent / "mcp_server" / "server.py"
        self._session: ClientSession | None = None
        self._stdio_context = None
        self._session_context = None
        self._mcp_tools: list = []
        # self._gemini_tools: list = []
        self._groq_tools: list = []

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
        # self._gemini_tools = self._mcp_tools_to_gemini(self._mcp_tools)
        self._groq_tools = self._build_groq_tools(self._mcp_tools)

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
    # Tool conversion: MCP → Gemini format (commented out, replaced by Groq)
    # ──────────────────────────────────────────────

    # def _mcp_tools_to_gemini(self, mcp_tools) -> list:
    #     """Convert MCP tool definitions to Gemini FunctionDeclaration format."""
    #     declarations = []
    #
    #     for tool in mcp_tools:
    #         schema = tool.inputSchema
    #         properties = {}
    #         required = schema.get("required", [])
    #
    #         for prop_name, prop_def in schema.get("properties", {}).items():
    #             gemini_prop = {}
    #
    #             # Map JSON Schema types to Gemini types
    #             json_type = prop_def.get("type", "string")
    #             type_map = {
    #                 "string": "STRING",
    #                 "integer": "INTEGER",
    #                 "number": "NUMBER",
    #                 "boolean": "BOOLEAN",
    #                 "array": "ARRAY",
    #             }
    #             gemini_prop["type"] = type_map.get(json_type, "STRING")
    #
    #             if "description" in prop_def:
    #                 gemini_prop["description"] = prop_def["description"]
    #
    #             # Handle array items
    #             if json_type == "array" and "items" in prop_def:
    #                 item_type = prop_def["items"].get("type", "string")
    #                 gemini_prop["items"] = {
    #                     "type": type_map.get(item_type, "STRING"),
    #                 }
    #
    #             properties[prop_name] = gemini_prop
    #
    #         decl = types.FunctionDeclaration(
    #             name=tool.name,
    #             description=tool.description,
    #             parameters={
    #                 "type": "OBJECT",
    #                 "properties": properties,
    #                 "required": required,
    #             },
    #         )
    #         declarations.append(decl)
    #
    #     return [types.Tool(function_declarations=declarations)]

    # ──────────────────────────────────────────────
    # Tool conversion: MCP → Groq/OpenAI format
    # ──────────────────────────────────────────────

    def _build_groq_tools(self, mcp_tools: list) -> list:
        """Convert MCP tool schemas to Groq/OpenAI function-calling format."""
        groq_tools = []
        for tool in mcp_tools:
            groq_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                },
            })
        return groq_tools

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
    # Groq tool-use loop with streaming
    # ──────────────────────────────────────────────

    async def stream_with_tools(self, question: str) -> AsyncGenerator[str, None]:
        """
        Run Groq tool-use loop and yield SSE event strings.

        Yields lines in the format:
            data: {"type": "token", "content": "..."}\n\n
            data: {"type": "done", "answer": "...", "chart_data": {...}, "metrics": {...}}\n\n
        """
        # client = genai.Client(api_key=config.GOOGLE_API_KEY)
        groq_client = Groq(api_key=config.GROQ_API_KEY)

        # messages = [
        #     types.Content(
        #         role="user",
        #         parts=[types.Part.from_text(_SYSTEM_PROMPT + "\n\nQuestion: " + question)],
        #     ),
        # ]
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]

        max_tool_rounds = 10

        for round_num in range(max_tool_rounds):
            logger.info(f"Groq tool-use round {round_num + 1}")

            # Non-streaming call to check for tool use
            # response = client.models.generate_content(
            #     model=config.GEMINI_MODEL,
            #     contents=messages,
            #     config=types.GenerateContentConfig(
            #         tools=self._gemini_tools,
            #         temperature=config.LLM_TEMPERATURE,
            #         max_output_tokens=config.LLM_MAX_TOKENS,
            #     ),
            # )

            response = groq_client.chat.completions.create(
                model=config.GROQ_MODEL,
                messages=messages,
                tools=self._groq_tools,
                tool_choice="auto",
                temperature=config.LLM_TEMPERATURE,
                max_tokens=config.LLM_MAX_TOKENS,
            )

            # candidate = response.candidates[0]
            #
            # # Check if any part contains a function call
            # has_tool_calls = any(
            #     part.function_call is not None for part in candidate.content.parts
            # )

            choice = response.choices[0]
            has_tool_calls = (
                choice.finish_reason == "tool_calls"
                and choice.message.tool_calls is not None
                and len(choice.message.tool_calls) > 0
            )

            if not has_tool_calls:
                # No tool calls — this is the final answer. Stream it.
                break

            # Execute tool calls
            # tool_call_parts = [
            #     part for part in candidate.content.parts if part.function_call is not None
            # ]
            #
            # # Add the model's response (with tool calls) to the conversation
            # messages.append(candidate.content)

            tool_calls = choice.message.tool_calls
            messages.append({
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            })

            # Execute each tool call and collect results
            # function_response_parts = []
            # for part in tool_call_parts:
            #     fc = part.function_call
            #     tool_name = fc.name
            #     tool_args = dict(fc.args) if fc.args else {}
            #
            #     try:
            #         tool_result = await self.call_tool(tool_name, tool_args)
            #     except Exception as e:
            #         tool_result = json.dumps({"error": str(e), "tool": tool_name})
            #
            #     function_response_parts.append(
            #         types.Part.from_function_response(
            #             name=tool_name,
            #             response={"result": tool_result},
            #         )
            #     )

            tool_results = []
            for tc in tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments)
                except Exception:
                    tool_args = {}
                try:
                    tool_result = await self.call_tool(tool_name, tool_args)
                except Exception as e:
                    tool_result = json.dumps({"error": str(e), "tool": tool_name})
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tool_name,
                    "content": tool_result,
                })

            # Add tool results to conversation
            # messages.append(
            #     types.Content(role="user", parts=function_response_parts)
            # )
            messages.extend(tool_results)
        else:
            # Exhausted all rounds — generate a final answer without tools
            logger.warning("Max tool-use rounds reached, generating final answer")

        # Stream the final text response, suppressing the ```chart_data block
        full_response = []
        in_chart_block = False
        chart_block_done = False
        chart_buffer = ""
        visible_text = ""

        # stream = client.models.generate_content_stream(
        #     model=config.GEMINI_MODEL,
        #     contents=messages,
        #     config=types.GenerateContentConfig(
        #         temperature=config.LLM_TEMPERATURE,
        #         max_output_tokens=config.LLM_MAX_TOKENS,
        #     ),
        # )

        stream = groq_client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=messages,
            temperature=config.LLM_TEMPERATURE,
            max_tokens=config.LLM_MAX_TOKENS,
            stream=True,
        )

        for chunk in stream:
            # if not chunk.text:
            #     continue
            # full_response.append(chunk.text)
            # text = chunk.text
            delta = chunk.choices[0].delta.content
            if not delta:
                continue
            full_response.append(delta)
            text = delta

            if not in_chart_block and not chart_block_done:
                # Check if this chunk contains the chart marker
                combined = visible_text[-20:] + text
                if "```chart_data" in combined:
                    marker_pos = combined.find("```chart_data")
                    safe_len = max(0, marker_pos - len(visible_text[-20:]))
                    if text[:safe_len]:
                        event = json.dumps({"type": "token", "content": text[:safe_len]})
                        yield f"data: {event}\n\n"
                    visible_text = ""
                    in_chart_block = True
                    chart_buffer += text[safe_len:]
                else:
                    visible_text = text
                    event = json.dumps({"type": "token", "content": text})
                    yield f"data: {event}\n\n"

            elif in_chart_block and not chart_block_done:
                chart_buffer += text
                # Check if the closing ``` appeared (after the opening marker)
                if "```" in chart_buffer[len("```chart_data"):]:
                    chart_block_done = True
                    in_chart_block = False
                    close_marker_pos = chart_buffer.find("```", len("```chart_data")) + 3
                    remainder = chart_buffer[close_marker_pos:]
                    if remainder.strip():
                        event = json.dumps({"type": "token", "content": remainder})
                        yield f"data: {event}\n\n"
            else:
                # After chart block is done, stream normally
                event = json.dumps({"type": "token", "content": text})
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
