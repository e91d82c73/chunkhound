"""Quickresearch command argument parser for ChunkHound CLI."""

import argparse
from pathlib import Path
from typing import Any, cast

from .common_arguments import (
    add_common_arguments,
    add_config_arguments,
    nonempty_path_filter,
)


def add_quickresearch_subparser(subparsers: Any) -> argparse.ArgumentParser:
    """Add quickresearch command subparser to the main parser."""
    p = subparsers.add_parser(
        "quickresearch",
        help="Index a directory in memory, then perform deep code research",
        description=(
            "Indexes files into a transient in-memory database and answers "
            "research questions. No index is persisted."
        ),
    )

    p.add_argument("query", help="Research question to investigate")

    p.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path("."),
        help="Directory to index and research (default: current directory)",
    )

    p.add_argument(
        "--path-filter",
        type=nonempty_path_filter,
        help="Optional path filter (e.g., 'src/', 'tests/')",
    )

    add_common_arguments(p)
    add_config_arguments(p, ["embedding", "llm", "research"])

    return cast(argparse.ArgumentParser, p)


__all__: list[str] = ["add_quickresearch_subparser"]
