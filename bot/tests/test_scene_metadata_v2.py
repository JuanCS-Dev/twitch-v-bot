import time
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from bot.scene_metadata import SceneMetadataService


class TestSceneMetadataV2(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = SceneMetadataService()

    def test_normalize_host_variants(self):
        self.assertEqual(self.service.normalize_host("WWW.YOUTUBE.COM"), "youtube.com")
        self.assertEqual(self.service.normalize_host("example.com:8080"), "example.com")

    def test_contains_unsafe_terms_boundary(self):
        self.assertTrue(self.service.contains_unsafe_terms("isso é sexo aqui"))
        self.assertFalse(self.service.contains_unsafe_terms("sextou galera"))

    def test_is_safe_scene_link_blocked(self):
        self.assertFalse(self.service.is_safe_scene_link("https://pornhub.com/vid", "msg"))
        self.assertFalse(self.service.is_safe_scene_link("https://ok.com/vid", "quer ver nude?"))

    def test_build_metadata_source_url_x(self):
        res = self.service.build_metadata_source_url("https://x.com/user/status/1", "x")
        self.assertIn("twitter.com", res)

    @patch("bot.scene_metadata.urlopen")
    def test_fetch_oembed_metadata_fail(self, mock_urlopen):
        # Use URLError which is caught by the code
        mock_urlopen.side_effect = URLError("offline")
        res = self.service.fetch_oembed_metadata("https://youtube.com/v", "youtube")
        self.assertIsNone(res)

    @patch("bot.scene_metadata.urlopen")
    def test_fetch_oembed_metadata_404(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 404
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        res = self.service.fetch_oembed_metadata("https://youtube.com/v", "youtube")
        self.assertIsNone(res)

    def test_cache_expiry(self):
        url = "https://test.com"
        self.service.set_cached_metadata(url, {"title": "t"})
        self.service.metadata_cache[url] = (time.monotonic() - 10, {"title": "t"})
        self.assertIsNone(self.service.get_cached_metadata(url))

    def test_build_sanitized_scene_description_variants(self):
        def mock_norm(t, max_len=None):
            return t

        res = self.service.build_sanitized_scene_description(
            "youtube", "Juan", {"title": "Top 10"}, normalize_text_for_scene=mock_norm
        )
        self.assertIn("Top 10", res)
        res = self.service.build_sanitized_scene_description(
            "x", "Juan", {"author_name": "Elon"}, normalize_text_for_scene=mock_norm
        )
        self.assertIn("Elon", res)

    def test_is_safe_scene_metadata_require_fail(self):
        self.assertFalse(
            self.service.is_safe_scene_metadata(None, "msg", "url", require_metadata=True)
        )
        self.assertTrue(
            self.service.is_safe_scene_metadata(None, "msg", "url", require_metadata=False)
        )
