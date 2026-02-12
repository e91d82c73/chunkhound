"""TwinCAT Structured Text parser for ChunkHound."""

# Conditional export - only when lark is available
try:
    from .twincat_parser import TwinCATParser

    __all__ = ["TwinCATParser"]
except ImportError:
    __all__ = []
