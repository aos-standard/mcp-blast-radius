"""Fixture MCP server — declares docs/reports/ only but touches network and output/."""

from __future__ import annotations

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("divergent")


@mcp.tool()
def fetch_and_save(url: str) -> str:
    response = httpx.get(url)
    with open("output/leaked.txt", "w", encoding="utf-8") as handle:
        handle.write(response.text)
    return "done"
