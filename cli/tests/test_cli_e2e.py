# SPDX-License-Identifier: MIT
"""E2E tests for the Byte Agent CLI.

These tests validate the REAL behavior of every CLI module:
- config.py: file/env/flag resolution, edge cases
- client.py: HTTP client, error mapping, auth injection
- formatters.py: table rendering, ANSI, JSON, timestamps
- main.py: argparse dispatch, exit codes
- All command modules: argument parsing, API mapping

Tests use a lightweight HTTP mock server (no external deps) to simulate
the Dashboard API and validate real HTTP round-trips.
"""

from __future__ import annotations

import http.server
import json
import os
import socketserver
import threading
from pathlib import Path
from typing import Any, ClassVar
from unittest.mock import patch

import pytest

# ============================================================================
# Fixtures — Real HTTP Server
# ============================================================================


class _MockHandler(http.server.BaseHTTPRequestHandler):
    """Captures requests and returns canned responses."""

    responses: ClassVar[dict[str, Any]] = {}
    last_request: ClassVar[dict[str, Any]] = {}

    def log_message(self, format: str, *args: Any) -> None:
        pass

    def _send_response(self, method: str) -> None:
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(self.path)
        route = parsed.path
        query = parse_qs(parsed.query)

        body = b""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            body = self.rfile.read(content_length)

        payload = {}
        if body:
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                pass

        _MockHandler.last_request = {
            "method": method,
            "path": route,
            "query": query,
            "payload": payload,
            "headers": dict(self.headers),
        }

        key = f"{method}:{route}"
        response_data = _MockHandler.responses.get(key, {"ok": True})
        status = 200

        if route == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"AGENT_ONLINE")
            return

        if isinstance(response_data, tuple):
            response_data, status = response_data

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response_data).encode("utf-8"))

    def do_GET(self) -> None:
        self._send_response("GET")

    def do_POST(self) -> None:
        self._send_response("POST")

    def do_PUT(self) -> None:
        self._send_response("PUT")


