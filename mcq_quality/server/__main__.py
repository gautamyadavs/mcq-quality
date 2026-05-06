"""Entry point: `python -m mcq_quality.server` or `mcq-quality-server`."""

from .mcq_server import mcp


def main():
    """Run the MCP server (stdio transport, default for FastMCP)."""
    mcp.run()


if __name__ == "__main__":
    main()
