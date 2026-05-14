"""Formatting helper shared by CLI and MCP websearch paths."""

from __future__ import annotations


def format_sources(results: list[tuple[str, str, str]]) -> str:
    """Render DuckDuckGo results as the CLI/MCP 'Sources' preamble."""
    return "\n".join(f"{title}\n  {url}\n  {desc}" for title, url, desc in results)
