"""
mcp_client.py — MCP client used by the workflow to call the mcq-quality server.

This is the workflow → MCP integration. When compare_pipelines is invoked
with --use-mcp, the workflow's Validator step uses this client to call the
server's validate_mcq tool through the MCP protocol, instead of importing
the validator function directly from mcq_quality.core.

Pedagogically, this demonstrates:
- Workflows can call MCP tools as steps in their pipeline
- The MCP protocol decouples the caller (workflow) from the implementation
  (server process holding the validator + the question bank)
- The same validator runs either way; what changes is the calling path

Architecturally, this lets the workflow run client-independent: it doesn't
need to be embedded in Claude Code or any other AI client to use the MCP
server's tools. The workflow connects to the server directly via stdio.
"""

import asyncio
import contextlib
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@contextlib.asynccontextmanager
async def open_mcp_session():
    """
    Context manager that spawns the mcq-quality MCP server as a subprocess
    over stdio and returns an open ClientSession to it.

    Usage:
        async with open_mcp_session() as session:
            result = await session.call_tool("validate_mcq", {...})
    """
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "mcq_quality.server"],
        env=None,
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def call_validate_mcq(
    stem: str,
    options: list[str],
    correct_index: int,
) -> dict[str, Any]:
    """
    Call the server's validate_mcq tool through MCP and return the parsed
    validation report.

    The server's tool calls into mcq_quality.core.run_validator (same
    function the skill's script imports), so the report shape is identical
    to what you'd get from a direct in-process call. The difference is the
    transport: this version goes through the MCP protocol, demonstrating
    that the workflow is acting as an MCP client to the server.
    """
    async with open_mcp_session() as session:
        result = await session.call_tool(
            "validate_mcq",
            arguments={
                "stem": stem,
                "options": options,
                "correct_index": correct_index,
            },
        )

    if result.isError:
        raise RuntimeError(f"MCP tool returned error: {result.content}")

    # Modern MCP SDK returns dict results in structuredContent. Fall back to
    # parsing JSON from the text content block for older servers/clients.
    if result.structuredContent is not None:
        return result.structuredContent

    import json
    if not result.content:
        raise RuntimeError("MCP tool returned no content")

    first_block = result.content[0]
    text = getattr(first_block, "text", None)
    if text is None:
        raise RuntimeError(
            f"Unexpected content type from MCP tool: {type(first_block).__name__}"
        )
    return json.loads(text)


def call_validate_mcq_sync(
    stem: str,
    options: list[str],
    correct_index: int,
) -> dict[str, Any]:
    """
    Synchronous wrapper around call_validate_mcq. The workflow's agents are
    written as plain functions (not async), so they need a sync entry point
    into the MCP client.
    """
    return asyncio.run(call_validate_mcq(stem, options, correct_index))
