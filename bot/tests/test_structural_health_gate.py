from pathlib import Path
from unittest.mock import patch

from bot.structural_health_gate import (
    COMPLEXITY_TARGETS,
    DUPLICATION_TARGETS,
    MAX_COMPLEXITY_BUDGET,
    StructuralGateStep,
    build_structural_gate_steps,
    run_step_subprocess,
    run_structural_gate,
)


def test_build_structural_gate_steps_uses_expected_targets():
    steps = build_structural_gate_steps()
    assert len(steps) == 2

    ruff_step, pylint_step = steps
    assert ruff_step.name == "ruff_c901"
    assert ruff_step.command[:6] == (
        "ruff",
        "check",
        "--select",
        "C901",
        "--config",
        f"lint.mccabe.max-complexity={MAX_COMPLEXITY_BUDGET}",
    )
    assert ruff_step.command[6:] == COMPLEXITY_TARGETS

    assert pylint_step.name == "pylint_r0801"
    assert pylint_step.command[:3] == ("pylint", "--disable=all", "--enable=R0801")
    assert pylint_step.command[3:] == DUPLICATION_TARGETS
    assert pylint_step.env_overrides == (("PYLINTHOME", "/tmp/pylint-cache"),)


def test_run_structural_gate_runs_all_steps_when_all_pass():
    steps = (
        StructuralGateStep(name="step_a", command=("cmd-a",)),
        StructuralGateStep(name="step_b", command=("cmd-b",)),
    )
    executed: list[str] = []

    def fake_runner(step: StructuralGateStep, _project_root: Path) -> int:
        executed.append(step.name)
        return 0

    exit_code = run_structural_gate(
        steps=steps, runner=fake_runner, project_root=Path("/tmp/project")
    )

    assert exit_code == 0
    assert executed == ["step_a", "step_b"]


def test_run_structural_gate_stops_on_first_failure():
    steps = (
        StructuralGateStep(name="step_a", command=("cmd-a",)),
        StructuralGateStep(name="step_b", command=("cmd-b",)),
    )
    executed: list[str] = []

    def fake_runner(step: StructuralGateStep, _project_root: Path) -> int:
        executed.append(step.name)
        if step.name == "step_a":
            return 3
        return 0

    exit_code = run_structural_gate(
        steps=steps, runner=fake_runner, project_root=Path("/tmp/project")
    )

    assert exit_code == 3
    assert executed == ["step_a"]


def test_run_step_subprocess_passes_env_overrides_and_root():
    step = StructuralGateStep(
        name="pylint_r0801",
        command=("pylint", "--disable=all", "--enable=R0801"),
        env_overrides=(("PYLINTHOME", "/tmp/pylint-cache"),),
    )

    with patch("bot.structural_health_gate.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0

        exit_code = run_step_subprocess(step, Path("/tmp/repo"))

    assert exit_code == 0
    mock_run.assert_called_once()
    _, kwargs = mock_run.call_args
    assert kwargs["cwd"] == "/tmp/repo"
    assert kwargs["check"] is False
    assert kwargs["env"]["PYLINTHOME"] == "/tmp/pylint-cache"
