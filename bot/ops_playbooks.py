import copy
import threading
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any

from bot.control_plane_constants import RISK_SUGGEST_STREAMER, clip_text, utc_iso

PLAYBOOK_STATE_IDLE = "idle"
PLAYBOOK_STATE_AWAITING_DECISION = "awaiting_decision"
PLAYBOOK_STATE_COOLDOWN = "cooldown"

PLAYBOOK_OUTCOME_NEVER_RUN = "never_run"
PLAYBOOK_OUTCOME_COMPLETED = "completed"
PLAYBOOK_OUTCOME_ABORTED = "aborted"


@dataclass(frozen=True)
class OpsPlaybookStep:
    title: str
    body_template: str


@dataclass(frozen=True)
class OpsPlaybookDefinition:
    id: str
    name: str
    description: str
    trigger_metric: str
    trigger_threshold: float
    trigger_comparison: str = "gte"
    trigger_min_sample_metric: str = ""
    trigger_min_sample_value: float = 0.0
    cooldown_seconds: int = 900
    risk: str = RISK_SUGGEST_STREAMER
    steps: tuple[OpsPlaybookStep, ...] = ()


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _metric_matches(value: float, threshold: float, comparison: str) -> bool:
    safe_comparison = str(comparison or "gte").strip().lower()
    if safe_comparison == "lte":
        return value <= threshold
    if safe_comparison == "eq":
        return abs(value - threshold) <= 1e-6
    return value >= threshold


def default_ops_playbooks() -> tuple[OpsPlaybookDefinition, ...]:
    return (
        OpsPlaybookDefinition(
            id="queue_backlog_recovery",
            name="Queue Backlog Recovery",
            description=(
                "Reduz backlog pendente da action queue com passos auditaveis de triagem."
            ),
            trigger_metric="queue_pending",
            trigger_threshold=6.0,
            trigger_comparison="gte",
            cooldown_seconds=900,
            risk=RISK_SUGGEST_STREAMER,
            steps=(
                OpsPlaybookStep(
                    title="Triagem de pendencias",
                    body_template=(
                        "Backlog em {queue_pending} itens. Priorize pendencias por impacto "
                        "imediato na live e descarte ruido operacional."
                    ),
                ),
                OpsPlaybookStep(
                    title="Fechamento de backlog",
                    body_template=(
                        "Aplique aprovacao conservadora e objetivo de reduzir a fila para "
                        "ate {queue_target_pending} pendencias antes do proximo ciclo."
                    ),
                ),
            ),
        ),
        OpsPlaybookDefinition(
            id="ignored_rate_guard",
            name="Ignored Rate Guard",
            description=(
                "Corrige excesso de ignorados com politica operacional de decisao explicita."
            ),
            trigger_metric="queue_ignored_rate_60m",
            trigger_threshold=35.0,
            trigger_comparison="gte",
            trigger_min_sample_metric="queue_decisions_total_60m",
            trigger_min_sample_value=4.0,
            cooldown_seconds=900,
            risk=RISK_SUGGEST_STREAMER,
            steps=(
                OpsPlaybookStep(
                    title="Diagnostico de ignorados",
                    body_template=(
                        "Ignored rate em {queue_ignored_rate_60m}% com "
                        "{queue_decisions_total_60m} decisoes na janela de 60m. "
                        "Revise causas de timeout e ambiguidade."
                    ),
                ),
                OpsPlaybookStep(
                    title="Ajuste de criterio",
                    body_template=(
                        "Reforce decisao explicita para itens de maior risco e reduza janela "
                        "de pendencia para evitar novos ignored por timeout."
                    ),
                ),
            ),
        ),
    )


