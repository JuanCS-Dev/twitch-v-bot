"""Tests for bot.web_search module."""

import asyncio
import unittest
from unittest.mock import MagicMock, patch

from bot.web_search import (
    WebSearchResult,
    _ddg_search_sync,
    format_search_context,
    search_web,
)


class TestWebSearchResult(unittest.TestCase):
    def test_dataclass_fields(self) -> None:
        result = WebSearchResult(title="T", snippet="S", url="https://example.com")
        self.assertEqual(result.title, "T")
        self.assertEqual(result.snippet, "S")
        self.assertEqual(result.url, "https://example.com")

    def test_frozen(self) -> None:
        result = WebSearchResult(title="T", snippet="S", url="https://example.com")
        with self.assertRaises(AttributeError):
            result.title = "X"  # type: ignore[misc]


class TestFormatSearchContext(unittest.TestCase):
    def test_empty_results(self) -> None:
        self.assertEqual(format_search_context([]), "")

    def test_single_result(self) -> None:
        results = [
            WebSearchResult(
                title="News",
                snippet="Big event happened.",
                url="https://news.com/article",
            )
        ]
        formatted = format_search_context(results)
        self.assertIn("[CONTEXTO WEB ATUALIZADO", formatted)
        self.assertIn("Big event happened.", formatted)
        self.assertIn("news.com", formatted)
        self.assertIn("[FIM DO CONTEXTO WEB", formatted)

    def test_multiple_results(self) -> None:
        results = [
            WebSearchResult(title="A", snippet="First.", url="https://a.com/1"),
            WebSearchResult(title="B", snippet="Second.", url="https://b.com/2"),
            WebSearchResult(title="C", snippet="Third.", url="https://c.com/3"),
        ]
        formatted = format_search_context(results)
        self.assertIn("1. First.", formatted)
        self.assertIn("2. Second.", formatted)
        self.assertIn("3. Third.", formatted)


class TestSearchWeb(unittest.TestCase):
    def test_empty_query(self) -> None:
        results = asyncio.run(search_web(""))
        self.assertEqual(results, [])

    def test_whitespace_query(self) -> None:
        results = asyncio.run(search_web("   "))
        self.assertEqual(results, [])

    @patch("bot.web_search._ddg_search_sync")
    def test_successful_search(self, mock_ddg: MagicMock) -> None:
        mock_ddg.return_value = [
            WebSearchResult(
                title="Result", snippet="Info found.", url="https://site.com"
            ),
        ]
        results = asyncio.run(search_web("test query"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].snippet, "Info found.")
        mock_ddg.assert_called_once_with("test query", 3)

    @patch("bot.web_search._ddg_search_sync")
    def test_search_timeout_returns_empty(self, mock_ddg: MagicMock) -> None:
        async def slow_search(*args: object, **kwargs: object) -> list[WebSearchResult]:
            await asyncio.sleep(10)
            return []

        mock_ddg.side_effect = TimeoutError("timeout")
        results = asyncio.run(search_web("test"))
        self.assertEqual(results, [])

    @patch("bot.web_search._ddg_search_sync")
    def test_search_exception_returns_empty(self, mock_ddg: MagicMock) -> None:
        mock_ddg.side_effect = RuntimeError("DDG unavailable")
        results = asyncio.run(search_web("test"))
        self.assertEqual(results, [])


class TestDdgSearchSync(unittest.TestCase):
    @patch("duckduckgo_search.DDGS")
    def test_sync_search_parses_items(self, mock_ddgs_cls: MagicMock) -> None:
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.text.return_value = [
            {"title": "Result 1", "body": "Snippet 1", "href": "https://one.com"},
            {"title": "Result 2", "body": "Snippet 2", "href": "https://two.com"},
        ]
        mock_ddgs_cls.return_value = mock_instance

        results = _ddg_search_sync("query", 3)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].title, "Result 1")
        self.assertEqual(results[1].url, "https://two.com")

    @patch("duckduckgo_search.DDGS")
    def test_sync_search_news_returns_results(self, mock_ddgs_cls: MagicMock) -> None:
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.news.return_value = [
            {"title": "News Result", "body": "News snippet", "url": "https://news.com"},
        ]
        mock_ddgs_cls.return_value = mock_instance

        results = _ddg_search_sync("query", 3)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "News Result")
        mock_instance.news.assert_called_once()

    @patch("duckduckgo_search.DDGS")
    def test_sync_search_news_skips_empty_snippet(
        self, mock_ddgs_cls: MagicMock
    ) -> None:
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.news.return_value = [
            {"title": "No Body", "body": "", "url": "https://empty.com"},
            {
                "title": "Has Body",
                "body": "Content here.",
                "url": "https://content.com",
            },
        ]
        mock_ddgs_cls.return_value = mock_instance

        results = _ddg_search_sync("query", 3)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].snippet, "Content here.")

    @patch("duckduckgo_search.DDGS")
    def test_sync_search_news_exception_fallback(
        self, mock_ddgs_cls: MagicMock
    ) -> None:
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.news.side_effect = Exception("News API failed")
        mock_instance.text.return_value = [
            {
                "title": "Fallback",
                "body": "Fallback snippet",
                "href": "https://fallback.com",
            },
        ]
        mock_ddgs_cls.return_value = mock_instance

        results = _ddg_search_sync("query", 3)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Fallback")

    @patch("duckduckgo_search.DDGS")
    def test_sync_search_text_exception(self, mock_ddgs_cls: MagicMock) -> None:
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.news.return_value = []
        mock_instance.text.side_effect = Exception("Text API failed")
        mock_ddgs_cls.return_value = mock_instance

        results = _ddg_search_sync("query", 3)
        self.assertEqual(len(results), 0)

    @patch("duckduckgo_search.DDGS")
    def test_sync_search_skips_empty_snippets(self, mock_ddgs_cls: MagicMock) -> None:
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.text.return_value = [
            {"title": "No Body", "body": "", "href": "https://empty.com"},
            {
                "title": "Has Body",
                "body": "Content here.",
                "href": "https://content.com",
            },
        ]
        mock_ddgs_cls.return_value = mock_instance

        results = _ddg_search_sync("query", 3)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].snippet, "Content here.")


if __name__ == "__main__":
    unittest.main()
