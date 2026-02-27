from __future__ import annotations

from typing import Any

import pytest

from bot.ops_playbooks import (
    PLAYBOOK_OUTCOME_ABORTED,
    PLAYBOOK_OUTCOME_COMPLETED,
    PLAYBOOK_STATE_AWAITING_DECISION,
    PLAYBOOK_STATE_COOLDOWN,
    PLAYBOOK_STATE_IDLE,
    OpsPlaybookRuntime,
)


def _playbook_by_id(snapshot: dict[str, Any], playbook_id: str) -> dict[str, Any]:
    playbooks = snapshot.get("playbooks", [])
    return next(item for item in playbooks if item.get("id") == playbook_id)


def _build_action_store() -> tuple[dict[str, dict[str, Any]], Any, Any, Any]:
    store: dict[str, dict[str, Any]] = {}
    counter = 0

    def enqueue_action(**kwargs: Any) -> dict[str, Any]:
        nonlocal counter
        counter += 1
        action_id = f"act_{counter}"
        item = {
            "id": action_id,
            "status": "pending",
            "kind": kwargs.get("kind", ""),
            "title": kwargs.get("title", ""),
            "payload": kwargs.get("payload", {}),
            "created_by": kwargs.get("created_by", ""),
        }
        store[action_id] = item
        return dict(item)

    def get_action(action_id: str, *, timestamp: float | None = None) -> dict[str, Any] | None:
        _ = timestamp
        item = store.get(action_id)
        return dict(item) if item else None

    def set_status(action_id: str, status: str) -> None:
        store[action_id]["status"] = status

    return store, enqueue_action, get_action, set_status


def test_ops_playbook_auto_run_completes_after_all_steps_are_approved():
    runtime = OpsPlaybookRuntime()
    _store, enqueue_action, get_action, set_status = _build_action_store()

    snapshot = runtime.evaluate(
        channel_id="canal_a",
        metrics={
            "queue_pending": 9,
            "queue_ignored_rate_60m": 0,
            "queue_decisions_total_60m": 0,
        },
        trigger_reason="heartbeat",
        get_action=get_action,
        enqueue_action=enqueue_action,
        timestamp=100.0,
    )
    playbook = _playbook_by_id(snapshot, "queue_backlog_recovery")
    assert playbook["state"] == PLAYBOOK_STATE_AWAITING_DECISION
    assert playbook["current_step_number"] == 1

    set_status(playbook["waiting_action_id"], "approved")
    snapshot = runtime.reconcile(
        channel_id="canal_a",
        metrics={"queue_pending": 7},
        get_action=get_action,
        enqueue_action=enqueue_action,
        timestamp=101.0,
    )
    playbook = _playbook_by_id(snapshot, "queue_backlog_recovery")
    assert playbook["state"] == PLAYBOOK_STATE_AWAITING_DECISION
    assert playbook["current_step_number"] == 2

    set_status(playbook["waiting_action_id"], "approved")
    snapshot = runtime.reconcile(
        channel_id="canal_a",
        metrics={"queue_pending": 4},
        get_action=get_action,
        enqueue_action=enqueue_action,
        timestamp=102.0,
    )
    playbook = _playbook_by_id(snapshot, "queue_backlog_recovery")
    assert playbook["state"] == PLAYBOOK_STATE_COOLDOWN
    assert playbook["last_outcome"] == PLAYBOOK_OUTCOME_COMPLETED
    assert snapshot["summary"]["completed"] >= 1


def test_ops_playbook_rejected_step_aborts_and_requires_force_during_cooldown():
    runtime = OpsPlaybookRuntime()
    _store, enqueue_action, get_action, set_status = _build_action_store()

    snapshot = runtime.trigger(
        playbook_id="ignored_rate_guard",
        channel_id="canal_a",
        reason="manual_dashboard",
        metrics={
            "queue_pending": 0,
            "queue_ignored_rate_60m": 88,
            "queue_decisions_total_60m": 12,
        },
        get_action=get_action,
        enqueue_action=enqueue_action,
        force=False,
        timestamp=200.0,
    )
    playbook = _playbook_by_id(snapshot, "ignored_rate_guard")
    assert playbook["state"] == PLAYBOOK_STATE_AWAITING_DECISION

    set_status(playbook["waiting_action_id"], "rejected")
    snapshot = runtime.reconcile(
        channel_id="canal_a",
        metrics={
            "queue_pending": 0,
            "queue_ignored_rate_60m": 80,
            "queue_decisions_total_60m": 14,
        },
        get_action=get_action,
        enqueue_action=enqueue_action,
        timestamp=201.0,
    )
    playbook = _playbook_by_id(snapshot, "ignored_rate_guard")
    assert playbook["state"] == PLAYBOOK_STATE_COOLDOWN
    assert playbook["last_outcome"] == PLAYBOOK_OUTCOME_ABORTED
    assert playbook["last_outcome_reason"] == "step_rejected"

    with pytest.raises(RuntimeError, match="playbook_cooldown"):
        runtime.trigger(
            playbook_id="ignored_rate_guard",
            channel_id="canal_a",
            reason="manual_dashboard_retry",
            metrics={"queue_decisions_total_60m": 10},
            get_action=get_action,
            enqueue_action=enqueue_action,
            force=False,
            timestamp=202.0,
        )

    snapshot = runtime.trigger(
        playbook_id="ignored_rate_guard",
        channel_id="canal_a",
        reason="manual_dashboard_retry",
        metrics={"queue_decisions_total_60m": 10},
        get_action=get_action,
        enqueue_action=enqueue_action,
        force=True,
        timestamp=203.0,
    )
    playbook = _playbook_by_id(snapshot, "ignored_rate_guard")
    assert playbook["state"] == PLAYBOOK_STATE_AWAITING_DECISION


def test_ops_playbook_ignored_rate_guard_requires_minimum_decision_sample():
    runtime = OpsPlaybookRuntime()
    _store, enqueue_action, get_action, _set_status = _build_action_store()

    snapshot = runtime.evaluate(
        channel_id="canal_a",
        metrics={
            "queue_pending": 0,
            "queue_ignored_rate_60m": 90,
            "queue_decisions_total_60m": 2,
        },
        trigger_reason="heartbeat",
        get_action=get_action,
        enqueue_action=enqueue_action,
        timestamp=300.0,
    )
    playbook = _playbook_by_id(snapshot, "ignored_rate_guard")
    assert playbook["state"] == PLAYBOOK_STATE_IDLE
    assert playbook["last_outcome"] == "never_run"