class OpsPlaybookRuntime:
    def __init__(self, definitions: tuple[OpsPlaybookDefinition, ...] | None = None) -> None:
        safe_definitions = definitions or default_ops_playbooks()
        self._lock = threading.Lock()
        self._definitions = {definition.id: definition for definition in safe_definitions}
        self._runtime = {
            definition.id: self._initial_runtime(definition) for definition in safe_definitions
        }
        self._run_counter = 0

    def _initial_runtime(self, definition: OpsPlaybookDefinition) -> dict[str, Any]:
        now = time.time()
        return {
            "id": definition.id,
            "name": definition.name,
            "description": definition.description,
            "state": PLAYBOOK_STATE_IDLE,
            "last_outcome": PLAYBOOK_OUTCOME_NEVER_RUN,
            "last_outcome_reason": "",
            "last_run_id": "",
            "last_started_at": "",
            "last_started_epoch": 0.0,
            "last_completed_at": "",
            "last_completed_epoch": 0.0,
            "trigger_reason": "",
            "current_step_index": -1,
            "current_step_number": 0,
            "current_step_title": "",
            "total_steps": len(definition.steps),
            "waiting_action_id": "",
            "last_action_status": "",
            "cooldown_until": "",
            "cooldown_until_epoch": 0.0,
            "updated_at": utc_iso(now),
            "updated_epoch": now,
            "steps": [
                {"index": index + 1, "title": step.title}
                for index, step in enumerate(definition.steps)
            ],
            "audit": [],
        }

    def _normalized_metrics(self, metrics: dict[str, Any] | None) -> dict[str, float]:
        safe_metrics = metrics if isinstance(metrics, dict) else {}
        return {
            "queue_pending": max(0.0, _as_float(safe_metrics.get("queue_pending"), 0.0)),
            "queue_ignored_rate_60m": max(
                0.0,
                _as_float(safe_metrics.get("queue_ignored_rate_60m"), 0.0),
            ),
            "queue_decisions_total_60m": max(
                0.0,
                _as_float(safe_metrics.get("queue_decisions_total_60m"), 0.0),
            ),
            "queue_target_pending": max(
                0.0,
                _as_float(safe_metrics.get("queue_target_pending"), 3.0),
            ),
        }

    def _append_audit_locked(
        self,
        runtime: dict[str, Any],
        *,
        event: str,
        note: str,
        timestamp: float,
    ) -> None:
        runtime["audit"].append(
            {
                "ts": utc_iso(timestamp),
                "event": clip_text(event or "event", max_chars=48),
                "note": clip_text(note or "", max_chars=220),
            }
        )
        if len(runtime["audit"]) > 30:
            runtime["audit"] = runtime["audit"][-30:]

    def _mark_runtime_updated_locked(self, runtime: dict[str, Any], timestamp: float) -> None:
        runtime["updated_epoch"] = timestamp
        runtime["updated_at"] = utc_iso(timestamp)

    def _clear_cooldown_if_needed_locked(self, runtime: dict[str, Any], timestamp: float) -> None:
        if runtime.get("state") != PLAYBOOK_STATE_COOLDOWN:
            return
        cooldown_until = float(runtime.get("cooldown_until_epoch", 0.0))
        if cooldown_until <= 0 or timestamp < cooldown_until:
            return
        runtime["state"] = PLAYBOOK_STATE_IDLE
        runtime["cooldown_until"] = ""
        runtime["cooldown_until_epoch"] = 0.0
        self._mark_runtime_updated_locked(runtime, timestamp)
        self._append_audit_locked(
            runtime,
            event="cooldown_finished",
            note="Playbook voltou para idle.",
            timestamp=timestamp,
        )

    def _queue_step_locked(
        self,
        definition: OpsPlaybookDefinition,
        runtime: dict[str, Any],
        *,
        step_index: int,
        channel_id: str,
        metrics: dict[str, float],
        enqueue_action: Any,
        timestamp: float,
    ) -> dict[str, Any]:
        step = definition.steps[step_index]
        safe_channel = str(channel_id or "default").strip().lower() or "default"
        payload = {
            "ops_playbook": {
                "playbook_id": definition.id,
                "run_id": runtime.get("last_run_id", ""),
                "step_index": step_index + 1,
                "total_steps": len(definition.steps),
                "channel_id": safe_channel,
                "trigger_reason": runtime.get("trigger_reason", ""),
            },
            "metrics": {
                "queue_pending": int(metrics.get("queue_pending", 0.0)),
                "queue_ignored_rate_60m": round(metrics.get("queue_ignored_rate_60m", 0.0), 1),
                "queue_decisions_total_60m": int(metrics.get("queue_decisions_total_60m", 0.0)),
            },
        }
        body = clip_text(
            step.body_template.format(
                channel_id=safe_channel,
                queue_pending=int(metrics.get("queue_pending", 0.0)),
                queue_ignored_rate_60m=round(
                    metrics.get("queue_ignored_rate_60m", 0.0),
                    1,
                ),
                queue_decisions_total_60m=int(metrics.get("queue_decisions_total_60m", 0.0)),
                queue_target_pending=int(metrics.get("queue_target_pending", 3.0)),
            ),
            max_chars=420,
        )
        queued_item = enqueue_action(
            kind="ops_playbook_step",
            risk=definition.risk,
            title=clip_text(
                f"{definition.name} - Passo {step_index + 1}: {step.title}",
                max_chars=80,
            ),
            body=body,
            payload=payload,
            created_by="ops_playbook",
            timestamp=timestamp,
        )
        runtime["state"] = PLAYBOOK_STATE_AWAITING_DECISION
        runtime["current_step_index"] = step_index
        runtime["current_step_number"] = step_index + 1
        runtime["current_step_title"] = step.title
        runtime["waiting_action_id"] = str(queued_item.get("id", "") or "")
        runtime["last_action_status"] = "pending"
        self._mark_runtime_updated_locked(runtime, timestamp)
        self._append_audit_locked(
            runtime,
            event="step_queued",
            note=(
                f"run={runtime.get('last_run_id', '')} "
                f"step={step_index + 1}/{len(definition.steps)} "
                f"action={runtime.get('waiting_action_id', '')}"
            ),
            timestamp=timestamp,
        )
        return queued_item

    def _finish_run_locked(
        self,
        definition: OpsPlaybookDefinition,
        runtime: dict[str, Any],
        *,
        outcome: str,
        reason: str,
        timestamp: float,
    ) -> None:
        safe_outcome = (
            PLAYBOOK_OUTCOME_COMPLETED
            if outcome == PLAYBOOK_OUTCOME_COMPLETED
            else PLAYBOOK_OUTCOME_ABORTED
        )
        runtime["state"] = PLAYBOOK_STATE_COOLDOWN
        runtime["last_outcome"] = safe_outcome
        runtime["last_outcome_reason"] = clip_text(reason or "", max_chars=120)
        runtime["last_completed_epoch"] = timestamp
        runtime["last_completed_at"] = utc_iso(timestamp)
        runtime["waiting_action_id"] = ""
        runtime["current_step_index"] = -1
        runtime["current_step_number"] = 0
        runtime["current_step_title"] = ""
        cooldown_until_epoch = timestamp + max(60, int(definition.cooldown_seconds))
        runtime["cooldown_until_epoch"] = cooldown_until_epoch
        runtime["cooldown_until"] = utc_iso(cooldown_until_epoch)
        self._mark_runtime_updated_locked(runtime, timestamp)
        self._append_audit_locked(
            runtime,
            event=f"run_{safe_outcome}",
            note=f"reason={runtime.get('last_outcome_reason', '')}",
            timestamp=timestamp,
        )

    def _start_run_locked(
        self,
        definition: OpsPlaybookDefinition,
        runtime: dict[str, Any],
        *,
        channel_id: str,
        trigger_reason: str,
        metrics: dict[str, float],
        enqueue_action: Any,
        timestamp: float,
    ) -> None:
        self._run_counter += 1
        runtime["last_run_id"] = f"pb_{definition.id}_{int(timestamp * 1000)}_{self._run_counter}"
        runtime["last_started_epoch"] = timestamp
        runtime["last_started_at"] = utc_iso(timestamp)
        runtime["trigger_reason"] = clip_text(trigger_reason or "", max_chars=120)
        runtime["last_action_status"] = ""
        runtime["cooldown_until"] = ""
        runtime["cooldown_until_epoch"] = 0.0
        runtime["last_outcome_reason"] = ""
        self._mark_runtime_updated_locked(runtime, timestamp)
        self._append_audit_locked(
            runtime,
            event="run_started",
            note=(
                f"run={runtime.get('last_run_id', '')} trigger={runtime.get('trigger_reason', '')}"
            ),
            timestamp=timestamp,
        )
        self._queue_step_locked(
            definition,
            runtime,
            step_index=0,
            channel_id=channel_id,
            metrics=metrics,
            enqueue_action=enqueue_action,
            timestamp=timestamp,
        )

    def _advance_from_action_status_locked(
        self,
        definition: OpsPlaybookDefinition,
        runtime: dict[str, Any],
        *,
        action_status: str,
        channel_id: str,
        metrics: dict[str, float],
        enqueue_action: Any,
        timestamp: float,
    ) -> None:
        safe_status = str(action_status or "").strip().lower()
        runtime["last_action_status"] = safe_status
        if safe_status == "approved":
            next_step_index = int(runtime.get("current_step_index", -1)) + 1
            if next_step_index >= len(definition.steps):
                self._finish_run_locked(
                    definition,
                    runtime,
                    outcome=PLAYBOOK_OUTCOME_COMPLETED,
                    reason="all_steps_approved",
                    timestamp=timestamp,
                )
                return
            self._queue_step_locked(
                definition,
                runtime,
                step_index=next_step_index,
                channel_id=channel_id,
                metrics=metrics,
                enqueue_action=enqueue_action,
                timestamp=timestamp,
            )
            return

        if safe_status in {"rejected", "ignored"}:
            self._finish_run_locked(
                definition,
                runtime,
                outcome=PLAYBOOK_OUTCOME_ABORTED,
                reason=f"step_{safe_status}",
                timestamp=timestamp,
            )

    def _reconcile_waiting_action_locked(
        self,
        definition: OpsPlaybookDefinition,
        runtime: dict[str, Any],
        *,
        channel_id: str,
        metrics: dict[str, float],
        get_action: Any,
        enqueue_action: Any,
        timestamp: float,
    ) -> None:
        if runtime.get("state") != PLAYBOOK_STATE_AWAITING_DECISION:
            return
        waiting_action_id = str(runtime.get("waiting_action_id", "") or "")
        if not waiting_action_id:
            return
        action = get_action(waiting_action_id, timestamp=timestamp)
        if not isinstance(action, dict):
            return
        action_status = str(action.get("status", "pending") or "pending").strip().lower()
        if action_status == "pending":
            return
        self._append_audit_locked(
            runtime,
            event="step_decided",
            note=(
                f"run={runtime.get('last_run_id', '')} "
                f"step={runtime.get('current_step_number', 0)} "
                f"status={action_status}"
            ),
            timestamp=timestamp,
        )
        self._advance_from_action_status_locked(
            definition,
            runtime,
            action_status=action_status,
            channel_id=channel_id,
            metrics=metrics,
            enqueue_action=enqueue_action,
            timestamp=timestamp,
        )

    def _can_auto_start_locked(
        self,
        definition: OpsPlaybookDefinition,
        runtime: dict[str, Any],
        metrics: dict[str, float],
    ) -> bool:
        if runtime.get("state") != PLAYBOOK_STATE_IDLE:
            return False
        metric_value = _as_float(metrics.get(definition.trigger_metric), 0.0)
        if not _metric_matches(
            metric_value,
            definition.trigger_threshold,
            definition.trigger_comparison,
        ):
            return False
        if definition.trigger_min_sample_metric:
            sample_value = _as_float(
                metrics.get(definition.trigger_min_sample_metric),
                0.0,
            )
            if sample_value < float(definition.trigger_min_sample_value):
                return False
        return True

    def _reconcile_all_locked(
        self,
        *,
        channel_id: str,
        metrics: dict[str, float],
        get_action: Any,
        enqueue_action: Any,
        timestamp: float,
    ) -> None:
        for definition in self._definitions.values():
            runtime = self._runtime[definition.id]
            self._clear_cooldown_if_needed_locked(runtime, timestamp)
            self._reconcile_waiting_action_locked(
                definition,
                runtime,
                channel_id=channel_id,
                metrics=metrics,
                get_action=get_action,
                enqueue_action=enqueue_action,
                timestamp=timestamp,
            )

    def _summary_locked(self) -> dict[str, int]:
        states = Counter(
            str(item.get("state", PLAYBOOK_STATE_IDLE)) for item in self._runtime.values()
        )
        outcomes = Counter(
            str(item.get("last_outcome", PLAYBOOK_OUTCOME_NEVER_RUN))
            for item in self._runtime.values()
        )
        return {
            "total": int(len(self._runtime)),
            "idle": int(states.get(PLAYBOOK_STATE_IDLE, 0)),
            "awaiting_decision": int(states.get(PLAYBOOK_STATE_AWAITING_DECISION, 0)),
            "cooldown": int(states.get(PLAYBOOK_STATE_COOLDOWN, 0)),
            "completed": int(outcomes.get(PLAYBOOK_OUTCOME_COMPLETED, 0)),
            "aborted": int(outcomes.get(PLAYBOOK_OUTCOME_ABORTED, 0)),
        }

    def _snapshot_locked(self, timestamp: float) -> dict[str, Any]:
        return {
            "enabled": True,
            "updated_at": utc_iso(timestamp),
            "summary": self._summary_locked(),
            "playbooks": copy.deepcopy(list(self._runtime.values())),
        }

    def evaluate(
        self,
        *,
        channel_id: str,
        metrics: dict[str, Any] | None,
        trigger_reason: str,
        get_action: Any,
        enqueue_action: Any,
        timestamp: float | None = None,
    ) -> dict[str, Any]:
        now = time.time() if timestamp is None else float(timestamp)
        safe_channel = str(channel_id or "default").strip().lower() or "default"
        safe_metrics = self._normalized_metrics(metrics)
        safe_trigger = clip_text(trigger_reason or "autonomy_tick", max_chars=80)

        with self._lock:
            self._reconcile_all_locked(
                channel_id=safe_channel,
                metrics=safe_metrics,
                get_action=get_action,
                enqueue_action=enqueue_action,
                timestamp=now,
            )
            for definition in self._definitions.values():
                runtime = self._runtime[definition.id]
                if not self._can_auto_start_locked(definition, runtime, safe_metrics):
                    continue
                self._start_run_locked(
                    definition,
                    runtime,
                    channel_id=safe_channel,
                    trigger_reason=f"auto:{safe_trigger}",
                    metrics=safe_metrics,
                    enqueue_action=enqueue_action,
                    timestamp=now,
                )
            return self._snapshot_locked(now)

    def reconcile(
        self,
        *,
        channel_id: str,
        metrics: dict[str, Any] | None,
        get_action: Any,
        enqueue_action: Any,
        timestamp: float | None = None,
    ) -> dict[str, Any]:
        now = time.time() if timestamp is None else float(timestamp)
        safe_channel = str(channel_id or "default").strip().lower() or "default"
        safe_metrics = self._normalized_metrics(metrics)

        with self._lock:
            self._reconcile_all_locked(
                channel_id=safe_channel,
                metrics=safe_metrics,
                get_action=get_action,
                enqueue_action=enqueue_action,
                timestamp=now,
            )
            return self._snapshot_locked(now)

    def trigger(
        self,
        *,
        playbook_id: str,
        channel_id: str,
        reason: str,
        metrics: dict[str, Any] | None,
        get_action: Any,
        enqueue_action: Any,
        force: bool = False,
        timestamp: float | None = None,
    ) -> dict[str, Any]:
        now = time.time() if timestamp is None else float(timestamp)
        safe_playbook_id = str(playbook_id or "").strip().lower()
        definition = self._definitions.get(safe_playbook_id)
        if definition is None:
            raise KeyError("playbook_not_found")

        safe_channel = str(channel_id or "default").strip().lower() or "default"
        safe_metrics = self._normalized_metrics(metrics)
        safe_reason = clip_text(reason or "manual_dashboard", max_chars=80)

        with self._lock:
            self._reconcile_all_locked(
                channel_id=safe_channel,
                metrics=safe_metrics,
                get_action=get_action,
                enqueue_action=enqueue_action,
                timestamp=now,
            )
            runtime = self._runtime[safe_playbook_id]
            state = str(runtime.get("state", PLAYBOOK_STATE_IDLE))
            if state == PLAYBOOK_STATE_AWAITING_DECISION:
                raise RuntimeError("playbook_busy")
            if state == PLAYBOOK_STATE_COOLDOWN and not force:
                raise RuntimeError("playbook_cooldown")
            if state == PLAYBOOK_STATE_COOLDOWN and force:
                runtime["state"] = PLAYBOOK_STATE_IDLE
                runtime["cooldown_until"] = ""
                runtime["cooldown_until_epoch"] = 0.0

            self._start_run_locked(
                definition,
                runtime,
                channel_id=safe_channel,
                trigger_reason=f"manual:{safe_reason}",
                metrics=safe_metrics,
                enqueue_action=enqueue_action,
                timestamp=now,
            )
            return self._snapshot_locked(now)


__all__ = [
    "PLAYBOOK_OUTCOME_ABORTED",
    "PLAYBOOK_OUTCOME_COMPLETED",
    "PLAYBOOK_OUTCOME_NEVER_RUN",
    "PLAYBOOK_STATE_AWAITING_DECISION",
    "PLAYBOOK_STATE_COOLDOWN",
    "PLAYBOOK_STATE_IDLE",
    "OpsPlaybookDefinition",
    "OpsPlaybookRuntime",
    "OpsPlaybookStep",
    "default_ops_playbooks",
]
