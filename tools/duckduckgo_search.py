"""Small DuckDuckGo HTML search adapter.

This is a fallback for OpenAI-compatible providers that do not implement the
Responses API web_search tool. It retrieves public search-result snippets, then
the LLM extracts structured product candidates from those snippets.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str

    def to_prompt_text(self) -> str:
        return f"Title: {self.title}\nURL: {self.url}\nSnippet: {self.snippet}"


class DuckDuckGoSearch:
    """Fetch search results from DuckDuckGo's lightweight HTML endpoint."""

    def search(self, query: str, limit: int = 10, market: str = "us-en") -> list[SearchResult]:
        params = urlencode({"q": query, "kl": market or "us-en"})
        request = Request(
            f"https://duckduckgo.com/html/?{params}",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urlopen(request, timeout=20) as response:
            html = response.read().decode("utf-8", errors="replace")

        parser = _DuckDuckGoParser()
        parser.feed(html)
        return parser.results[:limit]


class _DuckDuckGoParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchResult] = []
        self._in_result_link = False
        self._in_snippet = False
        self._current_title: list[str] = []
        self._current_url = ""
        self._pending_snippet: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        classes = attrs_dict.get("class", "")
        if tag == "a" and "result__a" in classes:
            self._in_result_link = True
            self._current_title = []
            self._current_url = attrs_dict.get("href") or ""
        elif "result__snippet" in classes:
            self._in_snippet = True
            self._pending_snippet = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_result_link:
            self._in_result_link = False
        elif self._in_snippet:
            self._in_snippet = False
            title = _clean(" ".join(self._current_title))
            snippet = _clean(" ".join(self._pending_snippet))
            if title and self._current_url:
                self.results.append(
                    SearchResult(title=title, url=self._current_url, snippet=snippet)
                )
            self._current_title = []
            self._current_url = ""
            self._pending_snippet = []

    def handle_data(self, data: str) -> None:
        if self._in_result_link:
            self._current_title.append(data)
        elif self._in_snippet:
            self._pending_snippet.append(data)


def _clean(text: str) -> str:
    return " ".join(unescape(text).split())
