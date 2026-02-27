from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

COMPLEXITY_TARGETS = (
    "bot/dashboard_server_routes.py",
    "bot/control_plane_config.py",
    "bot/irc_management.py",
    "bot/byte_semantics_quality.py",
)

MAX_COMPLEXITY_BUDGET = "17"

DUPLICATION_TARGETS = (
    "bot/dashboard_server_routes.py",
    "bot/dashboard_server_routes_post.py",
    "bot/persistence_layer.py",
    "bot/persistence_channel_config_repository.py",
    "bot/persistence_agent_notes_repository.py",
    "bot/persistence_observability_history_repository.py",
    "bot/persistence_cached_channel_repository.py",
)


@dataclass(frozen=True)
class StructuralGateStep:
    name: str
    command: tuple[str, ...]
    env_overrides: tuple[tuple[str, str], ...] = ()


GateRunner = Callable[[StructuralGateStep, Path], int]


def build_structural_gate_steps() -> tuple[StructuralGateStep, ...]:
    return (
        StructuralGateStep(
            name="ruff_c901",
            command=(
                "ruff",
                "check",
                "--select",
                "C901",
                "--config",
                f"lint.mccabe.max-complexity={MAX_COMPLEXITY_BUDGET}",
                *COMPLEXITY_TARGETS,
            ),
        ),
        StructuralGateStep(
            name="pylint_r0801",
            command=("pylint", "--disable=all", "--enable=R0801", *DUPLICATION_TARGETS),
            env_overrides=(("PYLINTHOME", "/tmp/pylint-cache"),),
        ),
    )


def run_step_subprocess(step: StructuralGateStep, project_root: Path) -> int:
    env = os.environ.copy()
    for key, value in step.env_overrides:
        env[key] = value

    completed = subprocess.run(
        list(step.command),
        cwd=str(project_root),
        env=env,
        check=False,
    )
    return int(completed.returncode)


def run_structural_gate(
    *,
    steps: Sequence[StructuralGateStep] | None = None,
    runner: GateRunner | None = None,
    project_root: Path | None = None,
) -> int:
    selected_steps = tuple(steps or build_structural_gate_steps())
    execute = runner or run_step_subprocess
    root = project_root or PROJECT_ROOT

    for step in selected_steps:
        command_text = " ".join(step.command)
        print(f"[structural-gate] running {step.name}: {command_text}")
        exit_code = execute(step, root)
        if exit_code != 0:
            print(f"[structural-gate] failed at {step.name} (exit={exit_code})")
            return int(exit_code)

    print("[structural-gate] ok")
    return 0


def main() -> int:
    return run_structural_gate()


if __name__ == "__main__":
    raise SystemExit(main())