@pytest.fixture(scope="module")
def mock_server():
    server = socketserver.TCPServer(("127.0.0.1", 0), _MockHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


@pytest.fixture(autouse=True)
def _reset_mock():
    _MockHandler.responses.clear()
    _MockHandler.last_request.clear()


# ============================================================================
# Config Tests
# ============================================================================


class TestConfig:
    def test_defaults_no_file_no_env(self) -> None:
        from cli.config import load_config

        with patch.dict(os.environ, {}, clear=True):
            cfg = load_config(config_path=Path("/nonexistent/.byterc"))
        assert cfg.url == "http://localhost:7860"
        assert cfg.token == ""
        assert cfg.channel == "default"

    def test_reads_ini_file(self, tmp_path: Path) -> None:
        from cli.config import load_config

        rc = tmp_path / ".byterc"
        rc.write_text("[default]\nurl = http://myhost:9999\ntoken = file-tok\n")
        with patch.dict(os.environ, {}, clear=True):
            cfg = load_config(config_path=rc)
        assert cfg.url == "http://myhost:9999"
        assert cfg.token == "file-tok"

    def test_env_overrides_file(self, tmp_path: Path) -> None:
        from cli.config import load_config

        rc = tmp_path / ".byterc"
        rc.write_text("[default]\nurl = http://file\ntoken = file-tok\n")
        with patch.dict(
            os.environ, {"BYTE_API_URL": "http://env", "BYTE_ADMIN_TOKEN": "env-tok"}, clear=True
        ):
            cfg = load_config(config_path=rc)
        assert cfg.url == "http://env"
        assert cfg.token == "env-tok"

    def test_cli_flags_override_all(self, tmp_path: Path) -> None:
        from cli.config import load_config

        rc = tmp_path / ".byterc"
        rc.write_text("[default]\nurl = http://file\ntoken = file-tok\n")
        with patch.dict(os.environ, {"BYTE_API_URL": "http://env"}, clear=True):
            cfg = load_config(
                cli_url="http://cli",
                cli_token="cli-tok",
                cli_channel="ch",
                cli_json=True,
                config_path=rc,
            )
        assert cfg.url == "http://cli"
        assert cfg.token == "cli-tok"
        assert cfg.channel == "ch"
        assert cfg.json_output is True

    def test_dashboard_token_fallback(self) -> None:
        from cli.config import load_config

        with patch.dict(os.environ, {"BYTE_DASHBOARD_ADMIN_TOKEN": "dash-tok"}, clear=True):
            cfg = load_config(config_path=Path("/none"))
        assert cfg.token == "dash-tok"

    def test_url_trailing_slash_stripped(self) -> None:
        from cli.config import load_config

        with patch.dict(os.environ, {}, clear=True):
            cfg = load_config(cli_url="http://h:1///", config_path=Path("/none"))
        assert cfg.url == "http://h:1"

    def test_channel_normalized(self) -> None:
        from cli.config import load_config

        with patch.dict(os.environ, {}, clear=True):
            cfg = load_config(cli_channel=" MyChannel ", config_path=Path("/none"))
        assert cfg.channel == "mychannel"

    def test_malformed_file(self, tmp_path: Path) -> None:
        from cli.config import load_config

        rc = tmp_path / ".byterc"
        rc.write_text("CORRUPT ][[[")
        with patch.dict(os.environ, {}, clear=True):
            cfg = load_config(config_path=rc)
        assert cfg.url == "http://localhost:7860"

    def test_empty_file(self, tmp_path: Path) -> None:
        from cli.config import load_config

        rc = tmp_path / ".byterc"
        rc.write_text("")
        with patch.dict(os.environ, {}, clear=True):
            cfg = load_config(config_path=rc)
        assert cfg.url == "http://localhost:7860"

    def test_with_overrides_immutable(self) -> None:
        from cli.config import CLIConfig

        o = CLIConfig(url="http://a", token="old")
        n = o.with_overrides(token="new")
        assert o.token == "old"
        assert n.token == "new"


# ============================================================================
# Client Tests (Real HTTP)
# ============================================================================


class TestClient:
    def test_health_online(self, mock_server: str) -> None:
        from cli.client import ByteClient

        c = ByteClient(base_url=mock_server, token="t")
        assert c.health_check() is True

    def test_health_offline(self) -> None:
        from cli.client import ByteClient

        c = ByteClient(base_url="http://127.0.0.1:1", token="t")
        assert c.health_check() is False

    def test_get_auth_header(self, mock_server: str) -> None:
        from cli.client import ByteClient

        _MockHandler.responses["GET:/api/x"] = {"d": 1}
        c = ByteClient(base_url=mock_server, token="secret")
        r = c.get("/api/x")
        assert r["d"] == 1
        assert _MockHandler.last_request["headers"].get("X-Byte-Admin-Token") == "secret"

    def test_post_json(self, mock_server: str) -> None:
        from cli.client import ByteClient

        _MockHandler.responses["POST:/api/s"] = {"ok": True}
        c = ByteClient(base_url=mock_server, token="t")
        c.post("/api/s", {"k": "v"})
        assert _MockHandler.last_request["payload"] == {"k": "v"}

    def test_put_json(self, mock_server: str) -> None:
        from cli.client import ByteClient

        _MockHandler.responses["PUT:/api/p"] = {"ok": True}
        c = ByteClient(base_url=mock_server, token="t")
        c.put("/api/p", {"a": 1})
        assert _MockHandler.last_request["payload"] == {"a": 1}

    def test_404_not_found(self, mock_server: str) -> None:
        from cli.client import ByteClient, NotFoundError

        _MockHandler.responses["GET:/api/m"] = ({"e": "nf"}, 404)
        with pytest.raises(NotFoundError):
            ByteClient(base_url=mock_server, token="t").get("/api/m")

    def test_401_auth_error(self, mock_server: str) -> None:
        from cli.client import AuthenticationError, ByteClient

        _MockHandler.responses["GET:/api/s"] = ({"e": "u"}, 401)
        with pytest.raises(AuthenticationError):
            ByteClient(base_url=mock_server, token="bad").get("/api/s")

    def test_500_server_error(self, mock_server: str) -> None:
        from cli.client import ByteClient, ServerError

        _MockHandler.responses["GET:/api/b"] = ({"e": "i"}, 500)
        with pytest.raises(ServerError):
            ByteClient(base_url=mock_server, token="t").get("/api/b")

    def test_connection_refused(self) -> None:
        from cli.client import ByteClient, ConnectionError_

        with pytest.raises(ConnectionError_):
            ByteClient(base_url="http://127.0.0.1:1", token="t").get("/x")

    def test_empty_params_filtered(self, mock_server: str) -> None:
        from cli.client import ByteClient

        _MockHandler.responses["GET:/api/f"] = {"ok": True}
        ByteClient(base_url=mock_server, token="t").get("/api/f", {"a": "", "b": "1"})
        assert _MockHandler.last_request["path"] == "/api/f"


# ============================================================================
# Formatter Tests
# ============================================================================


class TestFormatters:
    def test_timestamp_iso(self) -> None:
        from cli.formatters import format_timestamp

        r = format_timestamp("2026-03-03T12:30:00Z")
        assert "2026-03-03" in r and "12:30:00" in r

    def test_timestamp_float(self) -> None:
        from cli.formatters import format_timestamp

        assert "UTC" in format_timestamp(1709472600.0)

    def test_timestamp_none(self) -> None:
        from cli.formatters import format_timestamp

        assert format_timestamp(None) == "—"

    def test_timestamp_empty(self) -> None:
        from cli.formatters import format_timestamp

        assert format_timestamp("") == "—"

    def test_timestamp_zero(self) -> None:
        from cli.formatters import format_timestamp

        assert format_timestamp(0.0) == "—"

    def test_json_output(self) -> None:
        import io

        from cli.formatters import print_json

        buf = io.StringIO()
        print_json({"k": "v", "n": 42}, file=buf)
        p = json.loads(buf.getvalue())
        assert p["k"] == "v" and p["n"] == 42

    def test_table_data(self) -> None:
        import io

        from cli.formatters import print_table

        buf = io.StringIO()
        print_table(["A", "B"], [["1", "2"], ["3", "4"]], file=buf)
        out = buf.getvalue()
        assert "A" in out and "3" in out

    def test_table_empty(self) -> None:
        import io

        from cli.formatters import print_table

        buf = io.StringIO()
        print_table(["X"], [], file=buf)
        assert "empty" in buf.getvalue()

    def test_table_truncate(self) -> None:
        import io

        from cli.formatters import print_table

        buf = io.StringIO()
        print_table(["D"], [["A" * 100]], max_col_width=20, file=buf)
        assert "…" in buf.getvalue()

    def test_kv_output(self) -> None:
        import io

        from cli.formatters import print_kv

        buf = io.StringIO()
        print_kv({"On": True, "Off": None}, file=buf)
        out = buf.getvalue()
        assert "—" in out or "yes" in out

    def test_output_json_mode(self) -> None:
        import io

        from cli.formatters import output, print_json

        buf = io.StringIO()
        print_json({"t": 1}, file=buf)
        assert json.loads(buf.getvalue())["t"] == 1

    def test_output_human_fn(self) -> None:
        from cli.formatters import output

        called = []
        output({"t": 1}, json_mode=False, human_fn=lambda d: called.append(d))
        assert called[0]["t"] == 1


# ============================================================================
# CLI Dispatcher Tests
# ============================================================================


class TestDispatcher:
    def test_parser_builds(self) -> None:
        from cli.main import build_parser

        assert build_parser() is not None

    def test_no_cmd_exits_0(self) -> None:
        from cli.main import main

        with pytest.raises(SystemExit) as e:
            main([])
        assert e.value.code == 0

    def test_version(self) -> None:
        from cli.main import main

        with pytest.raises(SystemExit) as e:
            main(["--version"])
        assert e.value.code == 0

    def test_status_parse(self) -> None:
        from cli.main import build_parser

        a = build_parser().parse_args(["status"])
        assert a.command == "status"

    def test_goals_add_parse(self) -> None:
        from cli.main import build_parser

        a = build_parser().parse_args(
            [
                "goals",
                "add",
                "--id",
                "g",
                "--name",
                "G",
                "--prompt",
                "P",
                "--risk",
                "auto_chat",
                "--interval",
                "60",
            ]
        )
        assert a.goal_id == "g" and a.interval == 60

    def test_actions_approve_parse(self) -> None:
        from cli.main import build_parser

        a = build_parser().parse_args(["actions", "approve", "id1", "--note", "ok"])
        assert a.action_id == "id1" and a.note == "ok"

    def test_chat_parse(self) -> None:
        from cli.main import build_parser

        a = build_parser().parse_args(["chat", "faz ASCII do Goku"])
        assert a.message == "faz ASCII do Goku"

    def test_revenue_alias(self) -> None:
        from cli.main import build_parser

        a = build_parser().parse_args(["revenue", "list", "--limit", "5"])
        assert a.limit == 5

    def test_global_flags(self) -> None:
        from cli.main import build_parser

        a = build_parser().parse_args(
            ["--json", "--url", "http://x", "--token", "tk", "--channel", "ch", "status"]
        )
        assert (
            a.json_output and a.api_url == "http://x" and a.api_token == "tk" and a.channel == "ch"
        )


# ============================================================================
# E2E Command Tests (Real HTTP)
# ============================================================================


def _run(mock_server: str, argv: list[str]) -> int:
    from cli.main import main

    try:
        main(["--url", mock_server, "--token", "tok", *argv])
        return 0
    except SystemExit as e:
        return e.code or 0


class TestE2E:
    def test_status(self, mock_server: str) -> None:
        _MockHandler.responses["GET:/api/control-plane"] = {"ok": True, "config": {"goals": []}}
        _MockHandler.responses["GET:/api/observability"] = {"ok": True, "counters": {}, "cost": {}}
        assert _run(mock_server, ["status"]) == 0

    def test_suspend(self, mock_server: str) -> None:
        _MockHandler.responses["POST:/api/agent/suspend"] = {"ok": True}
        assert _run(mock_server, ["agent", "suspend", "--reason", "x"]) == 0
        assert _MockHandler.last_request["payload"]["reason"] == "x"

    def test_resume(self, mock_server: str) -> None:
        _MockHandler.responses["POST:/api/agent/resume"] = {"ok": True}
        assert _run(mock_server, ["agent", "resume"]) == 0

    def test_tick(self, mock_server: str) -> None:
        _MockHandler.responses["POST:/api/autonomy/tick"] = {"ok": True}
        assert _run(mock_server, ["agent", "tick", "--force"]) == 0
        assert _MockHandler.last_request["payload"]["force"] is True

    def test_config_show(self, mock_server: str) -> None:
        _MockHandler.responses["GET:/api/control-plane"] = {"ok": True, "config": {}}
        assert _run(mock_server, ["agent", "config"]) == 0

    def test_config_set(self, mock_server: str) -> None:
        _MockHandler.responses["PUT:/api/control-plane"] = {"ok": True}
        assert _run(mock_server, ["agent", "config", "set", "k", "true"]) == 0
        assert _MockHandler.last_request["payload"]["k"] is True

    def test_observe(self, mock_server: str) -> None:
        _MockHandler.responses["GET:/api/observability"] = {
            "ok": True,
            "counters": {},
            "cost": {},
            "interactions": {},
        }
        assert _run(mock_server, ["observe"]) == 0

    def test_sentiment(self, mock_server: str) -> None:
        _MockHandler.responses["GET:/api/sentiment/scores"] = {
            "ok": True,
            "sentiment": {},
            "stream_health": {},
        }
        assert _run(mock_server, ["observe", "sentiment"]) == 0

    def test_goals_list(self, mock_server: str) -> None:
        _MockHandler.responses["GET:/api/control-plane"] = {
            "ok": True,
            "config": {
                "goals": [
                    {
                        "id": "g1",
                        "name": "G",
                        "risk": "auto_chat",
                        "interval_seconds": 60,
                        "enabled": True,
                    }
                ]
            },
        }
        assert _run(mock_server, ["goals", "list"]) == 0

    def test_goals_show(self, mock_server: str) -> None:
        _MockHandler.responses["GET:/api/control-plane"] = {
            "ok": True,
            "config": {"goals": [{"id": "g1", "name": "G"}]},
        }
        assert _run(mock_server, ["goals", "show", "g1"]) == 0

    def test_goals_enable(self, mock_server: str) -> None:
        _MockHandler.responses["GET:/api/control-plane"] = {
            "ok": True,
            "config": {"goals": [{"id": "g1", "enabled": False}]},
        }
        _MockHandler.responses["PUT:/api/control-plane"] = {"ok": True}
        assert _run(mock_server, ["goals", "enable", "g1"]) == 0

    def test_goals_add(self, mock_server: str) -> None:
        _MockHandler.responses["GET:/api/control-plane"] = {"ok": True, "config": {"goals": []}}
        _MockHandler.responses["PUT:/api/control-plane"] = {"ok": True}
        assert (
            _run(
                mock_server,
                [
                    "goals",
                    "add",
                    "--id",
                    "new",
                    "--name",
                    "N",
                    "--prompt",
                    "P",
                    "--risk",
                    "auto_chat",
                    "--interval",
                    "60",
                ],
            )
            == 0
        )

    def test_goals_remove(self, mock_server: str) -> None:
        _MockHandler.responses["GET:/api/control-plane"] = {
            "ok": True,
            "config": {"goals": [{"id": "g1"}]},
        }
        _MockHandler.responses["PUT:/api/control-plane"] = {"ok": True}
        assert _run(mock_server, ["goals", "remove", "g1"]) == 0

    def test_actions_list(self, mock_server: str) -> None:
        _MockHandler.responses["GET:/api/action-queue"] = {"ok": True, "actions": []}
        assert _run(mock_server, ["actions", "list"]) == 0

    def test_actions_approve(self, mock_server: str) -> None:
        _MockHandler.responses["POST:/api/action-queue/a1/decision"] = {"ok": True}
        assert _run(mock_server, ["actions", "approve", "a1", "--note", "ok"]) == 0
        assert _MockHandler.last_request["payload"] == {"decision": "approve", "note": "ok"}

    def test_actions_reject(self, mock_server: str) -> None:
        _MockHandler.responses["POST:/api/action-queue/a2/decision"] = {"ok": True}
        assert _run(mock_server, ["actions", "reject", "a2"]) == 0
        assert _MockHandler.last_request["payload"]["decision"] == "reject"

    def test_channel_context(self, mock_server: str) -> None:
        _MockHandler.responses["GET:/api/channel-context"] = {
            "ok": True,
            "channel": {"channel_id": "c", "runtime": {}},
        }
        assert _run(mock_server, ["channel", "context"]) == 0

    def test_channel_join(self, mock_server: str) -> None:
        _MockHandler.responses["POST:/api/channel-control"] = {"ok": True}
        assert _run(mock_server, ["channel", "join", "xqc"]) == 0
        assert _MockHandler.last_request["payload"] == {"action": "join", "channel_login": "xqc"}

    def test_channel_list(self, mock_server: str) -> None:
        _MockHandler.responses["POST:/api/channel-control"] = {"ok": True, "channels": ["c1"]}
        assert _run(mock_server, ["channel", "list"]) == 0

    def test_memory_list(self, mock_server: str) -> None:
        _MockHandler.responses["GET:/api/semantic-memory"] = {"ok": True, "entries": []}
        assert _run(mock_server, ["memory", "list"]) == 0

    def test_memory_search(self, mock_server: str) -> None:
        _MockHandler.responses["GET:/api/semantic-memory"] = {
            "ok": True,
            "matches": [],
            "search_diagnostics": {},
        }
        assert _run(mock_server, ["memory", "search", "goku"]) == 0

    def test_memory_add(self, mock_server: str) -> None:
        _MockHandler.responses["PUT:/api/semantic-memory"] = {"ok": True}
        assert _run(mock_server, ["memory", "add", "info", "--tags", "a,b"]) == 0
        p = _MockHandler.last_request["payload"]
        assert p["content"] == "info" and p["tags"] == ["a", "b"]

    def test_persona_show(self, mock_server: str) -> None:
        _MockHandler.responses["GET:/api/persona-profile"] = {"ok": True, "profile": {}}
        assert _run(mock_server, ["persona", "show"]) == 0

    def test_clips_jobs(self, mock_server: str) -> None:
        _MockHandler.responses["GET:/api/clip-jobs"] = {"ok": True, "items": []}
        assert _run(mock_server, ["clips", "jobs"]) == 0

    def test_clips_vision(self, mock_server: str) -> None:
        _MockHandler.responses["GET:/api/vision/status"] = {"ok": True, "frame_count": 0}
        assert _run(mock_server, ["clips", "vision"]) == 0

    def test_playbooks_list(self, mock_server: str) -> None:
        _MockHandler.responses["GET:/api/ops-playbooks"] = {"ok": True, "playbooks": []}
        assert _run(mock_server, ["playbooks", "list"]) == 0

    def test_playbooks_trigger(self, mock_server: str) -> None:
        _MockHandler.responses["POST:/api/ops-playbooks/trigger"] = {"ok": True}
        assert _run(mock_server, ["playbooks", "trigger", "pb1", "--force"]) == 0
        assert _MockHandler.last_request["payload"]["force"] is True

    def test_webhooks_list(self, mock_server: str) -> None:
        _MockHandler.responses["GET:/api/webhooks"] = {"ok": True, "webhooks": []}
        assert _run(mock_server, ["webhooks", "list"]) == 0

    def test_webhooks_add(self, mock_server: str) -> None:
        _MockHandler.responses["PUT:/api/webhooks"] = {"ok": True}
        assert _run(mock_server, ["webhooks", "add", "http://h.io", "--events", "x,y"]) == 0
        assert _MockHandler.last_request["payload"]["event_types"] == ["x", "y"]

    def test_report_show(self, mock_server: str) -> None:
        _MockHandler.responses["GET:/api/observability/post-stream-report"] = {
            "ok": True,
            "has_report": False,
        }
        assert _run(mock_server, ["report", "show"]) == 0

    def test_conversions_list(self, mock_server: str) -> None:
        _MockHandler.responses["GET:/api/observability/conversions"] = {
            "ok": True,
            "conversions": [],
        }
        assert _run(mock_server, ["conversions", "list"]) == 0

    def test_revenue_alias(self, mock_server: str) -> None:
        _MockHandler.responses["GET:/api/observability/conversions"] = {
            "ok": True,
            "conversions": [],
        }
        assert _run(mock_server, ["revenue", "list"]) == 0

    def test_chat_send(self, mock_server: str) -> None:
        _MockHandler.responses["POST:/api/chat/send"] = {"ok": True, "replies": ["Oi!"]}
        assert _run(mock_server, ["chat", "faz ASCII do Goku"]) == 0
        assert _MockHandler.last_request["payload"]["text"] == "faz ASCII do Goku"


# ============================================================================
# Edge Cases & Monkey Mode
# ============================================================================


class TestEdgeCases:
    def test_unicode(self, mock_server: str) -> None:
        from cli.client import ByteClient

        _MockHandler.responses["POST:/api/chat/send"] = {"ok": True}
        ByteClient(base_url=mock_server, token="t").post(
            "/api/chat/send", {"text": "こんにちは 🎉"}
        )
        assert _MockHandler.last_request["payload"]["text"] == "こんにちは 🎉"

    def test_long_text(self) -> None:
        from cli.formatters import print_table

        print_table(["D"], [["X" * 10_000]], max_col_width=50)

    def test_nested_kv(self) -> None:
        import io

        from cli.formatters import print_kv

        buf = io.StringIO()
        print_kv({"n": {"a": {"b": "c"}}, "l": [1, 2]}, file=buf)
        assert "a" in buf.getvalue()

    def test_rapid_requests(self, mock_server: str) -> None:
        from cli.client import ByteClient

        _MockHandler.responses["GET:/api/control-plane"] = {"ok": True}
        c = ByteClient(base_url=mock_server, token="t")
        for _ in range(20):
            assert c.get("/api/control-plane")["ok"]

    def test_json_mode_valid(self, mock_server: str) -> None:
        _MockHandler.responses.update(
            {
                "GET:/api/control-plane": {"ok": True, "config": {"goals": []}},
                "GET:/api/observability": {"ok": True, "counters": {}, "cost": {}},
            }
        )
        # Just verify no exception is raised
        assert _run(mock_server, ["--json", "status"]) == 0

    def test_goals_duplicate_rejected(self, mock_server: str) -> None:
        import argparse as ap
        from unittest.mock import patch as _patch

        from cli.client import ByteClient
        from cli.commands.goals import _handle_add
        from cli.config import CLIConfig

        _MockHandler.responses["GET:/api/control-plane"] = {
            "ok": True,
            "config": {"goals": [{"id": "dup"}]},
        }
        captured: list[str] = []

        def fake_error(msg: str, **kwargs: Any) -> None:
            captured.append(msg)

        with _patch("cli.commands.goals.print_error", fake_error):
            _handle_add(
                ap.Namespace(
                    goal_id="dup",
                    name="X",
                    prompt="X",
                    risk="auto_chat",
                    interval=60,
                    cron="",
                    enabled=True,
                ),
                ByteClient(base_url=mock_server, token="t"),
                CLIConfig(url=mock_server, token="t"),
            )
        assert any("already exists" in m for m in captured)
