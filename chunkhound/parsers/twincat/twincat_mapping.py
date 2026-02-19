"""TwinCAT mapping for UniversalParser integration.

This module provides the TwinCATMapping class that enables TwinCAT Structured Text
files to be processed through the UniversalParser pipeline, benefiting from
chunk deduplication, cAST algorithm optimization, and comment merging.

Unlike other mappings that use tree-sitter queries, this mapping delegates
to TwinCATParser (Lark-based) and provides an `extract_universal_chunks()`
method that UniversalParser calls when engine=None.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from chunkhound.core.types.common import Language
from chunkhound.parsers.mappings.base import BaseMapping
from chunkhound.parsers.universal_engine import UniversalChunk

if TYPE_CHECKING:
    from chunkhound.parsers.twincat.twincat_parser import TwinCATParser

# Lazy import to avoid circular dependency
_parser: TwinCATParser | None = None


def _get_parser() -> TwinCATParser:
    """Get or create the TwinCATParser instance (lazy loading)."""
    global _parser
    if _parser is None:
        from chunkhound.parsers.twincat.twincat_parser import TwinCATParser

        _parser = TwinCATParser()
    return _parser


class TwinCATMapping(BaseMapping):
    """Mapping for TwinCAT Structured Text via Lark parser.

    Unlike other mappings that use tree-sitter queries, this mapping
    uses TwinCATParser (Lark-based) to extract UniversalChunk objects.

    The mapping provides `extract_universal_chunks()` which UniversalParser
    calls when engine=None, enabling TwinCAT files to benefit from the
    full cAST pipeline (deduplication, comment merging, greedy merge).
    """

    def __init__(self) -> None:
        """Initialize TwinCAT mapping."""
        super().__init__(Language.TWINCAT)

    def extract_universal_chunks(
        self,
        content: str,
        file_path: Path | None = None,
    ) -> list[UniversalChunk]:
        """Extract UniversalChunk objects from TcPOU content.

        Called by UniversalParser when engine is None and this method exists.

        Args:
            content: TcPOU XML content string
            file_path: Optional path to the source file

        Returns:
            List of UniversalChunk objects for cAST processing
        """
        parser = _get_parser()
        return parser.extract_universal_chunks(content, file_path)

    def extract_imports(
        self,
        content: str,
    ) -> list[UniversalChunk]:
        """Extract only import chunks from TcPOU content.

        More efficient than extract_universal_chunks() when only
        imports are needed.

        Args:
            content: TcPOU XML content string

        Returns:
            List of UniversalChunk objects representing imports
        """
        parser = _get_parser()
        return parser.extract_import_chunks(content)

    # Required abstract method implementations (not used for TwinCAT)
    # These are required by BaseMapping but TwinCAT uses Lark instead of tree-sitter

    def get_function_query(self) -> str:
        """Not used - TwinCAT uses Lark parser, not tree-sitter queries."""
        return ""

    def get_class_query(self) -> str:
        """Not used - TwinCAT uses Lark parser, not tree-sitter queries."""
        return ""

    def get_comment_query(self) -> str:
        """Not used - TwinCAT uses Lark parser, not tree-sitter queries."""
        return ""

    def extract_function_name(self, node: Any, source: str) -> str:
        """Not used - TwinCAT uses Lark parser, not tree-sitter nodes."""
        return ""

    def extract_class_name(self, node: Any, source: str) -> str:
        """Not used - TwinCAT uses Lark parser, not tree-sitter nodes."""
        return ""
