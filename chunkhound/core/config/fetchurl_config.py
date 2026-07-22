"""
FetchUrl configuration for the ChunkHound single-URL fetch feature.

Governs Option A (token-truncate) vs Option D (chunk + rerank + elbow) dispatch,
Option A truncation budget, and single-URL fetch retry count. Configuration
sources match the rest of ChunkHound: CLI arguments > env vars > config files >
defaults.
"""

import argparse
import os
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FetchUrlConfig(BaseSettings):
    """
    FetchUrl configuration.

    Configuration Sources (in order of precedence):
    1. CLI arguments
    2. Environment variables (CHUNKHOUND_FETCHURL_*)
    3. Config files
    4. Default values

    Environment Variables:
        CHUNKHOUND_FETCHURL_RERANK_THRESHOLD_TOKENS=20000
        CHUNKHOUND_FETCHURL_TRUNCATE_TOKENS=15000
        CHUNKHOUND_FETCHURL_MAX_RETRIES=3
    """

    model_config = SettingsConfigDict(
        env_prefix="CHUNKHOUND_FETCHURL_",
        env_nested_delimiter="__",
        case_sensitive=False,
        validate_default=True,
        extra="ignore",  # Ignore unknown fields for forward compatibility
    )

    rerank_threshold_tokens: int = Field(
        default=20_000,
        ge=1,
        description=(
            "Estimated token count at/above which Option D (chunk+rerank+elbow) "
            "is used instead of Option A (token-truncate). Tokens estimated via "
            "EMBEDDING_CHARS_PER_TOKEN (3 chars/token) — the same ratio "
            "chunk_splitter and HyDE use. Default 20_000 aligns with the HyDE "
            "'medium' comprehensiveness tier and the lower bound of "
            "gap-detection's shard_budget range (research_config.py:213-218)."
        ),
    )

    truncate_tokens: int = Field(
        default=15_000,
        ge=1,
        description=(
            "Token cap applied to Option A input before the LLM call. "
            "Estimated via LLM_CHARS_PER_TOKEN (char-ratio, 4 chars/token) — "
            "matches chunk_splitter's deterministic-and-cheap estimation and "
            "aligns with the HyDE/research tier's token-budget precedent "
            "(max_snippet_tokens, LLM_INPUT_TOKENS_MIN)."
        ),
    )

    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description=(
            "Fetch attempts (including the first). Exponential backoff with "
            "full jitter between attempts."
        ),
    )

    @classmethod
    def add_cli_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add fetchurl-related CLI arguments."""
        parser.add_argument(
            "--fetchurl-rerank-threshold-tokens",
            type=int,
            help=(
                "Estimated token count at/above which Option D "
                "(chunk+rerank+elbow) is used instead of Option A "
                "(token-truncate) (default: 20000)"
            ),
        )
        parser.add_argument(
            "--fetchurl-truncate-tokens",
            type=int,
            help="Token cap applied to Option A input before the LLM (default: 15000)",
        )
        parser.add_argument(
            "--fetchurl-max-retries",
            type=int,
            help="Fetch attempts including the first, with backoff (default: 3)",
        )

    @classmethod
    def load_from_env(cls) -> dict[str, Any]:
        """Load fetchurl config from environment variables."""
        config: dict[str, Any] = {}

        if threshold := os.getenv("CHUNKHOUND_FETCHURL_RERANK_THRESHOLD_TOKENS"):
            config["rerank_threshold_tokens"] = int(threshold)

        if truncate := os.getenv("CHUNKHOUND_FETCHURL_TRUNCATE_TOKENS"):
            config["truncate_tokens"] = int(truncate)

        if retries := os.getenv("CHUNKHOUND_FETCHURL_MAX_RETRIES"):
            config["max_retries"] = int(retries)

        return config

    @classmethod
    def extract_cli_overrides(cls, args: Any) -> dict[str, Any]:
        """Extract fetchurl config from CLI arguments."""
        overrides: dict[str, Any] = {}

        if (
            hasattr(args, "fetchurl_rerank_threshold_tokens")
            and args.fetchurl_rerank_threshold_tokens is not None
        ):
            overrides["rerank_threshold_tokens"] = args.fetchurl_rerank_threshold_tokens

        if (
            hasattr(args, "fetchurl_truncate_tokens")
            and args.fetchurl_truncate_tokens is not None
        ):
            overrides["truncate_tokens"] = args.fetchurl_truncate_tokens

        if (
            hasattr(args, "fetchurl_max_retries")
            and args.fetchurl_max_retries is not None
        ):
            overrides["max_retries"] = args.fetchurl_max_retries

        return overrides

    def __repr__(self) -> str:
        """String representation with key settings."""
        return (
            f"FetchUrlConfig("
            f"rerank_threshold_tokens={self.rerank_threshold_tokens}, "
            f"truncate_tokens={self.truncate_tokens}, "
            f"max_retries={self.max_retries})"
        )
