import json
import time
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from bot.scene_metadata import SceneMetadataService


class TestSceneMetadataV3:
    def test_build_oembed_endpoint(self):
        svc = SceneMetadataService()
        assert (
            svc.build_oembed_endpoint("http://youtube.com/watch?v=1", "youtube")
            == "https://www.youtube.com/oembed?url=http%3A%2F%2Fyoutube.com%2Fwatch%3Fv%3D1&format=json"
        )
        assert (
            svc.build_oembed_endpoint("http://x.com/status/1", "x")
            == "https://publish.twitter.com/oembed?url=http%3A%2F%2Fx.com%2Fstatus%2F1&omit_script=true"
        )
        assert svc.build_oembed_endpoint("http://other.com", "other") is None

    def test_build_metadata_source_url(self):
        svc = SceneMetadataService()
        assert svc.build_metadata_source_url("http://other.com", "youtube") == "http://other.com"
        assert (
            svc.build_metadata_source_url("http://x.com/status/1", "x")
            == "http://twitter.com/status/1"
        )
        assert (
            svc.build_metadata_source_url("http://twitter.com/status/1", "x")
            == "http://twitter.com/status/1"
        )

    @patch("bot.scene_metadata.urlopen")
    def test_fetch_oembed_metadata_success(self, mock_urlopen):
        svc = SceneMetadataService()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"title": "test"}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        assert svc.fetch_oembed_metadata("http://youtube.com/watch", "youtube") == {"title": "test"}

    @patch("bot.scene_metadata.urlopen")
    def test_fetch_oembed_metadata_non_200(self, mock_urlopen):
        svc = SceneMetadataService()
        mock_response = MagicMock()
        mock_response.status = 404
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        assert svc.fetch_oembed_metadata("http://youtube.com/watch", "youtube") is None

    @patch("bot.scene_metadata.urlopen")
    def test_fetch_oembed_metadata_urlerror(self, mock_urlopen):
        svc = SceneMetadataService()
        mock_urlopen.side_effect = URLError("error")
        assert svc.fetch_oembed_metadata("http://youtube.com/watch", "youtube") is None

    @patch("bot.scene_metadata.urlopen")
    def test_fetch_oembed_metadata_json_error(self, mock_urlopen):
        svc = SceneMetadataService()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b"not json"
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        assert svc.fetch_oembed_metadata("http://youtube.com/watch", "youtube") is None

    @patch("bot.scene_metadata.urlopen")
    def test_fetch_oembed_metadata_not_dict(self, mock_urlopen):
        svc = SceneMetadataService()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'["list"]'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        assert svc.fetch_oembed_metadata("http://youtube.com/watch", "youtube") is None

    def test_get_cached_metadata_expired(self):
        svc = SceneMetadataService()
        svc.metadata_cache["url"] = (time.monotonic() - 100, {"title": "test"})
        assert svc.get_cached_metadata("url") is None
        assert "url" not in svc.metadata_cache

    def test_metadata_to_safety_text(self):
        svc = SceneMetadataService()
        assert svc.metadata_to_safety_text(None) == ""
        assert svc.metadata_to_safety_text({"title": "t", "author_name": "a"}) == "t a"

    def test_is_safe_scene_metadata(self):
        svc = SceneMetadataService()
        assert svc.is_safe_scene_metadata(None, "", "", require_metadata=True) is False
        assert svc.is_safe_scene_metadata({"title": "safe"}, "", "", require_metadata=True) is True
        assert svc.is_safe_scene_metadata({"title": "porn"}, "", "", require_metadata=True) is False

    def test_build_sanitized_scene_description(self):
        svc = SceneMetadataService()

        def norm(x, **kw):
            return x

        assert (
            svc.build_sanitized_scene_description(
                "youtube", "author", None, normalize_text_for_scene=norm
            )
            == "Video do YouTube compartilhado por author"
        )
        assert (
            svc.build_sanitized_scene_description(
                "youtube", "author", {"title": "title"}, normalize_text_for_scene=norm
            )
            == 'Video do YouTube: "title" (compartilhado por author)'
        )

        assert (
            svc.build_sanitized_scene_description(
                "x", "author", None, normalize_text_for_scene=norm
            )
            == "Post do X compartilhado por author"
        )
        assert (
            svc.build_sanitized_scene_description(
                "x", "author", {"author_name": "poster"}, normalize_text_for_scene=norm
            )
            == "Post do X de poster (compartilhado por author)"
        )

        assert (
            svc.build_sanitized_scene_description(
                "other", "author", None, normalize_text_for_scene=norm
            )
            == "Contexto compartilhado por author"
        )
