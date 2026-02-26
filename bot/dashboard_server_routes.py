from typing import Any

from flask import Blueprint, jsonify, request

from bot import byte_semantics
from bot.control_plane import control_plane
from bot.logic import BOT_BRAND, context_manager
from bot.observability import observability
from bot.runtime_config import BYTE_VERSION, DASHBOARD_DIR, TWITCH_CHAT_MODE

dashboard_routes = Blueprint("dashboard", __name__, static_folder=str(DASHBOARD_DIR))


@dashboard_routes.route("/health")
def health() -> Any:
    return jsonify({"status": "ok", "version": BYTE_VERSION})


def build_observability_payload() -> dict[str, Any]:
    snapshot = observability.snapshot(
        bot_brand=BOT_BRAND,
        bot_version=BYTE_VERSION,
        bot_mode=TWITCH_CHAT_MODE,
        stream_context=context_manager.get(),
    )
    capabilities = control_plane.build_capabilities(bot_mode=TWITCH_CHAT_MODE)
    return {
        "snapshot": snapshot,
        "capabilities": capabilities,
    }


@dashboard_routes.route("/api/observability")
def api_observability() -> Any:
    return jsonify(build_observability_payload())


@dashboard_routes.route("/api/config", methods=["POST"])
def api_config_update() -> Any:
    payload = request.json or {}
    updated = control_plane.update_config(payload)
    return jsonify(updated)


@dashboard_routes.route("/api/actions")
def api_actions_list() -> Any:
    status = request.args.get("status")
    actions = control_plane.list_actions(status=status)
    return jsonify(actions)


@dashboard_routes.route("/api/actions/decide", methods=["POST"])
def api_action_decide() -> Any:
    payload = request.json or {}
    action_id = payload.get("action_id")
    decision = payload.get("decision")
    note = payload.get("note", "")

    if not action_id or not decision:
        return jsonify({"error": "action_id e decision obrigatorios"}), 400

    result = control_plane.decide_action(
        action_id=action_id,
        decision=decision,
        note=note,
        decided_by="dashboard",
    )
    return jsonify(result)
