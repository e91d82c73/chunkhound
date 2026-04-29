"""Websearch command for ChunkHound CLI."""

from __future__ import annotations

import argparse
import asyncio
import html
import html.parser
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Browser

from chunkhound.core.config.config import Config

from ..utils.rich_output import RichOutputFormatter

_MAX_FETCH_CONCURRENCY = 5


class _NextFormParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._form: list[dict[str, str | None]] | None = None
        self._forms: list[list[dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d: dict[str, str | None] = dict(attrs)
        if tag == "form":
            self._form = []
        elif tag == "input" and self._form is not None:
            self._form.append(d)

    def handle_endtag(self, tag: str) -> None:
        if tag == "form" and self._form is not None:
            self._forms.append(self._form)
            self._form = None

    def next_params(self) -> dict[str, str] | None:
        for form in self._forms:
            if any(
                a.get("type") == "submit" and a.get("value") == "Next" for a in form
            ):
                return {
                    name: a.get("value") or ""
                    for a in form
                    if a.get("type") == "hidden" and (name := a.get("name")) is not None
                }
        return None


class _ResultParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[tuple[str, str, str]] = []
        self._capture: str | None = None
        self._title = ""
        self._url = ""
        self._desc = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d: dict[str, str | None] = dict(attrs)
        cls = d.get("class") or ""
        if tag == "a" and "result__a" in cls:
            self._url = d.get("href") or ""
            self._title = ""
            self._capture = "title"
        elif tag == "a" and "result__snippet" in cls:
            self._desc = ""
            self._capture = "desc"

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._capture == "title":
            self._capture = None
        elif tag == "a" and self._capture == "desc":
            self._capture = None
            if self._title and self._url:
                self.results.append(
                    (
                        html.unescape(self._title),
                        self._url,
                        html.unescape(self._desc),
                    )
                )
            self._title = self._url = self._desc = ""

    def handle_data(self, data: str) -> None:
        if self._capture == "title":
            self._title += data
        elif self._capture == "desc":
            self._desc += data


def _fetch(params: dict[str, str]) -> str:
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        "https://html.duckduckgo.com/html/",
        data=data,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode()


def _url_to_filename(url: str, max_length: int = 100) -> str:
    name = re.sub(r"^https?://", "", url)
    name = re.sub(r"[^\w.-]", "_", name)
    return name[:max_length]


def _fetch_url(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode(errors="replace")


async def _fetch_page(browser: Browser, url: str) -> str:
    """Fetch rendered HTML of a single URL using an existing Playwright browser."""
    page = await browser.new_page()
    try:
        await page.goto(url, timeout=30000)
        return await page.content()
    finally:
        await page.close()


async def _fetch_one(
    url: str,
    tmpdir: Path,
    browser: Browser | None,
    progress_callback: Callable[[str], None] | None,
    warning_callback: Callable[[str], None] | None,
    semaphore: asyncio.Semaphore,
) -> None:
    async with semaphore:
        if progress_callback:
            progress_callback(f"Fetching {url}...")
        try:
            content = (
                await _fetch_page(browser, url)
                if browser is not None
                else await asyncio.to_thread(_fetch_url, url)
            )
            (tmpdir / _url_to_filename(url)).write_text(content, encoding="utf-8")
        except Exception as e:
            if warning_callback:
                warning_callback(f"Failed to fetch {url}: {type(e).__name__}: {e}")


async def _fetch_and_save(
    urls: list[str],
    tmpdir: Path,
    progress_callback: Callable[[str], None] | None = None,
    warning_callback: Callable[[str], None] | None = None,
) -> None:
    """Fetch each URL concurrently (bounded) and save HTML to tmpdir."""
    semaphore = asyncio.Semaphore(_MAX_FETCH_CONCURRENCY)

    async def _run(browser: Browser | None) -> None:
        tasks = [
            _fetch_one(
                url, tmpdir, browser, progress_callback, warning_callback, semaphore
            )
            for url in urls
        ]
        await asyncio.gather(*tasks)

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        await _run(None)
        return

    async with async_playwright() as pw:
        exe = pw.chromium.executable_path
        if not (exe and Path(exe).exists()):
            if warning_callback:
                warning_callback(
                    "Chromium not installed — run: playwright install chromium."
                    " Falling back to urllib."
                )
            await _run(None)
            return
        browser = await pw.chromium.launch()
        try:
            await _run(browser)
        finally:
            await browser.close()


def _search(
    query: str,
    limit: int = 30,
    progress_callback: Callable[[str], None] | None = None,
) -> list[tuple[str, str, str]]:
    results: list[tuple[str, str, str]] = []
    params: dict[str, str] = {"q": query, "b": ""}  # b = submit button name
    page_num = 0
    while True:
        page_num += 1
        if progress_callback:
            progress_callback(f"Fetching page {page_num}...")
        page = _fetch(params)
        rp = _ResultParser()
        rp.feed(page)
        if not rp.results:
            break
        results.extend(rp.results)
        if len(results) >= limit:
            break
        nfp = _NextFormParser()
        nfp.feed(page)
        next_params = nfp.next_params()
        if not next_params:
            break
        params = next_params
    return results[:limit]


async def websearch_command(args: argparse.Namespace, config: Config) -> None:
    """Fetch DuckDuckGo results for the given query."""
    formatter = RichOutputFormatter(verbose=getattr(args, "verbose", False))
    try:
        results = await asyncio.to_thread(
            _search, args.query, args.limit, formatter.progress_indicator
        )
    except urllib.error.URLError as e:
        formatter.error(f"Web search failed: {e.reason}")
        sys.exit(1)
    if not results:
        formatter.error(
            f"No results found for {args.query!r} — DDG HTML structure may have changed"
        )
        return
    output = "\n".join(f"{title}\n  {url}\n  {desc}" for title, url, desc in results)
    formatter.text_block(output)
    tmpdir = Path(tempfile.mkdtemp(prefix="chunkhound_websearch_"))
    await _fetch_and_save(
        [url for _, url, _ in results],
        tmpdir,
        formatter.progress_indicator,
        formatter.warning,
    )
    formatter.text_block(str(tmpdir))
