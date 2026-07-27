"""Contract tests for fetchurl's MCP surface.

Bullets 1-2 of spec §16.2 (tools/list filtering + schema shape) are covered
in ``tests/test_mcp_tool_consistency.py`` — see
``test_fetchurl_hidden_without_capabilities`` and ``test_fetchurl_schema``.
Bullet 4 (dispatcher reranker guard at ``common.py:225``) is derivable from
tested primitives: ``TOOL_REGISTRY["fetchurl"].requires_reranker`` is
asserted in ``test_tool_capability_requirements``, and
``has_reranker_support`` is exercised in ``test_embeddings.py``. No
per-tool runtime assertion.

This module covers bullet 3: ``fetchurl_impl`` wraps LLM output in the
shared ``Source:`` box.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chunkhound.core.config.config import Config
from chunkhound.mcp_server.tools import fetchurl_impl


@pytest.mark.asyncio
async def test_fetchurl_mcp_call_returns_source_boxed_markdown(tmp_path):
    url = "http://example.com/doc.md"
    canned_md = "# Hello\n\nBody paragraph."

    # query="" routes through option_truncate — the reranker path is not
    # exercised here, so the returned mock is unused on this path.
    embedding_manager = MagicMock()

    llm_manager = MagicMock()
    llm_manager.get_utility_provider.return_value.complete = AsyncMock(
        return_value=SimpleNamespace(content=canned_md)
    )

    async def fake_fetch(u, cfg, warning_callback=None):
        return (".md", "# Hello\n\nBody paragraph.", {"title": "Hello"})

    with patch(
        "chunkhound.utils.fetchurl._fetch_with_retry", side_effect=fake_fetch
    ):
        result = await fetchurl_impl(
            embedding_manager=embedding_manager,
            llm_manager=llm_manager,
            config=Config(target_dir=tmp_path),
            url=url,
            query="",
        )

    assert result == f"Source: {url}\n{'=' * 60}\n{canned_md}\n{'=' * 60}"
